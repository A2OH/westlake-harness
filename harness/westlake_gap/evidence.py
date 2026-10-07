"""Evidence a run can leave beside an app's log, read into blockers.

Two kinds of stop leave the log without a blocker the lifecycle patterns can name:

* a native crash whose dump has registers but no backtrace (OH's crash dumper often cannot unwind
  Westlake's processes). The process memory map, sampled during the run, places the faulting pc and
  the return address (x30) in a library: Telegram's EGLThread crash, read that way, was inside the Mali
  driver's EGL surface code, not in Telegram or Westlake.
* a stall: the app is alive at the screenshot and draws nothing. ART's thread dump (SIGQUIT, or the
  "All threads" dump of a runtime abort) shows what the Java main thread is doing.
* a native crash the log never mentions: a fault outside ART's handlers (a null constructor called
  by the loader, a fault inside musl's allocator) prints nothing to stderr. OH's crash dump
  (faultloggerd's cppcrash, beside the log as <app>.cppcrash) has the faulting thread and frames.
  In r83 such dumps existed for 12 apps the log scored as "no blocker" or as a slow start.
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
    """The app's main thread in the last ART thread dump of the log: its state, what it is waiting
    in, and its top frames.

    That is the thread running ActivityThread.main, not necessarily tid=1: appspawn-x starts the VM
    on a worker pthread, and ART hands tid 1 on to a later thread once the first one detaches
    (cclauncher: tid 1 was a WorkManager pool thread parked in its queue, while the main looper
    ran as "Thread-2" and sat idle). Then a thread named "main", then tid 1."""
    dumps = list(_DUMP.finditer(stderr))
    if not dumps:
        return None
    body = stderr[dumps[-1].end():]
    heads = list(_THREAD_HEAD.finditer(body))
    blocks = [(head, body[head.start():heads[i + 1].start() if i + 1 < len(heads)
                              else min(len(body), head.end() + 20000)]) for i, head in enumerate(heads)]
    chosen = (next((hb for hb in blocks if "android.app.ActivityThread.main(" in hb[1]), None)
              or next((hb for hb in blocks if hb[0][1] == "main"), None)
              or next((hb for hb in blocks if hb[0][2] == "1"), None))
    if chosen is None:
        return None
    head, block = chosen
    state = _STATE.search(block)
    frames = [f.strip() for f in _FRAME.findall(block)][:8]
    top = "\n".join(frames[:4])
    waiting = next((label for pattern, label in _WAITS if pattern.search(top)), "running")
    app_frame = next((f for f in frames if not f.startswith(("java.", "android.", "dalvik.", "sun.", "jdk.",
                                                               "libcore.", "com.android."))), None)
    return {"name": head[1], "java_state": head[3], "state": state[1] if state else None,
            "waiting": waiting, "frames": frames, "first_app_frame": app_frame}


_CPP_REASON = re.compile(r"^Reason:Signal:(\w+)\((\w+)\)@(?:0x)?([0-9a-fA-F]+)", re.M)
_CPP_TIME = re.compile(r"^Timestamp:\d{4}-(\d\d-\d\d) (\d\d):(\d\d):(\d\d)\.(\d+)", re.M)
_CPP_THREAD = re.compile(r"^Fault thread info:\s*\nTid:(\d+), Name:(.*)$", re.M)
_CPP_FRAME = re.compile(r"^#(\d+) pc ([0-9a-f]+) (.*)$")
# Westlake's runtime libraries: OH's dumper names the nearest exported symbol, which for these is
# not the function (libart.so frames read as vixl or riscv64 assembler code), so no name is kept.
_RUNTIME_DIR = "/data/local/tmp/asx/"
_APP_DIRS = ("/data/local/tmp/asx/lib/", "/data/data/", "/data/user/")
_INIT_COPY = re.compile(r"^\.(.+\.so)\.westlake-init\.\d+\.\d+$")


def _dump_frame(match: re.Match) -> dict:
    rest = match[3].strip()
    frame = {"pc": int(match[2], 16)}
    if rest.startswith(("Not mapped", "[Unknown]")):
        frame["library"] = rest.split()[0] if rest.startswith("[") else "not mapped"
        return frame
    path = rest.split("(", 1)[0].strip().removesuffix(" (deleted)").strip()
    name = path.rsplit("/", 1)[-1]
    copy = _INIT_COPY.match(name)  # the shim's private copy of an app library, loaded once
    frame["path"], frame["library"] = path, copy[1] if copy else name
    symbol = re.match(r"[^(]*\(([^)]*\+\d+)\)", rest)
    if symbol and not (path.startswith(_RUNTIME_DIR) and not path.startswith(_APP_DIRS)):
        frame["symbol"] = symbol[1]
    return frame


# musl's allocator entry points, and get_meta, mallocng's check of the chunk it is handed: Fennec's
# libxul freed with musl's free what libmozglue's mozjemalloc had allocated, and faulted there.
_ALLOCATOR = r"(__libc_malloc_impl|__libc_free|malloc|free|realloc|calloc|alloc_|get_meta)"


def _is_app(frame: dict) -> bool:
    return frame.get("path", "").startswith(_APP_DIRS)


_CPP_MAP = re.compile(r"^[0-9a-f]+-[0-9a-f]+ \S+ [0-9a-f]+ /", re.M)


_CPP_REGISTERS = re.compile(r"^lr:([0-9a-f]+) sp:[0-9a-f]+ pc:([0-9a-f]+)", re.M)


def _mapped_file(text: str, address: int) -> tuple[str, int] | None:
    """The file and file offset the dump's own Maps section places an address at."""
    at = text.find("\nMaps:")
    if at < 0:
        return None
    for line in text[at:].splitlines():
        if not _CPP_MAP.match(line):
            continue
        span, _, offset, path = line.split(None, 3)
        start, end = (int(x, 16) for x in span.split("-"))
        if start <= address < end:
            return path.strip().removesuffix(" (deleted)").strip(), address - start + int(offset, 16)
    return None


def _file_extents(text: str) -> dict[str, int]:
    """How far into each file the dump's own Maps section maps it: the furthest file offset any of
    its mappings reaches. A frame placed past that is not in the file. OH's dumper names such a pc
    after the file mapped before it: CapCut's crash "in libmetasec_ov.so+0x215d6ec" ran in anonymous
    memory after a 1.9 MB library (ByteDance decrypts code there), and TikTok's calling frames read
    0x20000 past libvcbasekit.so's end, where its saved frame records put them inside it."""
    at = text.find("\nMaps:")
    extents: dict[str, int] = {}
    if at < 0:
        return extents
    for line in text[at:].splitlines():
        if not _CPP_MAP.match(line):
            continue
        span, _, offset, path = line.split(None, 3)
        start, end = (int(x, 16) for x in span.split("-"))
        path = path.strip().removesuffix(" (deleted)").strip()
        extents[path] = max(extents.get(path, 0), end - start + int(offset, 16))
    return extents


def cppcrash(text: str) -> dict | None:
    """The fault in an OH crash dump: signal, address, faulting thread, its top frames, and what the
    frames say happened when it is one of the shapes Westlake apps keep hitting."""
    reason = _CPP_REASON.search(text)
    if reason is None:
        return None
    dump = {"signal": reason[1], "code": reason[2], "address": hex(int(reason[3], 16))}
    thread = _CPP_THREAD.search(text)
    frames = []
    if thread:
        dump["thread"] = thread[2].strip()
        for line in text[thread.end():].lstrip("\n").splitlines():
            match = _CPP_FRAME.match(line)
            if match is None:
                break
            frames.append(_dump_frame(match))
    # An app library's faulting frame from the pc register itself: the dump's own offset for it has
    # been wrong by 0x1a000 (CapCut's libmetasec_ov.so, a store at 0x15b6ec printed as 0x1756ec, in
    # .rodata) and 0x2000000 (Fennec's libxul.so). The Maps section gives file offsets, which in an
    # app library's text are its addresses; OH's own libraries come symbolized and right, and their
    # text is not at its file offset (ld-musl's lies 0x1000 above), so they keep the dump's.
    registers = _CPP_REGISTERS.search(text)
    if registers and frames and _is_app(frames[0]):
        placed = _mapped_file(text, int(registers[2], 16))
        if placed and placed[0].startswith(_APP_DIRS) and placed[1] != frames[0]["pc"]:
            frames[0]["dump_pc"] = frames[0]["pc"]
            frames[0]["pc"] = placed[1]
            if placed[0] != frames[0]["path"]:
                name = placed[0].rsplit("/", 1)[-1]
                copy = _INIT_COPY.match(name)
                frames[0]["path"], frames[0]["library"] = placed[0], copy[1] if copy else name
                frames[0].pop("symbol", None)
    extents = _file_extents(text)
    for frame in frames:
        if frame.get("path") in extents and frame["pc"] >= extents[frame["path"]]:
            frame["beyond_mapping"] = True
    dump["frames"] = frames[:8]
    app = next((f for f in frames if _is_app(f)), None)
    if app:
        dump["first_app_frame"] = "%s+%#x" % (app["library"], app["pc"]) + (
            " (past its mappings)" if app.get("beyond_mapping") else "")
    top = frames[0] if frames else {}
    caller = frames[1] if len(frames) > 1 else {}
    from_init = caller.get("symbol", "").startswith("do_init_fini")
    if from_init and (top.get("library") == "not mapped" or top.get("pc") == 0):
        dump["kind"] = "null-constructor"
        dump["summary"] = "a library constructor (INIT_ARRAY entry) is null: musl calls it, bionic skips it"
    elif from_init and top.get("library") == "[Unknown]":
        dump["kind"] = "unrelocated-constructor"
        dump["summary"] = "a constructor pointer kept its link-time value (%#x): a relocation the loader did not apply" % top["pc"]
    elif top.get("library", "").startswith("ld-musl") and re.match(_ALLOCATOR, top.get("symbol", "")):
        dump["kind"] = "heap"
        dump["summary"] = ("a fault inside musl's allocator: the heap was corrupt before this call, or it was "
                           "handed memory its heap never allocated")
        if app:
            dump["summary"] += " (allocating for %s)" % dump["first_app_frame"]
    elif dump["signal"] == "SIGABRT":
        after = next((f for f in frames if not re.match(r"(raise|abort)\b", f.get("symbol", ""))), None)
        dump["kind"] = "abort"
        dump["summary"] = "aborted from %s" % (after["library"] if after else "?")
    elif top.get("library") == "not mapped" and caller:
        dump["kind"] = "null-call"
        dump["summary"] = "a null function pointer called from %s+%#x" % (caller.get("library", "?"), caller.get("pc", 0))
    elif top.get("beyond_mapping"):
        dump["kind"] = "fault"
        dump["summary"] = ("in code past %s's mappings, where the dump places it at +%#x: anonymous memory "
                           "(generated or decrypted code), or an offset the dump got wrong"
                           % (top.get("library", "?"), top.get("pc", 0)))
    else:
        dump["kind"] = "fault"
        dump["summary"] = "in %s+%#x" % (top.get("library", "?"), top.get("pc", 0))
    return dump


_SIGNAL_NAMES = {4: "SIGILL", 5: "SIGTRAP", 6: "SIGABRT", 7: "SIGBUS", 8: "SIGFPE", 11: "SIGSEGV"}
_HILOG_TIME = re.compile(r"^\d\d-\d\d (\d\d):(\d\d):(\d\d)\.(\d+)\s+\d+\s+(\d+) ")
_HILOG_STAMP = re.compile(r"^(\d\d-\d\d) (\d\d):(\d\d):(\d\d)\.(\d+)\s+\d+\s+\d+ ", re.M)


def _stamp(match: re.Match) -> tuple[str, float]:
    return match[1], int(match[2]) * 3600 + int(match[3]) * 60 + int(match[4]) + float("0." + match[5])


def dump_predates_process(cppcrash_text: str, hilog: str) -> bool:
    """Whether a crash dump was written before the process in the app's own hilog logged its first
    line: the dump of an earlier process that had the same pid. A process logs before it dies, so its
    own dump never comes first. Pids repeat within a corpus run, and the run looks dumps up by pid:
    in r87, TikTok's launch (pid 9865) picked up the dump that PPSSPP's process, with the same pid,
    had left 2 h 22 min earlier."""
    written, started = _CPP_TIME.search(cppcrash_text), _HILOG_STAMP.search(hilog)
    if written is None or started is None:
        return False
    (day, when), (start_day, start) = _stamp(written), _stamp(started)
    return (day, when) < (start_day, start - 1)
_PASSED_ON = re.compile(r"MUSL-SIGCHAIN: signal_chain_handler call usr sigaction for signal: (\d+)")
_DFX_THREAD = re.compile(r"DFX_SignalHandler :: signo\((\d+)\), pid\(\d+\), processName\([^)]*\), threadName\(([^)]*)\)")


def _seconds(line: str) -> float | None:
    match = _HILOG_TIME.match(line)
    return (int(match[1]) * 3600 + int(match[2]) * 60 + int(match[3]) + float("0." + match[4])) if match else None


def hilog_signal(hilog: str) -> dict | None:
    """A fatal signal in the app's own hilog (hilog -P) that left no crash dump: one ART's handler did
    not claim (musl's signal chain passed it to the app's or OH's handler) and after which the
    process logged for under two seconds more. Instagram died that way, a SIGILL right after a
    numeric-host getaddrinfo, with nothing in its log or the fault log."""
    lines = hilog.splitlines()
    last = next((t for t in map(_seconds, reversed(lines)) if t is not None), None)
    for index in range(len(lines) - 1, -1, -1):
        match = _PASSED_ON.search(lines[index])
        if not match or int(match[1]) not in _SIGNAL_NAMES:
            continue
        when = _seconds(lines[index])
        if when is None or last is None or last - when > 2:
            return None
        tid = _HILOG_TIME.match(lines[index])[5]
        found = {"signal": _SIGNAL_NAMES[int(match[1])], "tid": int(tid)}
        thread = next((m[2] for m in map(_DFX_THREAD.search, lines[max(0, index - 40):index])
                       if m and m[1] == match[1]), None)
        if thread:
            found["thread"] = thread
        before = next((l for l in reversed(lines[max(0, index - 40):index])
                       if _HILOG_TIME.match(l) and _HILOG_TIME.match(l)[5] == tid
                       and "MUSL-SIGCHAIN" not in l and "DfxSignalHandler" not in l), None)
        if before:
            found["after"] = before.split(": ", 1)[-1][:160]
        return found
    return None


# The adapter reports the activity's first drawn frame, or 800 ms after its resume with none drawn, a
# timeout. Before build 88 both logged "(first-frame)", so in older logs a first frame may be the
# timeout: 80 of r85's apps sat 0.79-1.2 s after their resume, piled up at 0.8 s.
_STARTUP_MARKS = (("resumed", "activityResumed: OnDrawListener attached"),
                  ("first_frame", "activityResumed (first-frame)"),
                  ("first_frame_timeout", "activityResumed (first-frame timeout)"))


def startup_times(hilog: str) -> dict | None:
    """Seconds from the process starting (AppSpawnX's "Child process started") to its activity
    resuming and to that activity's first frame, from the app's own hilog. Compiled code, a slow
    main thread or a stall shows up here first: Telegram reached its first frame in 2.5 s with its
    code compiled, TikTok in 44 s interpreted."""
    start, found = None, {}
    for line in hilog.splitlines():
        if start is None and "Child process started" in line:
            start = _seconds(line)
            continue
        for key, marker in _STARTUP_MARKS:
            if start is not None and key not in found and marker in line:
                when = _seconds(line)
                if when is not None:
                    found[key] = round(when - start, 2)
    return found or None


_NULL_SERVICE = re.compile(r"Attempt to invoke [^']*'[^' ]+ ((?:[a-z]\w*\.)+I[A-Z]\w*)\.\w+\([^']*\)' on a null object reference")


def null_service_interfaces(*texts: str | None) -> list[str]:
    """Platform service interfaces the app dereferenced null, from the NullPointerException messages
    in its logs, caught or not: a binder that no in-process stand-in answers. wormhole2's device-info
    plugin failed on IDeviceIdentifiersPolicyService (Build.getSerial) and the app never drew; the
    launchers' LauncherApps calls failed on ILauncherApps."""
    found: set[str] = set()
    for text in texts:
        if text:
            found |= {match.group(1) for match in _NULL_SERVICE.finditer(text)}
    return sorted(found)


_REFUSED = re.compile(r"UnsupportedOperationException: (OH user service does not implement \w+)")


def service_refusals(*texts: str | None) -> list[str]:
    """Calls an in-process service refused outright, from the exception messages in the app's logs,
    caught or not: the user service throws for an IUserManager method it does not name (clauncher's
    UserManager.getUserProfiles: getProfileIds), and the app went on without its answer."""
    found: set[str] = set()
    for text in texts:
        if text:
            found |= {match.group(1) for match in _REFUSED.finditer(text)}
    return sorted(found)


_REQUEST_FAILED = re.compile(r"NativeWindowRequestBuffer>: RequestBuffer ret:(-?\d+), uniqueId: (\d+)")


def buffer_request_failures(hilog: str) -> dict | None:
    """Buffer requests OH refused on one of the app's windows (native_window.cpp's RequestBuffer
    error), most on one window: a producer that never got a buffer to draw into. SDL's EGL surface
    asked 13,915 times in anarchre's minute, after its (0, 0, visual) geometry had reached OH as a
    0x0 buffer size (NATIVE_ERROR_UNKNOWN, 50002000)."""
    counts: dict[tuple[str, str], int] = {}
    for line in hilog.splitlines():
        match = _REQUEST_FAILED.search(line)
        if match:
            counts[(match[1], match[2])] = counts.get((match[1], match[2]), 0) + 1
    if not counts:
        return None
    (code, window), count = max(counts.items(), key=lambda item: item[1])
    return {"count": count, "ret": int(code), "window": int(window), "windows": len({w for _, w in counts})}


_DLSYM_FAILED = re.compile(r"do_dlsym failed: Symbol not found: (\w+), version: \S+ so=(\S+)")
_HILOG_DOMAIN = re.compile(r"^\d\d-\d\d \d\d:\d\d:\d\d\.\d+\s+\d+\s+\d+\s+[A-Z]\s+(C[0-9a-fA-F]{5})/")


def dlsym_failures(*texts: str | None) -> list[dict]:
    """Lookups by handle that OH's dynamic linker refused, as the app logged them: a loader that
    passes dlsym's error on (Ebiten in aaaaxy: "gl: glGenVertexArrays is missing: do_dlsym failed:
    Symbol not found: glGenVertexArrays, version: null so=/system/lib64/ndk/libGLESv2.so"). A
    lookup that returns null is otherwise silent. Each name once, in the order first seen. Only
    the Android side's hilog domain (C00f00) counts: OH's graphics HAL logs its own optional probes
    (load_hdi: MapperImplRelease in /vendor/lib64/passthrough) in every app that draws."""
    seen: set[str] = set()
    found = []
    for text in texts:
        for line in (text or "").splitlines():
            match = _DLSYM_FAILED.search(line)
            if match is None:
                continue
            domain = _HILOG_DOMAIN.match(line)
            if domain is not None and domain[1].lower() != "c00f00":
                continue
            if match[1] not in seen:
                seen.add(match[1])
                found.append({"symbol": match[1], "library": match[2]})
    return found


_RESUMED = re.compile(r"activityResumed: OnDrawListener attached[^\n]*\(token=(\S+?)\)")
_FINISHED = re.compile(r"finishActivity: [^\n]*? for (\S+)")


def self_finish(hilog: str) -> dict | None:
    """The app's last resumed activity finishing itself, with no activity resuming after it: from
    the adapter's activityResumed and finishActivity lines in the app's hilog. On Android an app that
    does this has left the screen by its own choice -- a launcher activity that is not the task root
    (Activity.isTaskRoot was false for every activity before the task model), a Bluetooth app on a
    device without Bluetooth, a trampoline into another app. None when another activity took over."""
    resumed: list[tuple[float | None, str]] = []
    finished: dict[str, float | None] = {}
    for line in hilog.splitlines():
        match = _RESUMED.search(line)
        if match:
            resumed.append((_seconds(line), match.group(1)))
            continue
        match = _FINISHED.search(line)
        if match and match.group(1) not in finished:
            finished[match.group(1)] = _seconds(line)
    if not resumed or resumed[-1][1] not in finished:
        return None
    at, token = resumed[-1]
    gone = finished[token]
    out = {"token": token}
    if at is not None and gone is not None:
        out["after_ms"] = max(0, round((gone - at) * 1000))
    return out


_LOCAL_SERVICE = re.compile(r"^\[WESTLAKE-LOCAL-SERVICE\] ([\w.]+)\.(\w+)$", re.M)


def local_service_calls(stderr: str) -> list[str]:
    """The in-process services the app called, in the order of their first call: LocalServiceBinders
    logs each service and method once ("[WESTLAKE-LOCAL-SERVICE] role.isRoleAvailableAsUser")."""
    seen: list[str] = []
    for match in _LOCAL_SERVICE.finditer(stderr):
        if match.group(1) not in seen:
            seen.append(match.group(1))
    return seen


_WITNESS = re.compile(r"\[WESTLAKE-SIGNAL-WITNESS\] signal=(0x[0-9a-f]+) code=(0x[0-9a-f]+) tid=(0x[0-9a-f]+) "
                      r"thread=(.*?) pc=(0x[0-9a-f]+) x30=(0x[0-9a-f]+)")


_WITNESS_AT = re.compile(r" at (\S+)\+(0x[0-9a-f]+)")
_WITNESS_FROM = re.compile(r" from (\S+)\+(0x[0-9a-f]+)")
_WITNESS_INSN = re.compile(r" insn=(0x[0-9a-f]+) next=(0x[0-9a-f]+)")


def signal_witnesses(stderr: str, maps_text: str | None = None) -> list[dict]:
    """The bionic shim's signal witness lines (SIGILL, SIGTRAP, SIGBUS: the signals that can end a
    process without a crash dump). pc and x30 come placed by the shim itself (from /proc/self/maps
    at the signal, as file offsets), or by the process map the run sampled. insn is the word the
    CPU refused, which is not always the file's: Meta's tooling writes a trap (0xf4ccffcc) over
    abort's first instruction. A witnessed signal is not necessarily fatal: a library probing the
    CPU catches its own SIGILL."""
    maps = parse_maps(maps_text) if maps_text else []
    found = []
    for match in _WITNESS.finditer(stderr):
        line_end = stderr.find("\n", match.end())
        rest = stderr[match.end():line_end if line_end >= 0 else len(stderr)]
        event = {"signal": _SIGNAL_NAMES.get(int(match[1], 16), int(match[1], 16)), "code": int(match[2], 16),
                 "tid": int(match[3], 16), "thread": match[4]}
        for key, value, inline in (("pc", match[5], _WITNESS_AT.search(rest)), ("caller", match[6], _WITNESS_FROM.search(rest))):
            if inline:
                event[key] = {"library": inline[1].rsplit("/", 1)[-1], "path": inline[1], "offset": inline[2]}
                continue
            placed = place(int(value, 16), maps) if maps else None
            event[key] = ({"library": placed[0].rsplit("/", 1)[-1], "path": placed[0], "offset": hex(placed[1])}
                          if placed else {"address": value})
        insn = _WITNESS_INSN.search(rest)
        if insn:
            event["insn"], event["next"] = insn[1], insn[2]
        found.append(event)
    return found
