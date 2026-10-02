"""Evidence a run can leave beside an app's log, read into blockers.

Two kinds of stop leave the log without a blocker the lifecycle patterns can name:

* a native crash whose dump has registers but no backtrace (OH's crash dumper often cannot unwind
  Westlake's processes). The process memory map, sampled during the run, places the faulting pc and
  the return address (x30) in a library: Telegram's EGLThread crash, read that way, was inside the Mali
  driver's EGL surface code, not in Telegram or Westlake.
* a stall: the app is alive at the screenshot and draws nothing. ART's thread dump (SIGQUIT, or the
  "All threads" dump of a runtime abort) shows what the Java main thread is doing.
"""
from __future__ import annotations

import re

_MAP_LINE = re.compile(r"^([0-9a-f]+)-([0-9a-f]+) (\S+) ([0-9a-f]+) \S+ \d+\s*(.*)$")
_FATAL = re.compile(r"Fatal signal (\d+) \((\w+)\)")
_THREAD = re.compile(r'^Thread: \d+ "([^"]*)"', re.M)
_REGISTER = re.compile(r"\b(pc|x30): (0x[0-9a-f]+)")


def parse_maps(text: str) -> list[tuple[int, int, int, str]]:
    """(start, end, file offset, path) for every mapping."""
    rows = []
    for line in text.splitlines():
        match = _MAP_LINE.match(line.strip())
        if match:
            rows.append((int(match[1], 16), int(match[2], 16), int(match[4], 16), match[5].strip()))
    return rows


def place(address: int, maps: list[tuple[int, int, int, str]]) -> tuple[str, int] | None:
    """The mapped file holding an address and the address's offset in that file."""
    for start, end, offset, path in maps:
        if start <= address < end:
            return (path or "[anon]"), address - start + offset
    return None


def crash_site(stderr: str, maps_text: str) -> dict | None:
    """Where the first fatal signal in the log happened, by library and file offset."""
    fatal = _FATAL.search(stderr)
    if fatal is None or not maps_text:
        return None
    block = stderr[fatal.start():fatal.start() + 4000]
    registers = {name: int(value, 16) for name, value in _REGISTER.findall(block)}
    maps = parse_maps(maps_text)
    site = {"signal": fatal[2]}
    thread = _THREAD.search(block)
    if thread:
        site["thread"] = thread[1]
    for name, key in (("pc", "pc"), ("x30", "caller")):
        if name in registers:
            placed = place(registers[name], maps)
            if placed:
                site[key] = {"library": placed[0].rsplit("/", 1)[-1], "path": placed[0], "offset": hex(placed[1])}
    return site if "pc" in site else None


_DUMP = re.compile(r"DALVIK THREADS \(\d+\):\n")
_THREAD_HEAD = re.compile(r'^"([^"]*)"[^\n]*\btid=(\d+)\s+(\S+)', re.M)
_STATE = re.compile(r"\| state=(\w)")
_FRAME = re.compile(r"^\s+(?:at|native: #\d+ pc \S+)\s+(.+)$", re.M)
_WAITS = (
    (re.compile(r"java\.lang\.Object\.wait"), "waiting on a monitor"),
    (re.compile(r"(sun\.misc\.Unsafe|jdk\.internal\.misc\.Unsafe|java\.util\.concurrent\.locks\.LockSupport)\.park"),
     "parked"),
    (re.compile(r"BinderProxy\.transact|IPCObjectProxy|SendRequest"), "in a binder call"),
    (re.compile(r"java\.lang\.Thread\.sleep"), "sleeping"),
    (re.compile(r"android\.os\.MessageQueue\.nativePollOnce"), "idle in its message loop"),
)


def main_thread(stderr: str) -> dict | None:
    """The Java main thread (tid=1) in the last ART thread dump of the log: its state, what it is
    waiting in, and its top frames."""
    dumps = list(_DUMP.finditer(stderr))
    if not dumps:
        return None
    body = stderr[dumps[-1].end():]
    heads = list(_THREAD_HEAD.finditer(body))
    for i, head in enumerate(heads):
        if head[2] != "1":
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else min(len(body), head.end() + 20000)
        block = body[head.start():end]
        state = _STATE.search(block)
        frames = [f.strip() for f in _FRAME.findall(block)][:8]
        top = "\n".join(frames[:4])
        waiting = next((label for pattern, label in _WAITS if pattern.search(top)), "running")
        app_frame = next((f for f in frames if not f.startswith(("java.", "android.", "dalvik.", "sun.", "jdk.",
                                                                   "libcore.", "com.android."))), None)
        return {"name": head[1], "java_state": head[3], "state": state[1] if state else None,
                "waiting": waiting, "frames": frames, "first_app_frame": app_frame}
    return None
