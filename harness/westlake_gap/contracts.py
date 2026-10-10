"""Platform contracts that are neither a Java member nor a native symbol.

The class/member subtraction and the native-import resolution answer "does the name exist". Four of
McDonald's first blockers on the OH board passed both checks and still failed:

- `JobScheduler` exists; the service behind it was null                     → `services.py`
- `PackageManager.getServiceInfo` exists; it returned no components           → package-manager contract
- `mkfifo` resolves in musl; the kernel policy denies the object it creates   → sandbox contract
- the density split exists; the package manager never told resources about it → package-manager contract

This module extracts what the APK relies on at those layers (manifest facts, dependency markers)
and what the provider side supplies (Westlake package-manager source, OH policy), with provenance.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Any

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"


# --------------------------------------------------------------------------------------------
# APK side: manifest facts the platform contract depends on
# --------------------------------------------------------------------------------------------

def _base_apk(path: Path) -> tuple[bytes, list[str]]:
    """Return the base APK bytes and every split name for an .apk/.xapk/.apkm."""
    if path.suffix.lower() == ".apk":
        return path.read_bytes(), []
    with zipfile.ZipFile(path) as archive:
        from .scanner import _ordered_inner_apks

        names = _ordered_inner_apks(archive)
        return archive.read(names[0]), names[1:]


def _attr(element: Any, name: str, default: Any = None) -> Any:
    return element.get(ANDROID_NS + name, default)


def _meta(element: Any) -> dict[str, str]:
    out = {}
    for item in element.findall("meta-data"):
        key = _attr(item, "name")
        if key:
            out[key] = _attr(item, "value") or _attr(item, "resource") or ""
    return out


def manifest_facts(path: Path) -> dict[str, Any]:
    from .scanner import quiet_androguard
    from androguard.core.apk import APK

    quiet_androguard()
    raw, splits = _base_apk(path)
    apk = APK(raw, raw=True)
    root = apk.get_android_manifest_xml()
    app = root.find("application")
    components: list[dict[str, Any]] = []
    processes = set()
    for kind in ("activity", "activity-alias", "service", "receiver", "provider"):
        for element in app.findall(kind):
            process = _attr(element, "process")
            if process:
                processes.add(process)
            components.append({
                "kind": kind,
                "name": _attr(element, "name"),
                "exported": _attr(element, "exported"),
                "enabled": _attr(element, "enabled"),
                "process": process,
                "direct_boot_aware": _attr(element, "directBootAware") == "true",
                "meta_data": _meta(element),
                "authorities": _attr(element, "authorities"),
                "init_order": _attr(element, "initOrder"),
                "target_activity": _attr(element, "targetActivity"),
            })
    # A launcher entry may be an <activity-alias>; what starts is its target.
    targets = {c["name"]: c["target_activity"] for c in components if c["kind"] == "activity-alias" and c["target_activity"]}
    mains = sorted({targets.get(name, name) for name in (apk.get_main_activities() or [])})
    return {
        "package": apk.get_package(),
        "main_activities": mains,
        "version_name": apk.get_androidversion_name(),
        "target_sdk": apk.get_target_sdk_version(),
        "splits": splits,
        "extract_native_libs": _attr(app, "extractNativeLibs", "true") != "false",
        "application_class": _attr(app, "name"),
        "app_component_factory": _attr(app, "appComponentFactory"),
        "application_meta_data": _meta(app),
        "uses_libraries": [
            {"name": _attr(item, "name"), "required": _attr(item, "required", "true") != "false"}
            for item in app.findall("uses-library")
        ],
        "processes": sorted(processes),
        "components": components,
        "permissions": sorted(apk.get_permissions() or []),
    }


# --------------------------------------------------------------------------------------------
# Provider side: the Westlake package manager
# --------------------------------------------------------------------------------------------

_PM_METHOD = re.compile(
    r"@Override\s+public\s+[\w.<>\[\], ?]+\s+(\w+)\s*\(([^)]*)\)\s*(?:throws [\w., ]+)?\s*\{", re.S
)


# What a stub returns: a constant or an empty value, never something computed from the request.
_CONSTANT_RETURN = re.compile(
    r"null|true|false|-?\d+L?|\"\"|new [\w.]+\[0\]|[\w.]*Collections\.empty\w*\(\)"
    r"|[\w.]*ParceledListSlice\.emptyList\(\)|new [\w.]+(<[^>]*>)?\(\)|[\w.]+\.EMPTY\w*|[A-Z_]{2,}")


def pm_adapter_model(westlake_root: Path) -> dict[str, Any]:
    """IPackageManager method → bridged / stub, from PackageManagerAdapter source."""
    path = westlake_root / "framework/package-manager/java/PackageManagerAdapter.java"
    text = path.read_text(errors="replace")
    matches = list(_PM_METHOD.finditer(text))
    methods: dict[str, dict[str, Any]] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():end]
        name = match.group(1)
        returns = [r.strip() for r in re.findall(r"return\s+([^;]+);", body)]
        answered = [r for r in returns if not _CONSTANT_RETURN.fullmatch(r)]
        if "logStub(" in body and "logBridged(" not in body and not answered:
            status, detail = "stub", f"returns {returns[0] if returns else 'void'}"
        elif "logStub(" in body and "logBridged(" not in body:
            # logStub on a guard (null argument, unknown caller) and a real answer otherwise.
            status, detail = "bridged", f"answers {answered[0][:60]}; logStub only on its fallback path"
        elif "SourcePackageRegistry" in body:
            status, detail = "bridged", "source app answered from the original APK via AOSP PackageParser"
        else:
            status, detail = "bridged", "hand-written adapter body"
        line = text.count("\n", 0, match.start()) + 1
        methods.setdefault(name, {"status": status, "detail": detail,
                                  "source": f"framework/package-manager/java/PackageManagerAdapter.java:{line}"})

    registry = westlake_root / "framework/package-manager/java/SourcePackageRegistry.java"
    reg = registry.read_text(errors="replace") if registry.exists() else ""
    splits = westlake_root / "framework/package-manager/java/SplitApkResolver.java"
    bridge = westlake_root / "framework/activity/java/AppSchedulerBridge.java"
    return {
        "methods": methods,
        # Semantics the source-app path must reproduce from PackageManagerService, checked in source.
        "semantics": {
            "direct_boot_match_defaults": _evidence(reg, r"MATCH_DIRECT_BOOT_AWARE\s*\|\s*PackageManager\.MATCH_DIRECT_BOOT_UNAWARE|MATCH_DIRECT_BOOT_UNAWARE", registry, westlake_root),
            "split_paths_populated": _evidence(splits.read_text(errors="replace") if splits.exists() else "", r"splitSourceDirs\s*=", splits, westlake_root),
            # PackageManager hands providers to ActivityThread sorted by descending initOrder
            # (ComputerEngine.sProviderInitOrderSorter); the bind path must sort them the same way.
            "providers_sorted_by_init_order": _evidence(
                bridge.read_text(errors="replace") if bridge.exists() else "",
                r"[Pp]roviders\.sort\([^;]*initOrder", bridge, westlake_root),
            # Each provider authority goes to its first declaration, enabled or not; a provider left
            # with none is not installed (ComponentResolver.addProvidersLocked).
            "provider_authority_claims": _evidence(text, r"claimed\.add\(authority\)", path, westlake_root),
        },
        "provenance": git_state(westlake_root),
    }


def feature_claims_model(westlake_root: Path) -> dict[str, Any]:
    """The features PackageManagerAdapter.hasSystemFeature reports present, with their versions
    where it declares them, and those answered by a condition, with the condition.

    Two forms are read: case labels that reach `return true` (or a condition), and a table of
    CLAIMED_FEATURES.put("name", version) entries, which also gives each claim's version."""
    path = westlake_root / "framework/package-manager/java/PackageManagerAdapter.java"
    text = path.read_text(errors="replace") if path.exists() else ""
    match = re.search(r"public boolean hasSystemFeature\(String \w+, int \w+\)\s*\{", text)
    if not match:
        return {"claimed": [], "conditional": {}, "versions": {}, "source": None}
    claimed: list[str] = []
    conditional: dict[str, str] = {}
    versions: dict[str, int | None] = {}
    pending: list[str] = []
    body = _braced_block(text, match.start())
    for line in body.splitlines():
        stripped = line.strip()
        case = re.match(r'case "([^"]+)":', stripped)
        if case:
            pending.append(case.group(1))
            continue
        answer = re.match(r"return\s+([^;]+);", stripped)
        if answer and pending:
            value = answer.group(1).strip()
            if value == "true":
                claimed += pending
            elif value != "false":
                conditional.update({name: value for name in pending})
            pending = []
        elif stripped.startswith("default:"):
            pending = []
    for name, value in re.findall(r'if \("([^"]+)"\.equals\(\w+\)\)\s*\{\s*return\s+([^;]+);', body):
        if value.strip() == "true":
            claimed.append(name)
        elif value.strip() != "false":
            conditional[name] = value.strip()
    constants = {name: value for name, value in re.findall(r"static final int (\w+)\s*=\s*([^;]+);", text)}
    for name, value in re.findall(r'CLAIMED_FEATURES\.put\("([^"]+)",\s*([^)]+)\);', text):
        claimed.append(name)
        versions[name] = _int_expression(value, constants)
    line = text.count("\n", 0, match.start()) + 1
    return {"claimed": sorted(set(claimed)), "conditional": conditional, "versions": versions,
            "source": f"{path.relative_to(westlake_root)}:{line}"}


def shim_version_nodes(westlake_root: Path) -> set[str]:
    """The version nodes the bionic shim's version script defines (LIBC, LIBC_O, libmozglue.so, ...)."""
    path = westlake_root / "framework/webview-shim/webview_bionic_shim.map"
    text = path.read_text(errors="replace") if path.exists() else ""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return set(re.findall(r"^\s*([A-Za-z_][\w.]*)\s*\{", text, flags=re.M))


def _macro_arguments(text: str, start: int, count: int) -> list[str]:
    """The first count arguments of a macro call whose "(" is at start, split at top-level commas."""
    args, depth, current = [], 0, []
    for char in text[start + 1:]:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:
                break
            depth -= 1
        if char == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
            if len(args) == count:
                return args
            continue
        current.append(char)
    args.append("".join(current).strip())
    return args[:count]


def shim_versioned_definitions(westlake_root: Path) -> dict[str, set[str]]:
    """The names the bionic shim defines at each version node, from its ".symver x, name@version"
    directives and the forwarding macros that write them (WL_MOZGLUE_FORWARD(index, ret, name, ...)).
    An import versioned against an app library binds to the shim only for a name listed here; the
    version node alone covers nothing."""
    found: dict[str, set[str]] = {}
    for path in sorted((westlake_root / "framework/webview-shim").glob("*.c")):
        text = re.sub(r"/\*.*?\*/|//[^\n]*", "", path.read_text(errors="replace"), flags=re.S)
        for name, version in re.findall(r'\.symver\s+\w+\s*,\s*([A-Za-z_]\w*)@{1,2}([\w.]+)"', text):
            found.setdefault(version, set()).add(name)
        for macro, params, body in re.findall(r"#define\s+(\w+)\(([^)]*)\)((?:[^\n]*\\\n)*[^\n]*)", text):
            stringized = re.search(r'#\s*(\w+)\s*"@([\w.]+)"', body)
            names = [p.strip() for p in params.split(",")]
            if not stringized or stringized.group(1) not in names:
                continue
            index = names.index(stringized.group(1))
            for use in re.finditer(rf"^{re.escape(macro)}\(", text, re.M):
                args = _macro_arguments(text, use.end() - 1, index + 1)
                if len(args) > index and re.fullmatch(r"[A-Za-z_]\w*", args[index]):
                    found.setdefault(stringized.group(2), set()).add(args[index])
    return found


def _int_expression(text: str, constants: dict[str, str], depth: int = 0) -> int | None:
    """A Java int expression of literals, named int constants, parentheses and + - * << >> | &,
    or None when it is anything else."""
    import ast
    import operator
    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.LShift: operator.lshift,
           ast.RShift: operator.rshift, ast.BitOr: operator.or_, ast.BitAnd: operator.and_}

    def value(node: ast.AST) -> int | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name) and node.id in constants and depth < 4:
            return _int_expression(constants[node.id], constants, depth + 1)
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            left, right = value(node.left), value(node.right)
            return None if left is None or right is None else ops[type(node.op)](left, right)
        return None

    source = re.sub(r"//.*", "", text).strip()
    source = re.sub(r"\b(0[xX][0-9a-fA-F]+|\d+)[lL]\b", r"\1", source)
    try:
        return value(ast.parse(source, mode="eval").body)
    except SyntaxError:
        return None


def _braced_block(text: str, start: int) -> str:
    """The body of the first {...} block at or after start, braces balanced."""
    open_at = text.find("{", start)
    if open_at < 0:
        return ""
    depth = 0
    for index in range(open_at, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[open_at + 1:index]
    return text[open_at + 1:]


def direct_launch_am_model(westlake_root: Path) -> dict[str, Any]:
    """What an app gets from IActivityManager in direct launch, where there is no system_server.

    AppSpawnXInit installs a java.lang.reflect.Proxy for IActivityManager whose handler returns a
    type default for every method it does not answer by name: null for any object result, 0 or
    false otherwise. The methods it answers are read from the handler's label-specific block.
    """
    path = westlake_root / "framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java"
    text = path.read_text(errors="replace") if path.exists() else ""
    stub = re.search(r'makeProxyStub\(\s*"AdapterIAM-stub"', text)
    guard = text.find('"AdapterIAM-stub".equals(label)')
    answered = sorted(set(re.findall(r'"(\w+)"\.equals\(name\)', _braced_block(text, guard)))) if guard >= 0 else []
    line = text.count("\n", 0, stub.start()) + 1 if stub else None
    return {"proxy_stub": stub is not None, "answered": answered,
            "source": f"{path.relative_to(westlake_root)}:{line}" if stub else None}


#: ActivityManager's task queries -> the IActivityTaskManager method behind each.
TASK_QUERIES = {"getRunningTasks": "getTasks", "getAppTasks": "getAppTasks", "getRecentTasks": "getRecentTasks"}


def task_queries_model(westlake_root: Path) -> dict[str, Any]:
    """Which IActivityTaskManager task queries the adapter answers with the app's own task, and which
    with nothing: an empty list, or null (ActivityManager.getRecentTasks reads getList() off it)."""
    path = westlake_root / "framework/activity/java/ActivityTaskManagerAdapter.java"
    text = _strip_java_comments(path.read_text(errors="replace")) if path.exists() else ""
    answered, empty, first = [], [], None
    for method in sorted(set(TASK_QUERIES.values())):
        match = re.search(rf"\bpublic\s+[\w.<>, ]+\s+{method}\s*\(", text)
        if not match:
            continue
        first = first or match
        body = _braced_block(text, match.start())
        statements = [s.strip() for s in body.split(";") if s.strip() and not s.strip().startswith("logBridged")]
        if statements and re.fullmatch(r"return\s+(null|Collections\.emptyList\(\)|new\s+\w+(<[^>]*>)?\(\))", statements[-1]) \
                and len(statements) == 1:
            empty.append(method)
        else:
            answered.append(method)
    return {"answered": answered, "empty": empty,
            "source": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, first.start()) + 1}" if first else None}


def launch_intent_model(westlake_root: Path) -> dict[str, Any]:
    """Whether the app's own activities are launched with the Intent the app passed. The in-process
    launch goes out through OH's Want and is rebuilt from its JSON, which keeps strings and numbers
    but not Parcelable extras; the provider can hand the launch the caller's Intent instead."""
    path = westlake_root / "framework/activity/java/AppSchedulerBridge.java"
    text = _strip_java_comments(path.read_text(errors="replace")) if path.exists() else ""
    match = re.search(r"PendingLaunchIntents\.take\(", text)
    return {"original_intent": match is not None,
            "source": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, match.start()) + 1}" if match else None}


def thread_priority_model(art_build_root: Path | None) -> dict[str, Any]:
    """The Java priority ART gives a thread it attaches: its palette's PaletteSchedGetPriority answer.
    A constant 0 is outside Java's 1-10, and setPriority with a saved 0 throws."""
    path = art_build_root / "stubs/link_stubs_arm64.cc" if art_build_root else None
    if path is None or not path.exists():
        return {"answer": None, "source": None}
    text = path.read_text(errors="replace")
    match = re.search(r"int\s+PaletteSchedGetPriority\s*\([^)]*\)\s*\{[^}]*\*p\s*=\s*(\d+)", text)
    if not match:
        return {"answer": None, "source": None}
    return {"answer": int(match[1]), "source": f"art-build/stubs/link_stubs_arm64.cc:{text.count(chr(10), 0, match.start()) + 1}"}


def window_metrics_model(westlake_root: Path) -> dict[str, Any]:
    """Whether activities are launched with their window's bounds in the configuration.

    WindowManager.getCurrentWindowMetrics() and getMaximumWindowMetrics() answer from the
    configuration's windowConfiguration bounds. The relayout fills them later; an activity that
    measures itself in onCreate sees only what the bind-time configuration carried.
    """
    path = westlake_root / "framework/activity/java/AppSchedulerBridge.java"
    text = path.read_text(errors="replace") if path.exists() else ""
    match = re.search(r"Configuration buildConfiguration\(", text)
    body = _braced_block(text, match.start()) if match else ""
    bounds = re.search(r"windowConfiguration\.setBounds\(", body)
    line = text.count("\n", 0, match.start()) + 1 if match else None
    return {"bounds_at_bind": bounds is not None,
            "source": f"{path.relative_to(westlake_root)}:{line}" if match else None}


def native_egl_window_model(westlake_root: Path) -> dict[str, Any]:
    """Whether an eglCreateWindowSurface from native code reaches OH's EGL with an OH window.

    ANativeWindow_fromSurface hands an app the adapter's AOSP-shaped window (magic ANW1) around an
    OHNativeWindow, and OH's EGL takes only the OHNativeWindow. The preloaded bionic shim answers the
    call for app code; it must unwrap the window (oh_anw_get_oh) before passing it on.
    """
    path = westlake_root / "framework/webview-shim/webview_bionic_shim.c"
    text = path.read_text(errors="replace") if path.exists() else ""
    match = re.search(r"^\S[^\n;]*\beglCreateWindowSurface\([^;{]*\)\s*\{", text, re.M)
    body = _braced_block(text, match.start()) if match else ""
    line = text.count("\n", 0, match.start()) + 1 if match else None
    by_handle = re.search(r"\bwestlake_egl_by_handle\(", text)
    # ANativeWindow_setBuffersGeometry in Android's terms: a 0x0 size is the window's own, and the
    # format is translated from Android's numbering, not handed to OH's SET_FORMAT as is.
    geometry = re.search(r"^\S[^\n;]*\bANativeWindow_setBuffersGeometry\([^;{]*\)\s*\{", text, re.M)
    geometry_body = _braced_block(text, geometry.start()) if geometry else ""
    translated = (re.search(r"\bwidth\s*[!=]=\s*0\b", geometry_body) is not None
                  and re.search(r"\b\w*format\w*\s*\(", geometry_body) is not None)
    # libGLESv2.so from Android code answered with OH's libGLESv3.so, which carries GLES 3 as
    # Android's libGLESv2.so does (the WebView alone was given it before). It must come before the
    # .z.so probe, which returns a bare name's own library whenever it opens: placed after it, the
    # translation never saw "libGLESv2.so" (aaaaxy still failed on the shim that had it there).
    gles3 = re.search(r'strcmp\(basename, "libGLESv2\.so"\) == 0 &&\s*caller_is_android_dso\(', text)
    probe = re.search(r"\bvoid\s*\*\s*plain\s*=\s*real_dlopen\(actual_filename,", text)
    gles3_ok = (gles3 is not None and "libGLESv3.so" in text[gles3.end():gles3.end() + 400]
                and (probe is None or gles3.start() < probe.start()))
    return {"unwraps": "anw_get_oh" in body,
            "source": f"{path.relative_to(westlake_root)}:{line}" if match else None,
            "gles3_by_handle": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, gles3.start()) + 1}"
            if gles3_ok else None,
            # An Android library's dlsym of these by handle gets the shim's, not OH's EGL directly.
            "by_handle": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, by_handle.start()) + 1}"
            if by_handle else None,
            "geometry": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, geometry.start()) + 1}"
            if geometry and translated else None}


def software_canvas_model(westlake_root: Path) -> dict[str, Any]:
    """Whether a window can be drawn in software: the preloaded shim's ANativeWindow_lock requests and
    maps a buffer (it answered -ENODEV), and Surface.lockCanvas, whose runtime native handed back no
    buffer, is wrapped over that pair from libwl_missing_natives (canvas_natives.c, registered from
    its JNI_OnLoad and compiled by its build)."""
    shim = westlake_root / "framework/webview-shim/webview_bionic_shim.c"
    text = shim.read_text(errors="replace") if shim.exists() else ""
    match = re.search(r"^\S[^\n;]*\bANativeWindow_lock\([^;{]*\)\s*\{", text, re.M)
    body = _braced_block(text, match.start()) if match else ""
    native = f"{shim.relative_to(westlake_root)}:{text.count(chr(10), 0, match.start()) + 1}" \
        if match and "RequestBuffer" in body else None
    canvas = westlake_root / "framework/javacore-shim/canvas_natives.c"
    onload = westlake_root / "framework/javacore-shim/missing_natives.c"
    build = westlake_root / "tools/build_missing_natives.sh"
    read = lambda path: path.read_text(errors="replace") if path.exists() else ""
    canvas_text = read(canvas)
    wraps = re.search(r"^int wl_register_surface_canvas\(", canvas_text, re.M)
    java = (f"{canvas.relative_to(westlake_root)}:{canvas_text.count(chr(10), 0, wraps.start()) + 1}"
            if wraps and "wl_register_surface_canvas(env)" in read(onload) and "canvas_natives" in read(build)
            else None)
    return {"native": native, "java": java}


def sqlite_collations_model(westlake_root: Path) -> dict[str, Any]:
    """Whether a SQLite connection gets Android's collations over ICU: UNICODE on every connection,
    LOCALIZED and PHONEBOOK for the locale. The runtime registered no UNICODE, and its LOCALIZED and
    PHONEBOOK compare with strcoll (byte order on musl); libwl_missing_natives wraps SQLiteConnection's
    natives to register them (sqlite_natives.c, from its JNI_OnLoad, compiled by its build)."""
    source = westlake_root / "framework/javacore-shim/sqlite_natives.c"
    onload = westlake_root / "framework/javacore-shim/missing_natives.c"
    build = westlake_root / "tools/build_missing_natives.sh"
    read = lambda path: path.read_text(errors="replace") if path.exists() else ""
    text = read(source)
    match = re.search(r"^int wl_register_sqlite_collations\(", text, re.M)
    names = set(re.findall(r'wl_register_collation\(db, "(\w+)"', text))
    wired = match is not None and "wl_register_sqlite_collations(env)" in read(onload) and "sqlite_natives" in read(build)
    return {"collations": sorted(names) if wired else [],
            "source": f"{source.relative_to(westlake_root)}:{text.count(chr(10), 0, match.start()) + 1}"
            if wired else None}


def activity_client_model(westlake_root: Path) -> dict[str, Any]:
    """Whether the in-process IActivityClientController answers the task queries, or returns a
    constant: getTaskForActivity backs Activity.isTaskRoot() and getTaskId()."""
    path = westlake_root / "framework/activity/java/ActivityClientControllerAdapter.java"
    text = path.read_text(errors="replace") if path.exists() else ""
    match = re.search(r"public int getTaskForActivity\([^)]*\)\s*\{", text)
    if not match:
        return {"task_for_activity": None, "source": None}
    body = _braced_block(text, match.start())
    hollow = re.fullmatch(r"\s*return\s+-?\d+;\s*", body) is not None
    line = text.count("\n", 0, match.start()) + 1
    return {"task_for_activity": "constant" if hollow else "answered",
            "source": f"{path.relative_to(westlake_root)}:{line}"}


def own_intent_model(westlake_root: Path) -> dict[str, Any]:
    """Whether an implicit intent reaches the app's own activities: the source package's registry
    matches them against their manifest filters, the package manager's queryIntentActivities asks
    it, and startActivity makes such an intent explicit before it becomes a Want."""
    registry = westlake_root / "framework/package-manager/java/SourcePackageRegistry.java"
    manager = westlake_root / "framework/package-manager/java/PackageManagerAdapter.java"
    tasks = westlake_root / "framework/activity/java/ActivityTaskManagerAdapter.java"
    read = lambda path: _strip_java_comments(path.read_text(errors="replace")) if path.exists() else ""
    registry_text, manager_text, tasks_text = read(registry), read(manager), read(tasks)
    defined = re.search(r"\bstatic\b[^;{]*\bqueryActivities\s*\(", registry_text)
    query = re.search(r"public\s+\S+\s+queryIntentActivities\s*\(", manager_text)
    start = re.search(r"public\s+int\s+startActivity\s*\(", tasks_text)
    queried = bool(query and "SourcePackageRegistry.queryActivities(" in _braced_block(manager_text, query.start()))
    # startActivity resolves through a helper of its own that asks the registry.
    started = False
    if start:
        for name in set(re.findall(r"\b(\w+)\s*\(", _braced_block(tasks_text, start.start()))):
            helper = re.search(rf"\b{name}\s*\([^;{{]*\)\s*\{{", tasks_text)
            if helper and ".queryActivities(" in _braced_block(tasks_text, helper.start()):
                started = True
                break
    return {"resolved": bool(defined and queried), "started": started,
            "source": f"{registry.relative_to(westlake_root)}:{registry_text.count(chr(10), 0, defined.start()) + 1}"
                      if defined else None}


def launch_start_model(westlake_root: Path) -> dict[str, Any]:
    """Whether an activity's launch transaction carries its start (or its resume). handleLaunchActivity
    marks the transaction executor's pending actions -- restore the saved state, call onPostCreate --
    and the executor clears them when its transaction ends. A start in a transaction of its own finds
    them cleared: no onRestoreInstanceState, no onPostCreate."""
    path = westlake_root / "framework/activity/java/AppSchedulerBridge.java"
    text = _strip_java_comments(path.read_text(errors="replace")) if path.exists() else ""
    match = re.search(r"public\s+static\s+void\s+nativeOnScheduleLaunchAbility\s*\(", text)
    if not match:
        return {"carries_start": None, "source": None}
    body = _braced_block(text, match.start())
    carries = "LaunchActivityItem.obtain(" in body and re.search(
        r"\b(?:StartActivityItem|ResumeActivityItem)\.obtain\s*\(", body) is not None
    return {"carries_start": carries,
            "source": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, match.start()) + 1}"}


def permission_request_model(westlake_root: Path) -> dict[str, Any]:
    """Whether a runtime permission request gets an answer: Activity.requestPermissions starts the
    permission controller for a result, and the in-process activity task manager must answer that
    start with the result the controller would send (ActivityResultItem to the caller)."""
    path = westlake_root / "framework/activity/java/ActivityTaskManagerAdapter.java"
    text = _strip_java_comments(path.read_text(errors="replace")) if path.exists() else ""
    start = re.search(r"public\s+int\s+startActivity\s*\(", text)
    if not start:
        return {"answered": None, "source": None}
    body = _braced_block(text, start.start())
    answered = False
    if "ACTION_REQUEST_PERMISSIONS" in body:
        for name in set(re.findall(r"\b(\w+)\s*\(", body)):
            helper = re.search(rf"\b{name}\s*\([^;{{]*\)\s*\{{", text)
            if helper and "ActivityResultItem.obtain(" in _braced_block(text, helper.start()):
                answered = True
                break
    return {"answered": answered,
            "source": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, start.start()) + 1}"}


def activity_result_model(westlake_root: Path) -> dict[str, Any]:
    """Whether startActivityForResult between the app's own activities gets its answer. Activity.finish
    hands the result the activity set to IActivityClientController.finishActivity; the in-process
    controller must send it to the caller, in an ActivityResultItem, as ActivityTaskManager does.
    The item may be built in finishActivity or in a helper it calls (a class beside it)."""
    path = westlake_root / "framework/activity/java/ActivityClientControllerAdapter.java"
    text = _strip_java_comments(path.read_text(errors="replace")) if path.exists() else ""
    start = re.search(r"public\s+boolean\s+finishActivity\s*\(", text)
    if not start:
        return {"delivered": None, "source": None}
    body = _braced_block(text, start.start())
    delivered = "ActivityResultItem.obtain(" in body
    for owner, method in re.findall(r"\b([A-Z]\w*)\.(\w+)\s*\(", body):
        if delivered:
            break
        helper_path = path.parent / f"{owner}.java"
        if not helper_path.exists():
            continue
        helper = _strip_java_comments(helper_path.read_text(errors="replace"))
        found = re.search(rf"\b{method}\s*\([^;{{]*\)\s*\{{", helper)
        delivered = bool(found) and "ActivityResultItem.obtain(" in _braced_block(helper, found.start())
    return {"delivered": delivered,
            "source": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, start.start()) + 1}"}


def host_permission_model(westlake_root: Path) -> dict[str, Any]:
    """The OH permissions the host application requests, and the OH permission each Android permission
    maps to. Android apps run in the host's process, so OH checks the host's access token: what the
    app is granted in process is what OH has granted the host (PermissionMapper's mapping), and a
    capability OH guards with a permission works only when the host requests it."""
    host = westlake_root / "apps/imehost/module.json"
    mapper = westlake_root / "framework/package-manager/java/PermissionMapper.java"
    if not host.exists():
        return {"requested": None, "mapping": {}, "source": None}
    text = host.read_text(errors="replace")
    requested = sorted(item["name"] for item in json.loads(text).get("module", {}).get("requestPermissions", [])
                       if item.get("name"))
    mapping: dict[str, str] = {}
    if mapper.exists():
        for android, oh in re.findall(r'addMapping\(\s*"([\w.]+)"\s*,\s*"([\w.]+)"\s*\)', mapper.read_text(errors="replace")):
            mapping.setdefault(android, oh)
    match = re.search(r'"requestPermissions"', text)
    line = text.count("\n", 0, match.start()) + 1 if match else 1
    return {"requested": requested, "mapping": mapping, "source": f"{host.relative_to(westlake_root)}:{line}"}


def user_service_model(westlake_root: Path) -> dict[str, Any]:
    """The IUserManager methods the in-process user service answers. It is a proxy over the OH account
    service that throws UnsupportedOperationException for every method it does not name, where
    system_server would have answered: clauncher's UserManager.getUserProfiles met "OH user service
    does not implement getProfileIds"."""
    path = westlake_root / "framework/package-manager/java/OHUserManager.java"
    if not path.exists():
        return {"answered": None, "source": None}
    text = _strip_java_comments(path.read_text(errors="replace"))
    answered = set(re.findall(r'\bname\.equals\("(\w+)"\)', text)) | set(re.findall(r'\bcase\s+"(\w+)"\s*:', text))
    throws = re.search(r"throw new UnsupportedOperationException\(", text)
    line = text.count("\n", 0, throws.start()) + 1 if throws else None
    return {"answered": sorted(answered), "throws": throws is not None,
            "source": f"{path.relative_to(westlake_root)}:{line}" if throws else None}


def ce_storage_model(westlake_root: Path) -> dict[str, Any]:
    """Whether the in-process storage manager says the user's credential-encrypted storage is unlocked
    under Android 15's name for the call, isCeStorageUnlocked (it was isUserKeyUnlocked)."""
    path = westlake_root / "framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java"
    text = _strip_java_comments(path.read_text(errors="replace")) if path.exists() else ""
    match = re.search(r'"isCeStorageUnlocked"\.equals\(name\)[^{;]*\{\s*return\s+Boolean\.TRUE', text)
    return {"unlocked": match is not None,
            "source": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, match.start()) + 1}" if match else None}


def window_adapter_model(westlake_root: Path) -> dict[str, Any]:
    """Window-manager semantics the in-process IWindowSession must reproduce, checked in source."""
    path = westlake_root / "framework/window/java/WindowSessionAdapter.java"
    text = path.read_text(errors="replace") if path.exists() else ""
    return {
        # Android: an activity's dialogs stack above its base window whatever the add order.
        "dialogs_above_base": _evidence(text, r"shouldHoldBack\(", path, westlake_root),
        # Android: WMS places a window by LayoutParams.gravity/x/y (a dialog is centred).
        # Android's own WindowLayout, or a hand-written gravity application. A comment naming
        # ViewRootImpl's mWindowLayout.computeFrames is not support, hence "WindowLayout()".
        "placement_from_gravity": _evidence(
            text, r"WindowLayout\(\)\s*\.computeFrames\(|Gravity\.apply|attrs\.gravity", path, westlake_root),
        # Android: FLAG_DIM_BEHIND puts a dim layer of dimAmount under the window.
        "dim_behind": _evidence(text, r"FLAG_DIM_BEHIND|dimAmount", path, westlake_root),
    }


# JCA providers only Android's zygote installs (AndroidKeyStoreProvider.install), not libcore's defaults.
ANDROID_JCA_PROVIDERS = {"AndroidKeyStore", "AndroidKeyStoreBCWorkaround"}


def keystore_model(westlake_root: Path) -> dict[str, Any]:
    """Whether the runtime installs an "AndroidKeyStore" provider, and what answers it.

    On Android the zygote calls AndroidKeyStoreProvider.install() (ZygoteInit.warmUpJcaProviders);
    that provider's operations go to the keystore2 system service. Having the class in the boot jars
    is not enough: KeyStore.getInstance("AndroidKeyStore") throws until something installs it. A
    runtime may instead install its own Provider registered under that name (software or HUKS keys).
    """
    aosp_install = re.compile(r"AndroidKeyStoreProvider\s*\.\s*install\s*\(")
    backend = re.compile(r"android\.system\.keystore2|IKeystoreService|OH_Huks_|\bHuks\w*\(")
    sources = {}
    framework = westlake_root / "framework"
    for path in sorted(framework.rglob("*.java")) if framework.exists() else []:
        sources[path] = _strip_java_comments(path.read_text(errors="replace"))

    def first(pattern: re.Pattern[str]) -> dict[str, Any]:
        for path, text in sources.items():
            match = pattern.search(text)
            if match:
                return {"present": True, "source": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, match.start()) + 1}"}
        return {"present": False, "source": None}

    replacement = {"present": False, "source": None}
    for path, text in sources.items():
        declared = re.search(r"\bclass\s+(\w+)\s+extends\s+(?:java\.security\.)?Provider\b", text)
        if not declared or '"AndroidKeyStore"' not in text:
            continue
        name = declared.group(1)
        # Declared is not installed: code elsewhere must call its installer or add it to the list.
        installer = re.compile(rf"\b{name}\s*\.\s*install\s*\(|(?:add|insert)Provider\w*\(\s*new\s+{name}\b")
        if any(installer.search(other) for where, other in sources.items() if where != path):
            replacement = {"present": True, "source": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, declared.start()) + 1}",
                           "hardware_backed": bool(backend.search(text))}
            break
    # Every provider name a runtime Provider registers: Android installs two ("AndroidKeyStore" for
    # keys, "AndroidKeyStoreBCWorkaround" for operations on them) and apps name each directly.
    registered: dict[str, str] = {}
    for path, text in sources.items():
        for match in re.finditer(r'\bclass\s+\w+\s+extends\s+(?:java\.security\.)?Provider\b', text):
            body = text[match.end():]
            name = re.search(r'\bNAME\s*=\s*"([^"]+)"|super\(\s*"([^"]+)"', body)
            if name:
                registered.setdefault(name.group(1) or name.group(2),
                                      f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, match.start()) + 1}")
    return {"installed": first(aosp_install), "replacement": replacement, "backend": first(backend),
            "registered": registered}


def _strip_java_comments(text: str) -> str:
    """Blank out comments but keep line numbers: a comment naming an API is not support for it."""
    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))
    return re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\\n])*"', lambda m: m.group(0) if m.group(0).startswith('"') else blank(m),
                  text, flags=re.S)


# libc calls whose *arguments* are constants each libc numbers for itself. The name resolves and
# the call returns a plausible number, so nothing fails at load time: bionic's _SC_PAGESIZE is 39,
# OH musl reads 39 as _SC_BC_STRING_MAX and answers 1000, and McDonald's Realm rounded its mmap
# offsets with that until the kernel rejected the unaligned offset.
LIBC_CONSTANT_NAMESPACE_CALLS = {"sysconf", "pathconf", "fpathconf", "confstr"}


def android_caller_scope(text: str) -> dict[str, bool]:
    """Which callers the bionic shim's caller_is_android_dso counts as built against bionic: the
    app's packaged libraries (/data/local/tmp/asx/lib/), and the ones it writes and loads from its
    own storage (/data/data/..., the code_cache/wl-exec copies)."""
    if "caller_is_android_dso(void" not in text:
        # The test is used but not defined here: it has always covered the packaged libraries.
        return {"packaged": "caller_is_android_dso(" in text, "written": False}
    body = _braced_block(text, text.index("caller_is_android_dso(void"))
    return {"packaged": "/data/local/tmp/asx/lib/" in body, "written": '"/data/data/"' in body}


# Signal calls whose structures bionic and OH musl lay out differently on arm64: struct sigaction is
# 32 bytes in bionic and 152 in musl (flags first in one, the handler first in the other), sigset_t
# 8 bytes and 128.
SIGNAL_ABI_CALLS = {"sigaction", "sigemptyset", "sigfillset", "sigaddset", "sigdelset", "sigismember",
                    "sigprocmask", "pthread_sigmask"}
SIGNAL_ABI_CALLS_64 = {name + "64" for name in SIGNAL_ABI_CALLS}


def signal_abi_model(westlake_root: Path) -> dict[str, Any]:
    """Which signal calls the bionic shim translates, for which callers, and whether a lookup by
    name (dlsym) reaches the translation too."""
    path = westlake_root / "framework/webview-shim/webview_bionic_shim.c"
    if not path.exists():
        return {"translated": [], "scope": {"packaged": False, "written": False}, "dlsym": None, "source": None}
    raw = path.read_text(errors="replace")
    text = _strip_java_comments(raw)
    translated = sorted(name for name in SIGNAL_ABI_CALLS | SIGNAL_ABI_CALLS_64
                        if re.search(rf"^\s*int\s+{name}\s*\(", text, re.M))
    # A lookup by name reaches the translation through a dlsym interposer, or because an Android
    # caller's dlopen("libc.so") gets this library's own handle (searched before musl's).
    dlsym = (re.search(r"^\s*void\s*\*\s*dlsym\s*\(", text, re.M)
             or re.search(r'strcmp\(basename, "libc\.so"\) == 0 && caller_is_android_dso', text))
    first = re.search(r"^\s*int\s+sigaction\s*\(", text, re.M)
    return {"translated": translated, "scope": android_caller_scope(text),
            "dlsym": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, dlsym.start()) + 1}" if dlsym else None,
            "source": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, first.start()) + 1}" if first else None}


#: The lock calls that must see a Bionic static mutex initializer converted to musl's type first.
STATIC_MUTEX_LOCKS = ("pthread_mutex_lock", "pthread_mutex_trylock")


def static_mutex_model(westlake_root: Path) -> dict[str, Any]:
    """Which lock calls the bionic shim defines that convert Bionic's static recursive and
    error-checking initializers (0x4000, 0x8000 in the type word) to musl's types before musl locks
    the mutex. Defined in the preloaded shim, they are every caller's."""
    path = westlake_root / "framework/webview-shim/webview_bionic_shim.c"
    if not path.exists():
        return {"adopted": [], "source": None}
    text = _strip_java_comments(path.read_text(errors="replace"))
    adopted, first = [], None
    for name in STATIC_MUTEX_LOCKS:
        match = re.search(rf"^[ \t]*int\s+{name}\s*\(", text, re.M)
        if not match or "0x4000" not in text:
            continue
        body = _braced_block(text, match.start())
        callee = re.search(r"(\w+)\(\s*mutex\s*\)\s*;", body)
        # The conversion is called first thing, or lives in a helper called there that tests 0x4000.
        helper = callee and re.search(rf"\b{callee[1]}\s*\([^;{{]*\)\s*\{{", text)
        if helper and "0x4000" in _braced_block(text, helper.start()):
            adopted.append(name)
            first = first or match
    return {"adopted": adopted,
            "source": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, first.start()) + 1}" if first else None}


def thread_start_model(westlake_root: Path) -> dict[str, Any]:
    """Whether the bionic shim's pthread_create gives a new thread Bionic's order: the thread starts
    in a routine of the shim's that waits on a futex, and pthread_create wakes it after musl has
    stored the handle. Defined in the preloaded shim, it is every caller's."""
    path = westlake_root / "framework/webview-shim/webview_bionic_shim.c"
    if not path.exists():
        return {"ordered": False, "source": None}
    text = _strip_java_comments(path.read_text(errors="replace"))
    match = re.search(r"^[ \t]*int\s+pthread_create\s*\(", text, re.M)
    body = _braced_block(text, match.start()) if match else ""
    ordered = False
    if "FUTEX_WAKE" in body:
        for name in sorted(set(re.findall(r"\b([A-Za-z_]\w*)\b", body))):
            start = re.search(rf"^static\s+void\s*\*\s*{name}\s*\(\s*void\s*\*\s*\w+\s*\)\s*\{{", text, re.M)
            if start and "FUTEX_WAIT" in _braced_block(text, start.start()):
                ordered = True
                break
    return {"ordered": ordered,
            "source": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, match.start()) + 1}"
                      if ordered else None}


def passwd_lookup_model(westlake_root: Path) -> dict[str, Any]:
    """Which of getpwnam, getpwuid, getgrnam and getgrgid the bionic shim answers with a result per
    thread, as Bionic does: a definition whose body hands the lookup to a helper that keeps the
    thread's buffer under a pthread key. Defined in the preloaded shim, it is every caller's."""
    path = westlake_root / "framework/webview-shim/webview_bionic_shim.c"
    if not path.exists():
        return {"per_thread": [], "source": None}
    text = _strip_java_comments(path.read_text(errors="replace"))
    keyed = "pthread_getspecific(" in text and "pthread_key_create(" in text
    found, first = [], None
    for name in ("getpwnam", "getpwuid", "getgrnam", "getgrgid"):
        match = re.search(rf"^struct\s+(?:passwd|group)\s*\*\s*{name}\s*\(", text, re.M)
        if match and keyed and f"{name}_r" in text and "westlake_thread_" in _braced_block(text, match.start()):
            found.append(name)
            first = first if first is not None else match.start()
    return {"per_thread": found,
            "source": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, first) + 1}" if found else None}


def interface_index_model(westlake_root: Path) -> dict[str, Any]:
    """Whether the bionic shim answers if_nametoindex without the ioctl OH refuses an app's domain:
    its definition falls back to getifaddrs, whose AF_PACKET entries carry each link's index.
    Defined in the preloaded shim, it is every caller's."""
    path = westlake_root / "framework/webview-shim/webview_bionic_shim.c"
    if not path.exists():
        return {"answered": False, "source": None}
    text = _strip_java_comments(path.read_text(errors="replace"))
    match = re.search(r"^unsigned\s+int\s+if_nametoindex\s*\(", text, re.M)
    body = _braced_block(text, match.start()) if match else ""
    helpers = [name for name in re.findall(r"\b(\w+)\s*\(", body)
               if re.search(rf"^static\s+[\w ]+\b{name}\s*\([^)]*\)\s*\{{", text, re.M)]
    answered = "getifaddrs" in body or any(
        "getifaddrs" in _braced_block(text, re.search(rf"^static\s+[\w ]+\b{name}\s*\(", text, re.M).start())
        for name in helpers)
    return {"answered": answered,
            "source": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, match.start()) + 1}" if answered else None}


def legacy_keypair_model(westlake_root: Path) -> dict[str, Any]:
    """Whether the in-process AndroidKeyStore provider accepts the legacy KeyPairGeneratorSpec (API 18,
    deprecated in 23), which Android's provider still converts to a KeyGenParameterSpec."""
    framework = westlake_root / "framework"
    for path in sorted(framework.rglob("*.java")) if framework.exists() else []:
        text = _strip_java_comments(path.read_text(errors="replace"))
        if '"AndroidKeyStore"' not in text or not re.search(r"\bextends\s+(?:java\.security\.)?Provider\b", text):
            continue
        match = re.search(r"instanceof\s+(?:android\.security\.)?KeyPairGeneratorSpec\b", text)
        if match:
            return {"accepted": True, "source": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, match.start()) + 1}"}
    return {"accepted": False, "source": None}


def libc_constant_model(westlake_root: Path) -> dict[str, Any]:
    """Whether the bionic shim translates those constants, and for which callers.

    Translating for the WebView DSO alone is not enough: every library the APK packages is built
    against bionic and asks the same questions.
    """
    path = westlake_root / "framework/webview-shim/webview_bionic_shim.c"
    if not path.exists():
        return {"translated": [], "scope": "none", "source": None}
    text = _strip_java_comments(path.read_text(errors="replace"))
    translated = sorted(name for name in LIBC_CONSTANT_NAMESPACE_CALLS
                        if re.search(rf"^\s*(?:long|int|size_t)\s+{name}\s*\(", text, re.M))
    scope = "none"
    if translated:
        body = _braced_block(text, text.index(f"{translated[0]}("))
        if "caller_is_android_dso" in body:
            scope = "packaged-libraries"
        elif "caller_is_webview" in body:
            scope = "webview-only"
        else:
            scope = "all-callers"
    line = text.count(chr(10), 0, text.index(f"{translated[0]}(")) + 1 if translated else None
    return {"translated": translated, "scope": scope, "callers": android_caller_scope(text),
            "source": f"{path.relative_to(westlake_root)}:{line}" if translated else None}


def _evidence(text: str, pattern: str, path: Path, root: Path) -> dict[str, Any]:
    match = re.search(pattern, text)
    if not match:
        return {"present": False, "source": str(path.relative_to(root)) if path.exists() else None}
    return {"present": True, "source": f"{path.relative_to(root)}:{text.count(chr(10), 0, match.start()) + 1}"}


def git_state(root: Path) -> dict[str, Any]:
    """Commit and uncommitted files: a provider model is only as reproducible as its source tree."""
    def run(*args: str) -> str:
        try:
            return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=30).stdout.rstrip("\n")
        except Exception:
            return ""
    dirty = [line[3:] for line in run("status", "--porcelain").splitlines() if line]
    return {"commit": run("rev-parse", "HEAD"), "branch": run("rev-parse", "--abbrev-ref", "HEAD"), "uncommitted": dirty}


# App-side PackageManager call → IPackageManager method the adapter must answer. Same name unless listed.
PM_CLIENT_TO_BINDER = {
    "resolveActivity": "resolveIntent",
    "queryBroadcastReceivers": "queryIntentReceivers",
    "getLaunchIntentForPackage": "queryIntentActivities",
    "getResourcesForApplication": "getApplicationInfo",
    "getApplicationLabel": None,
    "getApplicationIcon": "getApplicationInfo",
    "getPackageArchiveInfo": None,
}


# --------------------------------------------------------------------------------------------
# Provider side: the OpenHarmony sandbox policy an app process runs under
# --------------------------------------------------------------------------------------------

def load_policy_matrix(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


# Native entry points that create an object whose *class* the kernel policy checks separately from
# regular files. Resolving the symbol says nothing about whether the call is allowed.
POLICY_SENSITIVE_IMPORTS = {
    "mkfifo": "fifo_file", "mkfifoat": "fifo_file",
    "mknod": "fifo_file", "mknodat": "fifo_file",
    "symlink": "lnk_file", "symlinkat": "lnk_file",
    "link": "file", "linkat": "file",
}


# --------------------------------------------------------------------------------------------
# External dependencies: services the app expects that are not part of any platform
# --------------------------------------------------------------------------------------------

GMS_MARKERS = {
    "com.google.android.gms.version": "Google Play services client (meta-data)",
}


def external_dependencies(facts: dict[str, Any], method_owners: set[str]) -> list[dict[str, Any]]:
    rows = []
    meta = facts.get("application_meta_data", {})
    if "com.google.android.gms.version" in meta:
        rows.append({"dependency": "Google Play services", "evidence": "application meta-data com.google.android.gms.version",
                     "oh_status": "absent on OpenHarmony (no GMS)"})
    for component in facts.get("components", []):
        registrars = [key.split(":", 1)[1] for key in component["meta_data"] if key.startswith("com.google.firebase.components:")]
        if registrars:
            rows.append({"dependency": "Firebase component discovery", "evidence": f"{component['name']} declares {len(registrars)} registrars",
                         "registrars": registrars, "direct_boot_aware": component["direct_boot_aware"],
                         "oh_status": "Firebase SDK is bundled; backends that need GMS (FCM tokens, Play Integrity) are absent"})
    gms_owners = sorted(o for o in method_owners if o.startswith("Lcom/google/android/gms/"))
    if gms_owners:
        rows.append({"dependency": "GMS client API calls", "evidence": f"{len(gms_owners)} com.google.android.gms classes called",
                     "sample": gms_owners[:10], "oh_status": "calls reach a missing Play services APK"})
    return rows
