"""One gap map per APK: every surface where it touches the platform, what backs it on OpenHarmony
under Westlake, the shim each gap needs, and what that shim costs.

Inputs are all produced without launching the app:

- the dex/ELF scan (`scan`), which now also records service requests and platform calls;
- manifest facts (`contracts.manifest_facts`);
- provider models extracted from Westlake source (`services`, `contracts.pm_adapter_model`);
- the OH board's exported symbols (`oh-import-resolution.json`) and kernel policy
  (`data/oh-app-data-policy.json`).

Each row carries its evidence and a confidence level, so "supplied" never hides "we only read the
source". Probe results measured on the board replace a row's static verdict, for the exact provider
commit they were measured on. A `known-blockers` file turns the map into a backtest: for every
failure already paid for on the device, did a row predict it?
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from . import contracts, ohresolve, services

CATEGORIES = [
    ("java-api", "Java framework API", "APK dex references − Westlake boot jars, filtered by API level"),
    ("system-services", "System services", "getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem"),
    ("security", "Keystore & crypto providers",
     "JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS"),
    ("package-manager", "Package manager & manifest", "manifest features and PackageManager calls → Westlake PM semantics"),
    ("app-framework", "Activity, window & process contracts",
     "what system_server would answer, answered in-process by Westlake in direct launch → white-box probes"),
    ("native-upcalls", "Java APIs called from native code", "JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars"),
    ("native-symbols", "Native platform symbols", "packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)"),
    ("native-loading", "Native loading & packaging", "how the libraries are packaged → what the OH linker can map"),
    ("sandbox-policy", "Process sandbox & policy", "objects the code creates → what OH SELinux lets an app create"),
    ("external-deps", "External services & SDK behaviour", "SDKs that expect Google services or probe the device"),
]

EFFORT = {
    "none": "nothing to build",
    "XS": "hours: configuration, labelling, or forwarding one symbol",
    "S": "about a day: a truthful local answer, a missing export, or a handful of methods",
    "M": "days: an Android facade over an existing OH capability, for the methods this app calls",
    "L": "weeks: port or build a subsystem or bridge",
    "OH": "needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake",
    "verify": "implemented according to source; run the conformance probe before trusting it",
}
_EFFORT_ORDER = ["none", "verify", "XS", "S", "M", "L", "OH"]

# Confidence ladder for a row's provider verdict.
STATIC = "static"                  # read from APK + provider source only
PROBED = "probe"                   # a conformance probe exercised the contract on the device
OBSERVED = "observed-on-device"    # the full app hit it on the device

# Java package → (area, OH subsystem that owns it; None = pure library code inside Westlake).
_AREAS = [
    ("android/net/wifi", "WiFi", "communication/wifi"),
    ("android/net/nsd", "Network service discovery (mDNS)", "netmanager/mdns"),
    ("android/net/http", "Legacy HTTP", None),
    ("android/net", "Networking", "netmanager"),
    ("android/bluetooth", "Bluetooth", "communication/bluetooth"),
    ("android/provider/MediaStore", "Media store", "multimedia/media_library"),
    ("android/media", "Media", "multimedia"),
    ("android/hardware/camera2", "Camera", "multimedia/camera_framework"),
    ("android/hardware/biometrics", "Biometrics", "useriam"),
    ("android/hardware", "Hardware", "drivers / sensors"),
    ("android/location", "Location", "location"),
    ("android/telephony", "Telephony", "telephony"),
    ("android/webkit", "WebView", "web (ArkWeb) or bundled Chromium"),
    ("android/adservices", "Privacy Sandbox", None),
    ("android/content/pm", "Package manager", "bundle_framework"),
    ("android/app/job", "Job scheduling", "resourceschedule/work_scheduler"),
    ("android/app", "App framework", "ability_runtime"),
    ("android/security", "Keystore & security", "security"),
    ("android/view", "Views & windows", "window_manager / render_service"),
    ("android/graphics", "Graphics", "render_service / graphic_2d"),
    ("android/widget", "Widgets", None),
    ("android/os", "OS services", "various system abilities"),
    ("android/provider", "Providers & settings", "various"),
    ("android/content", "Content & intents", "ability_runtime"),
    ("android/text", "Text", None),
    ("android/util", "Utilities", None),
    ("java/", "Java library", None),
    ("javax/", "Java extensions", None),
    ("android/", "Other Android", "unmapped"),
]


def _area(owner: str) -> tuple[str, str | None]:
    path = owner.lstrip("L")
    for prefix, area, oh in _AREAS:
        if path.startswith(prefix):
            return area, oh
    return "Other", "unmapped"


def _row(category: str, row_id: str, item: str, **fields: Any) -> dict[str, Any]:
    return {"category": category, "id": row_id, "item": item, **fields}


def _size_effort(count: int, small: str = "S", medium: str = "M", large: str = "L") -> str:
    return small if count <= 3 else medium if count <= 15 else large


# --------------------------------------------------------------------------------------------
# Category builders
# --------------------------------------------------------------------------------------------

def java_api_rows(scan: dict[str, Any], api_levels: dict[tuple, str]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Group missing, hollow and probed framework members by the subsystem that owns them."""
    groups: dict[str, dict[str, Any]] = {}
    excluded: Counter[str] = Counter()
    for finding in scan["findings"]:
        kind = finding["kind"]
        if kind not in {"missing_class", "missing_method", "missing_field", "hollow_method", "existence_probe"}:
            continue
        dep = finding["dependency"]
        key = (kind, dep["owner"], dep.get("name"), dep.get("signature"))
        level = api_levels.get(key)
        if level in {"absent-from-platform", "newer-than-reference"}:
            excluded[level] += 1
            continue
        area, oh = _area(dep["owner"])
        group = groups.setdefault(area, {"oh": oh, "missing": [], "hollow": [], "probe": []})
        member = dep["owner"].strip("L;").replace("/", ".") + (f".{dep['name']}" if dep.get("name") else "")
        bucket = "hollow" if kind == "hollow_method" else "probe" if kind == "existence_probe" else "missing"
        group[bucket].append(member)
        group.setdefault("keys", []).append({"kind": kind, "owner": dep["owner"], "name": dep.get("name"),
                                             "signature": dep.get("signature")})

    rows = []
    for area, group in sorted(groups.items(), key=lambda kv: -len(kv[1]["missing"]) * 3 - len(kv[1]["hollow"])):
        missing, hollow, probe = group["missing"], group["hollow"], group["probe"]
        oh = group["oh"]
        mapped = bool(oh) and oh != "unmapped"
        if missing:
            verdict, shim = "missing", "C4" if mapped else "C1/C5"
            effort = _size_effort(len(missing), "S", "M", "L") if mapped else "S"
        elif hollow:
            verdict, shim, effort = "hollow-candidate", "C9", "verify"
        else:
            verdict, shim, effort = "probe-only", "C8", "verify"
        rows.append(_row(
            "java-api", f"java:{area}", area,
            oh_touchpoint=oh or "none (library code inside Westlake)",
            verdict=verdict, shim_class=shim, effort=effort, confidence=STATIC,
            counts={"missing": len(missing), "hollow": len(hollow), "probe": len(probe)},
            members=group.get("keys", []),
            examples=sorted(set(missing))[:6] or sorted(set(hollow))[:6] or sorted(set(probe))[:6],
            shim=("implement the members over " + oh) if missing and mapped else
                 ("port from AOSP, or confirm the caller tolerates absence" if missing else
                  "check each hollow body against AOSP" if hollow else
                  "confirm the probed class should (not) exist on this platform"),
        ))
    return rows, dict(excluded)


def service_rows(scan: dict[str, Any], aosp: dict[str, Any], westlake: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    inventory = scan["inventory"]
    requests = inventory.get("service_requests", [])
    calls = {owner: set(names) for owner, names in inventory.get("platform_method_names", {}).items()}
    casts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cast in inventory.get("nonnull_casts") or []:
        casts["L" + cast["type"].replace(".", "/") + ";"].append(cast)
    rows = []
    for entry in services.service_map(requests, aosp, westlake, calls):
        verdict = entry["verdict"]
        methods = entry.get("manager_methods_called", [])
        analog = entry.get("oh_analog")
        if verdict == services.SUPPLIED:
            effort, shim = "verify", "none"
        elif verdict == services.UNRESOLVED:
            effort, shim = "verify", "trace the helper's binder; then treat as null, inert or supplied"
        elif verdict == services.INERT and entry["service"] in services.NULL_TOLERANT:
            effort, shim = "none", "none: the manager is written to run without its service"
        elif verdict == services.STRICT:
            effort = "S"
            shim = ("answer the methods callers use with Android's value for this device; a throw is never "
                    "Android's answer (inside a JNI callback, WebView aborts on it)")
        elif verdict == services.HOLLOW:
            effort = _size_effort(len(methods), "S", "M", "M")
            shim = f"replace the hollow binder with an implementation over {analog}" if analog and analog != "unmapped" \
                else "give the hollow binder truthful answers"
        elif verdict in {services.NULL, services.INERT}:
            effort = _size_effort(len(methods), "S", "M", "L") if analog and analog != "unmapped" else "S"
            shim = f"Android {entry.get('manager', '').split('/')[-1].rstrip(';')} facade over {analog}" \
                if analog and analog != "unmapped" else "truthful local manager (feature absent)"
        else:
            effort, shim = "none", "none (null on Android too)"
        basis = entry.get("westlake_basis") or {}
        # A null manager is survivable only where the caller checks. Kotlin's `as Manager` does
        # not: it throws, and inside a JS host function that is a JS exception.
        throwing = casts.get(entry.get("manager", ""), []) if verdict in {services.NULL, services.UNRESOLVED} else []
        evidence = None
        if throwing:
            owners = sorted({f"{c['owner'].strip('L;').replace('/', '.')}.{c['method']}" for c in throwing})
            evidence = (f"{entry['site_count']} call sites; Kotlin casts it non-null in {len(owners)} methods "
                        f"(e.g. {', '.join(owners[:3])}): a null answer throws there, it is not skipped")
        rows.append(_row(
            "system-services", f"svc:{entry['service']}", entry["service"],
            oh_touchpoint=analog or "none",
            verdict=verdict, shim_class=entry.get("shim_class", "C5"), effort=effort, confidence=STATIC,
            provider=basis.get("detail") or ("no Westlake provision: getSystemService returns null" if verdict == services.NULL else ""),
            provider_source=basis.get("source"),
            aosp_contract=f"{entry.get('manager')} needs binder(s) {[b['name'] for b in entry.get('binders', [])]} ({entry.get('aosp_source')})"
                if entry.get("manager") else None,
            app_calls=methods[:12], call_sites=entry["site_count"],
            example_site=_site(entry["sites"][0]) if entry.get("sites") else None,
            shim=shim, app_evidence=evidence, throws_if_null=len(throwing),
        ))
    dynamic = sum(1 for r in requests if r.get("dynamic"))
    return rows, dynamic


def _site(site: dict[str, Any]) -> str:
    return f"{site['owner'].strip('L;').replace('/', '.')}.{site['method']}"


def package_manager_rows(scan: dict[str, Any], facts: dict[str, Any], pm: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    calls = scan["inventory"].get("platform_method_names", {}).get("Landroid/content/pm/PackageManager;", [])
    methods = pm["methods"]
    semantics = pm["semantics"]

    # Contract rules: triggered by the APK, checked against Westlake source.
    discovery = [c for c in facts["components"] if c["meta_data"]]
    lookups = {"getServiceInfo", "getActivityInfo", "getReceiverInfo", "getProviderInfo", "getApplicationInfo", "getPackageInfo"} & set(calls)
    if discovery and lookups:
        check = semantics["direct_boot_match_defaults"]
        dba = [c["name"] for c in discovery if c["direct_boot_aware"]]
        rows.append(_row(
            "package-manager", "pm:component-metadata", "Component lookups return manifest <meta-data>",
            oh_touchpoint="none (answered from the APK inside Westlake)",
            verdict="supplied" if check["present"] else "missing",
            shim_class="C0" if check["present"] else "C6",
            effort="verify" if check["present"] else "S",
            confidence=STATIC, probe="probes/service-metadata",
            provider=("PMS-side direct-boot match defaults applied before PackageParser.isMatch" if check["present"]
                      else "caller flags reach PackageParser.isMatch without MATCH_DIRECT_BOOT_*: every component filtered out"),
            provider_source=check["source"],
            app_evidence=f"{len(discovery)} components carry meta-data ({len(dba)} directBootAware, e.g. "
                         f"{', '.join(n.split('.')[-1] for n in dba[:3])}); app calls {sorted(lookups)}",
            shim="apply updateFlagsForComponent semantics in the source-app PM path",
        ))
    if facts["splits"]:
        check = semantics["split_paths_populated"]
        rows.append(_row(
            "package-manager", "pm:splits", f"Split APKs visible to resources and class loading ({len(facts['splits'])} splits)",
            oh_touchpoint="none (Westlake PM + asset manager)",
            verdict="supplied" if check["present"] else "missing", shim_class="C0" if check["present"] else "C6",
            effort="verify" if check["present"] else "S", confidence=STATIC, probe="none yet (propose: split-resources)",
            provider="ApplicationInfo.splitSourceDirs populated" if check["present"] else "splitSourceDirs left empty",
            provider_source=check["source"], app_evidence=", ".join(facts["splits"]),
            shim="populate splitNames/splitSourceDirs from the installed split set",
        ))
    providers = [c for c in facts["components"] if c["kind"] == "provider" and not c["process"]]
    if providers:
        rows.append(_row(
            "package-manager", "pm:providers", f"Content providers installed at bind ({len(providers)}, initOrder honoured)",
            oh_touchpoint="none", verdict="unverified", shim_class="CU", effort="verify", confidence=STATIC,
            probe="probes/provider-manifest",
            app_evidence=", ".join(f"{c['name'].split('.')[-1]}{'@' + c['init_order'] if c['init_order'] else ''}" for c in providers),
            shim="install every main-process provider in initOrder before Application.onCreate",
        ))
    if facts["processes"]:
        rows.append(_row(
            "package-manager", "pm:multiprocess", f"Components in secondary processes: {', '.join(facts['processes'])}",
            oh_touchpoint="appspawn (second process)", verdict="missing", shim_class="C4", effort="L", confidence=STATIC,
            shim="spawn and route secondary Android processes",
        ))

    # PackageManager methods the app calls, against the adapter.
    stubbed = []
    for name in calls:
        binder = contracts.PM_CLIENT_TO_BINDER.get(name, name)
        if binder is None:
            continue
        status = methods.get(binder)
        if status and status["status"] == "stub":
            stubbed.append((name, binder, status))
    for name, binder, status in stubbed:
        deep = binder.startswith(("query", "resolve"))
        rows.append(_row(
            "package-manager", f"pm:call:{name}", f"PackageManager.{name}",
            oh_touchpoint="bundle_framework (for other packages)" if name in {"getInstallerPackageName", "getPackagesForUid", "getInstalledPackages"} else "none",
            verdict="stub", shim_class="C9", effort="M" if deep else "S", confidence=STATIC,
            provider=f"IPackageManager.{binder} {status['detail']}", provider_source=status["source"],
            shim=("resolve against the APK's intent filters" if deep else "answer from the APK/package state"),
        ))
    return rows


def ndk_symbol_rows(
    scan: dict[str, Any], oh_missing: list[dict[str, Any]], shim_exports: set[str], ndk_cov: dict[str, Any]
) -> list[dict[str, Any]]:
    """Native gaps classified by how the NDK supplies them: package, libc-abi, weld, absence.

    The provider is OpenHarmony plus the NDK Westlake packages, not the raw board: a missing
    `AAsset_open` is "compile asset_manager.cpp", a missing `ASensor_getName` is "weld to OH
    sensors", and a missing `__sF` is "translate in the bionic shim". Symbols outside the public
    NDK altogether (`__sF`, `_ctype_`) are bionic-private and belong to the libc-abi group.
    """
    from . import ndk as ndk_model

    model = ndk_model.load_model()
    by_symbol = {item["symbol"]: item for item in ndk_cov["symbols"]}
    importers: dict[str, list[str]] = defaultdict(list)
    for elf in ohresolve.target_elfs(scan):
        for symbol in elf.get("undefined_symbols", []):
            importers[symbol].append(elf.get("soname") or elf["name"])

    # Libraries an importer needs that are neither packaged nor NDK: a symbol whose every importer
    # needs one (JavaScriptCore's JS* for React Native's libjsctooling.so needing libjsc.so) comes
    # from that library, not from libc.
    packaged = {elf.get("soname") or elf["name"] for elf in ohresolve.target_elfs(scan)}
    ndk_libraries = set(model.get("libraries", []))
    unshipped: dict[str, set[str]] = {}
    for elf in ohresolve.target_elfs(scan):
        absent = {n for n in elf.get("needed", []) if n not in packaged and n not in ndk_libraries}
        if absent:
            unshipped[elf.get("soname") or elf["name"]] = absent

    groups: dict[tuple[str, str | None], list[dict[str, Any]]] = defaultdict(list)
    for item in oh_missing:
        symbol = item["symbol"]
        known = by_symbol.get(symbol)
        users = item.get("importing_libraries") or importers.get(symbol, [])
        wanted = set.intersection(*(unshipped.get(u, set()) for u in users)) if users else set()
        if known is None and wanted:
            how = {"group": "unshipped-library", "weld": ", ".join(sorted(wanted)), "oh": None, "source": None,
                   "in_ndk": False}
        elif known is None:
            how = {"group": "libc-abi", "weld": None, "oh": None, "source": None, "in_ndk": False}
        elif known["status"] != "missing":
            how = {"group": "now-provided", "weld": None, "oh": None, "source": None, "in_ndk": True,
                   "providers": known.get("providers", [])}
        else:
            how = {**{k: known.get(k) for k in ("group", "weld", "oh", "source")}, "in_ndk": True,
                   "manifests": known.get("westlake_manifests", [])}
        groups[(how["group"], how["weld"])].append({"symbol": symbol, **how})

    rows = []
    for (group, weld), items in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        names = [i["symbol"] for i in items]
        libs = sorted({lib for n in names for lib in importers.get(n, [])})
        fields: dict[str, Any] = {"importing_libraries": libs[:12], "confidence": STATIC}
        if group == "unshipped-library":
            fields.update(
                item=f"Library the APK needs but does not ship ({weld}): {len(names)} symbols",
                oh_touchpoint="none: neither Android's NDK nor OH provides it", verdict="missing",
                shim_class="CU", effort="verify",
                provider=f"{', '.join(libs)} list {weld} in DT_NEEDED; the APK does not package it",
                open_symbols=names[:20],
                shim="a blocker only if an importer is loaded: on Android too its load fails without the library; "
                     "check which code path loads it")
        elif group == "libc-abi":
            covered = [n for n in names if n in shim_exports]
            open_ = [n for n in names if n not in shim_exports]
            fields.update(
                item=f"bionic libc ABI: {len(names)} symbols to translate onto musl",
                oh_touchpoint="OH musl libc", verdict="supplied" if not open_ else "missing",
                shim_class="C0" if not open_ else "C1/C2", effort="none" if not open_ else "S",
                provider=f"{len(covered)} of {len(names)} exported by the Westlake bionic shim",
                open_symbols=open_[:20], covered_symbols=covered,
                shim="bionic-ABI shim: forward or translate; never ship a second libc")
        elif group == "package":
            built = [i for i in items if i.get("manifests")]
            manifests = sorted({m for i in built for m in i["manifests"]})
            all_built = len(built) == len(items)
            fields.update(
                item=f"NDK package: {len(names)} symbols compiled from AOSP source",
                oh_touchpoint="none beyond what Westlake already provides", verdict="missing", shim_class="C1",
                effort="XS" if all_built else "S",
                provider=(f"built by Westlake ({', '.join(manifests)}) but not deployed on the measured board" if all_built else
                          f"{len(built)} of {len(names)} have a Westlake build manifest"),
                open_symbols=names[:20],
                shim="compile the AOSP source (" + ", ".join(sorted({i['source'].rsplit('/', 1)[-1] for i in items if i.get('source')})) + ") and deploy it")
        elif group == "weld":
            info = model["welds"].get(weld, {})
            fields.update(
                item=f"NDK weld · {weld}: {len(names)} symbols", oh_touchpoint=info.get("oh", ""),
                verdict="missing", shim_class="C4", effort=info.get("effort", "M"),
                provider="no Westlake provision on the measured board", open_symbols=names[:20],
                shim=f"AOSP NDK source above, {info.get('oh', 'an OH subsystem')} below")
        elif group == "now-provided":
            fields.update(
                item=f"{len(names)} symbols provided since the import resolution was taken",
                oh_touchpoint="", verdict="supplied", shim_class="C0", effort="none",
                provider="exported on the board measured by ndk-coverage", covered_symbols=names[:20], shim="none")
        else:
            fields.update(
                item=f"NDK {group}: {len(names)} symbols", oh_touchpoint="", verdict="absent", shim_class="C5",
                effort="XS", provider=model["groups"].get(group, ""), open_symbols=names[:20],
                shim="export entry points that report the feature unavailable")
        rows.append(_row("native-symbols", f"ndk:{group}" + (f":{weld}" if weld else ""), fields.pop("item"), **fields))
    return rows


# ActivityManager process-table queries -> the IActivityManager method behind each. Since Android
# 5.1 an ordinary app sees only its own processes and services, so each has a local answer; null is
# never one of them, and SDKs iterate the result unchecked.
AM_PROCESS_TABLE = {"getRunningAppProcesses": "getRunningAppProcesses", "getRunningServices": "getServices",
                    "getProcessMemoryInfo": "getProcessMemoryInfo"}


def app_framework_rows(scan: dict[str, Any], am: dict[str, Any], wm: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rows = []
    names = scan["inventory"].get("platform_method_names", {})
    called = [name for name in AM_PROCESS_TABLE if name in names.get("Landroid/app/ActivityManager;", [])]
    if called:
        unanswered = [n for n in called if am["proxy_stub"] and AM_PROCESS_TABLE[n] not in am["answered"]]
        rows.append(_row(
            "app-framework", "am:process-table", f"ActivityManager process-table queries ({', '.join(called)})",
            oh_touchpoint="none (the caller's own process is the answer)",
            verdict="null" if unanswered else "supplied", shim_class="C9" if unanswered else "C0",
            effort="S" if unanswered else "verify", confidence=STATIC, probe="probes/running-app-processes",
            provider=(f"direct-launch IActivityManager proxy returns null for {', '.join(AM_PROCESS_TABLE[n] for n in unanswered)}"
                      if unanswered else "answered with the caller's own process"),
            provider_source=am["source"], app_evidence=f"app calls {', '.join(called)}",
            shim="answer with the caller's process: name, pid, uid, foreground importance, its package"))
    if "show" in names.get("Landroid/app/Dialog;", []):
        wm = wm or {}
        stacking = wm.get("dialogs_above_base", {})
        rows.append(_row(
            "app-framework", "wm:dialog-stacking", "Dialogs stack above their activity's window, whatever the add order",
            oh_touchpoint="window_manager (sub-window z-order: creation order)",
            verdict="supplied" if stacking.get("present") else "unverified",
            shim_class="C0" if stacking.get("present") else "CU", effort="verify",
            confidence=STATIC, probe="probes/dialog-before-window",
            provider=("a dialog's OH session is held back until its activity's window has one, so creation order is "
                      "Android's stacking order" if stacking.get("present")
                      else "Android WindowToken order: TYPE_BASE_APPLICATION below the token's other windows"),
            provider_source=stacking.get("source"),
            app_evidence="app shows dialogs (Dialog.show referenced); a dialog shown from onCreate/onResume is added "
                         "before the activity's own window",
            shim="stack a base application window below the dialogs already attached to its token"))
        for rid, key, item, shim, effort in (
                ("wm:window-placement", "placement_from_gravity", "Windows placed by LayoutParams gravity and x/y (dialogs centred)",
                 "compute the frame from gravity/x/y against the display, as WindowLayout.computeFrames does", "S"),
                ("wm:dim-behind", "dim_behind", "FLAG_DIM_BEHIND dims what is under a dialog",
                 "draw a dim layer of dimAmount under the window (OH has no dim flag)", "M")):
            check = wm.get(key, {})
            rows.append(_row(
                "app-framework", rid, item, oh_touchpoint="window_manager (session rect)" if key == "placement_from_gravity"
                else "render_service (a layer under the window)",
                verdict="supplied" if check.get("present") else "missing",
                shim_class="C0" if check.get("present") else "C6", effort="verify" if check.get("present") else effort,
                confidence=STATIC, probe="probes/dialog-before-window",
                provider="applied in the window adapter" if check.get("present")
                else "every window is laid out at (0,0) with no dim layer" if key == "placement_from_gravity"
                else "no dim layer is drawn",
                provider_source=check.get("source"),
                app_evidence="app shows dialogs (Dialog.show referenced)", shim=shim))
    return rows


def webview_process_model(aosp_root: Path | None, westlake_root: Path) -> dict[str, Any]:
    """Whether WebView will insist on its sandboxed renderer process, and whether anything hosts it.

    WebView runs its renderer in an isolated service process when WebViewDelegate says multiprocess.
    Since the update-service flags that answer is `true` whatever IWebViewUpdateService says, so a
    runtime answering false there does not get single-process WebView.
    """
    forced = {"present": False, "source": None}
    if aosp_root is not None:
        path = aosp_root / "frameworks-base/core/java/android/webkit/WebViewDelegate.java"
        if path.exists():
            text = path.read_text(errors="replace")
            body = re.search(r"public boolean isMultiProcessEnabled\(\)\s*\{(.*?)\n    \}", text, re.S)
            flag = re.search(r"if \((Flags\.\w+\(\))\)\s*\{\s*return true;", body.group(1)) if body else None
            if flag:
                forced = {"present": True, "flag": flag.group(1),
                          "source": f"frameworks-base/core/java/android/webkit/WebViewDelegate.java:{text.count(chr(10), 0, body.start()) + 1}"}
    hosted = {"present": False, "source": None}
    framework = westlake_root / "framework"
    for path in sorted(framework.rglob("*.java")) if framework.exists() else []:
        text = path.read_text(errors="replace")
        match = re.search(r"SandboxedProcessService", text)
        if match:
            hosted = {"present": True, "source": f"{path.relative_to(westlake_root)}:{text.count(chr(10), 0, match.start()) + 1}"}
            break
    return {"multiprocess_forced": forced, "renderer_hosted": hosted}


def native_load_short_circuit(art_build_root: Path | None) -> dict[str, Any]:
    """Library names the runtime's Runtime.nativeLoad answers without opening anything.

    The stub returns "already registered" -- a null error, which is success -- for a path matching
    any of these, on the assumption that those natives are linked into the runtime itself. When
    that assumption is wrong the caller is told the library loaded, JNI_OnLoad never runs, and the
    methods stay unbound with nothing in the log to say so. Read from the stub rather than listed
    here, because the only honest version of this row is the one the deployed runtime implements.
    """
    empty: dict[str, Any] = {"names": [], "source": None}
    if art_build_root is None:
        return empty
    path = art_build_root / "stubs/openjdk_stub.c"
    if not path.exists():
        return empty
    text = path.read_text(errors="replace")
    body = re.search(r"Runtime_nativeLoad\(JNIEnv\* env.*?\n\}", text, re.S)
    if not body:
        return empty
    accepted = re.search(r"if \(((?:strstr\(path, \"[\w-]+\"\)\s*\|\|\s*)*strstr\(path, \"[\w-]+\"\))\)\s*\{"
                         r"[^{}]*?return NULL;", body.group(0), re.S)
    if not accepted:
        return empty
    return {"names": sorted(set(re.findall(r"strstr\(path, \"([\w-]+)\"\)", accepted.group(1)))),
            "source": f"art-build/stubs/openjdk_stub.c:{text.count(chr(10), 0, body.start()) + 1}"}


def _matches(names: list[str], libraries: list[str]) -> dict[str, list[str]]:
    hit: dict[str, list[str]] = defaultdict(list)
    for library in libraries:
        for name in names:
            if name in library:
                hit[name].append(library)
    return hit


def silent_load_rows(scan: dict[str, Any], model: dict[str, Any],
                     runtime_libraries: list[str] | None = None) -> list[dict[str, Any]]:
    """Libraries whose load the runtime answers without opening them.

    Two sides, because the fix differs. An app that packages such a name loses its own natives.
    The runtime shipping such a name is worse: the library exists precisely to supply something,
    and the one component that would load it refuses to, while reporting success. That is the case
    that cost three build cycles on 2026-09-22 (libjavacore.so, java.lang.Math.rint), so it is
    checked even though it is a property of the provider rather than of the app.
    """
    names = model.get("names") or []
    if not names:
        return []
    shim = ("ship the library under a name none of those substrings match, or narrow the stub to the "
            "libraries the runtime really does link in. A load that reports success it did not perform "
            "cannot be told from one that worked, so nothing downstream can detect this.")
    rows = []
    app = _matches(names, [elf.get("soname") or Path(elf["name"]).name
                           for elf in ohresolve.target_elfs(scan)])
    if app:
        libraries = sorted({library for found in app.values() for library in found})
        rows.append(_row(
            "native-loading", "load:silent-success",
            f"Packaged libraries the runtime accepts without opening ({', '.join(libraries)})",
            oh_touchpoint="Runtime.nativeLoad in the runtime's own OpenJDK stub",
            verdict="hollow", shim_class="C3", effort="S", confidence=STATIC,
            provider="the load returns success without a dlopen, so JNI_OnLoad never runs and the "
                     f"library's natives stay unbound; matched on {', '.join(sorted(app))}",
            provider_source=model["source"],
            app_evidence=(f"{len(libraries)} packaged library matches the filter" if len(libraries) == 1
                          else f"{len(libraries)} packaged libraries match the filter"),
            shim=shim,
        ))
    runtime = _matches(names, sorted(set(runtime_libraries or [])))
    if runtime:
        libraries = sorted({library for found in runtime.values() for library in found})
        rows.append(_row(
            "native-loading", "load:runtime-silent-success",
            f"Runtime libraries its own loader will not open ({', '.join(libraries)})",
            oh_touchpoint="Runtime.nativeLoad in the runtime's own OpenJDK stub",
            # Not "hollow": the filter exists because the runtime registers these natives itself, from
            # its own stubs, and mostly it does. What cannot be seen from here is whether it registers
            # all of them. On 2026-09-22 the Math table was missing exactly one method, rint, and the
            # staged library that would have supplied it could not be loaded to say so.
            verdict="unresolved", shim_class="C3", effort="verify", confidence=STATIC,
            provider="the runtime stages these and then answers 'already registered' for them; their natives "
                     "are bound only where one of its built-in stubs registers them, which is per-method and "
                     f"not decidable from here; matched on {', '.join(sorted(runtime))}",
            provider_source=model["source"],
            app_evidence="a property of the runtime, not of this app: it holds for every app it launches",
            shim="compare the staged library's methods against the tables the runtime's own stubs register "
                 "(art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter "
                 "does not match. " + shim,
        ))
    return rows


def runtime_resolved_rows(scan: dict[str, Any], ndk_cov: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Platform entry points an app reaches by name at runtime, which the provider does not supply.

    A dlopen/dlsym pair declares nothing: the name is a string, so the library never records that
    it needs the function and the ordinary undefined-symbol check cannot see it. An engine looking
    up fourteen NDK SurfaceControl entry points still scanned as 288 of 289 resolved.

    Two things make this worth a row of its own rather than a footnote on the symbol rows. The
    failure is silent -- dlsym returns null and the caller carries on without the capability, so
    nothing is logged unless the caller chooses to. And the verdict here is weaker than a missing
    import: a name of the right shape may never be passed to dlsym at all. Only names in the
    public NDK surface are reported, which takes an engine from four thousand candidate strings to
    under a hundred real entry points, and even those stay `unresolved` until an on-device probe
    performs the lookup.
    """
    if not ndk_cov:
        return []
    surface = {entry["symbol"]: entry for entry in ndk_cov.get("symbols", [])}
    if not surface:
        return []
    by_library: dict[str, set[str]] = defaultdict(set)
    importers: dict[str, set[str]] = defaultdict(set)
    for elf in ohresolve.target_elfs(scan):
        name = elf.get("soname") or Path(elf["name"]).name
        for candidate in elf.get("runtime_symbol_candidates", []):
            entry = surface.get(candidate)
            if entry is None or entry.get("status") == "oh":
                continue
            by_library[entry.get("library", "unknown")].add(candidate)
            importers[entry.get("library", "unknown")].add(name)
    rows = []
    for library, symbols in sorted(by_library.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        names = sorted(symbols)
        rows.append(_row(
            "native-symbols", f"sym:runtime-resolved:{library}",
            f"{library} entry points looked up by name at runtime, not supplied ({len(names)})",
            oh_touchpoint=f"dlopen(\"{library}\") + dlsym, resolved against whatever the search path reaches first",
            verdict="unresolved", shim_class="C1/C2", effort=_size_effort(len(names)), confidence=STATIC,
            provider=f"the provider does not export these; {', '.join(sorted(importers[library]))} "
                     "carries them as strings, so nothing declares the dependency and a missing one "
                     "returns null rather than failing the load",
            app_evidence=f"{len(names)} public NDK symbols of {library} appear as literals: "
                         + ", ".join(names[:6]) + (" …" if len(names) > 6 else ""),
            decidable_by="probe",
            probe="probes/webview-boundaries measures the search path; resolving each name on the "
                  "board is what settles whether the lookup would succeed",
            shim=f"supply {library}'s entry points, or confirm the caller degrades without them: "
                 "this row cannot tell a lookup that happens from a string that is never used",
            symbols=names,
        ))
    return rows


def webview_rows(scan: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    called = scan["inventory"].get("platform_method_names", {}).get("Landroid/webkit/WebView;", [])
    if "<init>" not in called:
        return []
    forced, hosted = model["multiprocess_forced"], model["renderer_hosted"]
    return [_row(
        "app-framework", "wv:renderer-process", "WebView's renderer runs in an isolated service process",
        oh_touchpoint="process spawn (appspawn): an isolated Android service process with its own sandbox",
        verdict="supplied" if hosted["present"] else "missing", shim_class="C0" if hosted["present"] else "C4",
        effort="verify" if hosted["present"] else "L", confidence=STATIC,
        provider=("the runtime hosts WebView's sandboxed renderer service" if hosted["present"] else
                  "direct launch starts no isolated service processes: binding the renderer fails and Chromium aborts"
                  + (f"; answering isMultiProcessEnabled()=false does not help, WebViewDelegate returns true while "
                     f"{forced['flag']} is on" if forced["present"] else "")),
        provider_source=hosted["source"] or forced["source"],
        app_evidence=f"app constructs WebViews and calls {len(called)} WebView methods",
        shim="host the renderer: spawn an isolated child and bind Chromium's SandboxedProcessService over a local "
             "channel; or build the framework with the update-service flag off so WebView runs single-process",
    )]


def apply_probe_results(gap_map: dict[str, Any], results: dict[str, Any]) -> None:
    """Replace a probe-backed row's static verdict with the probe's measurement on the device.

    A result counts only for the exact Westlake commit it was measured on: a probe that passes on a
    later build says nothing about the provider under test.
    """
    commit = (gap_map["provider"]["westlake"].get("commit") or "")
    for row in gap_map["rows"]:
        probe = (row.get("probe") or "").removeprefix("probes/")
        measured = [r for r in results.get("results", []) if r["probe"] == probe]
        if not measured:
            continue
        exact = [r for r in measured if commit and (r["westlake_commit"].startswith(commit) or commit.startswith(r["westlake_commit"]))]
        if not exact:
            row["probe_result"] = {"note": "measured on other builds only", "builds": [r["westlake_commit"][:10] for r in measured]}
            continue
        result = exact[-1]
        row["probe_result"] = {k: result[k] for k in ("verdict", "passed", "date", "westlake_commit") if k in result}
        row["confidence"] = PROBED
        if result["passed"]:
            row.update(verdict="supplied", shim_class="C0", effort="none")
        else:
            row.update(verdict="missing" if row["verdict"] in {"unverified", "supplied"} else row["verdict"],
                       effort=result.get("effort", row["effort"] if row["effort"] != "verify" else "M"),
                       shim_class=result.get("shim_class", "C6" if row["shim_class"] in {"CU", "C0"} else row["shim_class"]))
            if result.get("finding"):
                row["provider"] = result["finding"]


def native_symbol_rows(scan: dict[str, Any], oh_missing: list[dict[str, Any]], shim_exports: set[str]) -> list[dict[str, Any]]:
    importers: dict[str, list[str]] = defaultdict(list)
    for elf in ohresolve.target_elfs(scan):
        for symbol in elf.get("undefined_symbols", []):
            importers[symbol].append(elf.get("soname") or elf["name"])
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in oh_missing:
        surface = item.get("surface") or "bionic libc"
        groups[surface].append(item)
    rows = []
    for surface, items in sorted(groups.items()):
        covered = [i["symbol"] for i in items if i["symbol"] in shim_exports]
        open_ = [i["symbol"] for i in items if i["symbol"] not in shim_exports]
        libs = sorted({lib for i in items for lib in importers.get(i["symbol"], [])})
        ndk = surface == "libandroid"
        rows.append(_row(
            "native-symbols", f"sym:{surface}", f"{surface}: {len(items)} symbols missing on the OH board",
            oh_touchpoint="OH musl / system libraries" if not ndk else "OH NDK equivalents (ArkUI/graphic/resource manager)",
            verdict="supplied" if not open_ else "missing",
            shim_class="C0" if not open_ else ("C4" if ndk else "C1/C2"),
            effort="none" if not open_ else _size_effort(len(open_), "S", "M", "L") if ndk else "S",
            confidence=STATIC,
            provider=f"{len(covered)} covered by Westlake bionic shim" if covered else "no Westlake provision",
            open_symbols=open_[:20], covered_symbols=covered, importing_libraries=libs[:12],
            shim=("NDK surface over OH equivalents" if ndk else "bionic-ABI shim: forward or translate to musl"),
        ))
    return rows


def libc_constant_rows(scan: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """Calls that resolve by name but carry a constant each libc numbers for itself."""
    importers: dict[str, list[str]] = defaultdict(list)
    for elf in ohresolve.target_elfs(scan):
        name = elf.get("soname") or elf["name"].rsplit("/", 1)[-1]
        for symbol in elf.get("undefined_symbols", []):
            if symbol in contracts.LIBC_CONSTANT_NAMESPACE_CALLS:
                importers[symbol].append(name)
    if not importers:
        return []
    untranslated = sorted(set(importers) - set(model["translated"]))
    covered = model["scope"] == "packaged-libraries" and not untranslated
    return [_row(
        "native-symbols", "libc:constant-namespace",
        "libc calls carrying a constant each libc numbers differently (" + ", ".join(sorted(importers)) + ")",
        oh_touchpoint="OH musl: the same selector number means a different limit than in bionic",
        verdict="supplied" if covered else "missing", shim_class="C0" if covered else "C2",
        effort="verify" if covered else "S", confidence=STATIC,
        provider=("the bionic shim translates them by name for the app's packaged libraries"
                  if covered else
                  f"the shim translates {', '.join(model['translated'])} for {model['scope'].replace('-', ' ')}"
                  if model["translated"] else "nothing translates them: musl answers a different limit"),
        provider_source=model["source"],
        app_evidence="; ".join(f"{symbol}: {len(names)} libraries, e.g. {', '.join(sorted(names)[:3])}"
                               for symbol, names in sorted(importers.items())),
        shim="translate the selector by name at the libc boundary for every library built against bionic; "
             "the call resolves and returns a plausible number either way, so nothing fails at load time",
    )]


def native_upcall_rows(scan: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per library that calls back into Java: what it names, and what the runtime lacks."""
    rows = []
    for lib in scan["inventory"].get("native_upcalls") or []:
        name = lib.get("soname") or lib["elf"]
        missing_classes = [c for c, state in lib["class_states"].items() if state == "missing"]
        unknown = [c for c, state in lib["class_states"].items() if state == "unknown"]
        missing = [m for m in lib["members"] if m["state"] == "missing"]
        hollow = [m for m in lib["members"] if m["state"] == "hollow"]
        candidates = [m for m in lib["members"] if m["state"] == "hollow-candidate"]
        broken = missing + hollow + candidates
        label = lambda m: f"{m['owner'].replace('/', '.')}.{m['name']}" + (m["descriptor"] if m["kind"] == "method" else "")
        owners = [f"L{c};" for c in missing_classes] + [f"L{m['owner']};" for m in broken]
        areas = sorted({_area(o)[1] or "none (library code inside Westlake)" for o in owners})
        if missing_classes or missing:
            verdict, shim_class = "missing", "C4" if any(a not in {"unmapped"} and "none" not in a for a in areas) else "C1/C5"
            effort = _size_effort(len(missing_classes) + len(missing))
        elif hollow:
            verdict, shim_class, effort = "hollow", "C9", _size_effort(len(hollow))
        elif candidates:
            verdict, shim_class, effort = "hollow-candidate", "C9", "verify"
        elif unknown:
            verdict, shim_class, effort = "unresolved", "CU", "verify"
        else:
            verdict, shim_class, effort = "supplied", "C0", "none"
        rows.append(_row(
            "native-upcalls", f"upcall:{name}", f"{name} → {len(lib['classes'])} classes, {len(lib['members'])} members",
            oh_touchpoint=", ".join(areas) if areas else "through the Java framework",
            verdict=verdict, shim_class=shim_class, effort=effort, confidence=STATIC,
            provider=((f"missing classes {missing_classes}; " if missing_classes else "")
                     + (f"{len(missing)} missing; " if missing else "")
                     + (f"{len(hollow)} hollow in Westlake adapter/stub jars; " if hollow else "")
                     + (f"{len(candidates)} constant-bodied in framework.jar (may be AOSP's own); " if candidates else "")
                     + (f"names {len(unknown)} class{'es' if len(unknown) != 1 else ''} neither the SDK nor the runtime has "
                        f"({', '.join(unknown[:4])}): version-specific or runtime internals, a runtime-integrity risk "
                        "rather than an API gap" if unknown else "")
                     ).rstrip("; ") or "every named class and member resolves in the runtime",
            app_evidence=", ".join(label(m) for m in broken[:6]) or f"e.g. {', '.join(lib['classes'][:4])}",
            unknown_classes=unknown[:10],
            shim=("implement or un-hollow the members the library calls back into" if missing or hollow or missing_classes else
                  "compare the constant bodies with AOSP" if candidates else
                  "confirm the library tolerates their absence; watch it under the runtime-integrity checks" if unknown else "none"),
        ))
    return rows


def security_rows(scan: dict[str, Any], keystore: dict[str, Any]) -> list[dict[str, Any]]:
    requests = scan["inventory"].get("jca_requests") or []
    # KeyStore.getInstance("AndroidKeyStore") names it as a type; the generators name it as the provider.
    named = [r for r in requests if r.get("provider") in contracts.ANDROID_JCA_PROVIDERS
             or (r["api"] == "KeyStore.getInstance" and r.get("type") in contracts.ANDROID_JCA_PROVIDERS)]
    if not named:
        return []
    owners = sorted({r["owner"] for r in named})
    calls = sorted({f"{r['api']}(\"{r['type']}\")" for r in named if r["api"] != "provider name" and r.get("type")})
    installed, backend = keystore["installed"], keystore["backend"]
    replacement = keystore.get("replacement", {"present": False})
    if replacement["present"]:
        verdict, provider, source = "supplied", ("a provider registered as AndroidKeyStore is installed in process: "
                                                 + ("hardware-backed keys" if replacement.get("hardware_backed") else
                                                    "software keys in app data, not hardware-backed, no attestation")), replacement["source"]
    elif installed["present"]:
        verdict = "supplied" if backend["present"] else "hollow"
        provider = ("installed and answered" if backend["present"]
                    else "installed, but nothing answers keystore2: key generation and use fail")
        source = installed["source"]
    else:
        verdict, source = "missing", None
        provider = ('never installed (Android installs it in the zygote): KeyStore.getInstance("AndroidKeyStore") '
                    'throws KeyStoreException "AndroidKeyStore not found"')
    return [_row(
        "security", "jca:AndroidKeyStore", 'Android keystore provider ("AndroidKeyStore")',
        oh_touchpoint="security/huks (OH Universal Keystore); keystore2 has no OH counterpart",
        verdict=verdict, shim_class="C0" if verdict == "supplied" else "C9" if verdict == "hollow" else "C4",
        effort="verify" if verdict == "supplied" else "M", confidence=STATIC,
        provider=provider, provider_source=source,
        app_evidence=f"{len(owners)} classes name it, e.g. {', '.join(owners[:4])}" + (f"; calls {', '.join(calls[:4])}" if calls else ""),
        shim='install an "AndroidKeyStore" provider whose keys come from KeyGenParameterSpec and stay per app: '
             "software keys in app data (days), or OH HUKS for hardware-backed keys (weeks). A blocker wherever the app "
             "opens it at startup (secure storage, encrypted preferences, biometric crypto, attestation)",
    )]


# Directories the Westlake child's default namespace searches before the app's own library
# directory (its LD_LIBRARY_PATH, as [SOURCE-NATIVE-LOAD] logs it on the board).
_SEARCHED_BEFORE_APP = ("/system/lib64/", "/vendor/lib64/")


def shadowed_libraries(scan: dict[str, Any], board_paths: list[str]) -> tuple[dict[str, str], list[str]]:
    """Packaged libraries a board library of the same name wins over, and the APK libraries whose
    DT_NEEDED graph reaches one: those must load in an isolated namespace to get the APK's copy."""
    board: dict[str, str] = {}
    for path in board_paths:
        if path.startswith(_SEARCHED_BEFORE_APP):
            board.setdefault(path.rsplit("/", 1)[-1], path)
    needed: dict[str, set[str]] = {}
    for elf in ohresolve.target_elfs(scan):
        name = elf.get("soname") or elf["name"].rsplit("/", 1)[-1]
        needed.setdefault(name, set()).update(elf.get("needed", []))
    shadowed = {name: board[name] for name in needed if name in board}
    reach = set(shadowed)
    grew = True
    while grew:
        grew = False
        for name, deps in needed.items():
            if name not in reach and deps & reach:
                reach.add(name)
                grew = True
    return shadowed, sorted(reach)


def launcher_namespace_option(manifest_root: Path | None) -> dict[str, Any]:
    path = manifest_root / "tools/probe_source_app.py" if manifest_root else None
    if path is None or not path.exists():
        return {"present": False, "source": None}
    text = path.read_text(errors="replace")
    match = re.search(r"--android-native-target", text)
    return {"present": bool(match), "source": f"manifest/tools/probe_source_app.py:{text.count(chr(10), 0, match.start()) + 1}" if match else None}


def native_loading_rows(facts: dict[str, Any], scan: dict[str, Any], launcher_extracts: dict[str, Any],
                        board_paths: list[str] | None = None, namespace_option: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rows = []
    elfs = ohresolve.target_elfs(scan)
    shadowed, targets = shadowed_libraries(scan, board_paths or [])
    if shadowed:
        option = namespace_option or {"present": False, "source": None}
        rows.append(_row(
            "native-loading", "load:shadowed-by-board",
            f"Packaged libraries a board library of the same name shadows ({', '.join(sorted(shadowed))})",
            oh_touchpoint="OH dynamic linker search order: " + ", ".join(sorted(set(shadowed.values()))) + " comes before the app's library directory",
            verdict="missing", shim_class="C3", effort="XS" if option["present"] else "M", confidence=STATIC,
            provider=("the launcher isolates only the libraries it is given (--android-native-target); nothing selects them"
                      if option["present"] else "no namespace isolation: DT_NEEDED resolves to the board's copy"),
            provider_source=option["source"],
            app_evidence=f"{len(targets)} APK libraries reach them through DT_NEEDED",
            shim=f"load these {len(targets)} libraries in the isolated Android namespace so DT_NEEDED picks the APK's copy "
                 "(e.g. NDK libc++_shared is std::__ndk1; OH's is not): " + " ".join(targets),
            launch_args=[arg for name in targets for arg in ("--android-native-target", name)],
        ))
    if not facts["extract_native_libs"] and elfs:
        rows.append(_row(
            "native-loading", "load:in-apk", f"Libraries mapped straight out of the APK ({len(elfs)} .so, extractNativeLibs=false)",
            oh_touchpoint="OH dynamic linker (cannot map zip!/ members: board test 2026-09-18)",
            verdict="supplied" if launcher_extracts["present"] else "missing",
            shim_class="C0" if launcher_extracts["present"] else "C3",
            effort="verify" if launcher_extracts["present"] else "S", confidence=STATIC,
            provider="launcher extracts split libraries to a real directory" if launcher_extracts["present"] else "none",
            provider_source=launcher_extracts.get("source"),
            shim="extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too)",
        ))
    return rows


def sandbox_rows(scan: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    oh = policy["oh"]["classes"]
    android = policy["android"]["classes"]
    hits: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for elf in ohresolve.target_elfs(scan):
        for symbol in elf.get("undefined_symbols", []):
            obj = contracts.POLICY_SENSITIVE_IMPORTS.get(symbol)
            if obj:
                hits[obj].append((elf.get("soname") or elf["name"], symbol))
    java = scan["inventory"].get("platform_method_names", {})
    for owner, names, obj in (("Landroid/system/Os;", {"mkfifo"}, "fifo_file"), ("Landroid/system/Os;", {"symlink"}, "lnk_file"),
                              ("Ljava/nio/file/Files;", {"createSymbolicLink"}, "lnk_file")):
        for name in names & set(java.get(owner, [])):
            hits[obj].append((owner.strip("L;").replace("/", "."), name))
    rows = []
    for obj, sites in sorted(hits.items()):
        oh_rule, android_rule = oh.get(obj, {}), android.get(obj, {})
        if oh_rule.get("allowed", True):
            continue
        fixable = oh_rule.get("fixable_by_policy")
        rows.append(_row(
            "sandbox-policy", f"policy:{obj}", f"Create {obj} in app data",
            oh_touchpoint=f"SELinux {policy['oh']['domain']} → {policy['oh']['app_data_type']}",
            verdict="denied", shim_class="C4" if fixable else "C5",
            effort="OH" if fixable else "M", confidence=STATIC,
            provider=f"OH kernel policy denies {obj} (Android {'allows' if android_rule.get('allowed') else 'denies'})",
            provider_source=policy["oh"]["source_rules"].get("fifo_granted_only_on_parent" if obj == "fifo_file" else "lnk_file_neverallow"),
            app_evidence=", ".join(sorted({f"{lib}:{sym}" for lib, sym in sites})),
            shim=oh_rule.get("fix", "") + (f" | bring-up workaround: {policy['oh']['workaround_without_policy_change']}" if fixable else ""),
        ))
    return rows


# Known SDKs whose behaviour depends on the device rather than on API presence.
_ENV_SDKS = [
    ("libakamaibmp.so", "Akamai Bot Manager", "device fingerprinting; self-traps (SIGILL) on unexpected environments"),
    ("com.forter", "Forter fraud SDK", "device fingerprinting via WiFi/telephony/build properties"),
]


def refused_libraries(westlake_root: Path) -> dict[str, str]:
    """Libraries the Westlake loader deliberately refuses to load, with where that is decided."""
    shim = westlake_root / "framework/webview-shim/webview_bionic_shim.c"
    if not shim.exists():
        return {}
    text = shim.read_text(errors="replace")
    match = re.search(r"g_refused_libraries\[\]\s*=\s*\{([^}]*)\}", text)
    if not match:
        return {}
    line = text.count("\n", 0, match.start()) + 1
    return {name: f"framework/webview-shim/webview_bionic_shim.c:{line}" for name in re.findall(r'"([^"]+)"', match.group(1))}


def external_rows(facts: dict[str, Any], scan: dict[str, Any], refused: dict[str, str] | None = None) -> list[dict[str, Any]]:
    rows = []
    for dep in contracts.external_dependencies(facts, set(scan["inventory"].get("platform_method_names", {}))):
        firebase = dep["dependency"].startswith("Firebase")
        suffix = dep["evidence"].split()[0].rsplit(".", 1)[-1] if firebase else ""
        rows.append(_row(
            "external-deps", "dep:" + dep["dependency"].lower().replace(" ", "-") + (f":{suffix}" if suffix else ""),
            dep["dependency"] + (f" ({suffix})" if suffix else ""),
            oh_touchpoint="none: no Google services on OH", verdict="absent" if not firebase else "partial",
            shim_class="C5", effort="M" if not firebase else "verify", confidence=STATIC,
            app_evidence=dep["evidence"], provider=dep["oh_status"],
            shim=("decide per feature: truthful 'unavailable' result, or an OH-backed replacement (push, maps, auth)"
                  if not firebase else "component discovery is local (see pm:component-metadata); GMS-backed components degrade"),
        ))
    names = {c["name"] for c in facts["components"]} | {e.get("soname", "") for e in ohresolve.target_elfs(scan)}
    for marker, sdk, behaviour in _ENV_SDKS:
        found = sorted(n for n in names if n and marker in n)
        if found:
            refusal = next(((n, (refused or {})[n]) for n in found if n in (refused or {})), None)
            rows.append(_row(
                "external-deps", f"env:{sdk.lower().replace(' ', '-')}", sdk, oh_touchpoint="device identity & environment",
                verdict="refused" if refusal else "environment-sensitive", shim_class="C5" if refusal else "CU",
                effort="verify", confidence=STATIC,
                app_evidence=", ".join(found[:4]),
                provider=(f"Westlake loader refuses {refusal[0]}: the app runs without this SDK; {behaviour}" if refusal else behaviour),
                provider_source=refusal[1] if refusal else None,
                shim=("confirm the app degrades cleanly without it, and whether its backend then rejects the session" if refusal else
                      "capture its inputs on the Android baseline; decide load/refuse and what identity to present"),
            ))
    return rows


# --------------------------------------------------------------------------------------------
# Assembly, backtest, rendering
# --------------------------------------------------------------------------------------------

def bionic_shim_exports(westlake_root: Path) -> set[str]:
    shim = westlake_root / "framework/webview-shim/webview_bionic_shim.c"
    if not shim.exists():
        return set()
    text = shim.read_text(errors="replace")
    names = set(re.findall(r"^(?:[A-Za-z_][\w \*]*?[\s\*])?([A-Za-z_]\w*)\s*\([^;]*\)\s*\{", text, re.M))
    names |= set(re.findall(r"^[A-Za-z_][\w \*]*?\s\**(__sF|_ctype_)\b", text, re.M))
    return {n for n in names if not n.startswith("westlake_") and n not in {"if", "for", "while", "switch", "return"}}


def launcher_extraction(manifest_root: Path | None) -> dict[str, Any]:
    if manifest_root is None:
        return {"present": False, "source": None}
    path = manifest_root / "tools/prepare_app.py"
    if not path.exists():
        return {"present": False, "source": None}
    text = path.read_text(errors="replace")
    match = re.search(r"def extract_libraries", text)
    return {"present": bool(match), "source": f"manifest/tools/prepare_app.py:{text.count(chr(10), 0, match.start()) + 1}" if match else None}


def build_map(
    scan: dict[str, Any],
    facts: dict[str, Any],
    api_levels: dict[tuple, str],
    aosp_services: dict[str, Any],
    westlake_root: Path,
    oh_missing: list[dict[str, Any]],
    policy: dict[str, Any],
    manifest_root: Path | None = None,
    ndk_cov: dict[str, Any] | None = None,
    observed: dict[str, Any] | None = None,
    probe_results: dict[str, Any] | None = None,
    board_paths: list[str] | None = None,
    aosp_root: Path | None = None,
    runtime_libraries: list[str] | None = None,
) -> dict[str, Any]:
    westlake_services = services.westlake_service_model(westlake_root)
    pm = contracts.pm_adapter_model(westlake_root)
    java, java_excluded = java_api_rows(scan, api_levels)
    svc, dynamic = service_rows(scan, aosp_services, westlake_services)
    rows = (java + svc + package_manager_rows(scan, facts, pm)
            + app_framework_rows(scan, contracts.direct_launch_am_model(westlake_root),
                                 contracts.window_adapter_model(westlake_root))
            + native_upcall_rows(scan)
            + (ndk_symbol_rows(scan, oh_missing, bionic_shim_exports(westlake_root), ndk_cov) if ndk_cov
               else native_symbol_rows(scan, oh_missing, bionic_shim_exports(westlake_root)))
            + native_loading_rows(facts, scan, launcher_extraction(manifest_root), board_paths,
                                  launcher_namespace_option(manifest_root))
            + libc_constant_rows(scan, contracts.libc_constant_model(westlake_root))
            + security_rows(scan, contracts.keystore_model(westlake_root))
            + webview_rows(scan, webview_process_model(aosp_root, westlake_root))
            # art-build sits beside the westlake checkout in the same workspace; absent, the row
            # is simply not claimed.
            + silent_load_rows(scan, native_load_short_circuit(westlake_root.parent / "art-build"),
                               runtime_libraries)
            + runtime_resolved_rows(scan, ndk_cov)
            + sandbox_rows(scan, policy) + external_rows(facts, scan, refused_libraries(westlake_root)))
    gap_map = {
        "app": {"package": facts["package"], "version": facts["version_name"], "target_sdk": facts["target_sdk"],
                "apk_sha256": scan["apk"]["sha256"]},
        "provider": {"westlake": pm["provenance"], "oh_board": policy["oh"]["board"]},
        "notes": {"java_excluded_by_api_level": java_excluded, "service_requests_with_computed_names": dynamic,
                  "native_upcalls_scanned": scan["inventory"].get("native_upcalls") is not None},
        "rows": rows,
    }
    if probe_results:
        apply_probe_results(gap_map, probe_results)
    if observed:
        apply_observed(gap_map, scan, observed, aosp_services)
    return gap_map


def apply_observed(gap_map: dict[str, Any], scan: dict[str, Any], observed: dict[str, Any], aosp: dict[str, Any]) -> None:
    """Mark every row with whether one recorded run on real Android touched it, and how we know."""
    touch = observed["platform_touch"]
    ran = set(observed["executed_app_methods"])
    platform_classes = set(observed.get("executed_platform_classes", []))
    loaded = set(observed.get("loaded_app_libraries", []))
    by_owner: dict[str, list[str]] = defaultdict(list)
    for key in touch:
        by_owner[key.partition("->")[0]].append(key)

    def caller_ran(site: dict[str, Any]) -> bool:
        return f"{site['owner']}->{site['method']}{site.get('descriptor', '')}" in ran

    requests: dict[str, list[dict[str, Any]]] = defaultdict(list)
    manager_to_service = {entry["manager"]: name for name, entry in aosp.items()}
    for request in scan["inventory"].get("service_requests", []):
        name = request.get("service") or manager_to_service.get(request.get("manager_class", ""))
        if name:
            requests[name].append(request)
    probes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for probe in scan["inventory"].get("existence_probes", []):
        probes[probe["descriptor"]].append(probe)

    for row in gap_map["rows"]:
        category, rid = row["category"], row["id"]
        on_path, evidence = False, ""
        if category == "java-api":
            executed = referenced = 0
            for member in row.get("members", []):
                owner = member["owner"]
                if member["kind"] == "existence_probe":
                    state = "referenced" if any(caller_ran(p) for p in probes.get(owner, [])) else None
                elif member["kind"] == "missing_class":
                    states = {touch[k] for k in by_owner.get(owner, [])}
                    state = "executed" if "executed" in states else "referenced" if states else None
                elif member["kind"] == "missing_field":
                    state = touch.get(f"{owner}->F:{member['name']}:{member['signature']}")
                else:
                    state = touch.get(f"{owner}->{member['name']}{member['signature']}")
                executed += state == "executed"
                referenced += state == "referenced"
            on_path = bool(executed or referenced)
            evidence = f"{executed} members executed, {referenced} more referenced by executed methods, of {len(row.get('members', []))}"
        elif category == "system-services":
            name = row["item"]
            callers = sum(1 for site in requests.get(name, []) if caller_ran(site))
            manager = (aosp.get(name) or {}).get("manager")
            manager_ran = manager in platform_classes
            on_path = bool(callers) or manager_ran
            evidence = f"{callers} of {len(requests.get(name, []))} requesting methods ran" + (
                f"; {manager.strip('L;').rsplit('/', 1)[-1]} code executed" if manager_ran else "")
        elif category == "package-manager":
            if rid.startswith("pm:call:"):
                states = {touch[k] for k in by_owner.get("Landroid/content/pm/PackageManager;", [])
                          if k.partition("->")[2].startswith(rid[8:] + "(")}
                on_path, evidence = bool(states), ", ".join(sorted(states)) or "not called"
            elif rid == "pm:component-metadata":
                states = {touch[k] for k in by_owner.get("Landroid/content/pm/PackageManager;", [])
                          if k.partition("->")[2].startswith(("getServiceInfo(", "getActivityInfo(", "getProviderInfo(", "getReceiverInfo("))}
                on_path, evidence = bool(states), "component lookups " + (", ".join(sorted(states)) or "not called")
            else:
                on_path, evidence = True, "done by the platform when the process is bound"
        elif category == "app-framework":
            owner, names = (("Landroid/app/ActivityManager;", tuple(AM_PROCESS_TABLE)) if rid == "am:process-table"
                            else ("Landroid/app/Dialog;", ("show",)))  # every wm: row is triggered by showing a dialog
            states = {k.partition("->")[2].split("(")[0]: touch[k] for k in by_owner.get(owner, [])
                      if k.partition("->")[2].split("(")[0] in names}
            on_path = bool(states)
            evidence = ", ".join(f"{n} {st}" for n, st in sorted(states.items())) or "not called"
        elif category in {"native-symbols", "native-upcalls", "sandbox-policy", "native-loading"}:
            if rid.startswith("upcall:"):
                libs = {rid[7:]}
            elif category == "sandbox-policy":
                libs = {part.split(":")[0] for part in (row.get("app_evidence") or "").split(", ") if part.endswith((":mkfifo", ":mkfifoat", ":symlink", ":symlinkat", ":mknod", ":link"))}
            elif category == "native-loading":
                libs = loaded
            else:
                libs = set(row.get("importing_libraries", []))
            hit = sorted(libs & loaded)
            on_path = bool(hit)
            evidence = ("loaded: " + ", ".join(hit)) if hit else ("none of its libraries loaded" if libs else "no native library involved")
        elif category == "external-deps":
            prefixes = {"dep:google-play-services": "Lcom/google/android/gms/", "dep:gms-client-api-calls": "Lcom/google/android/gms/",
                        "env:forter-fraud-sdk": "Lcom/forter/"}
            if rid.startswith("dep:firebase"):
                prefix = "Lcom/google/mlkit/" if "MlKit" in rid else "Lcom/google/firebase/components/"
            elif rid == "env:akamai-bot-manager":
                prefix = None
                on_path = "libakamaibmp.so" in loaded
                evidence = "libakamaibmp.so loaded" if on_path else "library not loaded"
            else:
                prefix = prefixes.get(rid)
            if prefix:
                count = sum(1 for name in ran if name.startswith(prefix))
                on_path, evidence = bool(count), f"{count} of its methods executed"
        row["observed"] = {"on_path": on_path, "evidence": evidence}
    gap_map["observed"] = {"scenario": observed.get("scenario", ""), "executed_methods": observed["executed_methods"],
                           "executed_app_methods": len(ran), "loaded_app_libraries": sorted(loaded)}


def backtest(gap_map: dict[str, Any], blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """For each failure already observed on the device: did a row flag it as a gap?"""
    by_id = {row["id"]: row for row in gap_map["rows"]}
    results = []
    for blocker in blockers:
        row = next((by_id[i] for i in blocker["predicted_by"] if i in by_id), None)
        if row is None:
            outcome = "missed: no row"
        elif row["verdict"] in HARD_GAPS:
            outcome = "predicted"
        elif row["verdict"] == "supplied":
            outcome = "missed: row claimed supplied"
        else:
            outcome = "flagged for verification"
        results.append({**blocker, "row": row["id"] if row else None,
                        "row_verdict": row["verdict"] if row else None, "outcome": outcome})
    return results


# Verdicts that assert the contract is broken, as opposed to "check this".
HARD_GAPS = {"missing", "null", "inert", "hollow", "strict", "denied", "stub", "absent"}


_STATUS = {"predicted": "open", "flagged for verification": "open (verify)",
           "missed: row claimed supplied": "closed per source (confirm on device)", "missed: no row": "no row"}


def markdown(gap_map: dict[str, Any], backtest_results: list[dict[str, Any]] | None = None, status_mode: bool = False) -> str:
    app = gap_map["app"]
    rows = gap_map["rows"]
    out = [f"# {app['package']} {app['version']} → OpenHarmony: API shim gap map", ""]
    wl = gap_map["provider"]["westlake"]
    out.append(f"Provider: Westlake `{wl.get('branch')}` @ `{(wl.get('commit') or '')[:10]}`"
               + (f" (+{len(wl['uncommitted'])} uncommitted files)" if wl.get("uncommitted") else "")
               + f"; OH board: {gap_map['provider']['oh_board']}. Target SDK {app['target_sdk']}.")
    out += ["", "## Summary", "", "| Category | How it reaches OH | Rows | Gaps | Effort profile |", "|---|---|---|---|---|"]
    for key, title, how in CATEGORIES:
        cat = [r for r in rows if r["category"] == key]
        gaps = [r for r in cat if r["verdict"] not in {"supplied"} and r["effort"] not in {"none"}]
        profile = Counter(r["effort"] for r in gaps)
        prof = ", ".join(f"{profile[e]}×{e}" for e in _EFFORT_ORDER if profile.get(e))
        out.append(f"| {title} | {how} | {len(cat)} | {len(gaps)} | {prof or '—'} |")
    out += ["", "Effort: " + "; ".join(f"**{k}** {v}" for k, v in EFFORT.items() if k != "none"), ""]
    observed = gap_map.get("observed")
    if observed:
        open_rows = [r for r in rows if r["verdict"] != "supplied" and r["effort"] != "none"]
        on_path = [r for r in open_rows if r.get("observed", {}).get("on_path")]
        order = {e: i for i, e in enumerate(["OH", "L", "M", "S", "XS", "verify"])}
        on_path.sort(key=lambda r: (order.get(r["effort"], 9), r["category"]))
        out += [f"## Gaps on the observed path: {observed['scenario']}", "",
                f"Recorded on real Android with full method tracing: {observed['executed_methods']} methods executed "
                f"({observed['executed_app_methods']} of them the app's own), app libraries loaded: "
                f"{', '.join(observed['loaded_app_libraries']) or 'none'}.", "",
                f"**{len(on_path)} of the {len(open_rows)} open gaps were touched on this path; "
                f"{len(open_rows) - len(on_path)} were not.**", "",
                "| Gap | Category | Verdict | Effort | How we know |", "|---|---|---|---|---|"]
        titles = {key: title for key, title, _ in CATEGORIES}
        for r in on_path:
            out.append(f"| {_escape(r['item'])} | {titles.get(r['category'], r['category'])} | {r['verdict']} | {r['effort']} | "
                       f"{_escape(r['observed']['evidence'])} |")
        out += ["", "\"Touched\" means the call ran, or a method containing the reference ran; it leans large, never small. "
                "A gap that was not touched can still matter for a later screen or feature.", ""]
    if backtest_results:
        label = (lambda r: _STATUS.get(r["outcome"], r["outcome"])) if status_mode else (lambda r: r["outcome"])
        tally = Counter(label(r) for r in backtest_results)
        if status_mode:
            out += ["## Known blockers: status against this provider", "",
                    f"Of {len(backtest_results)} blockers already hit on the board: "
                    + ", ".join(f"**{n}** {k}" for k, n in tally.most_common()) + "."]
        else:
            out += ["## Backtest against failures already hit on the board", "",
                    f"Against the provider state the app actually ran on, of {len(backtest_results)} observed blockers: "
                    + ", ".join(f"**{n}** {k}" for k, n in tally.most_common()) + "."]
        out += ["", "| Blocker | Symptom on device | Row | " + ("Status" if status_mode else "Outcome") + " |", "|---|---|---|---|"]
        for r in backtest_results:
            out.append(f"| {r['id']} | {_escape(r['symptom'])} | `{r['row'] or '—'}` ({r['row_verdict'] or '—'}) | {label(r)} |")
        out.append("")
    for key, title, how in CATEGORIES:
        cat = [r for r in rows if r["category"] == key]
        if not cat:
            continue
        cat.sort(key=lambda r: (r["verdict"] == "supplied", -_EFFORT_ORDER.index(r["effort"])))
        path_col = bool(gap_map.get("observed"))
        out += [f"## {title}", "", f"_{how}_", "",
                "| Item | Verdict | Class | Effort |" + (" On path |" if path_col else "") + " OH touchpoint | Shim / evidence |",
                "|---|---|---|---|---|---|" + ("---|" if path_col else "")]
        for r in cat:
            detail = r.get("shim", "")
            evidence = r.get("app_evidence") or (", ".join(r.get("examples", [])[:3]) if r.get("examples") else "") \
                or (f"{r['call_sites']} call sites, e.g. {r['example_site']}" if r.get("call_sites") else "")
            if r.get("open_symbols"):
                evidence = "open: " + ", ".join(r["open_symbols"][:8])
            src = f" `{r['provider_source']}`" if r.get("provider_source") else ""
            probe = f" — probe: `{r['probe']}`" if r.get("probe") else ""
            mark = (" yes |" if r.get("observed", {}).get("on_path") else " – |") if path_col else ""
            out.append(f"| {_escape(r['item'])} | {r['verdict']} | {r['shim_class']} | {r['effort']} |{mark} {_escape(r['oh_touchpoint'] or '')} | "
                       f"{_escape(detail)}{'<br>' + _escape(evidence) if evidence else ''}{src}{probe} |")
        out.append("")
    notes = gap_map["notes"]
    out += ["## Limits of this map", "",
            f"- {notes['service_requests_with_computed_names']} service requests use computed names and are not resolved statically.",
            f"- Java absences excluded by API level: {notes['java_excluded_by_api_level']}.",
            ("- Native code calling back into Java was matched from library strings against a reference android.jar; "
             "names built at runtime or encrypted are invisible." if notes.get("native_upcalls_scanned") else
             "- **Native code calling back into Java was not analysed**: rescan with `scan --platform-jar <android.jar>`."),
            "- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.",
            "- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them."]
    return "\n".join(out) + "\n"


def _escape(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
