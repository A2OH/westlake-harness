#!/usr/bin/env python3
"""Name the hosts an app asked for, from a capture taken on the board.

The payload is TLS, so this does not read responses. Two things are legible anyway and they are
usually the two that decide whether a blocker is ours:

  * DNS queries and answers, in plaintext — which hosts the app looks for and whether they resolve;
  * the TLS ClientHello SNI — which host an encrypted connection is for.

Together those answer "was the request even attempted, and to whom", which is the question an app
that logs nothing otherwise leaves open. They do not answer "what came back": an app that connects,
completes a handshake and is rejected looks identical here to one that succeeds.
"""
from __future__ import annotations

import argparse
import struct
import sys
from collections import Counter
from pathlib import Path


def frames(data: bytes):
    """Yield Ethernet payloads from a classic pcap, skipping anything malformed."""
    if len(data) < 24 or struct.unpack("<I", data[:4])[0] != 0xA1B2C3D4:
        raise SystemExit("not a little-endian classic pcap")
    link = struct.unpack("<I", data[20:24])[0]
    if link != 1:
        raise SystemExit(f"expected Ethernet link type, got {link}")
    offset = 24
    while offset + 16 <= len(data):
        _, _, caplen, _ = struct.unpack("<IIII", data[offset:offset + 16])
        offset += 16
        if caplen <= 0 or offset + caplen > len(data):
            break
        yield data[offset:offset + caplen]
        offset += caplen


def ipv4_payload(frame: bytes):
    """(protocol, src, dst, payload) for IPv4/IPv6 over Ethernet, else None."""
    if len(frame) < 14:
        return None
    ethertype = struct.unpack("!H", frame[12:14])[0]
    if ethertype == 0x0800 and len(frame) >= 34:
        ihl = (frame[14] & 0x0F) * 4
        src = ".".join(str(b) for b in frame[26:30])
        dst = ".".join(str(b) for b in frame[30:34])
        return frame[23], src, dst, frame[14 + ihl:]
    if ethertype == 0x86DD and len(frame) >= 54:
        return frame[20], frame[22:38].hex(), frame[38:54].hex(), frame[54:]
    return None


def dns_names(payload: bytes) -> list[str]:
    """Question names from a DNS message. Compression pointers are not followed: questions do
    not use them, and a half-decoded name is worse than none."""
    if len(payload) < 12:
        return []
    count = struct.unpack("!H", payload[4:6])[0]
    names, offset = [], 12
    for _ in range(min(count, 8)):
        labels = []
        while offset < len(payload):
            length = payload[offset]
            if length == 0:
                offset += 1
                break
            if length & 0xC0:
                return names
            offset += 1
            labels.append(payload[offset:offset + length].decode("ascii", "replace"))
            offset += length
        if labels:
            names.append(".".join(labels))
        offset += 4
    return names


def tls_sni(payload: bytes) -> str | None:
    """The server name from a TLS ClientHello, or None. Parsed defensively: a truncated or
    non-TLS segment must be ignored rather than guessed at."""
    if len(payload) < 45 or payload[0] != 0x16 or payload[5] != 0x01:
        return None
    try:
        offset = 43 + payload[43] + 1                       # session id
        offset += struct.unpack("!H", payload[offset:offset + 2])[0] + 2   # cipher suites
        offset += payload[offset] + 1                       # compression methods
        end = offset + 2 + struct.unpack("!H", payload[offset:offset + 2])[0]
        offset += 2
        while offset + 4 <= min(end, len(payload)):
            kind, size = struct.unpack("!HH", payload[offset:offset + 4])
            body = payload[offset + 4:offset + 4 + size]
            if kind == 0x0000 and len(body) >= 5:           # server_name
                return body[5:5 + struct.unpack("!H", body[3:5])[0]].decode("ascii", "replace")
            offset += 4 + size
    except (struct.error, IndexError):
        return None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pcap", type=Path)
    args = parser.parse_args()

    queries, hosts, peers = Counter(), Counter(), Counter()
    total = 0
    for frame in frames(args.pcap.read_bytes()):
        total += 1
        parsed = ipv4_payload(frame)
        if parsed is None:
            continue
        protocol, _, dst, payload = parsed
        if protocol == 17 and len(payload) >= 8:            # UDP
            ports = struct.unpack("!HH", payload[:4])
            if 53 in ports:
                for name in dns_names(payload[8:]):
                    queries[name] += 1
        elif protocol == 6 and len(payload) >= 20:          # TCP
            data_offset = (payload[12] >> 4) * 4
            peers[f"{dst}:{struct.unpack('!H', payload[2:4])[0]}"] += 1
            name = tls_sni(payload[data_offset:])
            if name:
                hosts[name] += 1

    print(f"packets={total}  dns-queries={sum(queries.values())}  tls-hellos={sum(hosts.values())}")
    for label, counter in (("DNS names asked for", queries), ("TLS SNI", hosts),
                           ("destinations", peers)):
        if counter:
            print(f"\n{label}:")
            for key, count in counter.most_common(12):
                print(f"  {count:>4}  {key}")
    if not queries and not hosts:
        # Said plainly: an idle keep-alive connection produces neither, and that is not a failure.
        print("\nno DNS and no handshakes in this window: either nothing was requested, or the "
              "app is reusing connections it opened earlier")
    return 0


if __name__ == "__main__":
    sys.exit(main())
