"""System-service contract: what an APK asks the platform for by name, and what backs it.

The class/member subtraction cannot see this surface. `JobScheduler` is a present, complete class in
the boot jars, so a scan reports nothing — yet on the OH board `getSystemService("jobscheduler")`
returned null and McDonald's died in WorkManager. A service is three things stacked:

1. the name the app requests (`Context.JOB_SCHEDULER_SERVICE`) or manager class it asks for;
2. the fetcher AOSP registers for that name, and the binder(s) the fetcher pulls from
   ServiceManager underneath;
3. what the Westlake runtime actually answers for that binder or fetcher.

This module extracts (2) from AOSP source and (3) from Westlake source — every fact carries a
`file:line` so the model can be audited and regenerated when either tree moves — and joins them
with (1) from the dex scan into one verdict per requested service.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

# Service name → OpenHarmony subsystem that owns the same capability. Curated: this is the "does an
# OH backend exist to put an Android facade over" question (C4) versus a truthful absence (C5).
OH_ANALOG: dict[str, str] = {
    "activity": "ability_runtime (AMS)",
    "activity_task": "ability_runtime (AMS)",
    "package": "bundle_framework (BMS)",
    "permissionmgr": "access_token",
    "window": "window_manager",
    "display": "display_manager",
    "input_method": "inputmethod_framework",
    "connectivity": "netmanager (NetConnManager)",
    "wifi": "communication/wifi",
    "wifip2p": "communication/wifi (p2p)",
    "bluetooth": "communication/bluetooth",
    "nfc": "communication/nfc",
    "location": "location",
    "jobscheduler": "resourceschedule/work_scheduler",
    "alarm": "time_service / reminder_agent",
    "notification": "notification (ANS)",
    "audio": "audio_framework",
    "media_session": "multimedia/av_session",
    "camera": "multimedia/camera_framework",
    "sensorservice": "sensors",
    "sensor": "sensors",
    "vibrator": "sensors/miscdevice",
    "power": "powermgr",
    "batterymanager": "powermgr/battery_manager",
    "clipboard": "miscservices/pasteboard",
    "wallpaper": "miscservices/wallpaper",
    "download": "miscservices/download_server",
    "print": "print_service",
    "usb": "usb_manager",
    "storage": "filemanagement/storage_service",
    "account": "account/os_account",
    "user": "account/os_account",
    "usagestats": "resourceschedule/device_usage_statistics",
    "keyguard": "theme/screenlock",
    "phone": "telephony/core_service",
    "telephony_subscription_service": "telephony/core_service",
    "carrier_config": "telephony/core_service",
    "uimode": "display / theme",
    "network_management": None,  # type: ignore[dict-item]
    "content_capture": None,  # type: ignore[dict-item]
    "game": None,  # type: ignore[dict-item]
}

# Verdict order: how much of the Android contract a requested service keeps.
SUPPLIED = "supplied"            # a real adapter or local implementation answers
HOLLOW = "hollow"                # something non-null answers, but calls return nothing (C9 at service layer)
NULL = "null"                    # getSystemService returns null / fetcher throws (C4 or C5)
INERT = "inert"                  # manager returned, but its (optional) binder is null: calls NPE or no-op
UNRESOLVED = "unresolved"        # binder fetched through a helper or native service the static read cannot follow
UNREGISTERED = "not-a-platform-service"  # no AOSP fetcher: vendor/OEM/app-private name

# Managers whose fetcher needs nothing from ServiceManager at all.
LOCAL_SERVICES = {"layout_inflater"}

# Managers that reach their binder through a helper class or a native service; curated from AOSP.
HELPER_BINDERS: dict[str, list[dict[str, Any]]] = {
    "phone": [{"name": "phone", "required": False, "via": "TelephonyServiceManager.ServiceRegisterer"}],
    "sensor": [{"name": "sensorservice", "required": False, "via": "native SensorManager (libsensor)"}],
    "vibrator": [{"name": "vibrator_manager", "required": False, "via": "SystemVibrator → VibratorManager"}],
    "download": [{"name": "downloads", "required": False, "via": "ContentResolver authority 'downloads'"}],
}

# Managers that are written to run with a null binder (Android itself runs them that way on some
# devices), so an inert manager costs nothing.
NULL_TOLERANT = {"accessibility", "autofill", "credential", "content_capture", "textclassification"}

_CONST = re.compile(r'public static final String ([A-Z0-9_]+)\s*=\s*"([^"]+)"\s*;')
_REGISTER = re.compile(r"\bregisterService\(\s*([A-Za-z0-9_.\"]+)\s*,\s*([A-Za-z0-9_.]+)\.class")
_INITIALIZER = re.compile(
    r"SystemServiceRegistry\.register(ContextAwareService|StaticService|ForeverStaticService)\(\s*"
    r"([A-Za-z0-9_.\"]+)\s*,\s*([A-Za-z0-9_.]+)\.class\s*,\s*(?:\(([^)]*)\)|([A-Za-z_]\w*))\s*->"
)
_SM_CALL = re.compile(r"ServiceManager\.(getServiceOrThrow|getService|checkService)\(\s*([A-Za-z0-9_.\"]+)\s*\)")
_IMPORT = re.compile(r"^\s*import\s+([a-zA-Z0-9_.]+)\s*;", re.M)
_PACKAGE = re.compile(r"^\s*package\s+([a-zA-Z0-9_.]+)\s*;", re.M)


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _resolve_name(expr: str, constants: dict[str, str]) -> str | None:
    expr = expr.strip()
    if expr.startswith('"') and expr.endswith('"'):
        return expr[1:-1]
    return constants.get(expr.split(".")[-1])


def _class_descriptor(simple: str, text: str) -> str:
    """Resolve a class name as written in a Java file to a dex descriptor via its imports."""
    if simple[0].islower():  # already fully qualified
        return "L" + simple.replace(".", "/") + ";"
    outer, _, nested = simple.partition(".")
    qualified = None
    for imported in _IMPORT.findall(text):
        if imported.rsplit(".", 1)[-1] == outer:
            qualified = imported
            break
    if qualified is None:
        package = _PACKAGE.search(text)
        qualified = (package.group(1) + "." if package else "") + outer
    return "L" + qualified.replace(".", "/") + ("$" + nested.replace(".", "$") if nested else "") + ";"


def context_constants(context_java: Path) -> dict[str, str]:
    return dict(_CONST.findall(context_java.read_text(errors="replace")))


def aosp_service_table(registry_java: Path, context_java: Path, source_roots: Iterable[Path] = ()) -> dict[str, dict[str, Any]]:
    """Service name → manager class and the binder names it needs, from AOSP source.

    Binders come from two places: the fetcher block itself, and — for managers such as
    `NotificationManager`, `AudioManager` or `ClipboardManager` that fetch lazily — the manager
    class source. Missing the second makes a null service look supplied.
    """
    source_roots = list(source_roots)
    constants = context_constants(context_java)
    table: dict[str, dict[str, Any]] = {}

    text = registry_java.read_text(errors="replace")
    matches = list(_REGISTER.finditer(text))
    for index, match in enumerate(matches):
        name = _resolve_name(match.group(1), constants)
        if not name:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.start():end]
        binders = []
        for call, arg in _SM_CALL.findall(block):
            binder = _resolve_name(arg, constants)
            if binder:
                binders.append({"name": binder, "required": call == "getServiceOrThrow"})
        table.setdefault(name, {
            "manager": _class_descriptor(match.group(2), text),
            "binders": binders,
            "source": f"{registry_java.name}:{_line_of(text, match.start())}",
            "registration": "SystemServiceRegistry",
        })

    for root in source_roots:
        for path in sorted(root.rglob("*FrameworkInitializer*.java")):
            if "/test" in str(path):
                continue
            body = path.read_text(errors="replace")
            for match in _INITIALIZER.finditer(body):
                kind, name_expr, cls, params, bare = match.groups()
                params = params if params is not None else bare
                name = _resolve_name(name_expr, constants)
                if not name or name in table:
                    continue
                arity = len([p for p in params.split(",") if p.strip()])
                with_binder = arity == (2 if kind == "ContextAwareService" else 1)
                table[name] = {
                    "manager": _class_descriptor(cls, body),
                    "binders": [{"name": name, "required": True}] if with_binder else [],
                    "source": f"{path.name}:{_line_of(body, match.start())}",
                    "registration": f"{path.stem}.register{kind}",
                }

    sources = _manager_sources(source_roots)
    for name, entry in table.items():
        manager = sources.get(entry["manager"])
        if manager is None or entry["binders"]:
            continue
        body = manager.read_text(errors="replace")
        local = {**constants, **dict(re.findall(r'static final String ([A-Z0-9_]+)\s*=\s*"([^"]+)"', body))}
        for call, arg in _SM_CALL.findall(body):
            binder = _resolve_name(arg, local)
            if binder and binder not in {b["name"] for b in entry["binders"]}:
                entry["binders"].append({"name": binder, "required": call == "getServiceOrThrow", "lazy": True})
    for name, binders in HELPER_BINDERS.items():
        if name in table and not table[name]["binders"]:
            table[name]["binders"] = [dict(b, lazy=True) for b in binders]
    return table


def _manager_sources(roots: list[Path]) -> dict[str, Path]:
    """Descriptor → source file, for every android/ class under the given roots."""
    index: dict[str, Path] = {}
    for root in roots:
        for path in root.rglob("*.java"):
            text = str(path)
            at = text.rfind("/android/")
            if at < 0 or "/test" in text:
                continue
            descriptor = "L" + text[at + 1:-5] + ";"
            index.setdefault(descriptor, path)
    return index


def westlake_service_model(westlake_root: Path) -> dict[str, list[dict[str, Any]]]:
    """Binder/fetcher name → every provision the Westlake source makes for it, with provenance."""
    model: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def add(name: str, kind: str, detail: str, path: Path, text: str, offset: int) -> None:
        rel = path.relative_to(westlake_root)
        model[name].append({"kind": kind, "detail": detail, "source": f"{rel}:{_line_of(text, offset)}"})

    oh_sm = westlake_root / "framework/core/java/OHServiceManager.java"
    text = oh_sm.read_text(errors="replace")
    start = text.find("private static IBinder lookupAdapter")
    body_end = text.find("private static IBinder getAdapterBinder", start)
    pending: list[tuple[str, int]] = []
    for line_match in re.finditer(r"[^\n]*\n", text[start:body_end]):
        line = line_match.group(0)
        offset = start + line_match.start()
        case = re.search(r'case "([^"]+)":', line)
        if case:
            pending.append((case.group(1), offset))
            continue
        if "return" in line and pending:
            stripped = line.strip()
            if stripped == "return null;":
                kind, detail = "explicit-null", "OHServiceManager returns null by design"
            elif "? " in stripped and ": null" in stripped:
                kind, detail = "adapter-conditional", stripped.removeprefix("return ").rstrip(";")
            else:
                adapter = re.search(r'"(adapter\.[A-Za-z0-9_.]+)"|([A-Z][A-Za-z0-9_]*Adapter)', stripped)
                kind = "adapter"
                detail = (adapter.group(1) or adapter.group(2)) if adapter else stripped
            for name, case_offset in pending:
                add(name, kind, detail, oh_sm, text, case_offset)
            pending = []
        elif "default:" in line:
            pending = []

    runtime_cpp = westlake_root / "framework/android-runtime/src/AndroidRuntime.cpp"
    cpp = runtime_cpp.read_text(errors="replace")
    seeds = re.search(r"kServices\[\]\s*=\s*\{([^}]*)\}", cpp)
    if seeds:
        for name in re.findall(r'"([^"]+)"', seeds.group(1)):
            add(name, "hollow-binder", "bare new Binder() seeded into ServiceManager.sCache (§416): every call transacts into nothing",
                runtime_cpp, cpp, seeds.start())
    for match in re.finditer(r"replace §416's bare `new Binder\(\)` for \"([^\"]+)\" with a real local", cpp):
        add(match.group(1), "local-impl", "real local implementation replaces the §416 bare binder", runtime_cpp, cpp, match.start())

    init = westlake_root / "framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java"
    java = init.read_text(errors="replace")
    for match in re.finditer(r'fetcherMap\.put\("([^"]+)"', java):
        add(match.group(1), "local-fetcher", "AppSpawnXInit replaces the SystemServiceRegistry fetcher", init, java, match.start())
    for match in re.finditer(r'(?:cache\.put|put\.invoke\(cache,)\s*\(?\s*"([^"]+)"', java):
        add(match.group(1), "cached-binder", "AppSpawnXInit seeds ServiceManager.sCache with a binder", init, java, match.start())
    audio = java.find("private static void installAudioServiceStub")
    if audio >= 0:
        add("audio", "hollow-proxy", "IAudioService dynamic proxy returning type defaults for every method", init, java, audio)
    job = java.find("newNoopJobSchedulerBinder")
    if job >= 0 and "RESULT_SUCCESS" in java[job:job + 4000]:
        add("jobscheduler", "hollow-proxy", "no-op IJobScheduler: schedule()/enqueue() return RESULT_SUCCESS, jobs never run", init, java, job)
    return dict(model)


_RANK = {"local-impl": 6, "adapter": 5, "cached-binder": 4, "adapter-conditional": 3,
         "local-fetcher": 2, "hollow-proxy": 1, "hollow-binder": 1, "explicit-null": 0}


def provision_verdict(provisions: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    """Collapse all provisions for one binder name into what the app actually gets."""
    if not provisions:
        return NULL, None
    hollow = [p for p in provisions if p["kind"] in {"hollow-proxy", "hollow-binder"}]
    strongest = max(provisions, key=lambda p: _RANK.get(p["kind"], 0))
    # A hollow proxy installed as the fetcher overrides whatever binder sits underneath it.
    if any(p["kind"] == "hollow-proxy" for p in provisions):
        return HOLLOW, next(p for p in provisions if p["kind"] == "hollow-proxy")
    if strongest["kind"] in {"local-impl", "adapter", "cached-binder", "adapter-conditional", "local-fetcher"}:
        return SUPPLIED, strongest
    if hollow:
        return HOLLOW, hollow[0]
    return NULL, strongest


def service_map(
    requests: list[dict[str, Any]],
    aosp: dict[str, dict[str, Any]],
    westlake: dict[str, list[dict[str, Any]]],
    manager_calls: dict[str, set[str]] | None = None,
) -> list[dict[str, Any]]:
    """Join the APK's service requests with the AOSP contract and the Westlake provision."""
    by_class = {entry["manager"]: name for name, entry in aosp.items()}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for request in requests:
        name = request.get("service") or by_class.get(request.get("manager_class", ""))
        if name:
            grouped[name].append(request)

    rows = []
    for name, sites in sorted(grouped.items()):
        contract = aosp.get(name)
        if contract is None:
            rows.append({"service": name, "verdict": UNREGISTERED, "sites": sites[:5], "site_count": len(sites),
                         "note": "no AOSP fetcher for this name; getSystemService returns null on Android too"})
            continue
        # The app gets the fetcher's result. A Westlake fetcher override decides alone; otherwise
        # the fetcher needs each required binder underneath.
        own = westlake.get(name, [])
        auxiliary: list[str] = []
        if any(p["kind"] in {"local-fetcher", "hollow-proxy"} for p in own):
            verdict, basis = provision_verdict(own)
        elif own and not contract["binders"]:
            verdict, basis = provision_verdict(own)
        elif contract["binders"]:
            verdict, basis = SUPPLIED, None
            # A manager that lazily reaches several services is decided by its own binder; the
            # others only affect the methods that use them.
            primary = [b for b in contract["binders"] if not b.get("lazy") or b["name"] == name]
            deciding = primary if any(b["name"] == name for b in primary) else contract["binders"]
            auxiliary = [b["name"] for b in contract["binders"] if b not in deciding]
            for binder in deciding:
                binder_verdict, binder_basis = provision_verdict(westlake.get(binder["name"], []))
                if binder_verdict == NULL and not binder["required"]:
                    binder_verdict = INERT
                    binder_basis = {"kind": "absent", "source": None,
                                    "detail": f"optional binder '{binder['name']}' has no Westlake provision"
                                              + (f" (reached via {binder['via']})" if binder.get("via") else "")}
                if _order(binder_verdict) < _order(verdict):
                    verdict, basis = binder_verdict, binder_basis
        elif name in LOCAL_SERVICES:
            verdict, basis = SUPPLIED, {"kind": "local", "detail": "fetcher needs no system binder",
                                        "source": contract["source"]}
        else:
            verdict, basis = UNRESOLVED, {"kind": "unresolved", "source": contract["source"],
                                          "detail": "no binder found in fetcher or manager source; reached through a helper"}
        analog = OH_ANALOG.get(name, "unmapped")
        calls = sorted((manager_calls or {}).get(contract["manager"], set()))
        rows.append({
            "service": name,
            "manager": contract["manager"],
            "binders": contract["binders"],
            "aosp_source": contract["source"],
            "verdict": verdict,
            "westlake_basis": basis,
            "oh_analog": analog,
            "shim_class": _shim_class(verdict, analog),
            "manager_methods_called": calls,
            "auxiliary_binders": auxiliary,
            "sites": sites[:5],
            "site_count": len(sites),
        })
    return rows


def _order(verdict: str) -> int:
    return {NULL: 0, INERT: 1, HOLLOW: 2, UNRESOLVED: 3, SUPPLIED: 4}.get(verdict, 4)


def _shim_class(verdict: str, analog: str | None) -> str:
    if verdict == SUPPLIED:
        return "C0"
    if verdict == HOLLOW:
        return "C9"
    if verdict == UNRESOLVED:
        return "CU"
    return "C4" if analog and analog != "unmapped" else "C5"
