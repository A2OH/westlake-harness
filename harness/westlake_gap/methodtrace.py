"""Decode an ART method trace and say which of an app's own methods actually ran.

Class-load tracing answers "was this class loaded", which is a different question: a startup step
can be constructed and never finish. McDonald's configuration initializer is loaded, its
configuration map is never filled, and nothing in between is logged. A sampling trace answers the
question directly, at the cost of only seeing what was on a stack when a sample was taken.

The file is ART's trace format: a text header listing every thread and method, then a binary
section of records. A sampling trace records the methods on each thread's stack at each interval,
so a method that appears was running; a method that does not appear either never ran or ran between
two samples. That asymmetry is the point: a hit is evidence, a miss is not proof.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any, Iterator


HEADER_MAGIC = 0x574F4C53   # "SLOW", little-endian


@dataclass
class Method:
    name: str            # class.method
    signature: str
    source: str
    samples: int = 0
    threads: set[int] = field(default_factory=set)


def _sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("*"):
            current = sections.setdefault(line[1:].strip(), [])
        elif current is not None:
            current.append(line)
    return sections


def parse(blob: bytes) -> dict[str, Any]:
    """Decode a trace file into its header values, methods and per-method sample counts."""
    marker = blob.find(b"*end\n")
    if marker < 0:
        raise ValueError("not an ART trace: no *end section")
    header_text = blob[:marker].decode("utf-8", "replace")
    body = blob[marker + len(b"*end\n"):]
    sections = _sections(header_text)

    values: dict[str, str] = {}
    for line in sections.get("version", []):
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip()

    methods: dict[int, Method] = {}
    for line in sections.get("methods", []):
        fields = line.split("\t")
        if len(fields) < 3:
            continue
        try:
            identifier = int(fields[0], 0)
        except ValueError:
            continue
        methods[identifier] = Method(name=f"{fields[1]}.{fields[2]}",
                                     signature=fields[3] if len(fields) > 3 else "",
                                     source=fields[4] if len(fields) > 4 else "")
    threads = {}
    for line in sections.get("threads", []):
        number, separator, name = line.partition("\t")
        if separator:
            try:
                threads[int(number)] = name
            except ValueError:
                continue

    if len(body) < 16 or struct.unpack_from("<I", body, 0)[0] != HEADER_MAGIC:
        raise ValueError("not an ART trace: bad binary magic")
    version, offset, record_size = (struct.unpack_from("<H", body, 4)[0],
                                    struct.unpack_from("<H", body, 6)[0],
                                    struct.unpack_from("<H", body, 14)[0])
    thread_bytes = 2 if version == 1 else 4
    if record_size == 0:
        record_size = thread_bytes + 4 + 4 + (4 if values.get("clock") == "dual" else 0)

    records = 0
    for record in _records(body, offset, record_size):
        thread = int.from_bytes(record[:thread_bytes], "little")
        encoded = int.from_bytes(record[thread_bytes:thread_bytes + 4], "little")
        method = methods.get(encoded & ~0x3)
        if method is None:
            continue
        method.samples += 1
        method.threads.add(thread)
        records += 1
    return {"values": values, "threads": threads, "records": records,
            "methods": sorted(methods.values(), key=lambda m: (-m.samples, m.name))}


def _records(body: bytes, offset: int, record_size: int) -> Iterator[bytes]:
    position = offset
    while position + record_size <= len(body):
        yield body[position:position + record_size]
        position += record_size


def ran(trace: dict[str, Any], prefixes: list[str]) -> list[dict[str, Any]]:
    """Methods whose class matches one of the prefixes, most-sampled first."""
    return [{"method": m.name, "samples": m.samples, "threads": sorted(m.threads), "source": m.source}
            for m in trace["methods"]
            if m.samples and any(m.name.startswith(prefix) for prefix in prefixes)]


def markdown(trace: dict[str, Any], hits: list[dict[str, Any]], prefixes: list[str], limit: int = 40) -> str:
    out = [f"# Methods that ran ({trace['records']} samples, {len(trace['methods'])} methods known)", "",
           "Prefixes: " + ", ".join(f"`{p}`" for p in prefixes), "",
           "A method here was on a thread's stack when a sample was taken. A method missing from the",
           "list either never ran or ran entirely between two samples: a hit is evidence, a miss is not.",
           "", "| Method | Samples | Threads |", "|---|---|---|"]
    for hit in hits[:limit]:
        out.append(f"| `{hit['method']}` | {hit['samples']} | {', '.join(str(t) for t in hit['threads'])} |")
    if len(hits) > limit:
        out.append(f"| … {len(hits) - limit} more | | |")
    return "\n".join(out) + "\n"
