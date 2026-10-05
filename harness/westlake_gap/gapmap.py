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

import bisect
import json
import re
import sys
import zipfile
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
    ("window", "Windows & surfaces",
     "how the first screen renders → whether it needs a surface of its own → OH window/surface model"),
    ("runtime-data", "Runtime data",
     "platform calls whose answer depends on runtime data or build → zone rules, ICU → what the runtime loads"),
    ("framework-natives", "Framework natives",
     "platform classes the app uses → their native methods → libraries the runtime registers them from"),
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
    # Requests whose result the app null-checks right away (R8's compiled Kotlin checks).
    checked: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for request in requests:
        if request.get("null_checked"):
            checked[request.get("service") or request.get("manager_class") or ""].append(request)
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
        # Unresolved means the binder could not be followed; the manager can still be null only
        # where AOSP's fetcher can fail.
        can_be_null = verdict == services.NULL or (verdict == services.UNRESOLVED and entry.get("fetcher_can_fail", True))
        throwing = (casts.get(entry.get("manager", ""), []) + checked.get(entry["service"], [])
                    + checked.get(entry.get("manager", ""), [])) if can_be_null else []
        evidence = None
        if throwing:
            owners = sorted({f"{c['owner'].strip('L;').replace('/', '.')}.{c['method']}" for c in throwing})
            evidence = (f"{entry['site_count']} call sites; the app requires it non-null in {len(owners)} methods, "
                        f"by a Kotlin cast or a compiled null check (e.g. {', '.join(owners[:3])}): a null answer "
                        f"throws there, it is not skipped")
        # A hollow binder answers null, and a manager that unwraps the answer (getList() on a
        # ParceledListSlice) throws inside the framework: no app code can catch it.
        unwrapping = entry.get("unwrapping_calls", []) if verdict == services.HOLLOW else []
        if unwrapping:
            manager = entry.get("manager", "").split("/")[-1].rstrip(";")
            evidence = (f"throws inside {manager}: the app calls {', '.join(unwrapping[:4])}, which unwrap "
                        f"the binder's answer (getList()); a hollow binder's null throws there, not in app code")
            effort = "S" if effort in {"none", "verify"} else effort
        rows.append(_row(
            "system-services", f"svc:{entry['service']}", entry["service"],
            oh_touchpoint=analog or "none",
            verdict=verdict, shim_class=entry.get("shim_class", "C5"), effort=effort, confidence=STATIC,
            provider=(f"answered as a device without it: {entry['device_answer']}" if entry.get("device_answer")
                      else basis.get("detail") or ("no Westlake provision: getSystemService returns null"
                                                   if verdict == services.NULL else "")),
            provider_source=basis.get("source"),
            aosp_contract=f"{entry.get('manager')} needs binder(s) {[b['name'] for b in entry.get('binders', [])]} ({entry.get('aosp_source')})"
                if entry.get("manager") else None,
            app_calls=methods[:12], call_sites=entry["site_count"],
            example_site=_site(entry["sites"][0]) if entry.get("sites") else None,
            shim=shim, app_evidence=evidence, throws_if_null=len(throwing), throws_in_framework=unwrapping,
            throwing_sites=sorted({f"{c['owner'].strip('L;').replace('/', '.')}.{c['method']}" for c in throwing})[:40],
            device_answer=entry.get("device_answer"),
        ))
    dynamic = sum(1 for r in requests if r.get("dynamic"))
    return rows, dynamic


def _site(site: dict[str, Any]) -> str:
    return f"{site['owner'].strip('L;').replace('/', '.')}.{site['method']}"


def package_manager_rows(scan: dict[str, Any], facts: dict[str, Any], pm: dict[str, Any],
                         null_consequences: dict[str, str] | None = None) -> list[dict[str, Any]]:
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
    ordered = [c for c in providers if c["init_order"] and str(c["init_order"]) not in ("0", "0x0")]
    if ordered:
        check = semantics.get("providers_sorted_by_init_order", {"present": False, "source": None})
        rows.append(_row(
            "package-manager", "pm:provider-init-order",
            f"Providers that must start before others ({len(ordered)} with initOrder)",
            oh_touchpoint="none (Westlake's bind path)",
            verdict="supplied" if check["present"] else "missing", shim_class="C0" if check["present"] else "C6",
            effort="verify" if check["present"] else "XS", confidence=STATIC,
            provider="providers sorted by descending initOrder before install" if check["present"]
            else "providers installed in manifest order", provider_source=check["source"],
            app_evidence=", ".join(f"{c['name'].split('.')[-1]}@{c['init_order']}" for c in ordered[:4]),
            shim="sort the bind's providers by descending initOrder, as PackageManager does: Citymapper's "
                 "androidx.startup ran before FirebaseInitProvider (initOrder 100) and died",
        ))
    # Each authority goes to the first provider that declares it, enabled or not, and a provider left
    # with none is never installed (ComponentResolver.addProvidersLocked). Quitter declares a disabled
    # androidx WorkManagerInitializer, then a plugin's provider for the same authority whose class R8
    # removed; installing the second failed the bind with ClassNotFoundException.
    claimed: set[str] = set()
    losers = []
    for component in (c for c in facts["components"] if c["kind"] == "provider"):
        names = [a for a in (component.get("authorities") or "").split(";") if a]
        if names and all(a in claimed for a in names) and component.get("enabled") != "false":
            losers.append(component)
        claimed.update(names)
    if losers:
        check = semantics.get("provider_authority_claims", {"present": False, "source": None})
        rows.append(_row(
            "package-manager", "pm:provider-authority",
            f"Providers whose authority an earlier declaration holds ({', '.join(c['name'].split('.')[-1] for c in losers[:4])})",
            oh_touchpoint="none (Westlake's bind path)",
            verdict="supplied" if check["present"] else "missing", shim_class="C0" if check["present"] else "C6",
            effort="verify" if check["present"] else "XS", confidence=STATIC,
            provider=("authorities claimed in manifest order; a provider left with none is not installed"
                      if check["present"] else "every declared provider is installed"),
            provider_source=check["source"],
            app_evidence="; ".join(f"{c['name']} declares {c['authorities']}, already held" for c in losers[:3]),
            shim="give each authority to its first declaration, enabled or not, and skip a provider left with none",
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
        consequence = (null_consequences or {}).get(binder)
        rows.append(_row(
            "package-manager", f"pm:call:{name}", f"PackageManager.{name}",
            throws_in_framework=bool(consequence and status["detail"].startswith("returns null")),
            framework_consequence=consequence,
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


_PRIMITIVES = {"boolean", "int", "long", "float", "double", "byte", "char", "short"}

# Out-parameter methods whose untouched argument is the right answer for the app itself:
# a new RunningAppProcessInfo already reads IMPORTANCE_FOREGROUND, the calling app's own state.
_AM_OUT_DEFAULTS_RIGHT = {"getMyMemoryState"}


def am_default_rows(scan: dict[str, Any], am: dict[str, Any], census: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Every other ActivityManager call the app makes whose binder method the direct-launch proxy
    does not answer: a census of type defaults. The curated rows above (memory info, task queries,
    process table) are left out. A default that reaches the app as null, or leaves an `out`
    parameter as the app made it, is open; a false or 0, or a null ActivityManager turns into an
    empty answer, is noted but not open."""
    if not am.get("proxy_stub") or not census:
        return []
    curated = {"getMemoryInfo"} | set(contracts.TASK_QUERIES) | set(AM_PROCESS_TABLE)
    called = sorted(set(scan["inventory"].get("platform_method_names", {}).get("Landroid/app/ActivityManager;", [])) - curated)
    open_, quiet = [], []
    for method in called:
        for call in census.get(method, []):
            if call["binder"] in am.get("answered", []):
                continue
            returns = call["returns"]
            if returns == "void" and call["out"] and call["binder"] in _AM_OUT_DEFAULTS_RIGHT:
                quiet.append(f"{method} ({call['binder']}: its out parameter as made, already the app's own answer)")
            elif returns == "void" and call["out"]:
                open_.append(f"{method} ({call['binder']}: its out parameter is left as the app made it)")
            elif returns == "void":
                continue
            elif returns in _PRIMITIVES:
                quiet.append(f"{method} ({call['binder']}: {'false' if returns == 'boolean' else '0'})")
            elif call["null_checked"]:
                quiet.append(f"{method} ({call['binder']}: null, which ActivityManager turns into an empty answer)")
            elif call.get("null_documented"):
                quiet.append(f"{method} ({call['binder']}: null, an answer its documentation names)")
            else:
                open_.append(f"{method} ({call['binder']}: null, handed to the app)")
    if not open_:
        return []
    return [_row(
        "app-framework", "am:type-defaults",
        f"Other ActivityManager calls answered with a type default ({len(open_)} open)",
        oh_touchpoint="none: in direct launch IActivityManager is a proxy with no system_server behind it",
        verdict="hollow", shim_class="C9", effort="S", confidence=STATIC,
        provider="the direct-launch IActivityManager proxy answers methods it does not name with null, 0 or false",
        provider_source=am.get("source"), open_symbols=open_[:16],
        app_evidence="app calls ActivityManager." + ", ActivityManager.".join(sorted({o.split(" ")[0] for o in open_}))
                     + (f"; answered harmlessly: {'; '.join(quiet[:4])}" if quiet else ""),
        shim="answer each method in the proxy as ActivityManagerService answers an app about itself",
    )]


def app_framework_rows(scan: dict[str, Any], am: dict[str, Any], wm: dict[str, Any] | None = None,
                       tasks: dict[str, Any] | None = None, launch: dict[str, Any] | None = None,
                       priority: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rows = []
    names = scan["inventory"].get("platform_method_names", {})
    # Extras only an Intent object carries: a launch rebuilt from the Want's JSON drops them.
    readers = sorted(set(names.get("Landroid/content/Intent;", [])) & {
        "getParcelableExtra", "getParcelableArrayExtra", "getParcelableArrayListExtra",
        "getSerializableExtra", "getBundleExtra"})
    if readers and launch is not None:
        kept = bool(launch.get("original_intent"))
        rows.append(_row(
            "app-framework", "am:launch-extras", "Parcelable, Serializable and Bundle extras of the app's own activity launches",
            oh_touchpoint="none: the app's activities launch in its own process",
            verdict="supplied" if kept else "missing", shim_class="C0" if kept else "C9",
            effort="verify" if kept else "S", confidence=STATIC,
            provider=("the launch takes the Intent the app passed to startActivity" if kept else
                      "the launch Intent is rebuilt from OH's Want JSON: Parcelable extras are lost, an undotted "
                      "action comes back under OH's prefix"),
            provider_source=launch.get("source"), open_symbols=[] if kept else readers,
            app_evidence="app calls Intent." + ", Intent.".join(readers),
            seen_blocking=["k9 (its UpgradeDatabaseActivity lost the start intent it is handed and started null once its "
                           "database service finished)"],
            shim="hand an in-process launch the caller's Intent, copied when startActivity is called"))
    if "setPriority" in names.get("Ljava/lang/Thread;", []) and priority is not None and priority.get("answer") is not None:
        valid = 1 <= priority["answer"] <= 10
        rows.append(_row(
            "runtime", "rt:thread-priority", "Java priority of threads the runtime attaches",
            oh_touchpoint="none (the thread's nice value)",
            verdict="supplied" if valid else "missing", shim_class="C0" if valid else "C9",
            effort="verify" if valid else "XS", confidence=STATIC,
            provider=(f"the palette answers {priority['answer']}" if valid else
                      f"the palette answers {priority['answer']}, outside Java's 1-10: a saved priority restored with "
                      "Thread.setPriority throws \"Priority out of range\""),
            provider_source=priority.get("source"),
            app_evidence="app calls Thread.setPriority",
            seen_blocking=["capcut (a thread pool restored priority 0: \"Priority out of range: 0\")"],
            shim="map the thread's nice value as Android's palette does, or answer NORM_PRIORITY"))
    am_calls = set(names.get("Landroid/app/ActivityManager;", []))
    if "getMemoryInfo" in am_calls and am["proxy_stub"]:
        answered = "getMemoryInfo" in am["answered"]
        rows.append(_row(
            "app-framework", "am:memory-info", "ActivityManager.getMemoryInfo (total, available, low-memory threshold)",
            oh_touchpoint="none (/proc/meminfo, as ProcessList reads it)",
            verdict="supplied" if answered else "hollow", shim_class="C0" if answered else "C9",
            effort="verify" if answered else "XS", confidence=STATIC,
            provider=("filled as ProcessList.getMemoryInfo does" if answered else
                      "direct-launch IActivityManager proxy leaves the MemoryInfo untouched: totalMem, availMem and "
                      "threshold read 0"),
            provider_source=am["source"], app_evidence="app calls ActivityManager.getMemoryInfo",
            shim="fill it from /proc/meminfo with ProcessList's levels: availMem MemFree + Cached, totalMem MemTotal"))
    used = sorted(am_calls & set(contracts.TASK_QUERIES))
    if used and tasks is not None:
        open_ = [n for n in used if contracts.TASK_QUERIES[n] not in tasks.get("answered", [])]
        rows.append(_row(
            "app-framework", "am:own-task", "ActivityManager task queries (" + ", ".join(used) + ")",
            oh_touchpoint="none: an app sees only its own task (since Android 5)",
            verdict="hollow" if open_ else "supplied", shim_class="C9" if open_ else "C0",
            effort="S" if open_ else "verify", confidence=STATIC,
            provider=("answered with the app's task from the activity client controller" if not open_ else
                      "answered with nothing (an empty list, or null for getRecentTasks): " + ", ".join(open_)),
            provider_source=tasks.get("source"), open_symbols=open_,
            app_evidence="app calls ActivityManager." + ", ActivityManager.".join(used),
            shim="report the app's own task: its root and top activity, the activity count; an AppTask whose "
                 "finishAndRemoveTask finishes the task's activities"))
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
    # The app's own services, started or bound. With no system_server, the direct-launch proxy
    # answers each IActivityManager call by name; one it does not answer returns null or 0, which
    # ContextImpl reads as "no such service" (start) or "bind failed".
    own_services = (scan.get("apk") or {}).get("services") or 0
    own_services = own_services if isinstance(own_services, int) else len(own_services)
    context_calls = set(names.get("Landroid/content/Context;", [])) | set(names.get("Landroid/content/ContextWrapper;", []))
    started = sorted(context_calls & {"startService", "startForegroundService"})
    bound = sorted(context_calls & {"bindService"})
    if own_services and (started or bound) and am["proxy_stub"]:
        needed = (["startService"] if started else []) + (["bindService"] if bound else [])
        unanswered = [n for n in needed if n not in am["answered"]]
        rows.append(_row(
            "app-framework", "am:in-app-services",
            f"The app's own services ({', '.join(started + bound)}; {own_services} declared)",
            oh_touchpoint="none: the app's services run in its own process",
            verdict="missing" if unanswered else "supplied", shim_class="C9" if unanswered else "C0",
            effort="S" if unanswered else "verify", confidence=STATIC,
            provider=(f"direct-launch IActivityManager proxy answers {', '.join(unanswered)} with a type default: "
                      "the service is never created" if unanswered
                      else "created in process; onStartCommand and onBind on the main thread"),
            provider_source=am["source"], open_symbols=unanswered,
            app_evidence=f"app calls Context.{', Context.'.join(started + bound)}",
            seen_blocking=["drawanywhere (r84: it starts the service that shows its overlay and finishes its "
                           "activity; the service never ran)"] if started else [],
            shim="create the service in process once; onStartCommand per start with its start id, onBind per bind, "
                 "onDestroy on stopService or stopSelf when nothing is bound"))
    # Receivers the app registers and broadcasts it sends itself: answered by the proxy or dropped.
    registers = sorted(context_calls & {"registerReceiver"})
    sends = sorted(context_calls & {"sendBroadcast", "sendOrderedBroadcast"})
    if (registers or sends) and am["proxy_stub"]:
        needed = (["registerReceiverWithFeature"] if registers else []) + (["broadcastIntentWithFeature"] if sends else [])
        unanswered = [n for n in needed if n not in am["answered"]]
        rows.append(_row(
            "app-framework", "am:broadcasts", f"The app's receivers and broadcasts ({', '.join(registers + sends)})",
            oh_touchpoint="none for the app's own broadcasts (OH common events would carry the system's)",
            verdict="missing" if unanswered else "supplied", shim_class="C9" if unanswered else "C0",
            effort="S" if unanswered else "verify", confidence=STATIC,
            provider=(f"direct-launch IActivityManager proxy answers {', '.join(unanswered)} with a type default: "
                      "no sticky intent (registerReceiver(null, BATTERY_CHANGED) is null) and no delivery"
                      if unanswered else "kept in process: the app's broadcasts reach its matching registrations"),
            provider_source=am["source"], open_symbols=unanswered,
            app_evidence=f"app calls Context.{', Context.'.join(registers + sends)}",
            shim="keep registrations in process; deliver the app's broadcasts to the ones whose filter matches; "
                 "answer sticky queries (BATTERY_CHANGED)"))
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


# Fixed Android paths code reads without asking the framework, with where a runtime that supplies
# them keeps the file (under its data build) and which of its directories the app namespace merges
# over the Android one. Each entry is a gap this port hit by path.
ANDROID_PATHS = {
    "/system/etc/security/cacerts": ("etc/security/cacerts/", "etc",
                                     "Android's system trust store: Dart's TLS refuses every connection without it"),
    "/system/etc/fonts.xml": ("etc/fonts.xml", "etc", "the system font list: Skia (Flutter) draws no text without it"),
    "/system/fonts/": ("fonts/", "fonts", "the system font files the font list names"),
    "/system/usr/share/zoneinfo/": (None, None, "the legacy tz database path"),
    "/apex/com.android.tzdata/": (None, None, "the tz module's data: ANDROID_TZDATA_ROOT readers use the variable"),
    "/system/etc/hosts": (None, None, "the hosts file some native resolvers read directly"),
}


def uses_library_rows(facts: dict[str, Any], runtime_data: dict[str, Any] | None,
                      westlake_root: Path | None) -> list[dict[str, Any]]:
    """One row per <uses-library>: the shared library Android puts on the app's class path.

    Westlake resolves a name to <runtime root>/framework/<name>.jar from the runtime data and hands
    LoadedApk a builtin SharedLibraryInfo for it (AppSchedulerBridge.sharedLibraryInfos). Meta's
    apps declare org.apache.http.legacy; without it the proxygen library's JNI_OnLoad stopped at
    FindClass("org/apache/http/Header") and EventBase.init later aborted on an unset method ID.
    A library an Android device may lack (required="false") is reported as absent, not missing.
    """
    bridge = westlake_root / "framework/activity/java/AppSchedulerBridge.java" if westlake_root else None
    resolves = bool(bridge and bridge.exists() and "sharedLibraryInfos(" in bridge.read_text(errors="replace"))
    shipped = set((runtime_data or {}).get("artifacts", {}))
    rows, seen = [], set()
    for item in facts.get("uses_libraries") or []:
        name = item.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        jar = f"framework/{name}.jar"
        supplied = resolves and jar in shipped
        verdict = "supplied" if supplied else ("missing" if item.get("required", True) else "absent")
        rows.append(_row(
            "package-manager", "pm:uses-library:" + name, f"Shared library {name}"
            + ("" if item.get("required", True) else " (optional)"),
            oh_touchpoint="LoadedApk shared-library class loaders (ApplicationInfo.sharedLibraryInfos)",
            verdict=verdict, shim_class="C1", effort="verify" if supplied else ("none" if verdict == "absent" else "S"),
            confidence=STATIC,
            provider=(f"runtime data ships {jar}; AppSchedulerBridge makes it a builtin SharedLibraryInfo"
                      if supplied else "the runtime ships no jar for it"),
            app_evidence=f'<uses-library android:name="{name}" android:required="{str(item.get("required", True)).lower()}">',
            seen_blocking=(["facebook, messenger (proxygen JNI_OnLoad: ClassNotFoundException org.apache.http.Header)"]
                           if name == "org.apache.http.legacy" else []),
            shim=f"build {name} from its AOSP source and ship it as {jar}",
        ))
    return rows


def android_path_rows(apk: Path | None, scan: dict[str, Any], runtime_data: dict[str, Any] | None,
                      westlake_root: Path | None) -> list[dict[str, Any]]:
    """Android file paths the APK's code names literally, against what the app namespace shows there.

    The CA store, the font list and the tz data were each found by an app failing: Dart's TLS, Skia
    and java.time read Android paths that OH lays out differently or not at all. The paths are plain
    strings in dex and native code, so the scan can name them; the provider answers from its data
    build and from the namespace helper that merges it over OH's directories.
    """
    if apk is None or not apk.exists():
        return []
    blobs = []
    try:
        with zipfile.ZipFile(apk) as archive:
            abi = scan["apk"].get("target_abi") or "arm64-v8a"
            for name in archive.namelist():
                if (name.startswith("classes") and name.endswith(".dex")) or \
                        (name.startswith(f"lib/{abi}/") and name.endswith(".so")):
                    blobs.append((name, archive.read(name)))
    except (zipfile.BadZipFile, OSError):
        return []
    helper = (westlake_root / "native/source_app_namespace.c") if westlake_root else None
    helper_text = helper.read_text(errors="replace") if helper and helper.exists() else ""
    shipped = set((runtime_data or {}).get("artifacts", {}))
    rows = []
    for path, (runtime_path, merged, what) in ANDROID_PATHS.items():
        needle = path.encode()
        users = sorted({Path(name).name for name, blob in blobs if needle in blob})
        if not users:
            continue
        in_data = runtime_path is not None and any(a == runtime_path or a.startswith(runtime_path) for a in shipped)
        is_merged = merged is not None and f'"{merged}", "/system/{merged}"' in helper_text
        if runtime_path is None:
            verdict, provider = "unverified", "not modelled: whether the app namespace shows it is a board question"
        elif in_data and is_merged:
            verdict, provider = "supplied", f"the runtime data's {runtime_path} is merged over /system/{merged}"
        elif in_data:
            verdict, provider = "missing", f"the runtime ships {runtime_path}, but nothing shows it at {path}"
        else:
            verdict, provider = "missing", f"the runtime ships nothing for {path}"
        rows.append(_row(
            "runtime-data", f"path:{path}", f"Android path read directly: {path}",
            oh_touchpoint="the app's mount namespace (OH's /system differs from Android's)",
            verdict=verdict, shim_class="C1" if verdict != "unverified" else "CU",
            effort="verify" if verdict == "supplied" else "S", confidence=STATIC,
            provider=provider, provider_source="native/source_app_namespace.c" if is_merged else None,
            app_evidence=f"named in {', '.join(users[:4])}" + (" ..." if len(users) > 4 else "") + f": {what}",
            shim=f"ship Android's {path} in the runtime data and show it at that path in the app namespace",
        ))
    return rows


# java.nio.channels classes whose use reaches sun.nio.ch's natives (Net, IOUtil, the poll selector).
NIO_CHANNELS = ("Ljava/nio/channels/Selector;", "Ljava/nio/channels/SocketChannel;",
                "Ljava/nio/channels/ServerSocketChannel;", "Ljava/nio/channels/DatagramChannel;",
                "Ljava/nio/channels/spi/SelectorProvider;")


def nio_rows(scan: dict[str, Any], runtime_class_paths: set[str] | None) -> list[dict[str, Any]]:
    """Non-blocking sockets: the app opens a Selector or a socket channel, which runs sun.nio.ch's
    natives (Net.pollinValue in Net.<clinit> first). A runtime that registers none of them fails the
    first Selector.open with UnsatisfiedLinkError (Mindustry, Unciv: Ktor and Arc's networking)."""
    names = scan["inventory"].get("platform_method_names", {})
    used = sorted(owner.split("/")[-1].rstrip(";") for owner in NIO_CHANNELS if owner in names)
    if not used or runtime_class_paths is None:
        return []
    registered = "sun/nio/ch/Net" in runtime_class_paths
    return [_row(
        "framework-natives", "nio:channels", f"NIO socket channels and selectors ({', '.join(used)})",
        oh_touchpoint="sockets and poll: OH has them; the runtime must register sun.nio.ch's natives",
        verdict="supplied" if registered else "missing", shim_class="C1", effort="verify" if registered else "M",
        confidence=STATIC,
        provider=("a runtime library names sun/nio/ch/Net" if registered else
                  "no runtime library registers sun.nio.ch.Net: Net.<clinit> throws UnsatisfiedLinkError on the "
                  "first Selector.open or channel"),
        app_evidence="calls " + ", ".join(used),
        seen_blocking=["mindustry (loop-1)", "unciv (batch-5)"],
        shim="register OpenJDK's sun.nio.ch natives (Net, IOUtil, PollArrayWrapper, SocketChannelImpl) over OH sockets",
    )]


def pm_null_consequences(aosp_root: Path | None) -> dict[str, str]:
    """IPackageManager method -> what AOSP's ApplicationPackageManager makes of a null answer.

    A stub that returns null is harmless only if the client wrapper passes the null on. Several
    turn it into an exception the app never expected from its own package: getInstallSourceInfo
    throws NameNotFoundException (package_info_plus then failed FOSS Warn, mucke and Cardabase),
    and a wrapper that unwraps a ParceledListSlice dereferences it.
    """
    path = aosp_root / "frameworks-base/core/java/android/app/ApplicationPackageManager.java" if aosp_root else None
    if path is None or not path.exists():
        return {}
    text = path.read_text(errors="replace")
    heads = list(re.finditer(r"\n    (?:public|protected|private)[^\n;=]*?\b\w+\s*\([^)]*\)[^{;]*\{", text))
    out: dict[str, str] = {}
    for index, head in enumerate(heads):
        body = text[head.end():heads[index + 1].start() if index + 1 < len(heads) else len(text)]
        for call in re.finditer(r"(\w+)\s*=\s*(?:\([\w.<>\[\] ]+\)\s*)?mPM\s*\.\s*(\w+)\(", body):
            variable, binder = call.group(1), call.group(2)
            after = body[call.end():]
            null_throw = re.search(rf"if\s*\(\s*{variable}\s*==\s*null\s*\)\s*\{{?\s*throw\s+new\s+NameNotFoundException", after)
            # "if (x != null) { ... return ...; } ... throw new NameNotFoundException" -- the throw is the null path
            guarded = re.search(rf"if\s*\(\s*{variable}\s*!=\s*null\b", after) and "throw new NameNotFoundException" in after
            if null_throw or guarded:
                out.setdefault(binder, "throws NameNotFoundException when the answer is null")
            elif re.search(rf"\b{variable}\.getList\(\)", after) and not re.search(rf"{variable}\s*[!=]=\s*null", after):
                out.setdefault(binder, "dereferences the null (ParceledListSlice.getList)")
    return out


def _aidl_methods(path: Path) -> dict[str, dict[str, Any]]:
    """Method name -> its return type and whether it takes an `out` parameter, from an AIDL file."""
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", path.read_text(errors="replace"), flags=re.S)
    text = re.sub(r"@[\w.]+(?:\([^)]*\))?", " ", text)
    methods: dict[str, dict[str, Any]] = {}
    # The delimiter is looked behind, not consumed: one declaration's ';' starts the next.
    for match in re.finditer(r"(?:(?<=[;{}])|\A)\s*(oneway\s+)?([\w.<>\[\], ]+?)\s+(\w+)\s*\(([^)]*)\)\s*;", text):
        returns, name, params = " ".join(match.group(2).split()), match.group(3), match.group(4)
        if returns in ("import", "package", "interface"):
            continue
        methods.setdefault(name, {"returns": returns, "out": bool(re.search(r"\b(?:in)?out\s", params))})
    return methods


def am_default_census(aosp_root: Path | None) -> dict[str, list[dict[str, Any]]]:
    """Public ActivityManager method -> the IActivityManager calls its body makes, each with the
    binder method's return type, whether it fills an `out` parameter, and whether ActivityManager
    checks the answer for null before handing it on.

    With no system_server the direct-launch proxy answers a method it does not name with a type
    default, and what the app sees depends on the wrapper: getHistoricalProcessExitReasons turns
    null into an empty list, getMyMemoryState leaves the caller's RunningAppProcessInfo as it was
    made (importance 0, not foreground)."""
    if aosp_root is None:
        return {}
    am_path = aosp_root / "frameworks-base/core/java/android/app/ActivityManager.java"
    aidl_path = aosp_root / "frameworks-base/core/java/android/app/IActivityManager.aidl"
    if not am_path.exists() or not aidl_path.exists():
        return {}
    binder = _aidl_methods(aidl_path)
    original = am_path.read_text(errors="replace")
    text = contracts._strip_java_comments(original)
    census: dict[str, list[dict[str, Any]]] = {}
    for head in re.finditer(r"\bpublic\s+(?:static\s+|final\s+|synchronized\s+)*[\w.<>\[\], ?]+?\s+(\w+)\s*\(", text):
        body = contracts._braced_block(text, head.end())
        if not body:
            continue
        # The method's javadoc: a null it documents (getProcessesInErrorState: "or null if there are no
        # processes in error") is an answer, not a default the app is unready for.
        doc, doc_end = "", original.rfind("*/", 0, head.start())
        if doc_end >= 0 and re.fullmatch(r"\*/\s*(?:@[\w.]+(?:\([^)]*\))?\s*)*", original[doc_end:head.start()]):
            doc = original[original.rfind("/**", 0, doc_end):doc_end]
        for call in re.finditer(r"(?<![\w.])getService\(\)\s*\.\s*(\w+)\s*\(", body):
            info = binder.get(call.group(1))
            if info is None:
                continue
            entry = {"binder": call.group(1), **info, "null_checked": bool(re.search(r"[!=]=\s*null", body)),
                     "null_documented": bool(re.search(r"\bnull\b", doc))}
            calls = census.setdefault(head.group(1), [])
            if entry not in calls:
                calls.append(entry)
    return census


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


#: Public calls that end in a runtime native, by the native (class/name): what an app names when it
#: reaches one. Only natives the runtime's openjdk stub registers with a constant body are looked up.
STUB_NATIVE_CALLERS = {
    "java/io/UnixFileSystem.getSpace0": ("Ljava/io/File;", ("getTotalSpace", "getFreeSpace", "getUsableSpace")),
    "java/io/UnixFileSystem.setPermission0": ("Ljava/io/File;", ("setReadable", "setWritable", "setExecutable")),
    "java/io/UnixFileSystem.setReadOnly0": ("Ljava/io/File;", ("setReadOnly",)),
    "java/io/UnixFileSystem.setLastModifiedTime0": ("Ljava/io/File;", ("setLastModified",)),
}


def stub_native_model(art_build_root: Path | None, westlake_root: Path) -> dict[str, Any]:
    """Natives the runtime's openjdk stub registers with a body that only returns a constant (0,
    NULL, false), and whether libwl_missing_natives binds a real one over it. Registered, they never
    fail: every caller gets the constant (File.getUsableSpace 0, File.setReadable false)."""
    stubs: dict[str, str] = {}
    path = art_build_root / "stubs/openjdk_stub.c" if art_build_root else None
    if path and path.exists():
        text = path.read_text(errors="replace")
        constant = {m[1]: text.count(chr(10), 0, m.start()) + 1 for m in re.finditer(
            r"^static\s+\w+\s+(\w+)\([^)]*\)\s*\{\s*return\s+(?:0|NULL|JNI_FALSE)\s*;\s*/\*\s*stub\s*\*/\s*\}",
            text, re.M)}
        owner = None
        for m in re.finditer(r'FindOptionalClass\(env,\s*"([\w/$]+)"\)|\{\s*"(\w+)",\s*"[^"]*",\s*\(void\s*\*\)\s*(\w+)\s*\}',
                             text):
            if m[1]:
                owner = m[1]
            elif owner and m[3] in constant:
                stubs[f"{owner}.{m[2]}"] = f"art-build/stubs/openjdk_stub.c:{constant[m[3]]}"
    rebound: set[str] = set()
    natives = westlake_root / "framework/javacore-shim/missing_natives.c"
    if natives.exists():
        text = natives.read_text(errors="replace")
        tables = dict(re.findall(r'bind\(env,\s*"([\w/$]+)",\s*(\w+),', text))
        for owner, table in tables.items():
            body = re.search(rf"\b{table}\[\]\s*=\s*\{{(.*?)\n\}};", text, re.S)
            for name in re.findall(r'\{\s*"(\w+)",', body[1] if body else ""):
                rebound.add(f"{owner}.{name}")
    return {"stubs": stubs, "rebound": sorted(rebound & set(stubs))}


def stub_native_rows(scan: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """App calls that reach a runtime native registered as a constant answer (stub_native_model)."""
    called = scan["inventory"].get("platform_method_names") or {}
    reached: dict[str, list[str]] = {}
    for native, (owner, methods) in STUB_NATIVE_CALLERS.items():
        if native not in model["stubs"]:
            continue
        hits = [f"{owner[1:-1].rsplit('/', 1)[-1]}.{m}" for m in methods if m in called.get(owner, ())]
        if hits:
            reached[native] = hits
    if not reached:
        return []
    open_ = sorted(n for n in reached if n not in model["rebound"])
    evidence = "; ".join(f"{', '.join(calls)} ({native.rsplit('/', 1)[-1]}"
                         + (", re-bound" if native in model["rebound"] else ", constant") + ")"
                         for native, calls in sorted(reached.items()))
    return [_row(
        "java-api", "runtime:stub-natives",
        "Runtime natives registered with a constant answer (" + ", ".join(
            sorted({c for calls in reached.values() for c in calls})[:4]) + ")",
        oh_touchpoint="none: the runtime's own openjdk stub registers the native",
        verdict="hollow" if open_ else "supplied", shim_class="C9" if open_ else "C2",
        effort="S" if open_ else "verify", confidence=STATIC,
        provider=("a real implementation is bound over the stub" if not open_ else
                  "registered as a constant: " + ", ".join(open_)),
        provider_source=model["stubs"].get(open_[0] if open_ else sorted(reached)[0]),
        open_symbols=open_, app_evidence=evidence,
        seen_blocking=["cnn (r84: File.getUsableSpace answered 0 for /data; CnnApplication sized its OkHttp cache "
                       "at half of it and died on \"maxSize <= 0\")"]
        if "java/io/UnixFileSystem.getSpace0" in reached else [],
        shim="bind libcore's implementation (UnixFileSystem_md.c) over the stub in libwl_missing_natives",
    )]


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
            importing_libraries=sorted(importers[library]),
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


def interposition_rows(scan: dict[str, Any], runtime: dict[str, Any] | None,
                       rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """App libraries exporting symbols a runtime library also exports.

    Android shows an app's code only the NDK's public libraries; Westlake's runtime libraries are
    global in the default namespace, where System.loadLibrary puts the app's own. An app library's
    calls to its own exported functions go through its PLT and bind to the first definition in the
    global scope, so a runtime library carrying the same symbols takes them over. PPSSPP's own Vulkan
    Memory Allocator calls ran in libhwui.so's copy and crashed in CalcAllocationParams. A copy of
    HarfBuzz, FreeType or libpng in an app meets the runtime's libharfbuzz_ng, libft2 and libpng the
    same way. A library routed to the Android namespace does not see them.
    """
    if not runtime:
        return []
    owners: dict[str, set[str]] = defaultdict(set)
    for lib in runtime.get("bridge_libraries", []):
        for symbol in lib.get("exported_symbols") or []:
            owners[symbol].add(lib.get("soname") or lib.get("name") or "?")
    routed = set()
    for row in rows:
        args = row.get("launch_args") or []
        routed |= {value for flag, value in zip(args[0::2], args[1::2]) if flag == "--android-native-target"}
    hits: dict[str, Counter] = {}
    for elf in ohresolve.target_elfs(scan):
        name = elf["name"].rsplit("/", 1)[-1]
        counts = Counter(owner for symbol in elf.get("exported_symbols") or []
                         if symbol not in ("JNI_OnLoad", "JNI_OnUnload") and not symbol.startswith("Java_")
                         for owner in owners.get(symbol, ()))
        if sum(counts.values()) >= 3:
            hits[name] = counts
    if not hits:
        return []
    exposed = sorted(name for name in hits if name not in routed)
    evidence = "; ".join(f"{name}: " + ", ".join(f"{count} with {owner}" for owner, count in hits[name].most_common(2))
                         for name in sorted(hits, key=lambda n: -sum(hits[n].values()))[:4])
    return [_row(
        "native-loading", "load:interposed-by-runtime",
        f"App libraries whose own symbols a runtime library also exports ({', '.join(sorted(hits)[:4])}"
        + (" ..." if len(hits) > 4 else "") + ")",
        oh_touchpoint="the default namespace: Westlake's runtime libraries are global there, ahead of the app's",
        verdict="missing" if exposed else "supplied", shim_class="C3", effort="S" if exposed else "verify",
        confidence=STATIC, open_symbols=exposed[:12],
        provider=("routed to the Android namespace, where the runtime's libraries are not global" if not exposed else
                  f"{len(exposed)} of {len(hits)} load in the default namespace"),
        app_evidence=evidence,
        # A crash this explains runs in the runtime library's copy, called from the app's library.
        libraries=exposed, crash_libraries=sorted({owner for name in exposed for owner in hits[name]}),
        seen_blocking=["ppsspp (r83: its own VMA calls ran in libhwui.so's copy; SIGSEGV in CalcAllocationParams)"],
        shim="route these libraries to the Android namespace (--android-native-target), or stop the runtime's "
             "libraries exporting what Android keeps private to the platform",
    )]


def task_root_rows(scan: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """Activity.isTaskRoot() and getTaskId(), which ask the activity client controller for the
    activity's task. A constant -1 makes every activity a non-root of no task: Instagram's launcher
    activity finished itself ("is not the root. Finishing activity instead of launching")."""
    called = set(scan["inventory"].get("platform_method_names", {}).get("Landroid/app/Activity;", []))
    used = sorted(called & {"isTaskRoot", "getTaskId", "moveTaskToBack"})
    if not used or model.get("task_for_activity") is None:
        return []
    answered = model["task_for_activity"] == "answered"
    return [_row(
        "app-framework", "am:task-root", "Activity task queries (" + ", ".join(used) + ")",
        oh_touchpoint="none: the in-process activity client controller answers for the absent system_server",
        verdict="supplied" if answered else "missing", shim_class="C9" if not answered else "C0",
        effort="verify" if answered else "XS", confidence=STATIC,
        provider=("the adapter keeps the app's one task and its root" if answered else
                  "getTaskForActivity returns a constant -1: no activity is ever a task root"),
        provider_source=model.get("source"),
        app_evidence="the app calls Activity." + ", Activity.".join(used),
        seen_blocking=["instagram (its launcher activity finished itself: \"is not the root\")"],
        shim="answer getTaskForActivity with the process's task id, and the oldest live activity as its root",
    )]


def own_intent_rows(scan: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """The app's own activities reached by implicit intent: its code names a scheme or action that
    only its own activity filters declare (scanner.named_filter_targets). Android resolves such an
    intent through the package manager; OH's bundle manager knows only OH's abilities."""
    named = scan["inventory"].get("own_intent_names") or []
    if not named:
        return []
    resolved, started = model.get("resolved", False), model.get("started", False)
    supplied = resolved and started
    open_ = [part for part, done in (("queryIntentActivities/resolveIntent", resolved),
                                     ("startActivity", started)) if not done]
    return [_row(
        "app-framework", "am:own-implicit-intents",
        "Implicit intents for the app's own activities (" + ", ".join(named[:4]) + ")",
        oh_touchpoint="bundle manager QueryAbilityInfos and StartAbility: OH's abilities only",
        verdict="supplied" if supplied else "missing", shim_class="C0" if supplied else "C9",
        effort="verify" if supplied else "S", confidence=STATIC,
        provider=("the app's own activities are matched against their manifest filters, and an implicit start "
                  "is made explicit" if supplied else "not resolved in process: " + ", ".join(open_)),
        provider_source=model.get("source"), open_symbols=open_,
        app_evidence="the app's code names " + ", ".join(named[:6]) + ", declared only by its own activity filters",
        seen_blocking=["shazam (r85: its splash resolved VIEW shazam_activity://configuration in its own package, "
                       "got nothing, started nothing and finished)"],
        shim="answer queryIntentActivities and resolveIntent for the app's own package from its parsed manifest "
             "filters (MATCH_DEFAULT_ONLY needs CATEGORY_DEFAULT), and resolve an implicit startActivity the same way",
    )]


def post_create_rows(scan: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """The app's own activity code in onPostCreate or onRestoreInstanceState (scanner.after_start_overrides),
    which Android calls after onStart from the pending actions its launch marked. A provider that
    resumes in a transaction of its own makes neither call."""
    overrides = scan["inventory"].get("after_start_overrides") or []
    if not overrides or model.get("carries_start") is None:
        return []
    supplied = bool(model["carries_start"])
    callbacks = sorted({name for item in overrides for name in item["callbacks"]})
    launch = set(scan.get("apk", {}).get("main_activities") or [])
    first = sorted(overrides, key=lambda item: item["activity"] not in launch)
    return [_row(
        "app-framework", "am:post-create",
        "Activity callbacks after onStart (" + ", ".join(callbacks) + ")",
        oh_touchpoint="none: the in-process transaction executor runs the activity lifecycle",
        verdict="supplied" if supplied else "missing", shim_class="C0" if supplied else "C9",
        effort="verify" if supplied else "XS", confidence=STATIC,
        provider=("the launch transaction carries the start, so its pending actions reach it" if supplied else
                  "the launch transaction stops at onCreate and the resume comes in one of its own: the pending "
                  "onRestoreInstanceState and onPostCreate are cleared in between"),
        provider_source=model.get("source"),
        app_evidence="; ".join(item["activity"] + " (" + ", ".join(item["callbacks"]) + ")" for item in first[:4])
        + (f"; {len(overrides) - 4} more" if len(overrides) > 4 else ""),
        seen_blocking=["linphone (r85: MainActivity marks its first screen ready in onPostCreate and cancels every "
                       "draw until then; its window never drew)"],
        shim="request the start state in the launch transaction, as Android's starts and resumes in it",
    )]


def permission_request_rows(scan: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """Runtime permission requests. Android answers every one, in onRequestPermissionsResult with what
    the user chose; a request that is never answered leaves the activity waiting on it."""
    called = set(scan["inventory"].get("platform_method_names", {}).get("Landroid/app/Activity;", []))
    if "requestPermissions" not in called or model.get("answered") is None:
        return []
    supplied = bool(model["answered"])
    return [_row(
        "app-framework", "am:permission-request", "Runtime permission requests (Activity.requestPermissions)",
        oh_touchpoint="access_token: the host application's grants (no permission dialog is raised)",
        verdict="supplied" if supplied else "missing", shim_class="C0" if supplied else "C9",
        effort="verify" if supplied else "XS", confidence=STATIC,
        provider=("answered in process with what OH has granted the host application, as the permission "
                  "controller's result" if supplied else
                  "the request goes to OH as an implicit action it does not know: no answer arrives"),
        provider_source=model.get("source"),
        app_evidence="the app calls Activity.requestPermissions",
        seen_blocking=["aat, castlab, element, msstart, ssh (r85: each asked and never heard back; each drew)"],
        shim="answer ACTION_REQUEST_PERMISSIONS with the permission controller's result: the names and their grants",
    )]


def ce_storage_rows(scan: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """StrictMode's VM checks, which report a credential-protected data access while the user's storage
    is locked, each with a stack trace: an app that turns them on pays for every file it touches when
    the provider says the storage is still locked."""
    called = set(scan["inventory"].get("platform_method_names", {}).get("Landroid/os/StrictMode$VmPolicy$Builder;", []))
    used = sorted(called & {"detectAll", "detectCredentialProtectedWhileLocked"})
    if not used:
        return []
    supplied = bool(model.get("unlocked"))
    return [_row(
        "app-framework", "os:ce-storage-unlocked", "Credential-encrypted storage unlocked, for StrictMode's checks",
        oh_touchpoint="none: the in-process storage manager answers for the user's storage",
        verdict="supplied" if supplied else "missing", shim_class="C0" if supplied else "C9",
        effort="verify" if supplied else "XS", confidence=STATIC,
        provider=("isCeStorageUnlocked answers true" if supplied else
                  "isCeStorageUnlocked gets a default false: every data access is a violation while locked"),
        provider_source=model.get("source"),
        app_evidence="the app enables StrictMode.VmPolicy." + ", ".join(used),
        seen_blocking=["osmand (r85: 730 violations in its hilog, 20,000 lines with their stacks, while it started; "
                       "it then aborted in a race with its own data copy)"],
        shim="answer isCeStorageUnlocked, Android 15's name for isUserKeyUnlocked, with true",
    )]


def window_metrics_rows(scan: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """WindowMetrics read before the first relayout. aat derived its button count from the window
    width in onCreate, got 0x0, and divided by zero."""
    # Jetpack WindowManager's WindowMetricsCalculator calls these too, from inside the app's dex.
    called = sorted(set(scan["inventory"].get("platform_method_names", {}).get("Landroid/view/WindowManager;", []))
                    & {"getCurrentWindowMetrics", "getMaximumWindowMetrics"})
    if not called:
        return []
    supplied = bool(model.get("bounds_at_bind"))
    return [_row(
        "app-framework", "wm:window-metrics", "Window metrics before the first layout",
        oh_touchpoint="window_manager (the window's rect)",
        verdict="supplied" if supplied else "missing", shim_class="C0" if supplied else "C9",
        effort="verify" if supplied else "XS", confidence=STATIC,
        provider=("activities are launched with the window bounds in their configuration" if supplied
                  else "windowConfiguration bounds stay empty until the first relayout: metrics read in "
                       "onCreate are 0x0"),
        provider_source=model.get("source"), app_evidence="the app calls WindowManager." + ", WindowManager.".join(called),
        seen_blocking=["aat (divide by zero on the button count it derived from the width)"],
        shim="put the window bounds in the bind-time configuration's windowConfiguration",
    )]


def vm_lookup_rows(scan: dict[str, Any], shim_exports: set[str]) -> list[dict[str, Any]]:
    """Native code that finds the process's JavaVM itself, with JNI_GetCreatedJavaVMs (scanner.vm_lookups).
    libnativehelper answers from the invocation table its JniInvocation filled; appspawn-x's is a
    local of startVm(), whose destructor clears that table, so once the VM runs it answers JNI_OK
    with no VM. A caller that checks only the result takes an uninitialized JavaVM*."""
    elfs = [elf for elf in scan["inventory"].get("elfs") or [] if elf.get("abi_matches_machine", True)]
    found = {(elf.get("soname") or elf.get("name")): elf["vm_lookup"] for elf in elfs if elf.get("vm_lookup")}
    if not found:
        return []
    libraries = sorted(found)
    supplied = "JNI_GetCreatedJavaVMs" in shim_exports
    return [_row(
        "native-loading", "jni:created-vms",
        "The process's JavaVM found from native code (" + ", ".join(libraries[:4]) + ")",
        oh_touchpoint="none: the runtime's libnativehelper and libart",
        verdict="supplied" if supplied else "missing", shim_class="C0" if supplied else "C3",
        effort="verify" if supplied else "XS", confidence=STATIC,
        provider=("the preloaded shim answers JNI_GetCreatedJavaVMs from libart's Runtime" if supplied else
                  "libnativehelper answers JNI_OK with no VM: the JniInvocation that filled its table is gone "
                  "once appspawn-x has started the VM"),
        app_evidence="; ".join(f"{name} {'imports' if how == 'import' else 'looks up'} JNI_GetCreatedJavaVMs"
                               for name, how in sorted(found.items())[:4]),
        libraries=libraries,
        seen_blocking=["elementx (r85: its Rust library took an uninitialized JavaVM* from the empty answer; "
                       "SIGSEGV in its first FindClass)"],
        shim="define JNI_GetCreatedJavaVMs in the preloaded shim, forwarding to libart's",
    )]


def native_egl_window_rows(scan: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """App code that creates its own EGL window surface. ANativeWindow_fromSurface gives it the
    adapter's AOSP-shaped window, which OH's EGL rejects: Flutter's Skia renderer (apps that opt out
    of Impeller) got no surface for its SurfaceView and never drew."""
    elfs = [elf for elf in scan["inventory"].get("elfs") or [] if elf.get("abi_matches_machine", True)]
    libraries = sorted({elf.get("soname") or elf.get("name") for elf in elfs
                        if "eglCreateWindowSurface" in (elf.get("undefined_symbols") or [])})
    # Libraries that look EGL up by handle (SDL dlopens libEGL.so): they reach the shim's entry
    # points only if its dlsym hands them over.
    by_handle = sorted({elf.get("soname") or elf.get("name") for elf in elfs if elf.get("egl_lookups")})
    rows = []
    if by_handle:
        handled = bool(model.get("by_handle"))
        rows.append(_row(
            "window", "egl:by-handle", "EGL looked up by handle from native code (" + ", ".join(by_handle[:4]) + ")",
            oh_touchpoint="graphic_2d (OH's EGL; its NDK libEGL.so loads into OH's ndk namespace)",
            verdict="supplied" if handled else "missing", shim_class="C0" if handled else "C6",
            effort="verify" if handled else "S", confidence=STATIC,
            provider=("the shim answers an Android dlopen of libEGL.so with the runtime's EGL and a dlsym of "
                      "eglCreateWindowSurface or eglTerminate with its own" if handled else
                      "lookups by handle reach OH's EGL directly: the adapter's window is refused and eglTerminate "
                      "tears down the display hwui renders through"),
            provider_source=model.get("by_handle"),
            app_evidence=f"{', '.join(by_handle[:4])} name EGL entry points without importing them",
            libraries=by_handle,
            seen_blocking=["anarchre (SDL: eglCreateWindowSurface refused, then hwui aborted with EGL_NOT_INITIALIZED)"],
            shim="answer dlopen(libEGL.so) with the runtime's EGL and dlsym of the shim's EGL overrides with its own",
        ))
    if not libraries:
        return rows
    supplied = bool(model.get("unwraps"))
    return rows + [_row(
        "window", "egl:native-window", "EGL window surfaces created from native code",
        oh_touchpoint="graphic_2d (OHNativeWindow under OH's EGL)",
        verdict="supplied" if supplied else "missing", shim_class="C0" if supplied else "C6",
        effort="verify" if supplied else "S", confidence=STATIC,
        provider=("the preloaded shim's eglCreateWindowSurface unwraps the adapter's window to its OHNativeWindow"
                  if supplied else "the adapter's AOSP-shaped window reaches OH's EGL, which takes only an OHNativeWindow"),
        provider_source=model.get("source"),
        app_evidence=f"{', '.join(libraries[:4])} import{'s' if len(libraries) == 1 else ''} eglCreateWindowSurface",
        seen_blocking=["cardswithcats, mousepounce, mobilev2 (Flutter, Skia: no surface for the SurfaceView)"],
        shim="unwrap the adapter's window with oh_anw_get_oh before calling OH's eglCreateWindowSurface",
    )]


# Feature name prefix → the getSystemService name of the service that reaches the hardware.
# Form factors (touchscreen, screen.*) and features no service backs are not listed.
_FEATURE_SERVICES = (
    ("android.hardware.camera", "camera"),
    ("android.hardware.bluetooth_le", "bluetooth"),
    ("android.hardware.bluetooth", "bluetooth"),
    ("android.hardware.wifi.direct", "wifip2p"),
    ("android.hardware.wifi.aware", "wifiaware"),
    ("android.hardware.wifi.rtt", "wifirtt"),
    ("android.hardware.wifi", "wifi"),
    ("android.hardware.telephony", "phone"),
    ("android.hardware.nfc", "nfc"),
    ("android.hardware.location", "location"),
    ("android.hardware.fingerprint", "fingerprint"),
    ("android.hardware.biometrics.face", "face"),
    ("android.hardware.usb", "usb"),
    ("android.hardware.consumerir", "consumer_ir"),
    ("android.software.device_admin", "device_policy"),
)


def _feature_service(feature: str) -> str | None:
    for prefix, service in _FEATURE_SERVICES:
        if feature == prefix or feature.startswith(prefix + "."):
            return service
    return None


def feature_rows(scan: dict[str, Any], claims: dict[str, Any], aosp: dict[str, Any],
                 westlake: dict[str, Any]) -> list[dict[str, Any]]:
    """Features the app asks about that Westlake reports present. A claim tells the app the
    hardware is there and reachable through its Android service; claimed without that service, the
    app takes its hardware path and finds nothing. CameraX checked its camera list against the
    claimed back camera, listed none, and retried its init until it failed (FairScan)."""
    queried: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for query in scan["inventory"].get("feature_queries") or []:
        if query.get("feature") in claims.get("claimed", []):
            queried[query["feature"]].append(query)
    rows = []
    for feature, sites in sorted(queried.items()):
        service = _feature_service(feature)
        if service is None:
            continue
        entries = services.service_map([{"service": service}], aosp, westlake)
        verdict = entries[0]["verdict"] if entries else services.NULL
        basis = (entries[0].get("westlake_basis") or {}) if entries else {}
        backed = verdict == services.SUPPLIED
        rows.append(_row(
            "system-services", f"feature:{feature}", feature,
            oh_touchpoint=services.OH_ANALOG.get(service) or "unmapped",
            verdict="supplied" if backed else "contradicted", shim_class="C0" if backed else "C5",
            effort="verify" if backed else "S", confidence=STATIC,
            provider=(f"claimed by hasSystemFeature; the {service} service answers ({basis.get('detail', '')})"
                      if backed else f"claimed by hasSystemFeature, but the {service} service is {verdict}: "
                                     "the app is told the hardware exists and finds none"),
            provider_source=claims.get("source"),
            app_evidence=f"{len(sites)} call sites, e.g. {_site(sites[0])}",
            call_sites=len(sites),
            shim="none" if backed else f"report {feature} absent until the {service} service is provided",
        ))
    return rows


def _vulkan_version(encoded: int) -> str:
    """VK_MAKE_API_VERSION's major.minor.patch, as android.hardware.vulkan.version carries it."""
    return f"{(encoded >> 22) & 0x7f}.{(encoded >> 12) & 0x3ff}.{encoded & 0xfff}"


def vulkan_feature_rows(scan: dict[str, Any], claims: dict[str, Any],
                        runtime_libraries: list[str] | None) -> list[dict[str, Any]]:
    """An app that asks for android.hardware.vulkan.version must get the answer its native side
    finds. Godot checks the feature in Java before it makes a Vulkan view, and its engine probes
    libvulkan on its own: with the runtime's libvulkan working and the feature unclaimed, the Java
    side fell back to an OpenGL view that never hands the engine a window, while the engine chose
    Vulkan, failed on the null window and called its renderer through a null pointer (duckrun,
    playmaker)."""
    feature = "android.hardware.vulkan.version"
    sites = [q for q in scan["inventory"].get("feature_queries") or [] if q.get("feature") == feature]
    if not sites:
        return []
    loader = "libvulkan.so" in (runtime_libraries or [])
    claimed = feature in claims.get("claimed", [])
    version = (claims.get("versions") or {}).get(feature)
    if not claimed and not loader:
        return []
    if claimed and loader:
        verdict, shim_class, effort = "supplied", "C0", "verify"
        provider = (f"claimed at Vulkan {_vulkan_version(version) if version else '(version unread)'}; the "
                    "runtime's libvulkan forwards to OH's loader with VK_KHR_android_surface")
        shim = "none"
    elif loader:
        verdict, shim_class, effort = "contradicted", "C1", "XS"
        provider = ("reported absent while the runtime's libvulkan answers: an engine that checks the feature "
                    "in Java and probes Vulkan natively takes two paths")
        shim = "claim android.hardware.vulkan.version at the board's Vulkan API version"
    else:
        verdict, shim_class, effort = "contradicted", "C5", "S"
        provider = "claimed, but the runtime ships no libvulkan"
        shim = "report android.hardware.vulkan.version absent until a Vulkan loader is staged"
    return [_row(
        "package-manager", f"feature:{feature}", "Vulkan feature against the runtime's Vulkan",
        oh_touchpoint="OH's Vulkan loader (VK_OHOS_surface) and the board's ICD",
        verdict=verdict, shim_class=shim_class, effort=effort, confidence=STATIC,
        provider=provider, provider_source=claims.get("source"),
        app_evidence=f"{len(sites)} call site{'s' if len(sites) != 1 else ''}, e.g. {_site(sites[0])}",
        call_sites=len(sites),
        seen_blocking=["duckrun, playmaker (Godot 4.5: OpenGL view, Vulkan engine, null native window)"],
        shim=shim,
    )]


def weak_api_rows(weak: list[dict[str, Any]], shim_exports: set[str]) -> list[dict[str, Any]]:
    """Weak imports of the NDK's API that nothing on the board defines (ohresolve.weak_missing). The
    loader binds them to 0; an app calls one once the device reports an API level that has it, and a
    call to 0 is a SIGSEGV with nothing in the log. The bionic shim, preloaded, can define them."""
    if not weak:
        return []
    open_ = [item for item in weak if item["symbol"] not in shim_exports]
    shown = open_ or weak
    surfaces = sorted({item["surface"] for item in shown})
    return [_row(
        "native-symbols", "ndk:weak-api",
        f"Weak NDK imports nothing on the board defines ({', '.join(i['symbol'] for i in shown[:4])}"
        + (" ..." if len(shown) > 4 else "") + ")",
        oh_touchpoint="the loader binds an undefined weak import to 0; the app checks the device's API level, "
                      "not the symbol",
        verdict="missing" if open_ else "supplied", shim_class="C1", effort="S" if open_ else "verify",
        confidence=STATIC, open_symbols=[i["symbol"] for i in open_][:16],
        provider=("the bionic shim defines them" if not open_ else
                  f"{len(open_)} of {len(weak)} undefined: a call jumps to address 0"),
        app_evidence="; ".join(f"{i['symbol']} ({i['surface']}): {', '.join(i['importing_libraries'][:2])}"
                               for i in shown[:4]),
        libraries=sorted({name.rsplit("/", 1)[-1] for i in shown for name in i["importing_libraries"]}),
        crash_kinds=["null-call"],
        seen_blocking=["fennec (its font-list thread called ASystemFontIterator_open, API 29, through a PLT slot "
                       "holding 0)"],
        shim="define the " + "/".join(surfaces) + " functions in the bionic shim, answering as the board can",
    )]


def symbol_version_rows(oh_missing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Imports a library defines, but under another symbol version. OH's loader binds a versioned
    import to a versioned library only under the same version name, so the load fails as if the
    symbol were absent: Messenger's libcore.so asked for __system_property_read_callback@LIBC_O, and
    the bionic shim defined it under LIBC."""
    mismatched = [item for item in oh_missing if item.get("version_mismatch")]
    if not mismatched:
        return []
    return [_row(
        "native-symbols", "abi:symbol-version",
        "Imports defined under another symbol version (" + ", ".join(i["symbol"] for i in mismatched[:4])
        + (" ..." if len(mismatched) > 4 else "") + ")",
        oh_touchpoint="OH musl's loader: a versioned import matches a versioned library only by version name",
        verdict="missing", shim_class="C1", effort="XS", confidence=STATIC,
        open_symbols=[f"{i['symbol']}@{'/'.join(i['version_mismatch']['wanted'])} "
                      f"(defined @{'/'.join(i['version_mismatch']['defined'])})" for i in mismatched][:12],
        app_evidence="; ".join(f"{i['symbol']}: {', '.join(i['importing_libraries'][:3])}" for i in mismatched[:4]),
        seen_blocking=["messenger (superpack libcore.so: __system_property_read_callback@LIBC_O)"],
        shim="define the symbol under the version Bionic gives it (the bionic shim's version script)",
    )]


def versioned_clash_rows(clashes: list[dict[str, Any]], shim_definitions: dict[str, set[str]]) -> list[dict[str, Any]]:
    """Imports versioned against the app's own library that a board library without symbol versions
    also defines (ohresolve.versioned_clashes). OH's loader binds them to the board's copy, searched
    first; the bionic shim restores Android's binding for the names it defines forwarders for at
    that version (contracts.shim_versioned_definitions), as non-default versions that call the app
    library's own definitions. A version the shim covers for malloc and free says nothing of its
    operator delete: Fennec's sized delete still bound to a libc++'s."""
    if not clashes:
        return []
    forwarded = lambda c: c["symbol"] in (shim_definitions.get(c["version"], set())
                                          | shim_definitions.get(c["version"] + ".so", set()))
    supplied = sorted({c["version"] for c in clashes if forwarded(c)})
    open_ = [c for c in clashes if not forwarded(c)]
    shown = open_ or clashes
    provider = []
    if supplied:
        provider.append("the bionic shim defines non-default " + "/".join(v + ".so" for v in supplied)
                        + " forwarders that call the app library's own definitions, for "
                        + str(sum(forwarded(c) for c in clashes)) + " of these names")
    if open_:
        provider.append("nothing under " + "/".join(sorted({c["version"] + ".so" for c in open_}))
                        + " precedes the board's unversioned copy, so the import binds to it")
    return [_row(
        "native-symbols", "abi:versioned-import-clash",
        "Imports versioned against the app's own libraries, also defined unversioned on the board ("
        + ", ".join(f"{c['symbol']}@{c['version']}" for c in shown[:4]) + (" ..." if len(shown) > 4 else "") + ")",
        oh_touchpoint="OH musl's check_verinfo: an import naming its version by hash matches a library without versions",
        verdict="missing" if open_ else "supplied", shim_class="C1", effort="S" if open_ else "verify",
        confidence=STATIC, provider="; ".join(provider),
        open_symbols=[f"{c['symbol']}@{c['version']}" for c in shown][:16],
        app_evidence="; ".join(f"{c['symbol']}: {', '.join(c['importing_libraries'][:3])}" for c in shown[:4]),
        libraries=sorted({name for c in shown for name in c["importing_libraries"]}),
        # A crash it explains runs in one of the clashing names, or in musl's allocator for one of them.
        crash_symbols="^(" + "|".join(sorted({re.escape(c["symbol"]) for c in shown}
                                              | ({"__libc_\\w+", "get_meta"} if {c["symbol"] for c in shown}
                                                 & {"malloc", "free", "calloc", "realloc"} else set())))
                      + r")\b",
        seen_blocking=["fennec (libxul freed with musl's free what libmozglue's mozjemalloc allocated)"],
        shim="none" if not open_ else "define the open names under their version in the bionic shim, forwarding to "
                                      "the app library's definitions",
    )]


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
    callers = model.get("callers", {"packaged": model["scope"] == "packaged-libraries", "written": False})
    written = sorted({elf.get("soname") or elf["name"].rsplit("/", 1)[-1] for elf in ohresolve.target_elfs(scan)
                      if elf.get("origin") == "unpacked"
                      and contracts.LIBC_CONSTANT_NAMESPACE_CALLS & set(elf.get("undefined_symbols", []))})
    covered = (model["scope"] == "packaged-libraries" and not untranslated and callers.get("packaged")
               and (callers.get("written") or not written))
    return [_row(
        "native-symbols", "libc:constant-namespace",
        "libc calls carrying a constant each libc numbers differently (" + ", ".join(sorted(importers)) + ")",
        oh_touchpoint="OH musl: the same selector number means a different limit than in bionic",
        verdict="supplied" if covered else "missing", shim_class="C0" if covered else "C2",
        effort="verify" if covered else "S", confidence=STATIC,
        provider=("the bionic shim translates them by name for the app's packaged libraries"
                  + (" and the ones it writes" if written else "")
                  if covered else
                  f"the shim translates them for packaged libraries, not the {len(written)} the app writes "
                  f"({', '.join(written[:3])})" if written and callers.get("packaged") else
                  f"the shim translates {', '.join(model['translated'])} for {model['scope'].replace('-', ' ')}"
                  if model["translated"] else "nothing translates them: musl answers a different limit"),
        provider_source=model["source"],
        app_evidence="; ".join(f"{symbol}: {len(names)} libraries, e.g. {', '.join(sorted(names)[:3])}"
                               for symbol, names in sorted(importers.items())),
        shim="translate the selector by name at the libc boundary for every library built against bionic; "
             "the call resolves and returns a plausible number either way, so nothing fails at load time",
    )]


def signal_abi_rows(scan: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """Signal calls made with bionic's structures. Passed to musl as they are, a sigaction installs
    bionic's flags word as the handler (0x18000804 in TikTok's and CapCut's chains) and writes a
    152-byte old action into a 32-byte one; sigemptyset writes 128 bytes into 8."""
    names = contracts.SIGNAL_ABI_CALLS | contracts.SIGNAL_ABI_CALLS_64
    importers: dict[str, list[str]] = defaultdict(list)
    written: set[str] = set()
    lookups: dict[str, list[str]] = {}
    for elf in ohresolve.target_elfs(scan):
        name = elf.get("soname") or elf["name"].rsplit("/", 1)[-1]
        used = names & {s.split("@")[0] for s in elf.get("undefined_symbols", []) + elf.get("undefined_weak_symbols", [])}
        for symbol in used:
            importers[symbol].append(name)
        if used and elf.get("origin") == "unpacked":
            written.add(name)
        if elf.get("signal_lookups"):
            lookups[name] = elf["signal_lookups"]
    if not importers and not lookups:
        return []
    scope = model["scope"]
    untranslated = sorted(set(importers) - set(model["translated"]))
    open_ = (untranslated + ([] if scope.get("packaged") else ["packaged callers"])
             + (["libraries written at run time"] if written and not scope.get("written") else [])
             + (["lookups by name"] if lookups and not model.get("dlsym") else []))
    return [_row(
        "native-symbols", "abi:signal",
        "Signal calls with bionic's structures (" + ", ".join(sorted(importers) or sorted({n for v in lookups.values() for n in v})) + ")",
        oh_touchpoint="OH musl: struct sigaction 152 bytes, handler first; sigset_t 128 bytes (bionic: 32, flags first; 8)",
        verdict="supplied" if not open_ else "missing", shim_class="C2", effort="verify" if not open_ else "S",
        confidence=STATIC, provider=("the bionic shim translates them for every bionic-built caller" if not open_ else
                                     "not translated for: " + ", ".join(open_)),
        provider_source=model.get("source"), open_symbols=open_[:12],
        app_evidence="; ".join([f"{symbol}: {len(libs)} libraries, e.g. {', '.join(sorted(libs)[:3])}"
                                for symbol, libs in sorted(importers.items())][:4]
                               + ([f"looked up by name in {', '.join(sorted(lookups)[:4])}"] if lookups else [])
                               + ([f"{len(written)} of the importers written at run time"] if written else [])),
        seen_blocking=["whatsapp (a rerun of r83: its Breakpad setup, running from a wl-exec copy, got a 152-byte old action in a "
                       "32-byte struct and freed the std::string it clobbered, 4 s in)"],
        suspected_blocking=["capcut, tiktok (a SIGSEGV handler of 0x18000804, bionic flags in musl's handler slot; "
                            "heap faults in musl's allocator)"],
        shim="translate for every bionic-built caller, the libraries the app writes included, and answer a dlsym of "
             "these names from such a caller with the translating version",
    )]


def static_mutex_rows(scan: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """Mutexes a library initializes with Bionic's static recursive or error-checking initializer and
    then locks (scanner.bionic_static_mutexes). musl reads the type from the low bits of the word
    Bionic put it in bits 14-15 of, so both are normal mutexes to it: a recursive relock deadlocks
    on its own thread, an error-checking one no longer reports EDEADLK."""
    found: dict[str, dict[str, int]] = {}
    for elf in ohresolve.target_elfs(scan):
        if elf.get("bionic_static_mutexes"):
            found[elf.get("soname") or elf["name"].rsplit("/", 1)[-1]] = elf["bionic_static_mutexes"]
    if not found:
        return []
    open_ = [name for name in contracts.STATIC_MUTEX_LOCKS if name not in model.get("adopted", [])]
    kinds = sorted({kind for counts in found.values() for kind in counts})
    return [_row(
        "native-symbols", "abi:static-mutex-init",
        f"Bionic static {' and '.join(kinds)} mutex initializers ({', '.join(sorted(found)[:4])})",
        oh_touchpoint="OH musl: the mutex type is the low bits of the first word (Bionic: bits 14-15, 0x4000 recursive, "
                      "0x8000 error-checking); musl locks either as a normal mutex",
        verdict="supplied" if not open_ else "missing", shim_class="C2", effort="verify" if not open_ else "S",
        confidence=STATIC,
        provider=("the bionic shim's lock calls convert an unlocked mutex holding Bionic's type word to musl's "
                  "type before musl locks it" if not open_ else "not converted in: " + ", ".join(open_)),
        provider_source=model.get("source"), open_symbols=open_,
        app_evidence="; ".join(f"{name}: " + ", ".join(f"{count} {kind}" for kind, count in sorted(counts.items()))
                               + " locked as initialized" for name, counts in sorted(found.items())[:6]),
        libraries=sorted(found),
        seen_blocking=["discord (r84: sentry-native's sentry_init holds its options lock and takes it again in "
                       "sentry_close; the crash-reporting thread never left initSentryNative and the main thread "
                       "waited out two 30 s application-initialization timeouts, first frame at 62.9 s)"],
        shim="convert the type word of an unlocked mutex holding Bionic's static initializer to musl's recursive or "
             "error-checking type before musl's lock sees it; a held mutex is left alone",
    )]


def bionic_tls_rows(scan: dict[str, Any]) -> list[dict[str, Any]]:
    """Libraries that read Bionic's TLS slots directly (scanner.bionic_tls_slots). OH musl lays out
    the words above the thread pointer differently, and no shim can change what a load from them
    reads: the thread pointer's layout is the loader's."""
    found: dict[str, dict[str, int]] = {}
    for elf in ohresolve.target_elfs(scan):
        if elf.get("bionic_tls_slots"):
            found[elf.get("soname") or elf["name"].rsplit("/", 1)[-1]] = elf["bionic_tls_slots"]
    if not found:
        return []
    slots = sorted({slot for counts in found.values() for slot in counts})
    return [_row(
        "native-symbols", "abi:bionic-tls-slots",
        f"Bionic TLS slots read directly ({', '.join(slots)}: {', '.join(sorted(found)[:4])}"
        + (" ..." if len(found) > 4 else "") + ")",
        oh_touchpoint="OH musl's thread pointer: its own reserved slots lie below it, a 16-byte gap and the "
                      "static TLS blocks above it, where Bionic keeps eight slots",
        verdict="missing", shim_class="C6", effort="L", confidence=STATIC,
        provider="none: what a load from the thread pointer reads is the loader's layout",
        app_evidence="; ".join(f"{name}: " + ", ".join(f"{count} {slot}" for slot, count in sorted(counts.items()))
                               for name, counts in sorted(found.items())[:6]),
        libraries=sorted(found), crash_kinds=["fault"],
        seen_blocking=["capcut (its security library's inlined vfork cleared pthread_internal_t's cached pid "
                       "through the thread id slot, which held -1 on OH: a store to 0x13)"],
        shim="none from a library: Bionic's slots above the thread pointer would need a loader that lays them out",
    )]


def thread_handle_rows(scan: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """Threads created with their handle stored inside the object they are handed
    (scanner.thread_handles_in_argument). Bionic stores the handle before the thread runs; musl
    after clone returns, so a thread that first reads its own handle from that object can read 0."""
    found: dict[str, int] = {}
    for elf in ohresolve.target_elfs(scan):
        if elf.get("thread_handle_in_argument"):
            found[elf.get("soname") or elf["name"].rsplit("/", 1)[-1]] = elf["thread_handle_in_argument"]
    if not found:
        return []
    ordered = model.get("ordered", False)
    return [_row(
        "native-symbols", "abi:thread-handle-order",
        f"threads handed the object that holds their own handle ({', '.join(sorted(found)[:4])})",
        oh_touchpoint="OH musl: pthread_create stores *thread after clone returns, and the thread may already run "
                      "(Bionic stores it first and holds the thread until then)",
        verdict="supplied" if ordered else "missing", shim_class="C2", effort="verify" if ordered else "S",
        confidence=STATIC,
        provider=("the bionic shim's pthread_create starts an Android caller's thread in a routine that waits until "
                  "the handle is stored" if ordered else "pthread_create is musl's: the thread may run before *thread "
                                                         "is stored"),
        provider_source=model.get("source"),
        app_evidence="; ".join(f"{name}: {count} call{'s' if count > 1 else ''} pthread_create(&obj->thread, ..., obj)"
                               for name, count in sorted(found.items())[:6])
                     + " (a risk: whether the thread reads the field first is not seen)",
        libraries=sorted(found), crash_symbols=r"^pthread_",
        seen_blocking=["tiktok (r85: vcbasekit's thread named itself with pthread_setname_np(this->thread_, ...) "
                       "before pthread_create stored thread_, and died in musl's pthread_setname_np on handle 0; it "
                       "drew in the run before)"],
        shim="start the thread in a routine that waits until pthread_create has stored the handle, as Bionic's "
             "startup lock does",
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
    )] + [_row(
        "security", f"jca:{name}", f'Android keystore operations provider ("{name}")',
        oh_touchpoint="JCA provider list (Android installs it beside AndroidKeyStore)",
        verdict="supplied" if name in keystore.get("registered", {}) else "missing",
        shim_class="C0" if name in keystore.get("registered", {}) else "C4",
        effort="verify" if name in keystore.get("registered", {}) else "S", confidence=STATIC,
        provider=("registered: operations on keystore keys" if name in keystore.get("registered", {})
                  else f'not registered: {name} lookups throw NoSuchProviderException'),
        provider_source=keystore.get("registered", {}).get(name),
        app_evidence=", ".join(sorted({r["owner"] for r in named if r.get("provider") == name})[:4]),
        seen_blocking=["jiyi (batch-13)", "toolbox (batch-11)"] if name == "AndroidKeyStoreBCWorkaround" else [],
        shim=f'register a "{name}" provider serving Cipher/Signature/Mac for the keystore\'s keys',
    ) for name in sorted({r.get("provider") for r in named} - {"AndroidKeyStore", None, "(Provider object)"})]


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
    # Packaged only: a library the app writes at run time loads in the Android namespace already.
    for elf in ohresolve.packaged_elfs(scan):
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


# libc entry points whose argument or result structures differ between Bionic and OH musl.
NETWORK_ABI_IMPORTS = {"getaddrinfo"}


def launcher_namespace_option(manifest_root: Path | None) -> dict[str, Any]:
    path = manifest_root / "tools/probe_source_app.py" if manifest_root else None
    if path is None or not path.exists():
        return {"present": False, "source": None, "net": {"present": False, "source": None}}
    text = path.read_text(errors="replace")

    def find(option: str) -> dict[str, Any]:
        match = re.search(re.escape(option) + r"'", text)
        return {"present": bool(match),
                "source": f"manifest/tools/probe_source_app.py:{text.count(chr(10), 0, match.start()) + 1}" if match else None}

    found = find("--android-native-target")
    found["net"] = find("--android-native-net-target")
    return found


def bionic_loader_model(westlake_root: Path | None, manifest_root: Path | None = None) -> dict[str, str | None]:
    """Where Westlake supplies what OH's loader does not, as source locations.

    code_cache_copy: the bionic shim loads a library app storage may not map executable from a copy
    in code_cache. android_relr_launcher: the launcher stages the APK's libraries with
    DT_ANDROID_RELR renumbered to DT_RELR; android_relr_shim: the shim does the same for libraries
    an app writes at run time. null_entries_launcher: the launcher drops null init/fini array entries
    from the libraries it stages. funopen_unbuffered: the shim's funopen avoids OH's buffered
    fopencookie refill, which overwrites what it has just read.
    """
    def find(relative: str, marker: str, root: Path | None = westlake_root) -> str | None:
        path = root / relative if root else None
        if path is None or not path.exists():
            return None
        text = path.read_text(errors="replace")
        index = text.find(marker)
        return f"{relative}:{text.count(chr(10), 0, index) + 1}" if index >= 0 else None

    return {"code_cache_copy": find("framework/webview-shim/webview_bionic_shim.c", "westlake_load_from_code_cache("),
            "android_relr_launcher": find("tools/probe_source_app.py", "def android_relr_retagged(", manifest_root),
            "android_relr_shim": find("framework/webview-shim/android_relocs.c", "wl_write_loadable_copy("),
            "null_entries_launcher": find("tools/probe_source_app.py", "def init_array_sanitized(", manifest_root),
            "funopen_unbuffered": find("framework/webview-shim/webview_bionic_shim.c", "setvbuf(file, NULL, _IONBF, 0)"),
            "apk_member_redirect": find("framework/webview-shim/webview_bionic_shim.c", 'strstr(filename, ".apk!/lib/")'),
            "open_by_name": find("framework/webview-shim/webview_bionic_shim.c", "westlake_open_lib_by_name("),
            "written_shares_packaged": find("framework/webview-shim/webview_bionic_shim.c",
                                            "westlake_shared_with_default("),
            # art-build sits beside the westlake checkout; the runtime's init array sanitizer.
            "sanitizer_knows_packed_rela": find("stubs/link_stubs_arm64.cc", "case 0x60000011:",
                                                westlake_root.parent / "art-build")}


def native_loading_rows(facts: dict[str, Any], scan: dict[str, Any], launcher_extracts: dict[str, Any],
                        board_paths: list[str] | None = None, namespace_option: dict[str, Any] | None = None,
                        runtime_libraries: list[str] | None = None,
                        loader: dict[str, str | None] | None = None) -> list[dict[str, Any]]:
    rows = []
    elfs = ohresolve.target_elfs(scan)
    packaged = ohresolve.packaged_elfs(scan)
    unpacked = [elf for elf in elfs if elf.get("origin") == "unpacked"]
    shadowed, targets = shadowed_libraries(scan, board_paths or [])
    # The graph is by DT_NEEDED name (the SONAME), but the launcher routes files by name, and a name it
    # cannot find stops the launch: TikTok's libeffect_plugin.so is libeffect.so, and r77 and r82
    # never launched it ("Android namespace target is not a pinned APK DSO").
    files: dict[str, str] = {}
    for elf in packaged:
        base = elf["name"].rsplit("/", 1)[-1]
        files.setdefault(elf.get("soname") or base, base)
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
            launch_args=[arg for name in targets for arg in ("--android-native-target", files.get(name, name))],
        ))
        # In that namespace libandroid.so is the WebView shim's, whose AAsset* go through a companion
        # (libwestlake_asset_bridge.so) to the framework's asset manager. React Native loads its
        # bundle that way and reported "Unable to load script" when the companion was not shipped.
        asset_users = sorted({elf.get("soname") or Path(elf["name"]).name for elf in elfs
                              if (elf.get("soname") or Path(elf["name"]).name) in targets
                              and {"AAssetManager_fromJava", "AAssetManager_open"}
                              & {n.split("@")[0] for n in elf.get("undefined_symbols", [])}})
        if asset_users:
            bridge = "libwestlake_asset_bridge.so" in (runtime_libraries or [])
            rows.append(_row(
                "native-loading", "ns:assets", f"NDK assets opened from the isolated Android namespace ({', '.join(asset_users[:3])})",
                oh_touchpoint="the Android namespace's libandroid.so (WebView shim) -> the framework's AssetManager2",
                verdict="supplied" if bridge else "missing", shim_class="C1", effort="verify" if bridge else "S",
                confidence=STATIC,
                provider=("the runtime ships the asset companion the shim loads" if bridge else
                          "the shim's AAsset* need libwestlake_asset_bridge.so, which the runtime does not ship: "
                          "AAssetManager_fromJava returns null there"),
                app_evidence=f"{len(asset_users)} namespace-routed libraries import AAssetManager_*",
                seen_blocking=["nori, rushhour, marlin, mobile, siftrecipes (React Native: Unable to load script)"],
                shim="ship the companion in the parent namespace and let the Android namespace inherit it",
            ))
    # Packaged only: the launcher names a library to translate by file, and one the app writes at run
    # time is covered by --android-native-net-app-libraries (load:app-storage-exec below).
    resolvers = sorted({elf.get("soname") or Path(elf["name"]).name for elf in packaged
                        if NETWORK_ABI_IMPORTS & {name.split("@")[0] for name in
                                                  elf.get("undefined_symbols", []) + elf.get("undefined_weak_symbols", [])}})
    if resolvers:
        option = (namespace_option or {}).get("net") or {"present": False, "source": None}
        rows.append(_row(
            "native-loading", "abi:addrinfo",
            f"Packaged libraries that resolve hosts through libc ({', '.join(resolvers[:4])}"
            + (" ..." if len(resolvers) > 4 else "") + ")",
            oh_touchpoint="OH musl getaddrinfo: struct addrinfo orders ai_addr and ai_canonname the other way from Bionic",
            verdict="supplied" if option["present"] else "missing", shim_class="C2", effort="XS" if option["present"] else "M",
            confidence=STATIC,
            provider=("the launcher translates addrinfo for the libraries it is given (--android-native-net-target)"
                      if option["present"] else "no translation: every host lookup these libraries make is misread"),
            provider_source=option["source"],
            app_evidence=f"{len(resolvers)} APK libraries import getaddrinfo",
            seen_blocking=["hacki (batch-12), fixed by the launch args", "fdroid2 (batch-14), fixed by the launch args"],
            shim="route these libraries through the network ABI translation: " + " ".join(resolvers),
            launch_args=[arg for name in resolvers for arg in ("--android-native-net-target", name)],
        ))
    # funopen: the bionic shim supplies it over OH's fopencookie. A buffered cookie FILE on OH is
    # refilled by calling the reader with the FILE's own buffer, which cookieread also uses for its
    # last byte, so every refill overwrote what it had read (probes/runtime-answers). superpack reads
    # its archive through one: Facebook, Instagram and Messenger failed its magic check.
    funopen_users = sorted({elf.get("soname") or Path(elf["name"]).name for elf in elfs
                            if "funopen" in {n.split("@")[0] for n in
                                             elf.get("undefined_symbols", []) + elf.get("undefined_weak_symbols", [])}})
    if funopen_users:
        fixed = (loader or {}).get("funopen_unbuffered")
        rows.append(_row(
            "native-loading", "abi:funopen",
            f"funopen streams ({', '.join(funopen_users[:4])}" + (" ..." if len(funopen_users) > 4 else "") + ")",
            oh_touchpoint="OH musl fopencookie: a buffered refill (__fill_buffer -> cookieread into f->buf) "
                          "overwrites the bytes it just read",
            verdict="supplied" if fixed else "missing", shim_class="C2", effort="verify" if fixed else "S",
            confidence=STATIC, probe="probes/runtime-answers",
            provider=("the bionic shim's funopen makes the FILE unbuffered and buffers in its cookie"
                      if fixed else "the shim's funopen is buffered: reads past the first refill are corrupted"),
            provider_source=fixed,
            app_evidence=f"{len(funopen_users)} APK libraries import funopen",
            seen_blocking=["facebook, instagram, messenger (superpack: could not extract file from archive)"],
            shim="keep funopen FILEs unbuffered on OH, buffering inside the cookie",
        ))
    if not facts["extract_native_libs"] and packaged:
        rows.append(_row(
            "native-loading", "load:in-apk", f"Libraries mapped straight out of the APK ({len(packaged)} .so, extractNativeLibs=false)",
            oh_touchpoint="OH dynamic linker (cannot map zip!/ members: board test 2026-09-18)",
            verdict="supplied" if launcher_extracts["present"] else "missing",
            shim_class="C0" if launcher_extracts["present"] else "C3",
            effort="verify" if launcher_extracts["present"] else "S", confidence=STATIC,
            provider="launcher extracts split libraries to a real directory" if launcher_extracts["present"] else "none",
            provider_source=launcher_extracts.get("source"),
            shim="extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too)",
        ))
    # Libraries an app copies into its own storage and loads from there. Android maps them
    # executable; OH's policy refuses every app-data directory but code_cache (probes/runtime-answers:
    # files, cache and no_backup fail with errno 13). WhatsApp's SoLoader unpacks every library into
    # files/decompressed/libs.spo/; CapCut's libmetasec_ov.so failed the same way.
    loader = loader or {}
    inventory = scan.get("inventory", {})
    loaders = sorted({m.get("owner", "").split("/")[2] for m in inventory.get("declared_native_methods", [])
                      if m.get("owner", "").startswith("Lcom/facebook/soloader/")})
    path_loads = [c for c in inventory.get("load_library_calls", []) if c.get("api") == "load"]
    # A library loaded from inside an APK (<apk>!/lib/<abi>/<name>): OH's loader maps the stored member
    # itself and so gets the APK's bytes, without the fixes the launcher applies to the copy it
    # stages. SoLoader does this with a split APK: Threads' libc++_shared.so kept DT_ANDROID_RELR.
    unfixed = sorted({elf.get("soname") or Path(elf["name"]).name for elf in packaged
                      if elf.get("split_apk") and (elf.get("android_relocation_tags")
                                                   or (elf.get("null_array_entries") or {}).get("init"))})
    if loaders and unfixed:
        redirect = loader.get("apk_member_redirect")
        rows.append(_row(
            "native-loading", "load:apk-member",
            f"Split-APK libraries SoLoader may load in place ({', '.join(unfixed[:4])}" + (" ..." if len(unfixed) > 4 else "") + ")",
            oh_touchpoint="OH musl dlopen: maps a stored zip member (<apk>!/lib/<abi>/<name>) itself",
            verdict="supplied" if redirect else "missing", shim_class="C3", effort="verify" if redirect else "S",
            confidence=STATIC, provider=("the bionic shim loads the launcher's staged copy for such a path" if redirect else
                                         "none: the in-place load bypasses the staged, fixed copy"),
            provider_source=redirect,
            app_evidence=f"SoLoader is in the app; {len(unfixed)} split-APK libraries need a staging fix",
            seen_blocking=["threads (r83 and a rerun: libc++_shared.so from split_config.arm64_v8a.apk, constructor "
                           "at its link-time address)"],
            shim="answer an APK-member path with the staged copy of the same library",
        ))
    # A library Java loads that names a packaged sibling in DT_NEEDED. OH's loader matches DT_NEEDED
    # against short names only, and a library opened by path has none: a sibling loaded by path first
    # (ART opens app libraries by path) is loaded again for its dependent. Chaquopy loads
    # libpython3.11.so, then libchaquopy_java.so, and econverter ran two Python runtimes.
    java_loaded = {"lib" + call["value"] + ".so" for call in inventory.get("load_library_calls", [])
                   if call.get("api") == "loadLibrary" and call.get("value")}
    packaged_names = {elf.get("soname") or Path(elf["name"]).name for elf in packaged}
    dependents = sorted({name for elf in packaged
                         for name in [elf.get("soname") or Path(elf["name"]).name]
                         if name in java_loaded and set(elf.get("needed") or []) & (packaged_names - {name})})
    if dependents:
        by_name = loader.get("open_by_name")
        rows.append(_row(
            "native-loading", "load:needed-sibling",
            f"Java-loaded libraries that need a packaged sibling ({', '.join(dependents[:4])}"
            + (" ..." if len(dependents) > 4 else "") + ")",
            oh_touchpoint="OH musl: DT_NEEDED is matched against short names; a library opened by path has none",
            verdict="supplied" if by_name else "missing", shim_class="C3", effort="verify" if by_name else "S",
            confidence=STATIC,
            provider=("the bionic shim opens an app library by name where the name finds the same file"
                      if by_name else "none: a sibling ART loaded by path is loaded a second time for its dependent"),
            provider_source=by_name,
            app_evidence=f"{len(dependents)} libraries loaded through System.loadLibrary name packaged siblings in DT_NEEDED",
            seen_blocking=["econverter (Chaquopy: two copies of libpython3.11.so; a call through a null slot)"],
            shim="open app libraries by name where the name finds the same file, so a later DT_NEEDED matches them",
        ))
    # A Java-loaded library relocated only by Android's packed format, with constructors. The slots
    # the packed table fills read as zero in the file; a sanitizer that does not recognize the format
    # drops them all as null (libwaze.so: 2189, libsignal_jni.so: 2).
    # Java loads a library by a name the scan may not see (libsignal's loader computes it); a packaged
    # library no other packaged library needs is loaded from Java too, since nothing else pulls it in.
    needed_by_siblings = {name for elf in packaged for name in elf.get("needed") or []}
    packed = sorted({(elf.get("soname") or Path(elf["name"]).name, elf["packed_init_entries"]) for elf in packaged
                     if elf.get("packed_init_entries")
                     and ((elf.get("soname") or Path(elf["name"]).name) in java_loaded
                          or (elf.get("soname") or Path(elf["name"]).name) not in needed_by_siblings)})
    if packed:
        known = loader.get("sanitizer_knows_packed_rela")
        rows.append(_row(
            "native-loading", "load:packed-init-array",
            "Java-loaded libraries whose constructors packed relocations fill ("
            + ", ".join(f"{name}: {count}" for name, count in packed[:4]) + (" ..." if len(packed) > 4 else "") + ")",
            oh_touchpoint="none: the runtime's own init array sanitizer, before ART opens the library",
            verdict="supplied" if known else "missing", shim_class="C3", effort="verify" if known else "XS",
            confidence=STATIC,
            provider=("the sanitizer leaves a library with DT_ANDROID_REL or DT_ANDROID_RELA as it is" if known else
                      "the sanitizer does not recognize DT_ANDROID_RELA: it reads the slots as null and drops every "
                      "constructor"),
            provider_source=known,
            app_evidence=f"{len(packed)} libraries System.loadLibrary names",
            libraries=[name for name, _ in packed],
            seen_blocking=["waze (all 2189 of libwaze.so's constructors dropped; an abort in its own code)"],
            shim="leave libraries in Android's packed relocation format to the loader, which applies the table",
        ))
    # A library the app writes at run time that needs one it packages. The shim loads written
    # libraries in a namespace of its own; with no Android namespace ART's loader put the packaged
    # ones in the default namespace, and a written library found its packaged dependency again on
    # its own path: Chaquopy's extension modules loaded a second, uninitialized libpython3.11.so
    # (econverter, werewolvesgame). Chaquopy is recognized by its packaged libraries even when no
    # run has harvested the modules it writes.
    written_needs = sorted({name for elf in unpacked for name in elf.get("needed") or [] if name in packaged_names})
    # By file name: libchaquopy_java.so's SONAME carries the Python version (libchaquopy_java-3.11.so).
    files = {Path(elf["name"]).name for elf in packaged}
    chaquopy = "libchaquopy_java.so" in files and any(n.startswith("libpython") for n in files)
    if written_needs or chaquopy:
        shared = loader.get("written_shares_packaged")
        needs = written_needs or sorted(n for n in files if n.startswith("libpython"))
        rows.append(_row(
            "native-loading", "load:written-needs-packaged",
            f"Libraries written at run time that need packaged ones ({', '.join(needs[:4])}"
            + (" ..." if len(needs) > 4 else "") + ")",
            oh_touchpoint="OH musl namespaces: a library is shared across namespaces only by an inherit list",
            verdict="supplied" if shared else "missing", shim_class="C3", effort="verify" if shared else "S",
            confidence=STATIC,
            provider=("the written-library namespace shares the APK's packaged libraries with the default namespace"
                      if shared else "none: the written library's namespace loads its packaged dependency again"),
            provider_source=shared,
            app_evidence=(f"{len(written_needs)} packaged libraries needed by harvested ones" if written_needs
                          else "Chaquopy (libchaquopy_java.so and libpython): its extension modules are written at run time"),
            libraries=needs,
            seen_blocking=["econverter, werewolvesgame (Chaquopy: a second libpython3.11.so; a call through a PLT slot "
                           "never relocated)"],
            shim="share the packaged libraries with the namespace written libraries load in",
        ))
    if loaders or path_loads or unpacked:
        copy = loader.get("code_cache_copy")
        rows.append(_row(
            "native-loading", "load:app-storage-exec",
            "Native libraries loaded from the app's own storage",
            oh_touchpoint="OH SELinux: app data files may not be mapped executable, except in code_cache",
            verdict="supplied" if copy else "missing", shim_class="C6", effort="verify" if copy else "M",
            confidence=STATIC, probe="probes/runtime-answers",
            provider=("the bionic shim's dlopen retries a refused library from a copy in code_cache/wl-exec"
                      if copy else "none"),
            provider_source=copy,
            app_evidence=(("SoLoader unpacks and loads libraries from app storage; " if loaders else "")
                          + (f"System.load with a path from {len(path_loads)} call sites; " if path_loads else "")
                          + (f"{len(unpacked)} libraries harvested from its data directory after a run"
                             if unpacked else "")).strip("; "),
            seen_blocking=["whatsapp, capcut (top-apps batch: failed to map library errno=13)"],
            shim="load such libraries from a location OH lets the app map executable (copy there first), "
                 "or allow app_data_file execute mapping for Westlake apps",
            # Such libraries are NDK code the launch cannot name in advance; they need the Bionic
            # addrinfo translation too (Messenger's superpack-unpacked liger).
            launch_args=["--android-native-net-app-libraries"],
        ))
    # Null init array entries (scanner.null_array_entries): bionic skips them, musl calls them. ART's
    # OpenNativeLibrary drops them from the library it loads, not from that library's dependencies.
    null_init = sorted({elf.get("soname") or Path(elf["name"]).name for elf in elfs
                        if (elf.get("null_array_entries") or {}).get("init")})
    if null_init:
        written = sorted({elf.get("soname") or Path(elf["name"]).name for elf in unpacked
                          if (elf.get("null_array_entries") or {}).get("init")})
        fixed = loader.get("null_entries_launcher")
        supplied = bool(fixed) and not written
        rows.append(_row(
            "native-loading", "load:null-constructors",
            f"Libraries whose init array holds null entries ({', '.join(null_init[:4])}"
            + (" ..." if len(null_init) > 4 else "") + ")",
            oh_touchpoint="OH musl do_init_fini: calls every init array entry; bionic skips 0 and -1",
            verdict="supplied" if supplied else "missing", shim_class="C3",
            effort="verify" if supplied else "XS" if not written else "S", confidence=STATIC,
            provider=(("the launcher drops them from every library it stages" if fixed else
                       "ART drops them only from a library System.loadLibrary names, not its dependencies")
                      + (f"; nothing drops them from the {len(written)} written at run time" if written else "")),
            provider_source=fixed,
            app_evidence=f"{len(null_init)} libraries", open_symbols=written[:12],
            seen_blocking=["tiktok (r83, t138: pc 0 from do_init_fini; libttffmpeg.so, a dependency of "
                           "libttmverify.so)", "toutiao (libEncryptor.so)"],
            shim="drop null and -1 entries (compacting the rest, relocations included) before the loader sees the library",
        ))
    # DT_ANDROID_RELR (scanner.ANDROID_RELOCATION_TAGS): musl skips it, so a constructor pointer
    # keeps its link-time value and the load dies calling it.
    android_relocated = sorted({elf.get("soname") or Path(elf["name"]).name for elf in elfs
                                if elf.get("android_relocation_tags")})
    if android_relocated:
        # The launcher renumbers what it stages; a library written at run time needs the shim to.
        written = sorted({elf.get("soname") or Path(elf["name"]).name for elf in unpacked
                          if elf.get("android_relocation_tags")})
        staged = len(written) < len(android_relocated)
        launcher_fix, shim_fix = loader.get("android_relr_launcher"), loader.get("android_relr_shim")
        applied = (launcher_fix or not staged) and (shim_fix or not written)
        if applied:
            provider = ("the launcher stages them with the tags renumbered to DT_RELR, which musl applies"
                        if staged else "")
            if shim_fix:
                provider += ("; " if provider else "") + "the bionic shim does the same for libraries the app writes at run time"
        elif launcher_fix and staged:
            provider = (f"the launcher renumbers only what it stages; nothing renumbers the {len(written)} "
                        "written at run time: their pointers keep link-time values")
        else:
            provider = "none: pointers the table covers keep their link-time values"
        tags = sorted({t for elf in elfs for t in elf.get("android_relocation_tags") or ()})
        rows.append(_row(
            "native-loading", "load:android-relocations",
            f"Libraries with DT_ANDROID_RELR relocations ({', '.join(android_relocated[:4])}"
            + (" ..." if len(android_relocated) > 4 else "") + ")",
            oh_touchpoint="OH musl dynamic linker: skips " + ", ".join(tags) + " (applies standard DT_RELR)",
            verdict="supplied" if applied else "missing", shim_class="C3", effort="verify" if applied else "S",
            confidence=STATIC, provider=provider,
            provider_source=(launcher_fix if staged else shim_fix) or None,
            app_evidence=f"{len(android_relocated)} APK libraries carry {', '.join(tags)}"
                         + (f", {len(written)} of them written at run time ({', '.join(written[:3])})" if written else ""),
            seen_blocking=["facebook, messenger, instagram (SIGSEGV with pc == fault addr == the library's "
                           "unrelocated INIT_ARRAY entry)"],
            shim="renumber DT_ANDROID_RELR/RELRSZ/RELRENT to DT_RELR/RELRSZ/RELRENT (same encoding); "
                 "OH's musl applies DT_RELR and DT_ANDROID_RELA itself",
        ))
    return rows


# Always present: the bionic names OH's musl loader answers for itself.
_LOADER_PROVIDED = {"libc.so", "libm.so", "libdl.so", "ld-android.so"}


# The SDK level Westlake reports (android_os_SystemProperties.cpp's table, mirrored by the bionic
# shim) and the ART its runtime is built from.
REPORTED_SDK, ART_SOURCE = 34, "AOSP 15 (API 35)"


def art_internal_rows(scan: dict[str, Any]) -> list[dict[str, Any]]:
    """Libraries that reach into ART through its C++ symbols. They find them (Westlake's libart.so
    exports every symbol; on Android they read its symbol table) and patch heap, GC, JIT and thread
    state at offsets chosen by the SDK level the device reports. Westlake reports 34 and runs an
    AOSP 15 ART, so what they write lands by Android 14's layout in Android 15's structures."""
    users = sorted(((elf.get("soname") or Path(elf["name"]).name, elf["art_internal_symbols"],
                     elf.get("art_internal_sample", []))
                    for elf in ohresolve.target_elfs(scan) if elf.get("art_internal_symbols", 0) >= 3),
                   key=lambda item: -item[1])
    if not users:
        return []
    return [_row(
        "native-symbols", "art:internals",
        f"Libraries that patch ART internals ({', '.join(name for name, _, _ in users[:4])}"
        + (" ..." if len(users) > 4 else "") + ")",
        oh_touchpoint=f"Westlake's ART: built from {ART_SOURCE}, reported as SDK {REPORTED_SDK}",
        verdict="unverified", shim_class="C2", effort="L", confidence=STATIC,
        provider="none: nothing keeps the runtime's layout to the one the reported SDK level implies",
        app_evidence="; ".join(f"{name} names {count} ({', '.join(sample[:2])})" for name, count, sample in users[:6]),
        suspected_blocking=["capcut (r83 and a rerun: musl's allocator faults about 10 s in, after libjato, "
                            "libsysoptimizer and libgodzilla-sysopt load; unconfirmed)"],
        shim="report the SDK level the runtime's ART is built from, or make these libraries' version check "
             "fail closed (most disable themselves on an unknown layout)",
    )]


def needed_library_rows(scan: dict[str, Any], board_paths: list[str] | None,
                        runtime_libraries: list[str] | None) -> list[dict[str, Any]]:
    """Libraries an APK library lists in DT_NEEDED that nothing on the device provides.

    oh-resolve checks symbols, so a whole missing library looked like a few missing symbols,
    or like nothing at all when every symbol also exists elsewhere. The loader refuses the load
    before any symbol is looked at: Fennec's libxul.so needs libmediandk.so, which neither the
    APK, the Westlake runtime nor the board ships.
    """
    if board_paths is None:
        return []
    elfs = ohresolve.target_elfs(scan)
    provided = ({(e.get("soname") or e.get("name")) for e in elfs} | {e.get("name") for e in elfs}
                | {p.rsplit("/", 1)[-1] for p in board_paths} | set(runtime_libraries or []) | _LOADER_PROVIDED)
    missing: dict[str, list[str]] = defaultdict(list)
    for elf in elfs:
        for needed in elf.get("needed", []):
            if needed not in provided:
                missing[needed].append(elf.get("soname") or elf["name"])
    if not missing:
        return []
    names = sorted(missing)
    return [_row(
        "native-loading", "load:needed-missing",
        f"Libraries named in DT_NEEDED that nothing provides ({', '.join(names)})",
        oh_touchpoint="OH dynamic linker: the load fails before symbols are resolved",
        verdict="missing", shim_class="C1", effort="L" if any(n in {"libmediandk.so", "libGLESv1_CM.so", "libcamera2ndk.so", "libaaudio.so"} for n in names) else "M",
        confidence=STATIC,
        app_evidence="; ".join(f"{n} needed by {', '.join(sorted(set(missing[n]))[:3])}" for n in names),
        open_symbols=names,
        shim="ship the library (an NDK library: build it over OH's equivalent) or confirm its importer is never loaded",
    )]


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

def bionic_shim_sources(westlake_root: Path) -> list[Path]:
    """The C sources the shim's build compiles (tools/build_bionic_shim.sh), the main one first."""
    directory = westlake_root / "framework/webview-shim"
    build = westlake_root / "tools/build_bionic_shim.sh"
    names = re.findall(r"\$W/(\w+\.c)\b", build.read_text(errors="replace")) if build.exists() else []
    sources = [directory / "webview_bionic_shim.c"] + [directory / n for n in names if n != "webview_bionic_shim.c"]
    return [path for path in sources if path.exists()]


def bionic_shim_exports(westlake_root: Path) -> set[str]:
    names: set[str] = set()
    for source in bionic_shim_sources(westlake_root):
        text = source.read_text(errors="replace")
        # A definition's parameters hold at most one level of parentheses (a function pointer); an
        # unbounded match ran from a macro call on one line into the next definition and took it.
        names |= set(re.findall(r"^(?:[A-Za-z_][\w \*]*?[\s\*])?([A-Za-z_]\w*)\s*\((?:[^;(){}]|\([^;(){}]*\))*\)\s*\{",
                                text, re.M))
        names |= set(re.findall(r"^[A-Za-z_][\w \*]*?\s\**(__sF|_ctype_)\b", text, re.M))
        # Forwarders a macro defines: WESTLAKE_ALOOPER_FORWARD(ret, name, params, args).
        names |= set(re.findall(r"^WESTLAKE_\w+_FORWARD\([^,]+,\s*(\w+)\s*,", text, re.M))
        # AConfiguration's getter/setter pairs: WL_CONFIG_FIELD(Name, field).
        for field in re.findall(r"^WL_CONFIG_FIELD\((\w+)\s*,", text, re.M):
            names |= {"AConfiguration_get" + field, "AConfiguration_set" + field}
    return {n for n in names if not n.startswith(("westlake_", "wl_")) and not n.isupper()
            and n not in {"if", "for", "while", "switch", "return", "__attribute__"}}


def launcher_extraction(manifest_root: Path | None) -> dict[str, Any]:
    if manifest_root is None:
        return {"present": False, "source": None}
    path = manifest_root / "tools/prepare_app.py"
    if not path.exists():
        return {"present": False, "source": None}
    text = path.read_text(errors="replace")
    match = re.search(r"def extract_libraries", text)
    return {"present": bool(match), "source": f"manifest/tools/prepare_app.py:{text.count(chr(10), 0, match.start()) + 1}" if match else None}


ENGINE_LIBRARIES = {
    "libgdx.so": "libGDX", "libarc.so": "Arc (a libGDX fork)", "libflutter.so": "Flutter", "libSDL2.so": "SDL", "libunity.so": "Unity",
    "libgodot_android.so": "Godot", "libcocos2dcpp.so": "Cocos2d-x", "liblove.so": "LOVE",
    "libUE4.so": "Unreal", "libmain.so": "a NativeActivity engine",
}


def surfaceview_model(westlake_root: Path | None, manifest_root: Path | None,
                      runtime_libraries: list[str] | None) -> dict[str, Any]:
    """Whether the provider gives a SurfaceView an OH surface of its own, and Vulkan an Android surface.

    Three pieces, each read from where it lives: the window adapter's attachSurfaceView, the pinned
    frameworks-base patch whose SurfaceView calls it, and the runtime's libvulkan.so shim (Flutter's
    Impeller creates its surface with vkCreateAndroidSurfaceKHR, which OH's loader lacks).
    """
    def has(path: Path | None, needle: str) -> str | None:
        if path is None or not path.exists():
            return None
        text = path.read_text(errors="replace")
        return f"{path.name}:{text.count(chr(10), 0, text.index(needle)) + 1}" if needle in text else None

    adapter = has(westlake_root / "framework/window/java/WindowSessionAdapter.java" if westlake_root else None,
                  "public static int attachSurfaceView")
    patches = sorted((manifest_root / "patches").glob("**/frameworks-base*.patch")) if manifest_root else []
    patch = next((hit for hit in (has(p, "attachSurfaceView") for p in patches) if hit), None)
    vulkan = "libvulkan.so" in (runtime_libraries or [])
    # OH moves focus to the SurfaceView's own window once it shows; the window bridge counts that focus
    # as the activity window's when the session is created for a SurfaceViewWindow.
    bridge = has(westlake_root / "framework/window/java/WindowCallbackBridge.java" if westlake_root else None,
                 "instanceof SurfaceViewWindow")
    created = has(westlake_root / "framework/window/java/WindowSessionAdapter.java" if westlake_root else None,
                  "new SurfaceViewWindow(")
    return {"own_surface": bool(adapter and patch), "vulkan_android_surface": vulkan,
            "focus_group": bridge if bridge and created else None,
            "evidence": ", ".join(filter(None, [adapter, patch, "runtime libvulkan.so" if vulkan else None]))}


# Engines that render only while their activity's window has focus: SDL pauses its native loop when it
# loses focus (SDLActivity.onWindowFocusChanged, single-window), Cocos2d-x resumes its GLSurfaceView only
# with focus (Cocos2dxActivity.resumeIfHasFocus).
FOCUS_GATED_ENGINES = {"libSDL2.so": "SDL", "libSDL3.so": "SDL", "libcocos2dcpp.so": "Cocos2d-x"}
FOCUS_GATED_ACTIVITIES = {"Lorg/libsdl/app/SDLActivity;": "SDL", "Lorg/cocos2dx/lib/Cocos2dxActivity;": "Cocos2d-x"}


def engine_surface_rows(scan: dict[str, Any], model: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Apps whose first screen is drawn by an engine into a SurfaceView it creates.

    On this platform a SurfaceView gets the activity's own OH window rather than a surface of its
    own, so the engine and hwui fight over one window: PPSSPP's EGL surface failed
    (EGL_BAD_ALLOC), Mindustry's hwui lost its surface, Shattered Pixel Dungeon (libGDX) never drew.
    The engine is recognised by its packaged library, which obfuscation does not rename, or by a
    NativeActivity in the launch activity's superclass chain.
    """
    libraries = {elf.get("soname") or elf.get("name") for elf in ohresolve.target_elfs(scan)}
    engines = sorted({ENGINE_LIBRARIES[lib] for lib in libraries if lib in ENGINE_LIBRARIES})
    chains = scan["inventory"].get("launch_activity_chains") or {}
    native_activity = sorted(name for name, chain in chains.items() if any("NativeActivity" in c for c in chain))
    if not engines and not native_activity:
        return []
    evidence = []
    if engines:
        evidence.append(f"packages {', '.join(engines)}")
    if native_activity:
        evidence.append(f"launch activity extends a NativeActivity ({', '.join(native_activity)})")
    model = model or {}
    supplied = bool(model.get("own_surface"))
    return [_row(
        "window", "window:engine-surface", "First screen drawn by an engine into its own SurfaceView",
        oh_touchpoint="window_manager / render_service: one OH window per activity",
        verdict="supplied" if supplied else "missing", shim_class="C9",
        effort="verify" if supplied else "L", confidence=STATIC,
        provider=("a SurfaceView that fills its window gets an OH sub-window session of its own, above the "
                  "activity's (OH windows cannot be placed here: a smaller SurfaceView still shares its window)"
                  + ("; Vulkan's Android surface maps onto VK_OHOS_surface" if model.get("vulkan_android_surface")
                     else "; no VK_KHR_android_surface: a Vulkan engine (Flutter's Impeller) still fails")
                  if supplied else "a SurfaceView shares its activity's one OH window"),
        provider_source=model.get("evidence") or None,
        app_evidence="; ".join(evidence),
        engine_libraries=sorted(lib for lib in libraries if lib in ENGINE_LIBRARIES),
        shim="give each SurfaceView its own OH surface (a child RS node) instead of the activity's window",
    )] + surfaceview_focus_rows(scan, libraries, model)


def surfaceview_focus_rows(scan: dict[str, Any], libraries: set[str], model: dict[str, Any]) -> list[dict[str, Any]]:
    """An engine that renders only while its window has focus, in a provider that gives its SurfaceView
    an OH window of its own: OH moves focus to that window once it shows, and the activity's window
    sees only the loss unless the bridge counts the SurfaceView's focus as its window's."""
    if not model.get("own_surface"):
        return []
    chains = scan["inventory"].get("launch_activity_chains") or {}
    engines = sorted({FOCUS_GATED_ENGINES[lib] for lib in libraries if lib in FOCUS_GATED_ENGINES}
                     | {FOCUS_GATED_ACTIVITIES[c] for chain in chains.values() for c in chain if c in FOCUS_GATED_ACTIVITIES})
    if not engines:
        return []
    supplied = bool(model.get("focus_group"))
    return [_row(
        "window", "window:surfaceview-focus", "An engine that renders only with focus, in a SurfaceView's own window ("
        + ", ".join(engines) + ")",
        oh_touchpoint="window_manager: focus moves to the topmost window, the SurfaceView's",
        verdict="supplied" if supplied else "missing", shim_class="C0" if supplied else "C9",
        effort="verify" if supplied else "S", confidence=STATIC,
        provider=("a SurfaceView's window and its activity's are one focus group: the activity stays focused"
                  if supplied else "the SurfaceView's window takes OH focus and the activity's window sees it lost"),
        provider_source=model.get("focus_group"),
        app_evidence=", ".join(engines) + " stops rendering when its activity loses focus",
        engine_libraries=sorted(lib for lib in libraries if lib in FOCUS_GATED_ENGINES),
        # With the focus kept, anarchre and diesimu still showed nothing: this row is not their whole story.
        seen_blocking=["anarchre, diesimu (SDL: OH moved focus to their SurfaceView's window and the activity's window "
                       "saw only the loss)"],
        shim="count the SurfaceView window's OH focus as its activity window's",
    )]


# Platform calls that resolve but whose answer depends on what the runtime loads or how it was built.
# Measured on the board by probes/icu-data (framework 57); each entry names what it showed.
RUNTIME_DATA = {
    "data:tzdata": dict(
        item="java.time zone rules (tzdata)",
        members={"Ljava/time/ZoneId;": None, "Ljava/time/ZonedDateTime;": None, "Ljava/time/OffsetDateTime;": None,
                 "Ljava/time/zone/ZoneRulesProvider;": None, "Ljava/time/zone/ZoneRules;": None},
        # LocalDate.now()/Clock.systemDefaultZone() are left out: three apps that call them at
        # startup draw, the board's default zone evidently needing no rules.
        provider="the runtime's tzdata directory is staged empty: ICU4J lists 0 zones, java.util.TimeZone "
                 "answers GMT for every zone, java.time throws 'No time-zone data files registered' "
                 "(probes/icu-data; duckduckgo)",
        shim="stage Android's tz data (tzdata, icu_tzdata.dat) under ANDROID_TZDATA_ROOT", shim_class="C1",
    ),
    "data:icu-locale-display": dict(
        item="ICU locale display names",
        members={"Ljava/util/Locale;": {"getDisplayName", "getDisplayLanguage", "getDisplayCountry",
                                         "getDisplayVariant", "getDisplayScript"},
                 "Landroid/icu/util/ULocale;": {"getDisplayName", "getDisplayLanguage", "getDisplayCountry"}},
        provider="libicu_jni is built without AOSP's zero-initialized locals, so ScopedIcuLocale's "
                 "uninitialized UErrorCode makes LocaleNative return null at random and "
                 "Locale.getDisplayName throw (probes/icu-data; wifianalyzer). ICU data itself loads",
        shim="build libicu_jni, like all AOSP native code, with -ftrivial-auto-var-init=zero", shim_class="C7",
    ),
}


def runtime_data_rows(scan: dict[str, Any]) -> list[dict[str, Any]]:
    """Platform calls that resolve but answer wrongly on this runtime: zone rules, locale display names."""
    names = scan["inventory"].get("platform_method_names", {})
    rows = []
    for rid, spec in RUNTIME_DATA.items():
        members = sorted(f"{owner}->{name}" for owner, wanted in spec["members"].items()
                         for name in names.get(owner, []) if wanted is None or name in wanted)
        if not members:
            continue
        rows.append(_row(
            "runtime-data", rid, spec["item"],
            oh_touchpoint="data files the runtime loads at first use, not a symbol or a service",
            verdict="missing", shim_class=spec["shim_class"], effort="S", confidence=OBSERVED,
            provider=spec["provider"], shim=spec["shim"], data_members=members,
            app_evidence=f"the app calls {', '.join(m.split('/')[-1].replace(';->', '.') for m in members[:4])}"
                         + (" …" if len(members) > 4 else ""),
        ))
    return rows


_CLASS_INIT_NATIVE = re.compile(r"(?i)^_?native_?(class_?)?init$")


def _jni_mangle(text: str) -> str:
    out = []
    for ch in text:
        if ch == "/": out.append("_")
        elif ch == "_": out.append("_1")
        elif ch == ";": out.append("_2")
        elif ch == "[": out.append("_3")
        elif ch.isalnum(): out.append(ch)
        else: out.append("_0%04x" % ord(ch))
    return "".join(out)


def runtime_class_strings(directory: Path | None) -> set[str] | None:
    """JNI class paths ("android/media/MediaCodec") named anywhere in the runtime's libraries.

    Registration tables are not always parseable (their layout varies with the compiler), but a
    library that registers a class names it for FindClass. A class named nowhere is registered
    nowhere; a class named somewhere is given the benefit of the doubt -- per method: its natives
    count as registered only where their names are strings there too, entered here as "#name".
    The AudioTrack shim names AudioTrack and registers most of it, but not
    native_get_buffer_size_frames, whose name is in no library (MuseKit died on it).
    """
    if directory is None or not directory.is_dir():
        return None
    found: set[str] = set()
    for lib in directory.glob("*.so"):
        data = lib.read_bytes()
        found.update(m.decode() for m in re.findall(rb"(?:android|com/android|sun/nio|java/nio|libcore)/[A-Za-z0-9_/$]+",
                                                    data))
        found.update("#" + m.decode() for m in re.findall(rb"(?<=\x00)[A-Za-z_][A-Za-z0-9_]{1,80}(?=\x00)", data))
    return found


_REVERSED_NAMES: dict[tuple[int, int], list[str]] = {}


def _names_string(strings: set[str], name: str) -> bool:
    """Whether a library string is the method name, or ends with it: the linker merges a string
    into the tail of a longer one (getParameters into native_getParameters)."""
    if "#" + name in strings:
        return True
    reversed_names = _REVERSED_NAMES.get((id(strings), len(strings)))
    if reversed_names is None:
        reversed_names = sorted(entry[:0:-1] for entry in strings if entry.startswith("#"))
        _REVERSED_NAMES.clear()
        _REVERSED_NAMES[(id(strings), len(strings))] = reversed_names
    key = name[::-1]
    i = bisect.bisect_left(reversed_names, key)
    return i < len(reversed_names) and reversed_names[i].startswith(key)


_LIBCORE_OWNERS = ("Ljava/", "Ljavax/", "Lsun/", "Llibcore/", "Ljdk/", "Ldalvik/")
# Public NIO classes whose implementation is chosen through SelectorProvider (virtual dispatch the
# native-call index does not follow): the implementation classes that hold their natives.
_NIO_IMPLEMENTATIONS = {
    "Ljava/nio/channels/SocketChannel;": ("Lsun/nio/ch/Net;", "Lsun/nio/ch/IOUtil;", "Lsun/nio/ch/SocketChannelImpl;"),
    "Ljava/nio/channels/ServerSocketChannel;": ("Lsun/nio/ch/Net;", "Lsun/nio/ch/IOUtil;", "Lsun/nio/ch/ServerSocketChannelImpl;"),
    "Ljava/nio/channels/DatagramChannel;": ("Lsun/nio/ch/Net;", "Lsun/nio/ch/IOUtil;", "Lsun/nio/ch/DatagramChannelImpl;"),
    # Android's selector is PollSelectorImpl (PollArrayWrapper); AOSP registers no EPoll natives.
    "Ljava/nio/channels/Selector;": ("Lsun/nio/ch/PollArrayWrapper;", "Lsun/nio/ch/IOUtil;"),
    "Ljava/nio/channels/spi/SelectorProvider;": ("Lsun/nio/ch/Net;", "Lsun/nio/ch/PollArrayWrapper;", "Lsun/nio/ch/IOUtil;"),
}
# Public NIO buffer classes whose typed bulk gets and puts reach libcore.io.Memory's natives through
# the heap or direct implementation (HeapByteBuffer -> Memory.unsafeBulkGet, a direct buffer ->
# Memory.peekIntArray ...), behind virtual dispatch the native-call index does not follow. Instagram
# died on unsafeBulkGet; Mindustry and Unciv on pokeFloatArray and pokeShortArray.
_BUFFER_IMPLEMENTATIONS = {
    "Ljava/nio/" + name + ";": ("Llibcore/io/Memory;",)
    for name in ("ByteBuffer", "CharBuffer", "ShortBuffer", "IntBuffer", "LongBuffer", "FloatBuffer", "DoubleBuffer")
}
# Declared native in libcore but registered by AOSP itself neither (ojluni's Net.c has no entry for
# them): no Android app can depend on them.
_AOSP_UNIMPLEMENTED = {
    "Lsun/nio/ch/Net;": {"remoteInetAddress(Ljava/io/FileDescriptor;)Ljava/net/InetAddress;",
                          "remotePort(Ljava/io/FileDescriptor;)I"},
}
# Declared native, implemented by ART itself (signature-polymorphic invokes, the thread entry).
_ART_INTRINSIC_OWNERS = {"Ljava/lang/invoke/MethodHandle;", "Ljava/lang/invoke/VarHandle;",
                         "Ldalvik/system/NativeStart;"}


def framework_native_rows(scan: dict[str, Any], runtime: dict[str, Any] | None,
                          class_strings: set[str] | None = None) -> list[dict[str, Any]]:
    """Platform classes the app uses whose native methods no deployed library registers.

    ART binds a native method only when a loaded library registers it (RegisterNatives) or
    exports its Java_ name. A boot class the runtime ships without its JNI half fails on first
    touch: EGL14's static initializer (Element, during bind), android.hardware.Camera (OpenCamera).
    A class is flagged when the app calls one of its unbound natives directly, when a class-init
    native is unbound (it runs on first use of the class), or when none of its natives is bound.
    A row says the gap exists, not that startup reaches it: Element reached EGL14 during bind,
    while many apps that reference android.hardware.Camera never open it before their first screen.
    """
    if not runtime:
        return []
    registered: set[tuple[str, str]] = set()
    exported: set[str] = set()
    for lib in runtime.get("bridge_libraries", []) + runtime.get("system_libraries", []):
        for entry in lib.get("jni_registration_entries") or []:
            registered.add((entry.get("name"), entry.get("signature")))
        for name in lib.get("jni_exports") or []:
            exported.add(name if isinstance(name, str) else name.get("symbol", ""))
    classes = runtime.get("classes", {})
    unbound_cache: dict[str, list[str]] = {}

    def unbound_of(owner: str) -> list[str]:
        if owner not in unbound_cache:
            # $ravenwood natives are host-side test doubles, never called on a device.
            natives = [m for m in (classes.get(owner) or {}).get("native_methods") or [] if "$ravenwood" not in m]
            # libcore's natives are registered by table (libart's own, the runtime's libraries) or
            # exported by name, never looked up by class string: judge them by those alone.
            if class_strings is not None and not owner.startswith(_LIBCORE_OWNERS):
                named = owner[1:-1] in class_strings
                unbound_cache[owner] = [m for m in natives
                                        if not (named and _names_string(class_strings, m[:m.index("(")]))]
                return unbound_cache[owner]
            prefix = "Java_" + _jni_mangle(owner[1:-1]) + "_"
            unbound = []
            # Named in no runtime library: nothing registers it, whatever other class shares a
            # native's name and signature (EGL10's _nativeClassInit()V made EGL14's look bound).
            for method in natives:
                name, sig = method[:method.index("(")], method[method.index("("):]
                if (name, sig) in registered:
                    continue
                if any(e == prefix + _jni_mangle(name) or e.startswith(prefix + _jni_mangle(name) + "__") for e in exported):
                    continue
                unbound.append(method)
            unbound_cache[owner] = [m for m in unbound if m not in _AOSP_UNIMPLEMENTED.get(owner, ())]
        return unbound_cache[owner]

    # libcore's natives are ART's own (libart's stubs register them), so they can be judged only
    # when the index includes libart. They are not all there: r73 found MappedByteBuffer.load0
    # (Zoom's "no compatible CPU" link-error dialog) and sun.nio.ch.Net's natives unregistered.
    core_indexed = any((lib.get("name") or "") == "libart.so" for lib in runtime.get("bridge_libraries", []))
    owners = ("Landroid/", "Lcom/android/") + (_LIBCORE_OWNERS if core_indexed else ())
    app_calls = {owner: set(names) for owner, names in scan["inventory"].get("platform_method_names", {}).items()
                 if owner.startswith(owners) and owner not in _ART_INTRINSIC_OWNERS}
    # The app's call to a framework wrapper that calls an unbound native: in a class whose natives
    # are partly registered this is the only trace (MuseKit's AudioTrack.getBufferSizeInFrames,
    # Mouse Pounce's AudioManager.getParameters through ExoPlayer). Keyed by the native's class.
    via: dict[str, dict[str, str]] = defaultdict(dict)
    for owner, called in app_calls.items():
        for method, targets in ((classes.get(owner) or {}).get("native_calls") or {}).items():
            if method[:method.index("(")] not in called:
                continue
            for target in targets:
                target_owner, native = target.split("->", 1)
                if (target_owner.startswith(owners) and target_owner not in _ART_INTRINSIC_OWNERS
                        and native in unbound_of(target_owner)):
                    wrapper = f"{owner[1:-1].rsplit('/', 1)[-1]}.{method[:method.index('(')]}"
                    via[target_owner].setdefault(native, wrapper)
    if core_indexed:
        for table, how in ((_NIO_IMPLEMENTATIONS, "its SelectorProvider implementation"),
                           (_BUFFER_IMPLEMENTATIONS, "its heap or direct buffer implementation")):
            for public, implementations in table.items():
                if public not in app_calls:
                    continue
                for implementation in implementations:
                    for native in unbound_of(implementation):
                        via[implementation].setdefault(native, public[1:-1].rsplit("/", 1)[-1] + f" ({how})")
    rows = []
    for owner in sorted(set(app_calls) | set(via)):
        natives = [m for m in (classes.get(owner) or {}).get("native_methods") or [] if "$ravenwood" not in m]
        unbound = unbound_of(owner)
        if not natives or not unbound:
            continue
        called = app_calls.get(owner, set())
        direct = [m for m in unbound if m[:m.index("(")] in called]
        init = [m for m in unbound if _CLASS_INIT_NATIVE.match(m[:m.index("(")])]
        reached = [m for m in unbound if m in via.get(owner, {})]
        # OpenJDK's convention for libcore, whose calls are not indexed: public foo() calls native
        # foo0() (MappedByteBuffer.load -> load0, FileInputStream.length -> length0).
        if owner.startswith(_LIBCORE_OWNERS):
            for m in unbound:
                name = m[:m.index("(")]
                if name.endswith("0") and name[:-1] in called and m not in reached:
                    reached.append(m)
                    via[owner].setdefault(m, f"{owner[1:-1].rsplit('/', 1)[-1]}.{name[:-1]}")
        # A libcore class with no registered native is often one whose natives are unused helpers
        # (TimeZone, Package); flag it only on a traced path to one.
        entire = len(unbound) == len(natives) and bool(called) and not owner.startswith(_LIBCORE_OWNERS)
        if not (direct or init or entire or reached):
            continue
        cls = owner[1:-1].replace("/", ".")
        why = ("its class initializer is native and unbound" if init else
               "the app calls an unbound native directly" if direct else
               "the app calls " + ", ".join(sorted({via[owner][m] for m in reached})[:3])
               + ", which calls an unbound native" if reached else
               "none of its natives is registered")
        evidence = f"{why}; the app calls {', '.join(sorted(called)[:4])}" if called else why
        rows.append(_row(
            "framework-natives", f"jni:{cls}", f"{cls}: {len(unbound)} of {len(natives)} natives unregistered",
            oh_touchpoint="the JNI half of the framework class (libandroid_runtime in AOSP)",
            verdict="missing", shim_class="C3",
            effort="S" if len(unbound) <= 5 else "M" if len(unbound) <= 40 else "L",
            confidence=STATIC,
            app_calls=sorted(called)[:12], open_symbols=(init or direct or reached or unbound)[:12],
            app_evidence=evidence,
            shim="port the AOSP JNI source for the class and register it at startup, before application bind",
        ))
    return rows


# Framework entry points every app runs through, whatever its own code calls: the activity
# lifecycle and the memory callbacks ActivityThread delivers, the view root's traversal, input and
# teardown, and the frame callback. Prefixes of method names, per class.
LIFECYCLE_ENTRY_POINTS: dict[str, tuple[str, ...]] = {
    "Landroid/app/ActivityThread;": ("handle", "perform", "purge", "schedule", "main", "attach"),
    "Landroid/view/ViewRootImpl;": ("perform", "draw", "doTraversal", "setView", "dispatch", "deliverInput",
                                    "handle", "doConsume"),
    "Landroid/view/Choreographer;": ("doFrame", "doCallbacks"),
    "Landroid/view/InputEventReceiver;": ("dispatch", "consume", "finish"),
    "Landroid/app/Activity;": ("perform",),
    "Landroid/app/Instrumentation;": ("call",),
}


def lifecycle_native_rows(runtime: dict[str, Any] | None,
                          class_strings: set[str] | None) -> list[dict[str, Any]]:
    """Unbound natives the framework itself reaches from the entry points every app runs through.

    framework_native_rows follows the app's own calls. These natives are reached by the framework
    whatever the app calls, often only under a condition: RedReader died on
    ActivityThread.nPurgePendingResources, which handleTrimMemory calls once the system is short of
    memory -- no app code names it, so no app-call row could. The rows are the same for every app
    on a runtime; they say which framework paths are unsafe, and under what trigger.
    """
    if not runtime or class_strings is None:
        return []
    classes = runtime.get("classes", {})
    reached: dict[str, set[str]] = defaultdict(set)
    for cls, prefixes in LIFECYCLE_ENTRY_POINTS.items():
        for method, targets in ((classes.get(cls) or {}).get("native_calls") or {}).items():
            if not method.startswith(prefixes):
                continue
            for target in targets:
                owner, native = target.split("->", 1)
                name = native[:native.index("(")]
                if owner[1:-1] in class_strings and _names_string(class_strings, name):
                    continue
                reached[target].add(f"{cls[1:-1].rsplit('/', 1)[-1]}.{method[:method.index('(')]}")
    rows = []
    for target, entries in sorted(reached.items()):
        owner, native = target.split("->", 1)
        cls = owner[1:-1].replace("/", ".")
        rows.append(_row(
            "framework-natives", f"jni-lifecycle:{cls}.{native[:native.index('(')]}",
            f"{cls}.{native} unregistered, reached by the framework itself",
            oh_touchpoint="the JNI half of the framework class (libandroid_runtime in AOSP)",
            verdict="missing", shim_class="C3", effort="S", confidence=STATIC,
            app_calls=[], open_symbols=[native],
            app_evidence=f"reached from {', '.join(sorted(entries)[:3])} on every app, whatever the app calls",
            shim="register the native with AOSP's answer; most of these are hints or cleanup",
        ))
    return rows


def apply_ledger(rows: list[dict[str, Any]], ledger: dict[str, Any]) -> None:
    """Mark rows that have already blocked an app at startup on the board: the empirical ranking a
    static map cannot make by itself."""
    seen: dict[str, list[str]] = defaultdict(list)
    for entry in ledger.get("blockers", []):
        if entry.get("row"):
            seen[entry["row"]].append(f"{entry['app']} ({entry['corpus']})"
                                      + (f", fixed in {entry['fixed_in']}" if entry.get("fixed_in") else ", open"))
    for row in rows:
        if row["id"] in seen:
            row["seen_blocking"] = seen[row["id"]]


def android_namespace_rows(scan: dict[str, Any], rows: list[dict[str, Any]],
                           namespace_libs: list[dict[str, Any]] | None, runtime: dict[str, Any] | None,
                           shim_exports: set[str], ndk_cov: dict[str, Any] | None) -> list[dict[str, Any]]:
    """NDK symbols the runtime supplies that a library in the Android namespace still cannot reach.

    A library the launcher routes to the Android namespace (--android-native-target), or one the
    app writes and loads at run time, finds its DT_NEEDED in that namespace's search order, where
    the WebView shim's directory comes before the runtime: its libandroid.so is the WebView shim's
    74-symbol copy, not the runtime's. An import the runtime's copy (or a library it needs, such
    as libhwui.so for AHardwareBuffer_*) defines therefore fails to relocate there unless the
    bionic shim, global in that namespace, forwards it. Instagram's libscrollmerged.so stopped on
    AHardwareBuffer_unlock that way in r77 while the map counted the symbol as supplied.
    """
    if not namespace_libs or not runtime or not ndk_cov:
        return []
    # Only what the NDK declares for the library: the runtime's libhwui.so also exports GL, zlib and
    # log entry points, which an importer gets from its other DT_NEEDED, not from libandroid.so.
    declared: dict[str, set[str]] = defaultdict(set)
    for item in ndk_cov["symbols"]:
        declared[item["library"]].add(item["symbol"])
    targets = set()
    for row in rows:
        args = row.get("launch_args") or []
        targets |= {value for flag, value in zip(args[0::2], args[1::2]) if flag == "--android-native-target"}
    app_written = any(row["id"] == "load:app-storage-exec" for row in rows)
    written = {elf["name"] for elf in ohresolve.target_elfs(scan) if elf.get("origin") == "unpacked"}
    if not targets and not app_written:
        return []
    bridge = {lib.get("soname") or lib["name"]: lib for lib in runtime.get("bridge_libraries", [])}

    def runtime_closure(name: str) -> set[str]:
        seen, queue, symbols = {name}, [name], set()
        while queue:
            lib = bridge.get(queue.pop())
            if lib is None:
                continue
            symbols |= set(lib.get("exported_symbols", []))
            for dep in lib.get("needed", []):
                if dep in bridge and dep not in seen:
                    seen.add(dep)
                    queue.append(dep)
        return symbols

    elfs = ohresolve.target_elfs(scan)
    packaged = set()
    for elf in elfs:
        packaged |= set(elf.get("exported_symbols", []))
    out = []
    for lib in namespace_libs:
        name = lib.get("soname") or lib["name"]
        if name not in bridge:
            continue
        unreachable = (runtime_closure(name) & declared.get(name, set())) - set(lib.get("exported_symbols", [])) - packaged
        importers: dict[str, set[str]] = defaultdict(set)
        routed = harvested = False
        for elf in elfs:
            if name not in elf.get("needed", []):
                continue
            elf_name = elf.get("soname") or elf["name"].rsplit("/", 1)[-1]
            in_targets = elf_name in targets or elf["name"].rsplit("/", 1)[-1] in targets
            if targets and not in_targets and not app_written:
                continue
            routed |= in_targets
            for symbol in set(elf.get("undefined_symbols", [])) & unreachable:
                importers[symbol].add(elf_name)
                harvested |= elf["name"] in written
        if not importers:
            continue
        names = sorted(importers)
        open_ = [n for n in names if n not in shim_exports]
        libs = sorted({lib for users in importers.values() for lib in users})
        out.append(_row(
            "native-symbols", f"load:android-namespace-ndk:{name}",
            f"{len(names)} {name} symbols the runtime defines but the Android namespace's {name} lacks",
            importing_libraries=libs[:12], confidence=STATIC,
            oh_touchpoint="none: a Westlake namespace layout", verdict="supplied" if not open_ else "missing",
            shim_class="C0" if not open_ else "C1", effort="none" if not open_ else "XS",
            provider=f"{len(names) - len(open_)} of {len(names)} forwarded by the Westlake bionic shim",
            open_symbols=open_[:20], covered_symbols=[n for n in names if n in shim_exports][:20],
            app_evidence=("imported by libraries the launcher routes to the Android namespace" if routed else
                          "imported by libraries the app wrote at run time (harvested after a run), which load "
                          "in the Android namespace" if harvested else
                          "the app writes and loads libraries at run time, which load in the Android namespace; "
                          "its packaged libraries import these, so the ones it writes likely do too"),
            shim="forward each from the bionic shim to the runtime's own library, as it does ALooper_*"))
    return out


_LIBRARY_TARGET_FLAGS = ("--android-native-target", "--android-native-net-target")


def unpackaged_launch_targets(args: list[str], scan: dict[str, Any]) -> list[str]:
    """Library targets in launch args that name no packaged file. The launcher routes files by name and
    refuses such a target, so the app never starts: TikTok's maps once named libeffect.so, the SONAME
    of its libeffect_plugin.so, and TikTok did not launch in two whole-corpus runs."""
    files = {elf["name"].rsplit("/", 1)[-1] for elf in ohresolve.packaged_elfs(scan)}
    return sorted({value for flag, value in zip(args[0::2], args[1::2])
                   if flag in _LIBRARY_TARGET_FLAGS and value not in files})


def launch_args(rows: list[dict[str, Any]]) -> list[str]:
    """Every row's launch_args, flag and value pairs kept together, each pair once."""
    pairs: list[tuple[str, str]] = []
    for row in rows:
        args = row.get("launch_args") or []
        for flag, value in zip(args[0::2], args[1::2]):
            if (flag, value) not in pairs:
                pairs.append((flag, value))
    return [item for pair in pairs for item in pair]


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
    runtime_index: dict[str, Any] | None = None,
    runtime_class_paths: set[str] | None = None,
    ledger: dict[str, Any] | None = None,
    apk_path: Path | None = None,
    runtime_data: dict[str, Any] | None = None,
    android_namespace_libs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    westlake_services = services.westlake_service_model(westlake_root)
    pm = contracts.pm_adapter_model(westlake_root)
    java, java_excluded = java_api_rows(scan, api_levels)
    svc, dynamic = service_rows(scan, aosp_services, westlake_services)
    rows = (java + svc + package_manager_rows(scan, facts, pm, pm_null_consequences(aosp_root))
            + am_default_rows(scan, contracts.direct_launch_am_model(westlake_root), am_default_census(aosp_root))
            + app_framework_rows(scan, contracts.direct_launch_am_model(westlake_root),
                                 contracts.window_adapter_model(westlake_root),
                                 contracts.task_queries_model(westlake_root),
                                 contracts.launch_intent_model(westlake_root),
                                 contracts.thread_priority_model(westlake_root.parent / "art-build"))
            + engine_surface_rows(scan, surfaceview_model(westlake_root, manifest_root, runtime_libraries))
            + runtime_data_rows(scan)
            + android_path_rows(apk_path, scan, runtime_data, westlake_root)
            + uses_library_rows(facts, runtime_data, westlake_root)
            + framework_native_rows(scan, runtime_index, runtime_class_paths)
            + lifecycle_native_rows(runtime_index, runtime_class_paths)
            + native_upcall_rows(scan)
            + (ndk_symbol_rows(scan, [m for m in oh_missing if not m.get("version_mismatch")
                                      and not m.get("versioned_clash") and not m.get("weak")],
                               bionic_shim_exports(westlake_root), ndk_cov) if ndk_cov
               else native_symbol_rows(scan, [m for m in oh_missing if not m.get("version_mismatch")
                                                and not m.get("versioned_clash") and not m.get("weak")],
                                       bionic_shim_exports(westlake_root)))
            + weak_api_rows([m for m in oh_missing if m.get("weak")], bionic_shim_exports(westlake_root))
            + vm_lookup_rows(scan, bionic_shim_exports(westlake_root))
            + symbol_version_rows(oh_missing)
            + versioned_clash_rows([m for m in oh_missing if m.get("versioned_clash")],
                                   contracts.shim_versioned_definitions(westlake_root))
            + task_root_rows(scan, contracts.activity_client_model(westlake_root))
            + own_intent_rows(scan, contracts.own_intent_model(westlake_root))
            + post_create_rows(scan, contracts.launch_start_model(westlake_root))
            + permission_request_rows(scan, contracts.permission_request_model(westlake_root))
            + ce_storage_rows(scan, contracts.ce_storage_model(westlake_root))
            + feature_rows(scan, contracts.feature_claims_model(westlake_root), aosp_services, westlake_services)
            + vulkan_feature_rows(scan, contracts.feature_claims_model(westlake_root), runtime_libraries)
            + window_metrics_rows(scan, contracts.window_metrics_model(westlake_root))
            + native_egl_window_rows(scan, contracts.native_egl_window_model(westlake_root))
            + native_loading_rows(facts, scan, launcher_extraction(manifest_root), board_paths,
                                  launcher_namespace_option(manifest_root), runtime_libraries,
                                  bionic_loader_model(westlake_root, manifest_root))
            + nio_rows(scan, runtime_class_paths)
            + art_internal_rows(scan)
            + needed_library_rows(scan, board_paths, runtime_libraries)
            + libc_constant_rows(scan, contracts.libc_constant_model(westlake_root))
            + signal_abi_rows(scan, contracts.signal_abi_model(westlake_root))
            + static_mutex_rows(scan, contracts.static_mutex_model(westlake_root))
            + thread_handle_rows(scan, contracts.thread_start_model(westlake_root))
            + bionic_tls_rows(scan)
            + security_rows(scan, contracts.keystore_model(westlake_root))
            + webview_rows(scan, webview_process_model(aosp_root, westlake_root))
            # art-build sits beside the westlake checkout in the same workspace; absent, the row
            # is simply not claimed.
            + silent_load_rows(scan, native_load_short_circuit(westlake_root.parent / "art-build"),
                               runtime_libraries)
            + stub_native_rows(scan, stub_native_model(westlake_root.parent / "art-build", westlake_root))
            + runtime_resolved_rows(scan, ndk_cov)
            + sandbox_rows(scan, policy) + external_rows(facts, scan, refused_libraries(westlake_root)))
    rows += android_namespace_rows(scan, rows, android_namespace_libs, runtime_index,
                                   bionic_shim_exports(westlake_root), ndk_cov)
    rows += interposition_rows(scan, runtime_index, rows)
    if ledger:
        apply_ledger(rows, ledger)
    gap_map = {
        "app": {"package": facts["package"], "version": facts["version_name"], "target_sdk": facts["target_sdk"],
                "apk_sha256": scan["apk"]["sha256"]},
        "provider": {"westlake": pm["provenance"], "oh_board": policy["oh"]["board"]},
        "notes": {"java_excluded_by_api_level": java_excluded, "service_requests_with_computed_names": dynamic,
                  "native_upcalls_scanned": scan["inventory"].get("native_upcalls") is not None},
        "rows": rows,
        # Launch remedies the rows name, in row order: a runner applies exactly these, so a gap the
        # launcher can close is closed on the app's first launch.
        "launch_args": launch_args(rows),
    }
    bad_targets = unpackaged_launch_targets(gap_map["launch_args"], scan)
    if bad_targets:
        gap_map["checks"] = {"unpackaged_launch_targets": bad_targets}
        print("gap-map: launch targets name no packaged file: " + " ".join(bad_targets), file=sys.stderr)
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
        elif category == "window":
            # The engine is on the startup path when it created its SurfaceView or loaded its library.
            surface = sorted({touch[k] for k in by_owner.get("Landroid/view/SurfaceView;", [])})
            engines = sorted(set(row.get("engine_libraries", [])) & loaded)
            on_path = "executed" in surface or bool(engines)
            evidence = "; ".join(filter(None, [f"SurfaceView {'/'.join(surface)}" if surface else "",
                                               f"loaded: {', '.join(engines)}" if engines else ""])) or "no SurfaceView, engine not loaded"
        elif category == "runtime-data":
            hit = sorted(k.split("(")[0] for k in touch if touch[k] == "executed"
                         and k.split("(")[0] in set(row.get("data_members", [])))
            on_path = bool(hit)
            evidence = ("executed: " + ", ".join(h.split("/")[-1].replace(";->", ".") for h in hit[:4])) if hit else "not called"
        elif category == "framework-natives":
            # An unbound class-init native fails when the class is first used: any executed method counts.
            descriptor = "L" + rid.partition(":")[2].replace(".", "/") + ";"
            on_path = descriptor in platform_classes
            evidence = "class code executed" if on_path else "no code of the class executed"
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
    seen_rows = [r for r in gap_map["rows"] if r.get("seen_blocking")]
    if seen_rows:
        out += ["## Rows that have blocked an app at startup before", "",
                "From the blockers ledger: gaps this app has in common with an app that died on them.", "",
                "| Row | Verdict | Blocked |", "|---|---|---|"]
        out += [f"| `{r['id']}` | {r['verdict']} | {_escape('; '.join(r['seen_blocking']))} |" for r in seen_rows]
        out.append("")
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
