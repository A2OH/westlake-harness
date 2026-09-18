"""Third-party component provenance and platform-surface reach for packaged ELFs.

Two questions this answers about a shared object that carries no symbol table:

1. **Provenance** — which upstream open-source component is inside it, at which version.
   A library that is 80% FFmpeg is replaced from upstream, never reverse engineered.
2. **Surface reach** — which Android platform surfaces each registered JNI method can
   actually touch. A method that reaches nothing platform-specific ports unchanged; one
   that reaches ``AndroidBitmap_*`` or EGL is real porting work.

Both are deliberately conservative. Provenance separates *containing* a component from
merely *linking against* it. Surface reach walks direct ``bl`` edges only and is reported
as a lower bound: indirect calls through function pointers, virtual dispatch and task
queues are not followed, and ``dlopen``/``dlsym`` resolution is reported as a blind spot
rather than silently treated as absence.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from bisect import bisect_right
from pathlib import Path
from typing import Any, Iterable, Sequence

ARM64_MACHINES = {"AArch64"}

#: ``(component, banner regex or None, defined-symbol regex or None, minimum symbol hits)``.
#: A banner match alone is sufficient; a symbol-only match needs ``minimum`` distinct hits so
#: that a handful of coincidental names cannot name a component.
COMPONENT_SIGNATURES: tuple[tuple[str, str | None, str | None, int], ...] = (
    ("FFmpeg", r"FFmpeg version ([\w.\-]+)|Lavc(\d+\.\d+\.\d+)", r"^(av_|avcodec_|avformat_|avfilter_|sws_|swr_)", 8),
    ("OpenSSL", r"OpenSSL (\d\.\d\.\d+\w*)", r"^(SSL_|EVP_|X509_|OPENSSL_|CRYPTO_)", 8),
    ("BoringSSL", r"BoringSSL", None, 0),
    ("mbedTLS", r"mbed ?TLS (\d\.\d+\.\d+)", r"^mbedtls_", 8),
    ("SQLite", r"^(20\d\d-\d\d-\d\d \d\d:\d\d:\d\d [0-9a-f]{40})", r"^sqlite3_", 8),
    ("zlib", r"(?:deflate|inflate) (\d\.\d+\.\d+(?:\.\d+)?) Copyright", r"^(deflate|inflate|crc32|adler32|uncompress)$", 4),
    ("libpng", r"libpng version (\d\.\d\.\d+)", r"^png_", 8),
    ("libjpeg-turbo", r"libjpeg-turbo version ([\d.]+)", r"^(jpeg_|jinit_)", 8),
    ("libwebp", r"WEBP_", r"^(WebPDecode|WebPEncode|VP8Get)", 4),
    ("libcurl", r"libcurl/(\d+\.\d+\.\d+)", r"^curl_", 8),
    ("Cronet", None, r"^Cronet_", 4),
    ("OpenCV", r"General configuration for OpenCV (\d\.\d+\.\d+)", r"^(_ZN2cv|cvCreate)", 8),
    ("protobuf", None, r"^_ZN6google8protobuf", 8),
    ("TensorFlow Lite", r"TensorFlow Lite", r"^(TfLite|_ZN6tflite)", 4),
    ("ONNX Runtime", r"onnxruntime", r"^Ort", 4),
    ("ncnn", None, r"^_ZN4ncnn", 8),
    ("MNN", None, r"^_ZN3MNN", 8),
    ("WebRTC", None, r"^(_ZN6webrtc|WebRtc_)", 8),
    ("libyuv", None, r"^(I420To|ARGBTo|NV12To|NV21To)", 4),
    ("Opus", r"libopus (\d[\w.\-]+)", r"^opus_", 4),
    ("x264", r"x264 - core (?:([1-9]\d{1,2})\b)?", r"^x264_", 4),
    ("libvpx", r"WebM Project VP[89]", r"^vpx_", 4),
    ("LAME", r"LAME(\d[\w.]*)", r"^lame_", 4),
    ("FreeType", r"FreeType", r"^FT_", 8),
    ("HarfBuzz", None, r"^hb_", 8),
    ("Skia", None, r"^(_ZN2Sk|Sk[A-Z]\w+::)", 8),
    ("ICU", None, r"^(ucnv_|uloc_|_ZN\d+icu)", 8),
    ("Lua", r"\$?Lua (\d\.\d(?:\.\d)?)", r"^(lua_|luaL_)", 8),
    ("QuickJS", r"QuickJS", r"^JS_(New|Free|Eval)", 4),
    ("V8", None, r"^_ZN2v8", 8),
    ("Hermes", None, r"^_ZN(8facebook)?6hermes", 8),
    ("React Native", None, r"^_ZN8facebook5react", 8),
    ("fbjni", None, r"^_ZN8facebook3jni", 4),
    ("Yoga", None, r"^YG(Node|Config)", 4),
    ("Flutter engine", r"io\.flutter", None, 0),
    ("Unity IL2CPP", None, r"^il2cpp_", 4),
    ("Mono", None, r"^mono_", 8),
    ("Boost", None, r"^_ZN5boost", 8),
    ("jsoncpp", None, r"^_ZN4Json", 4),
    ("zstd", None, r"^ZSTD_", 4),
    ("lz4", None, r"^LZ4_", 4),
    ("brotli", None, r"^Brotli", 4),
    ("xz/lzma", None, r"^(lzma_|Lzma)", 4),
    ("bzip2", None, r"^BZ2_", 4),
    ("MMKV", r"MMKV", r"^_ZN4mmkv", 4),
    ("Realm", None, r"^_ZN5realm", 8),
    ("LevelDB", None, r"^_ZN7leveldb", 8),
    ("Breakpad", None, r"^_ZN15google_breakpad", 8),
    ("HDiffPatch", r"HDiffPatch::\w+ v([\d.]+)", r"^(hpatch_|hdiff_)", 4),
    ("mpg123", r"MPG123_|mpg123", r"^mpg123_", 4),
    ("ShadowHook", r"shadowhook init", r"^shadowhook_", 4),
    ("bytehook/xHook", None, r"^(bytehook_|xhook_)", 3),
    ("libc++ (NDK)", None, r"^_ZNSt6__ndk1", 32),
    ("Rust", r"/rustc/[0-9a-f]{40}", None, 0),
    ("Go runtime", r"runtime\.gopanic", None, 0),
)

#: Imported-symbol patterns that mark an Android platform surface, with the porting cost the
#: Westlake taxonomy assigns. ``portable`` surfaces are POSIX and cross Android unchanged.
PLATFORM_SURFACES: tuple[tuple[str, str, str], ...] = (
    ("bitmap", r"^AndroidBitmap_", "platform"),
    ("gles-egl", r"^(gl[A-Z]|egl[A-Z])", "platform"),
    ("vulkan", r"^vk[A-Z]", "platform"),
    ("opencl", r"^cl[A-Z]", "platform"),
    ("libandroid", r"^(AAsset|ANativeWindow|AInputQueue|ALooper|AChoreographer|ASensor|AConfiguration|ASharedMemory|ATrace|AHardwareBuffer)", "platform"),
    ("media-ndk", r"^(AMedia|AImage|ACamera)", "platform"),
    ("audio", r"^(AAudio|slCreateEngine|SL_)", "platform"),
    ("binder", r"^(AIBinder|AParcel|AServiceManager)", "platform"),
    ("sysprop", r"^__system_property", "identity"),
    ("process-control", r"^(ptrace|fork|vfork|kill|prctl|waitpid|personality)$", "integrity"),
    ("dynamic-load", r"^(dlopen|dlsym|dlclose|dladdr|dl_iterate_phdr|android_dlopen_ext)$", "blind"),
    ("log", r"^__android_log", "shim"),
    ("net", r"^(socket|connect|bind|sendto|recvfrom|sendmsg|recvmsg|getaddrinfo|gethostbyname|inet_addr|setsockopt)$", "portable"),
    ("file", r"^(open|openat|__openat_2|__open_2|fopen|creat|unlink|remove|rename|mkdir|stat|lstat|access|faccessat|opendir|readlink)$", "portable"),
    ("thread", r"^pthread_", "portable"),
)

_COMPONENTS = tuple(
    (name, re.compile(banner, re.M) if banner else None, re.compile(symbols) if symbols else None, minimum)
    for name, banner, symbols, minimum in COMPONENT_SIGNATURES
)
_SURFACES = tuple((name, re.compile(pattern), cost) for name, pattern, cost in PLATFORM_SURFACES)
_PLATFORM_TYPE_RE = re.compile(r"L(android/[A-Za-z0-9/$]+|javax?/[A-Za-z0-9/$]+);")
_DLSYM_CANDIDATE_RE = re.compile(rb"[A-Za-z_][A-Za-z0-9_]{3,63}")
_PRINTABLE_RUN_RE = re.compile(rb"[\x20-\x7e]{6,}")
_PLACEHOLDER_VERSION_RE = re.compile(r"^[0.]+$")


def surface_of(symbol: str) -> tuple[str, str] | None:
    """Return ``(surface, cost)`` for an imported symbol, or ``None`` if it is neutral."""
    for name, pattern, cost in _SURFACES:
        if pattern.search(symbol):
            return name, cost
    return None


def classify_symbols(symbols: Iterable[str]) -> dict[str, list[str]]:
    """Group symbols by the platform surface they belong to."""
    grouped: dict[str, list[str]] = {}
    for symbol in sorted(set(symbols)):
        hit = surface_of(symbol)
        if hit:
            grouped.setdefault(hit[0], []).append(symbol)
    return grouped


def boundary_platform_types(signature: str) -> list[str]:
    """Return the ``android/*`` types a JNI descriptor carries across the boundary.

    A platform object in the descriptor is coupling that no amount of call-graph walking
    can remove: the method is handed an Android object and must use platform APIs to read
    it. ``java/*`` types are excluded — those cross every JNI boundary.
    """
    return sorted(
        {match.group(1) for match in _PLATFORM_TYPE_RE.finditer(signature) if match.group(1).startswith("android/")}
    )


def identify_components(
    data: bytes,
    exported_symbols: Sequence[str] = (),
    undefined_symbols: Sequence[str] = (),
) -> list[dict[str, Any]]:
    """Identify upstream components inside, or linked by, one ELF.

    ``contains`` requires a version banner or enough *defined* symbols; ``links-against``
    means the component's symbols are imported from a separate shared object. Conflating
    the two is the most common way to misattribute vendored code.
    """
    text = "\n".join(
        run.decode("ascii", "replace") for run in _PRINTABLE_RUN_RE.findall(data)
    )
    exported = list(exported_symbols)
    undefined = list(undefined_symbols)
    results: list[dict[str, Any]] = []
    for name, banner, symbols, minimum in _COMPONENTS:
        version = None
        banner_matched = False
        evidence: list[str] = []
        if banner:
            match = banner.search(text)
            if match:
                banner_matched = True
                version = next((group for group in match.groups() if group), None) if match.groups() else None
                if version and _PLACEHOLDER_VERSION_RE.match(version):
                    version = None  # An unfilled format placeholder, e.g. "x264 - core 0000".
                evidence.append("version-banner" if version else "banner")
        defined_hits = sum(1 for symbol in exported if symbols and symbols.search(symbol)) if symbols else 0
        imported_hits = sum(1 for symbol in undefined if symbols and symbols.search(symbol)) if symbols else 0
        if defined_hits:
            evidence.append(f"{defined_hits} defined symbols")
        if imported_hits:
            evidence.append(f"{imported_hits} imported symbols")
        # A banner string is physically inside this file, so it settles containment on its own.
        contains = banner_matched or bool(symbols and minimum and defined_hits >= minimum)
        links = not contains and bool(symbols and minimum and imported_hits >= minimum)
        if not contains and not links:
            continue
        results.append(
            {
                "component": name,
                "relation": "contains" if contains else "links-against",
                "version": version,
                "defined_symbol_hits": defined_hits,
                "imported_symbol_hits": imported_hits,
                "exported_symbol_share": round(defined_hits / len(exported), 3) if exported else None,
                "evidence": evidence,
            }
        )
    return sorted(results, key=lambda item: (item["relation"], -item["defined_symbol_hits"], item["component"]))


def dynamic_symbol_candidates(data: bytes, surfaces: Iterable[str] | None = None) -> dict[str, list[str]]:
    """Platform symbol names present as *strings*, i.e. candidates for ``dlsym`` resolution.

    A library that resolves OpenCL or GLES through ``dlopen`` imports none of those symbols.
    The names still have to exist as text for ``dlsym`` to find them, so the string table
    recovers the dependency the import table hides.
    """
    wanted = set(surfaces) if surfaces else None
    grouped: dict[str, list[str]] = {}
    for token in {match.group(0).decode("ascii") for match in _DLSYM_CANDIDATE_RE.finditer(data)}:
        hit = surface_of(token)
        if not hit or hit[1] in {"portable", "blind"}:
            continue
        if wanted and hit[0] not in wanted:
            continue
        grouped.setdefault(hit[0], []).append(token)
    return {surface: sorted(names) for surface, names in sorted(grouped.items())}


def find_objdump(explicit: str | None = None) -> str | None:
    """Locate an aarch64-capable ``llvm-objdump``; the NDK ships one, binutils often does not."""
    if explicit:
        return explicit if Path(explicit).exists() or shutil.which(explicit) else None
    found = shutil.which("llvm-objdump")
    if found:
        return found
    for root in sorted(Path("/home/dspfac/android-sdk/ndk").glob("*/toolchains/llvm/prebuilt/*/bin"), reverse=True):
        candidate = root / "llvm-objdump"
        if candidate.exists():
            return str(candidate)
    return None


def _disassemble(path: Path, objdump: str, timeout: int = 900) -> str:
    proc = subprocess.run(
        [objdump, "-d", "--no-show-raw-insn", str(path)],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return proc.stdout


def _plt_map(disassembly: str, jump_slots: dict[int, str]) -> dict[int, str]:
    """Map each PLT stub address to the symbol its GOT slot is relocated to."""
    stubs: dict[int, str] = {}
    section = None
    page = stub = None
    for line in disassembly.splitlines():
        header = re.match(r"^Disassembly of section (\S+):", line)
        if header:
            section = header.group(1)
            page = stub = None
            continue
        if section not in {".plt", ".iplt"}:
            continue
        instruction = re.match(r"^\s*([0-9a-f]+):\s+(\S+)\s*(.*)$", line)
        if not instruction:
            continue
        address, mnemonic, operands = int(instruction.group(1), 16), instruction.group(2), instruction.group(3)
        if mnemonic == "adrp":
            target = re.search(r"0x([0-9a-f]+)", operands)
            page, stub = (int(target.group(1), 16), address) if target else (None, None)
        elif mnemonic == "ldr" and page is not None:
            offset = re.search(r"#(\d+)", operands)
            if offset:
                slot = page + int(offset.group(1))
                if slot in jump_slots:
                    stubs[stub] = jump_slots[slot]
            page = None
    return stubs


def _call_graph(disassembly: str, extra_entries: Iterable[int]) -> tuple[dict[int, set[int]], set[int]]:
    """Direct call graph from ``bl``, plus ``b`` tail calls into known function entries.

    At -O2 a function whose last act is another call compiles to an unconditional ``b``, not
    ``bl``. Ignoring those loses whole subtrees. A ``b`` is treated as a tail call only when
    its target is itself a function entry (a PLT stub or something else calls it), which
    leaves ordinary intra-function branches out of the graph.
    """
    call_edges: list[tuple[int, int]] = []
    branch_edges: list[tuple[int, int]] = []
    targets: set[int] = set()
    for line in disassembly.splitlines():
        instruction = re.match(r"^\s*([0-9a-f]+):\s+(bl|b)\s+0x([0-9a-f]+)", line)
        if not instruction:
            continue
        source, destination = int(instruction.group(1), 16), int(instruction.group(3), 16)
        if instruction.group(2) == "bl":
            call_edges.append((source, destination))
            targets.add(destination)
        else:
            branch_edges.append((source, destination))
    entries = sorted(targets | set(extra_entries))
    entry_set = set(entries)
    graph: dict[int, set[int]] = {}
    for source, destination in call_edges + [
        edge for edge in branch_edges if edge[1] in entry_set
    ]:
        index = bisect_right(entries, source) - 1
        if index >= 0 and entries[index] != destination:
            graph.setdefault(entries[index], set()).add(destination)
    return graph, targets


def method_surface_reach(
    path: Path,
    registration_entries: Sequence[dict[str, Any]],
    jump_slots: dict[int, str],
    objdump: str | None = None,
    node_budget: int = 50_000,
    symbols_of_interest: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Per-JNI-method reachable platform surfaces, as a lower bound.

    Direct ``bl`` edges only. Every result carries ``basis`` so no caller can mistake this
    for a complete call graph, and any method reaching ``dlopen``/``dlsym`` is flagged
    ``dynamic_resolution`` — its clean verdict is unproven, not proven.

    ``symbols_of_interest`` attributes named imports — typically the ones no provider
    resolves — to the methods that reach them, which is what turns a missing symbol into a
    list of app-facing methods that break.
    """
    wanted = set(symbols_of_interest or ())
    tool = find_objdump(objdump)
    if not tool:
        return {"supported": False, "reason": "no aarch64-capable llvm-objdump found", "methods": []}
    disassembly = _disassemble(path, tool)
    if not disassembly.strip():
        return {"supported": False, "reason": "disassembly produced no output", "methods": []}
    stubs = _plt_map(disassembly, jump_slots)
    entries = [int(entry["function_vaddr"]) for entry in registration_entries]
    graph, _ = _call_graph(disassembly, list(stubs) + entries)

    methods: list[dict[str, Any]] = []
    for entry in registration_entries:
        start = int(entry["function_vaddr"])
        seen: set[int] = set()
        stack = [start]
        imports: set[str] = set()
        truncated = False
        while stack:
            address = stack.pop()
            if address in seen:
                continue
            if len(seen) >= node_budget:
                truncated = True
                break
            seen.add(address)
            symbol = stubs.get(address)
            if symbol:
                imports.add(symbol)
                continue
            stack.extend(graph.get(address, ()))
        grouped = classify_symbols(imports)
        costs = {cost for name in grouped for _, _, cost in [next(s for s in _SURFACES if s[0] == name)]}
        record = {
            "name": entry["name"],
            "signature": entry["signature"],
            "function_vaddr": start,
            "functions_reached": len(seen),
            "boundary_platform_types": boundary_platform_types(entry["signature"]),
            "surfaces": grouped,
            "platform_coupled": "platform" in costs or bool(boundary_platform_types(entry["signature"])),
            "dynamic_resolution": "dynamic-load" in grouped,
            "truncated": truncated,
        }
        if wanted:
            record["symbols_of_interest_reached"] = sorted(imports & wanted)
        methods.append(record)
    return {
        "supported": True,
        "objdump": tool,
        "basis": "direct-bl-lower-bound",
        "indirect_calls_followed": False,
        "plt_stubs_resolved": len(stubs),
        "methods": sorted(methods, key=lambda item: item["function_vaddr"]),
    }


def jump_slot_map(data: bytes) -> dict[int, str]:
    """GOT address -> imported symbol name, from ``R_*_JUMP_SLOT`` relocations."""
    import io

    from elftools.elf.elffile import ELFFile
    from elftools.elf.relocation import RelocationSection

    slots: dict[int, str] = {}
    elf = ELFFile(io.BytesIO(data))
    for section in elf.iter_sections():
        if not isinstance(section, RelocationSection):
            continue
        symbol_table = elf.get_section(section["sh_link"]) if int(section["sh_link"]) else None
        if symbol_table is None:
            continue
        for relocation in section.iter_relocations():
            if "JUMP_SLOT" not in str(relocation["r_info_type"]) and relocation["r_info_type"] not in {1026, 22}:
                continue
            index = int(relocation["r_info_sym"])
            if not index:
                continue
            name = symbol_table.get_symbol(index).name
            if name:
                slots[int(relocation["r_offset"])] = name
    return slots


def analyze_library(path: Path, elf_record: dict[str, Any], objdump: str | None = None) -> dict[str, Any]:
    """Provenance, library-level surface ceiling and per-method reach for one ELF."""
    data = path.read_bytes()
    exported = list(elf_record.get("exported_symbols") or ())
    undefined = list(elf_record.get("undefined_symbols") or ())
    entries = list(elf_record.get("jni_registration_entries") or ())
    result: dict[str, Any] = {
        "library": elf_record.get("name") or path.name,
        "sha256": elf_record.get("sha256"),
        "abi": elf_record.get("abi"),
        "needed": list(elf_record.get("needed") or ()),
        "components": identify_components(data, exported, undefined),
        "surface_ceiling": classify_symbols(undefined),
        "registered_method_count": len(entries),
    }
    dynamic = dynamic_symbol_candidates(data)
    if dynamic:
        result["dlsym_candidates"] = dynamic
    if elf_record.get("machine") in ARM64_MACHINES and entries:
        result["method_reach"] = method_surface_reach(path, entries, jump_slot_map(data), objdump=objdump)
    elif entries:
        result["method_reach"] = {
            "supported": False,
            "reason": f"call-graph reach implemented for AArch64 only; machine is {elf_record.get('machine')!r}",
            "methods": [],
        }
    return result


#: Symbol families that are part of the C++ runtime's own internal linkage rather than a
#: platform contract. They resolve from whichever libc++ wins the namespace, so an absence
#: here is an ``N-C3`` ordering question, not a missing shim.
_CXX_INTERNAL_RE = re.compile(r"^(_ZTI|_ZTS|_ZTV|_ZNSt|_ZNKSt|_ZSt|__cxa_|__gxx_|_Unwind_)")


def resolve_native_imports(
    elf_records: Sequence[dict[str, Any]],
    apk_exports: dict[str, Any],
    bridge_exports: dict[str, Any],
    system_exports: dict[str, Any],
    system_index_available: bool,
) -> list[dict[str, Any]]:
    """Resolve every packaged ELF's undefined symbols against what the runtime provides.

    This is the native half of the subtraction the DEX side already performs. One record per
    symbol, aggregating the libraries that import it, so the canonical gap deduplicates across
    a corpus on the symbol itself.

    **Absence is only claimed when it can be.** With no deployed system libraries in the
    runtime lock, every ``libc`` import would otherwise read as missing; in that state each
    unresolved symbol is ``CU`` with a state naming the missing index, never ``N-C1``.
    """
    importers: dict[str, list[dict[str, Any]]] = {}
    weak: set[str] = set()
    for record in elf_records:
        undefined = record.get("undefined_symbols") or ()
        record_weak = set(record.get("undefined_weak_symbols") or ())
        weak |= record_weak
        for symbol in undefined:
            importers.setdefault(symbol, []).append(
                {
                    "elf": record["name"],
                    "elf_sha256": record.get("sha256"),
                    "weak": symbol in record_weak,
                }
            )

    results: list[dict[str, Any]] = []
    for symbol, sources in sorted(importers.items()):
        providers: list[dict[str, Any]] = []
        scope = None
        for label, table in (
            ("PLATFORM_SYSTEM", system_exports),
            ("PLATFORM_BRIDGE", bridge_exports),
            ("APP_BUNDLED", apk_exports),
        ):
            if symbol in table:
                providers.extend({"scope": label, **item} for item in table[symbol][:8])
                scope = scope or label
        strong_importers = [item for item in sources if not item["weak"]]
        if providers:
            state, classification = "provider-resolved", "C0"
        elif not strong_importers:
            state, classification = "weak-undefined-unresolved", "N-C5-candidate"
        elif _CXX_INTERNAL_RE.match(symbol):
            state, classification = "cxx-runtime-internal", "CU"
        elif not system_index_available:
            state, classification = "runtime-system-index-unavailable", "CU"
        else:
            state, classification = "no-provider", "N-C1-candidate"
        results.append(
            {
                "symbol": symbol,
                "state": state,
                "classification": classification,
                "provider_scope": scope,
                "providers": providers[:8],
                "importing_libraries": sources[:16],
                "importing_library_count": len(sources),
                "weak_only": not strong_importers,
                "surface": (surface_of(symbol) or (None, None))[0],
            }
        )
    return results


def attribute_unresolved_imports(
    library_path: Path,
    elf_record: dict[str, Any],
    symbols: Iterable[str],
    objdump: str | None = None,
) -> dict[str, list[str]]:
    """Map unresolved symbols to the registered JNI methods that reach them.

    Turns "this library is missing 12 symbols" into "these app-facing methods break". The
    walk is the same direct-call lower bound as :func:`method_surface_reach`, so an empty
    result means *not proven to reach*, never *proven not to reach*.
    """
    wanted = set(symbols)
    entries = list(elf_record.get("jni_registration_entries") or ())
    if not wanted or not entries or elf_record.get("machine") not in ARM64_MACHINES:
        return {}
    data = library_path.read_bytes()
    reach = method_surface_reach(
        library_path, entries, jump_slot_map(data), objdump=objdump, symbols_of_interest=wanted
    )
    if not reach.get("supported"):
        return {}
    attributed: dict[str, list[str]] = {}
    for method in reach["methods"]:
        for symbol in method.get("symbols_of_interest_reached", ()):
            attributed.setdefault(symbol, []).append(method["name"])
    return {symbol: sorted(set(names)) for symbol, names in sorted(attributed.items())}


_PATCH_PATH_RE = re.compile(r"(hotfix|patch|plugin|\.odex$|\.dex$|/files/|/app_)", re.I)


def compare_runtime_capture(
    capture_rows: Iterable[dict[str, Any]], native_surface: dict[str, Any]
) -> dict[str, Any]:
    """Join a runtime JNI capture to the static native-surface scan of the same APK.

    The capture comes from ``harness/jniprobe`` — a Frida agent that hooks
    ``RegisterNatives``, ``dlopen`` and ``dlsym``. Its value is entirely in the difference:
    methods only the runtime saw are the surface static reading cannot reach (code delivered
    after install, libraries whose tables are built at runtime), and methods only the scan
    saw are the surface this scenario never exercised.
    """
    runtime: set[tuple[str, str, str]] = set()
    by_library: dict[str, set[tuple[str, str]]] = {}
    classes: set[str] = set()
    tables = 0
    opened: set[str] = set()
    dlsym_failed: set[str] = set()
    dlsym_ok: set[str] = set()

    for row in capture_rows:
        kind = row.get("type")
        if kind == "registerNatives":
            tables += 1
            name = row.get("clazz")
            if name and name != "?":
                classes.add(name)
            for method in row.get("methods") or ():
                library = (method.get("lib") or "?").rsplit("/", 1)[-1]
                key = (method.get("name") or "", method.get("signature") or "")
                runtime.add((library, *key))
                by_library.setdefault(library, set()).add(key)
        elif kind == "dlopen" and row.get("path"):
            opened.add(row["path"])
        elif kind == "dlsym" and row.get("symbol"):
            (dlsym_ok if row.get("resolved") else dlsym_failed).add(row["symbol"])

    static: set[tuple[str, str, str]] = set()
    static_by_library: dict[str, set[tuple[str, str]]] = {}
    packaged = {library["library"] for library in native_surface.get("libraries", ())}
    for library in native_surface.get("libraries", ()):
        for method in library.get("method_reach", {}).get("methods", ()):
            key = (method["name"], method["signature"])
            static.add((library["library"], *key))
            static_by_library.setdefault(library["library"], set()).add(key)

    absent = sorted(
        ({"library": name, "methods": len(methods)} for name, methods in by_library.items() if name not in packaged),
        key=lambda item: -item["methods"],
    )
    opaque = sorted(
        (
            {"library": name, "methods": len(methods)}
            for name, methods in by_library.items()
            if name in packaged and name not in static_by_library
        ),
        key=lambda item: -item["methods"],
    )
    return {
        "static": {"libraries_with_tables": len(static_by_library), "libraries_packaged": len(packaged), "methods": len(static)},
        "runtime": {"registration_tables": tables, "libraries": len(by_library), "methods": len(runtime), "classes_named": len(classes)},
        "runtime_only_methods": len(runtime - static),
        "static_only_methods": len(static - runtime),
        "union_methods": len(runtime | static),
        "libraries_absent_from_apk": absent,
        "libraries_opaque_to_static": opaque,
        "dlsym_unresolved": sorted(dlsym_failed),
        "dlsym_resolved_count": len(dlsym_ok),
        "runtime_loaded_code_objects": sorted(p for p in opened if _PATCH_PATH_RE.search(p)),
        "libraries_opened": len(opened),
    }
