# What the app actually put on the wire

Capture from the OS rather than from the app. `wl-netcap` binds `AF_PACKET` to one interface and
writes a classic pcap; `read.py` names the hosts.

```
NETCAP interface=wlan0 packets=57 bytes=13312 file=/data/local/tmp/cap3.pcap

packets=57  dns-queries=8  tls-hellos=1
DNS names asked for:   bdsp.x.jd.com, mon.zijieapi.com, msv6.wosms.cn, id6.me
TLS SNI:               mon.zijieapi.com
```

## Why this exists

An app's own network stack logs nothing we control. Chromium's does, because the WebView shim sits
underneath it — that is where `[WESTLAKE-WEBVIEW-NET] connect …` comes from. Toutiao's cronet, an
SDK's OkHttp and every statically linked client do not, which left "is the request even sent"
unanswerable from the app side.

On 2026-09-22 that was briefly written down as needing an instrument the harness does not have.
It does not. **We own the board.** `/proc/<pid>/net/tcp6` already gives per-connection state and
the owning uid; this adds the part `/proc` cannot: which names are asked for, and when.

## What is legible, and what is not

The payload is TLS. Two things are readable anyway and they are usually the two that decide
whether a blocker is ours:

| | |
|---|---|
| **DNS queries** | plaintext — which hosts the app looks for, and whether they resolve |
| **TLS ClientHello SNI** | the host of an encrypted connection |
| ~~response body~~ | **not available** — an app that connects, handshakes and is rejected looks identical to one that succeeds |

So this answers *was it asked, and of whom*. It does not answer *what came back*. That distinction
is the whole reason it is worth having: an empty screen with no requests is a different gap from an
empty screen with requests that were refused, and no amount of reading the app's log separates them.

## Running it

```bash
OHOS_SDK_NATIVE=<oh-sdk>/native ./build.sh
hdc file send out/wl-netcap /data/local/tmp/wl-netcap
hdc shell "chmod 755 /data/local/tmp/wl-netcap; /data/local/tmp/wl-netcap wlan0 30 /data/local/tmp/cap.pcap"
hdc file recv /data/local/tmp/cap.pcap cap.pcap
python3 read.py cap.pcap
```

Pick the interface that carries the app's traffic — match the local address in
`/proc/<pid>/net/tcp6`. On this board that is `wlan0`; the `sipa_eth*` devices are the modem path.

An idle app produces almost nothing: keep-alive connections carry no DNS and no handshakes, and
the reader says so rather than leaving a silent zero. Capture across the action you care about.

## What it found first time out

Toutiao's feed was empty and the transport looked healthy — three idle ESTABLISHED HTTPS
connections. Capturing across a consent tap moved it from 11 packets to 57, with eight DNS queries
and one handshake, and the app's category tabs went from nine to eleven.

That is worth more than the packet count: **server data was fetched and rendered**, so the app can
reach its backend and display what it returns. The article feed specifically stays empty, which
matches the prior diagnosis in the project record rather than replacing it — registration does not
yield the ids the feed API needs, so the request is never usefully made.

None of the captured DNS names is a feed endpoint. They are monitoring and third-party SDK hosts
(`mon.zijieapi.com`, `bdsp.x.jd.com`, `msv6.wosms.cn`, `id6.me`), which says the feed host was not
asked for in that window at all.
