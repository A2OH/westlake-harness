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
    return {
        "methods": methods,
        # Semantics the source-app path must reproduce from PackageManagerService, checked in source.
        "semantics": {
            "direct_boot_match_defaults": _evidence(reg, r"MATCH_DIRECT_BOOT_AWARE\s*\|\s*PackageManager\.MATCH_DIRECT_BOOT_UNAWARE|MATCH_DIRECT_BOOT_UNAWARE", registry, westlake_root),
            "split_paths_populated": _evidence(splits.read_text(errors="replace") if splits.exists() else "", r"splitSourceDirs\s*=", splits, westlake_root),
        },
        "provenance": git_state(westlake_root),
    }


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
    return {"installed": first(aosp_install), "replacement": replacement, "backend": first(backend)}


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
    return {"translated": translated, "scope": scope,
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
