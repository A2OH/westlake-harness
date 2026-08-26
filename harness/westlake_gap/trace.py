"""Runtime watchlists and evidence-ledger ingestion for Westlake traces."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


TRACE_SCHEMA_VERSION = "westlake-runtime-evidence/v0.1"
STRUCTURED_PREFIX = "[WESTLAKE-TRACE]"
DLSYM_RE = re.compile(r"\[WESTLAKE-JNIDLSYM\]\s+resolved\s+(\S+)\s+via\s+RTLD_DEFAULT")
REGISTRY_HIT_RE = re.compile(r"\[WESTLAKE-JNIREG-HIT\]\s+([^\s.]+(?:/[^\s.]*)*)\.([^\s(]+)(\(.*)$")
PRIMARY_MISS_RE = re.compile(r"\[WESTLAKE-JNIMISS\]\s+(.+?)(?:\s+declaring_class=\S+)?$")
TERMINAL_MISS_RE = re.compile(r"(?:No implementation found for|UnsatisfiedLinkError).*?(Java_[A-Za-z0-9_]+)")
PRETTY_METHOD_RE = re.compile(
    r"^(?P<return>\S+)\s+(?P<owner>[A-Za-z0-9_.$]+)\."
    r"(?P<name>[^.(\s]+)\((?P<parameters>.*)\)$"
)


def build_watchlist(scans: Iterable[dict[str, Any]]) -> dict[str, Any]:
    native: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    classes: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    runtime_ids: set[str] = set()
    apk_hashes: set[str] = set()
    excluded_native_states: Counter[str] = Counter()
    for scan in scans:
        runtime_ids.add(scan["runtime_lock_id"])
        apk_hashes.add(scan["apk"]["sha256"])
        package = scan["apk"].get("package")
        for item in scan.get("inventory", {}).get("declared_native_methods", []):
            if item.get("classification") == "C0":
                continue
            if item.get("state") in {"target-abi-unavailable", "target-abi-elf-mismatch"}:
                excluded_native_states[item["state"]] += 1
                continue
            key = (
                scan["apk"]["sha256"],
                item["owner"],
                item["name"],
                item["descriptor"],
                item.get("dex", ""),
            )
            native[key] = {
                "package": package,
                "apk_sha256": scan["apk"]["sha256"],
                "runtime_lock_id": scan["runtime_lock_id"],
                "class_descriptor": item["owner"],
                "method_name": item["name"],
                "method_signature": item["descriptor"],
                "dex_name": item.get("dex"),
                "dex_sha256": item.get("dex_sha256"),
                "jni_short": item.get("jni_short"),
                "jni_long": item.get("jni_long"),
                "static_state": item.get("state"),
            }
        for finding in scan.get("findings", []):
            if finding.get("kind") != "existence_probe" or finding.get("classification") != "CU":
                continue
            target = finding["dependency"]["owner"]
            for evidence in finding.get("evidence", []):
                key = (
                    scan["apk"]["sha256"],
                    target,
                    evidence.get("owner", ""),
                    evidence.get("method", ""),
                    evidence.get("dex", ""),
                )
                classes[key] = {
                    "package": package,
                    "apk_sha256": scan["apk"]["sha256"],
                    "runtime_lock_id": scan["runtime_lock_id"],
                    "requested_class": target,
                    "caller_class": evidence.get("owner"),
                    "caller_method": evidence.get("method"),
                    "caller_signature": evidence.get("descriptor"),
                    "caller_dex_name": evidence.get("dex"),
                    "source_api": evidence.get("api"),
                }
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "runtime_lock_ids": sorted(runtime_ids),
        "apk_sha256s": sorted(apk_hashes),
        "excluded_native_state_counts": dict(sorted(excluded_native_states.items())),
        "native_methods": sorted(
            native.values(),
            key=lambda item: (
                item.get("package") or "",
                item["class_descriptor"],
                item["method_name"],
                item["method_signature"],
            ),
        ),
        "reflective_loads": sorted(
            classes.values(),
            key=lambda item: (
                item.get("package") or "",
                item["requested_class"],
                item.get("caller_class") or "",
                item.get("caller_method") or "",
            ),
        ),
    }


def parse_trace_files(paths: Iterable[Path]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in paths:
        with path.open(encoding="utf-8", errors="replace") as stream:
            for line_number, raw_line in enumerate(stream, 1):
                event = parse_trace_line(raw_line.rstrip("\n"))
                if event is None:
                    continue
                material = json.dumps(
                    {"path": str(path), "line": line_number, "event": event},
                    sort_keys=True,
                ).encode()
                event.setdefault("event_id", "sha256:" + hashlib.sha256(material).hexdigest())
                event["trace_path"] = str(path)
                event["trace_line"] = line_number
                events.append(event)
    return events


def parse_trace_line(line: str) -> dict[str, Any] | None:
    structured = line
    if STRUCTURED_PREFIX in line:
        structured = line.split(STRUCTURED_PREFIX, 1)[1].strip()
    if structured.startswith("{"):
        try:
            value = json.loads(structured)
            if isinstance(value, dict) and value.get("event_type"):
                return value
        except json.JSONDecodeError:
            pass
    match = DLSYM_RE.search(line)
    if match:
        return {
            "event_type": "JNI_DLSYM_HIT",
            "symbol": match.group(1),
            "registration_path": "RTLD_DEFAULT",
            "reachability": "invocation-attempted",
            "legacy_text": True,
        }
    match = REGISTRY_HIT_RE.search(line)
    if match:
        return {
            "event_type": "REGISTER_NATIVE",
            "class_descriptor": "L" + match.group(1).replace(".", "/") + ";",
            "method_name": match.group(2),
            "method_signature": match.group(3),
            "registration_path": "SHADOW_REGISTRY",
            "reachability": "invocation-attempted",
            "legacy_text": True,
        }
    match = TERMINAL_MISS_RE.search(line)
    if match:
        return {
            "event_type": "JNI_LOOKUP_MISS",
            "symbol": match.group(1),
            "terminal": True,
            "legacy_text": True,
        }
    match = PRIMARY_MISS_RE.search(line)
    if match:
        event = {
            "event_type": "JNI_PRIMARY_LOOKUP_MISS",
            "pretty_method": match.group(1),
            "terminal": False,
            "legacy_text": True,
        }
        event.update(_contract_from_pretty_method(match.group(1)))
        return event
    return None


def build_evidence_ledger(
    scans: Iterable[dict[str, Any]],
    events: Iterable[dict[str, Any]],
    run_id: str,
    scenario: str,
) -> dict[str, Any]:
    scans = list(scans)
    events = list(events)
    watchlist = build_watchlist(scans)
    native_by_contract: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    native_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in watchlist["native_methods"]:
        native_by_contract[
            (item["class_descriptor"], item["method_name"], item["method_signature"])
        ].append(item)
        for symbol in (item.get("jni_short"), item.get("jni_long")):
            if symbol:
                native_by_symbol[symbol].append(item)

    observations: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    reflection_events: list[dict[str, Any]] = []
    library_events: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for event in events:
        if event["event_type"].startswith("CLASS_LOAD"):
            reflection_events.append(event)
            continue
        if event["event_type"].startswith("NATIVE_LIBRARY_LOAD"):
            library_events.append(event)
            continue
        matched: list[dict[str, Any]] = []
        if event.get("symbol"):
            matched.extend(native_by_symbol.get(event["symbol"], []))
        contract = (
            event.get("class_descriptor"),
            event.get("method_name"),
            event.get("method_signature"),
        )
        if all(contract):
            matched.extend(native_by_contract.get(contract, []))
        unique = {
            (
                item["apk_sha256"],
                item["class_descriptor"],
                item["method_name"],
                item["method_signature"],
                item.get("dex_name") or "",
            ): item
            for item in matched
            if _event_matches_artifact(event, item, watchlist)
        }
        if not unique:
            unmatched.append({**event, "join_status": _unmatched_reason(event, matched, watchlist)})
            continue
        for key in unique:
            observations[key].append(event)

    native_evidence: list[dict[str, Any]] = []
    runtime_states: Counter[str] = Counter()
    for item in watchlist["native_methods"]:
        key = (
            item["apk_sha256"],
            item["class_descriptor"],
            item["method_name"],
            item["method_signature"],
            item.get("dex_name") or "",
        )
        seen = observations.get(key, [])
        runtime_state = _runtime_native_state(seen)
        runtime_states[runtime_state] += 1
        native_evidence.append({**item, "runtime_state": runtime_state, "observations": seen})

    reflection_evidence, unmatched_reflection, reflection_states = _join_reflection_events(
        watchlist["reflective_loads"], reflection_events, watchlist
    )
    unmatched.extend(unmatched_reflection)

    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "run_id": run_id,
        "scenario": scenario,
        "runtime_lock_ids": watchlist["runtime_lock_ids"],
        "apk_sha256s": watchlist["apk_sha256s"],
        "metrics": {
            "event_count": len(events),
            "native_watch_count": len(watchlist["native_methods"]),
            "native_watch_excluded_by_state": watchlist["excluded_native_state_counts"],
            "reflection_watch_count": len(watchlist["reflective_loads"]),
            "native_runtime_states": dict(sorted(runtime_states.items())),
            "reflection_runtime_states": dict(sorted(reflection_states.items())),
            "library_event_count": len(library_events),
            "unmatched_event_count": len(unmatched),
        },
        "native_evidence": native_evidence,
        "reflection_evidence": reflection_evidence,
        "library_events": library_events,
        "unmatched_events": unmatched,
    }


def markdown_evidence_report(ledger: dict[str, Any]) -> str:
    metrics = ledger["metrics"]
    lines = [
        "# Westlake runtime gap evidence",
        "",
        f"Run: `{ledger['run_id']}`  ",
        f"Scenario: `{ledger['scenario']}`  ",
        f"Runtime locks: {', '.join(f'`{item}`' for item in ledger['runtime_lock_ids'])}  ",
        f"APK hashes: {', '.join(f'`{item}`' for item in ledger['apk_sha256s'])}",
        "",
        "## Evidence coverage",
        "",
        f"- Parsed events: **{metrics['event_count']}**",
        f"- Native contracts watched: **{metrics['native_watch_count']}**",
        f"- Native records excluded from this ABI's watchlist: **{sum(metrics['native_watch_excluded_by_state'].values())}**",
        f"- Reflection sites watched: **{metrics['reflection_watch_count']}**",
        f"- Library load events: **{metrics['library_event_count']}**",
        f"- Events deliberately left unmatched: **{metrics['unmatched_event_count']}**",
        "",
        "### Native states",
        "",
        "| Runtime state | Contracts |",
        "|---|---:|",
    ]
    for state, count in metrics["native_runtime_states"].items():
        lines.append(f"| `{state}` | {count} |")
    lines.extend(["", "### Reflection states", "", "| Runtime state | Probe sites |", "|---|---:|"])
    for state, count in metrics["reflection_runtime_states"].items():
        lines.append(f"| `{state}` | {count} |")

    observed_native = [
        item for item in ledger["native_evidence"] if item["runtime_state"] != "not-observed"
    ]
    lines.extend(
        [
            "",
            "## Observed native contracts",
            "",
            "| State | Package | Contract | Events |",
            "|---|---|---|---:|",
        ]
    )
    for item in sorted(
        observed_native,
        key=lambda value: (
            value["runtime_state"],
            value.get("package") or "",
            value["class_descriptor"],
            value["method_name"],
        ),
    ):
        contract = (
            item["class_descriptor"] + "->" + item["method_name"] + item["method_signature"]
        )
        lines.append(
            f"| `{item['runtime_state']}` | `{item.get('package') or 'unknown'}` | "
            f"`{contract}` | {len(item['observations'])} |"
        )

    observed_reflection = [
        item for item in ledger["reflection_evidence"] if item["runtime_state"] != "not-observed"
    ]
    lines.extend(
        [
            "",
            "## Observed reflection sites",
            "",
            "| State | Package | Requested class | Caller | Events |",
            "|---|---|---|---|---:|",
        ]
    )
    for item in sorted(
        observed_reflection,
        key=lambda value: (
            value["runtime_state"],
            value.get("package") or "",
            value["requested_class"],
        ),
    ):
        caller = (item.get("caller_class") or "unknown") + "->" + (
            item.get("caller_method") or "unknown"
        )
        lines.append(
            f"| `{item['runtime_state']}` | `{item.get('package') or 'unknown'}` | "
            f"`{item['requested_class']}` | `{caller}` | {len(item['observations'])} |"
        )
    lines.extend(
        [
            "",
            "A primary JNI lookup miss is non-terminal: it remains a miss-only observation unless "
            "a later registry/dlsym hit or terminal lookup failure is captured. Legacy events without "
            "package/hash provenance are joined only when the ledger contains exactly one APK.",
            "",
        ]
    )
    return "\n".join(lines)


def _runtime_native_state(events: list[dict[str, Any]]) -> str:
    event_types = {event["event_type"] for event in events}
    if "JNI_INVOKE_SUCCESS" in event_types:
        return "runtime-invoked-ok"
    if any(event["event_type"] in {"JNI_INVOKE_FAILURE", "JNI_LOOKUP_MISS"} and event.get("terminal", True) for event in events):
        return "runtime-confirmed-miss"
    if "JNI_DLSYM_HIT" in event_types:
        return "runtime-dlsym-resolved"
    if "REGISTER_NATIVE" in event_types:
        return "runtime-registered"
    if "JNI_PRIMARY_LOOKUP_MISS" in event_types:
        return "runtime-primary-lookup-miss-only"
    return "not-observed"


def _contract_from_pretty_method(pretty: str) -> dict[str, str]:
    match = PRETTY_METHOD_RE.match(pretty)
    if not match:
        return {}
    try:
        parameters = match.group("parameters").strip()
        parameter_descriptor = "".join(
            _java_type_to_descriptor(part.strip())
            for part in parameters.split(",")
            if part.strip()
        )
        return {
            "class_descriptor": _java_type_to_descriptor(match.group("owner")),
            "method_name": match.group("name"),
            "method_signature": f"({parameter_descriptor})"
            + _java_type_to_descriptor(match.group("return")),
        }
    except ValueError:
        return {}


def _java_type_to_descriptor(java_type: str) -> str:
    dimensions = 0
    while java_type.endswith("[]"):
        dimensions += 1
        java_type = java_type[:-2]
    primitives = {
        "void": "V",
        "boolean": "Z",
        "byte": "B",
        "char": "C",
        "short": "S",
        "int": "I",
        "long": "J",
        "float": "F",
        "double": "D",
    }
    if java_type in primitives:
        descriptor = primitives[java_type]
    elif java_type and not any(char.isspace() for char in java_type):
        descriptor = "L" + java_type.replace(".", "/") + ";"
    else:
        raise ValueError(f"unsupported pretty type: {java_type}")
    return "[" * dimensions + descriptor


def _event_matches_artifact(
    event: dict[str, Any], item: dict[str, Any], watchlist: dict[str, Any]
) -> bool:
    if event.get("runtime_lock_id") and event["runtime_lock_id"] != item.get("runtime_lock_id"):
        return False
    if event.get("apk_sha256") and event["apk_sha256"] != item.get("apk_sha256"):
        return False
    if event.get("package") and event["package"] != item.get("package"):
        return False
    has_artifact_identity = bool(event.get("apk_sha256") or event.get("package"))
    if has_artifact_identity:
        return True
    # Legacy text has no package/hash envelope. It is safe to join only when the
    # caller supplied one APK scan for the run; otherwise identical contracts in
    # multiple APKs would create false reachability.
    return len(watchlist["apk_sha256s"]) == 1


def _unmatched_reason(
    event: dict[str, Any], candidates: list[dict[str, Any]], watchlist: dict[str, Any]
) -> str:
    if candidates and not (event.get("apk_sha256") or event.get("package")):
        if len(watchlist["apk_sha256s"]) > 1:
            return "ambiguous-artifact-provenance"
    if event.get("runtime_lock_id") and event["runtime_lock_id"] not in watchlist["runtime_lock_ids"]:
        return "runtime-lock-mismatch"
    if event.get("apk_sha256") and event["apk_sha256"] not in watchlist["apk_sha256s"]:
        return "apk-hash-mismatch"
    return "no-static-contract-match"


def _join_reflection_events(
    watches: list[dict[str, Any]],
    events: list[dict[str, Any]],
    watchlist: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    observations: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    unmatched: list[dict[str, Any]] = []
    for event in events:
        requested = event.get("requested_class") or event.get("class_descriptor")
        candidates = [
            item
            for item in watches
            if item["requested_class"] == requested
            and _event_matches_artifact(event, item, watchlist)
        ]
        caller_fields = {
            "caller_class": event.get("caller_class"),
            "caller_method": event.get("caller_method"),
            "caller_signature": event.get("caller_signature"),
        }
        supplied_callers = {key: value for key, value in caller_fields.items() if value}
        if supplied_callers:
            candidates = [
                item
                for item in candidates
                if all(item.get(key) == value for key, value in supplied_callers.items())
            ]
        # Without a caller identity, a target shared by multiple probe sites is
        # deliberately left ambiguous instead of painting every site reachable.
        if len(candidates) != 1:
            reason = (
                "ambiguous-caller-provenance"
                if len(candidates) > 1
                else _unmatched_reason(event, candidates, watchlist)
            )
            unmatched.append({**event, "join_status": reason})
            continue
        item = candidates[0]
        observations[_reflection_key(item)].append(event)

    evidence: list[dict[str, Any]] = []
    states: Counter[str] = Counter()
    for item in watches:
        seen = observations.get(_reflection_key(item), [])
        state = _runtime_reflection_state(seen)
        states[state] += 1
        evidence.append({**item, "runtime_state": state, "observations": seen})
    return evidence, unmatched, states


def _reflection_key(item: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        item["apk_sha256"],
        item["requested_class"],
        item.get("caller_class") or "",
        item.get("caller_method") or "",
        item.get("caller_signature") or "",
    )


def _runtime_reflection_state(events: list[dict[str, Any]]) -> str:
    event_types = {event["event_type"] for event in events}
    if "CLASS_LOAD_SUCCESS" in event_types:
        return "runtime-load-success"
    if "CLASS_LOAD_FAILURE" in event_types:
        return "runtime-load-failure"
    if "CLASS_LOAD_ATTEMPT" in event_types:
        return "runtime-load-attempted"
    return "not-observed"
