"""One gap map per APK: every surface where it touches the platform, what backs it on OpenHarmony
under Westlake, the shim each gap needs, and what that shim costs.

Inputs are all produced without launching the app:

- the dex/ELF scan (`scan`), which now also records service requests and platform calls;
- manifest facts (`contracts.manifest_facts`);
- provider models extracted from Westlake source (`services`, `contracts.pm_adapter_model`);
- the OH board's exported symbols (`oh-import-resolution.json`) and kernel policy
  (`data/oh-app-data-policy.json`).

Each row carries its evidence and a confidence level, so "supplied" never hides "we only read the
source". A `known-blockers` file turns the map into a backtest: for every failure already paid for
on the device, did a row predict it?
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from . import contracts, services

CATEGORIES = [
    ("java-api", "Java framework API", "APK dex references − Westlake boot jars, filtered by API level"),
    ("system-services", "System services", "getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem"),
    ("package-manager", "Package manager & manifest", "manifest features and PackageManager calls → Westlake PM semantics"),
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
            shim=shim,
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
    for elf in scan["inventory"].get("elfs", []):
        for symbol in elf.get("undefined_symbols", []):
            importers[symbol].append(elf.get("soname") or elf["name"])

    groups: dict[tuple[str, str | None], list[dict[str, Any]]] = defaultdict(list)
    for item in oh_missing:
        symbol = item["symbol"]
        known = by_symbol.get(symbol)
        if known is None:
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
        if group == "libc-abi":
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


def native_symbol_rows(scan: dict[str, Any], oh_missing: list[dict[str, Any]], shim_exports: set[str]) -> list[dict[str, Any]]:
    importers: dict[str, list[str]] = defaultdict(list)
    for elf in scan["inventory"].get("elfs", []):
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


def native_loading_rows(facts: dict[str, Any], scan: dict[str, Any], launcher_extracts: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    elfs = scan["inventory"].get("elfs", [])
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
    for elf in scan["inventory"].get("elfs", []):
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
    names = {c["name"] for c in facts["components"]} | {e.get("soname", "") for e in scan["inventory"].get("elfs", [])}
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
) -> dict[str, Any]:
    westlake_services = services.westlake_service_model(westlake_root)
    pm = contracts.pm_adapter_model(westlake_root)
    java, java_excluded = java_api_rows(scan, api_levels)
    svc, dynamic = service_rows(scan, aosp_services, westlake_services)
    rows = (java + svc + package_manager_rows(scan, facts, pm)
            + native_upcall_rows(scan)
            + (ndk_symbol_rows(scan, oh_missing, bionic_shim_exports(westlake_root), ndk_cov) if ndk_cov
               else native_symbol_rows(scan, oh_missing, bionic_shim_exports(westlake_root)))
            + native_loading_rows(facts, scan, launcher_extraction(manifest_root))
            + sandbox_rows(scan, policy) + external_rows(facts, scan, refused_libraries(westlake_root)))
    gap_map = {
        "app": {"package": facts["package"], "version": facts["version_name"], "target_sdk": facts["target_sdk"],
                "apk_sha256": scan["apk"]["sha256"]},
        "provider": {"westlake": pm["provenance"], "oh_board": policy["oh"]["board"]},
        "notes": {"java_excluded_by_api_level": java_excluded, "service_requests_with_computed_names": dynamic,
                  "native_upcalls_scanned": scan["inventory"].get("native_upcalls") is not None},
        "rows": rows,
    }
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
HARD_GAPS = {"missing", "null", "inert", "hollow", "denied", "stub", "absent"}


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
