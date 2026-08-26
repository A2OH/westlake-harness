"""Portfolio aggregation and human-readable reporting."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .scanner import SCHEMA_VERSION, sha256_bytes, utc_now


def aggregate(scans: Iterable[dict[str, Any]], corpus: dict[str, Any] | None = None) -> dict[str, Any]:
    scans = list(scans)
    ranks = {
        item["package"]: item
        for item in ((corpus or {}).get("downloads") or {}).get("artifacts", [])
    }
    by_gap: dict[tuple[str, str, str | None, str | None], dict[str, Any]] = {}
    finding_kinds: Counter[str] = Counter()
    unresolved_kinds: Counter[str] = Counter()
    unresolved_contracts: dict[str, set[tuple[str, str | None, str | None]]] = {}
    native_states: Counter[str] = Counter()
    native_contracts: set[tuple[str, str, str]] = set()
    native_contracts_by_state: dict[str, set[tuple[str, str, str]]] = {}
    abi_statuses: Counter[str] = Counter()
    for scan in scans:
        package = scan["apk"].get("package") or scan["apk"]["filename"]
        native_resolution = scan.get("inventory", {}).get("native_resolution", {})
        abi_statuses[native_resolution.get("abi_status", "unknown")] += 1
        for native in scan.get("inventory", {}).get("declared_native_methods", []):
            state = native.get("state", "unknown")
            contract = (native["owner"], native["name"], native["descriptor"])
            native_states[state] += 1
            native_contracts.add(contract)
            native_contracts_by_state.setdefault(state, set()).add(contract)
        for finding in scan["findings"]:
            if finding.get("classification") == "CU":
                unresolved_kinds[finding["kind"]] += 1
                dep = finding["dependency"]
                unresolved_contracts.setdefault(finding["kind"], set()).add(
                    (dep["owner"], dep.get("name"), dep.get("signature"))
                )
                continue
            dep = finding["dependency"]
            key = (finding["kind"], dep["owner"], dep.get("name"), dep.get("signature"))
            finding_kinds[finding["kind"]] += 1
            if key not in by_gap:
                material = json.dumps(key, sort_keys=True).encode()
                by_gap[key] = {
                    "gap_id": "sha256:" + sha256_bytes(material),
                    "kind": finding["kind"],
                    "dependency": dep,
                    "classifications": set(),
                    "affected_apks": set(),
                    "reference_count": 0,
                }
            item = by_gap[key]
            item["classifications"].add(finding["classification"])
            item["affected_apks"].add(package)
            item["reference_count"] += finding.get("reference_count", 0)

    gaps = []
    for item in by_gap.values():
        item["classifications"] = sorted(item["classifications"])
        item["affected_apks"] = sorted(item["affected_apks"])
        item["affected_apk_count"] = len(item["affected_apks"])
        gaps.append(item)
    kind_order = {"missing_class": 0, "missing_method": 0, "missing_field": 0, "existence_probe": 1, "hollow_method": 2}
    gaps.sort(key=lambda item: (kind_order.get(item["kind"], 9), -item["affected_apk_count"], -item["reference_count"], item["dependency"]["owner"]))

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "runtime_lock_id": scans[0]["runtime_lock_id"] if scans else None,
        "corpus": corpus,
        "metrics": {
            "apk_count": len(scans),
            "scan_success_count": len(scans),
            "unique_gap_count": len(gaps),
            "unique_direct_absence_count": sum(item["kind"].startswith("missing_") for item in gaps),
            "findings_by_kind": dict(sorted(finding_kinds.items())),
            "candidate_finding_count": sum(finding_kinds.values()),
            "unresolved_by_kind": dict(sorted(unresolved_kinds.items())),
            "unresolved_unique_by_kind": {
                kind: len(contracts) for kind, contracts in sorted(unresolved_contracts.items())
            },
            "unresolved_finding_count": sum(unresolved_kinds.values()),
            "native_declaration_count": sum(native_states.values()),
            "native_unique_contract_count": len(native_contracts),
            "native_records_by_state": dict(sorted(native_states.items())),
            "native_unique_contracts_by_state": {
                state: len(contracts)
                for state, contracts in sorted(native_contracts_by_state.items())
            },
            "native_abi_statuses": dict(sorted(abi_statuses.items())),
            "score_suppressed": len(scans) < 25,
            "score_suppressed_reason": "The process forbids composite portfolio scoring below 25 APKs." if len(scans) < 25 else None,
        },
        "apks": [
            {
                "package": scan["apk"].get("package"),
                "app_name": scan["apk"].get("app_name"),
                "version_name": scan["apk"].get("version_name"),
                "sha256": scan["apk"]["sha256"],
                "bytes": scan["apk"]["bytes"],
                "eligible_rank": ranks.get(scan["apk"].get("package"), {}).get("eligible_rank"),
                "chart_rank": ranks.get(scan["apk"].get("package"), {}).get("chart_rank"),
                "defined_classes": scan["inventory"]["defined_classes"],
                "platform_type_references": scan["inventory"]["platform_type_references"],
                "platform_method_references": scan["inventory"]["platform_method_references"],
                "platform_field_references": scan["inventory"]["platform_field_references"],
                "target_abi": scan.get("inventory", {}).get("native_resolution", {}).get("target_abi"),
                "native_abi_status": scan.get("inventory", {}).get("native_resolution", {}).get("abi_status"),
                "native_abis": scan.get("inventory", {}).get("native_resolution", {}).get("available_abis", []),
                **scan["summary"],
            }
            for scan in scans
        ],
        "gaps": gaps,
    }


def markdown_report(portfolio: dict[str, Any]) -> str:
    metrics = portfolio["metrics"]
    lines = [
        "# Westlake API-gap benchmark",
        "",
        f"Generated: `{portfolio['generated_at']}`  ",
        f"Runtime: `{portfolio['runtime_lock_id']}`  ",
        f"APKs scanned: **{metrics['apk_count']}**  ",
        f"Unique static gap candidates: **{metrics['unique_gap_count']}**  ",
        f"Directly absent classes/members: **{metrics['unique_direct_absence_count']}**  ",
        f"Unresolved `CU` native/reflection records (not counted as gaps): **{metrics['unresolved_finding_count']}**",
        "",
        "> This is a static compatibility overview, not a claim that every finding is reached at runtime. "
        "Computed reflection, downloaded code, dynamically registered JNI, and semantic differences require runtime probes.",
        "",
        "## Corpus",
        "",
    ]
    selection = ((portfolio.get("corpus") or {}).get("selection") or {})
    selection_rule = selection.get("selection", {})
    if selection:
        lines.extend(
            [
                f"Source: [{selection.get('name', 'ranking source')}]({selection.get('ranking_source', '')}), observed `{selection.get('observed_at', 'unknown')}`.",
                "",
                f"Selection rule: {selection_rule.get('rule', 'not recorded')}. Excluded: {selection_rule.get('excluded', 'none recorded')}.",
                "",
                "Exact downloaded versions, container hashes, split counts, and retrieval tooling are recorded in the supplied download lock.",
                "",
            ]
        )
    lines.extend([
        "## Per-APK overview",
        "",
        "| Rank | App | Package | Version | DEX classes | Platform types | Methods | Fields | Candidates | Unresolved |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for apk in portfolio["apks"]:
        lines.append(
            "| {rank} | {app} | `{pkg}` | {version} | {classes} | {types} | {methods} | {fields} | {findings} | {unresolved} |".format(
                rank=apk.get("eligible_rank") or "?",
                app=_escape(apk.get("app_name") or apk.get("package") or "unknown"),
                pkg=apk.get("package") or "unknown",
                version=_escape(str(apk.get("version_name") or "unknown")),
                classes=apk.get("defined_classes", "?"),
                types=apk.get("platform_type_references", "?"),
                methods=apk.get("platform_method_references", "?"),
                fields=apk.get("platform_field_references", "?"),
                findings=apk.get("finding_count", 0),
                unresolved=apk.get("unresolved_count", 0),
            )
        )
    lines.extend(
        [
            "",
            "## Native evidence funnel",
            "",
            f"DEX native declarations: **{metrics.get('native_declaration_count', 0)}** records / "
            f"**{metrics.get('native_unique_contract_count', 0)}** unique contracts.",
            "",
            f"Retained native `CU`: **{metrics.get('unresolved_by_kind', {}).get('unbound_native', 0)}** records / "
            f"**{metrics.get('unresolved_unique_by_kind', {}).get('unbound_native', 0)}** unique contracts. "
            f"Retained reflection `CU`: **{metrics.get('unresolved_by_kind', {}).get('existence_probe', 0)}** records / "
            f"**{metrics.get('unresolved_unique_by_kind', {}).get('existence_probe', 0)}** unique contracts.",
            "",
            "| State | Records | Unique contracts |",
            "|---|---:|---:|",
        ]
    )
    unique_native_states = metrics.get("native_unique_contracts_by_state", {})
    for state, count in metrics.get("native_records_by_state", {}).items():
        lines.append(f"| `{state}` | {count} | {unique_native_states.get(state, 0)} |")
    lines.extend(
        [
            "",
            "### Native ABI coverage",
            "",
            "| App | Target ABI | Packaged ABIs | Status | Native declarations | Resolved | Unresolved | Candidates |",
            "|---|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for apk in portfolio["apks"]:
        lines.append(
            "| {app} | `{target}` | {available} | `{status}` | {declared} | {resolved} | {unresolved} | {candidates} |".format(
                app=_escape(apk.get("app_name") or apk.get("package") or "unknown"),
                target=apk.get("target_abi") or "unspecified",
                available=", ".join(f"`{abi}`" for abi in apk.get("native_abis", [])) or "none",
                status=apk.get("native_abi_status") or "unknown",
                declared=apk.get("native_declaration_count", 0),
                resolved=apk.get("native_resolved_count", 0),
                unresolved=apk.get("native_unresolved_count", 0),
                candidates=apk.get("native_candidate_count", 0),
            )
        )
    lines.extend(
        [
            "",
            "### Per-app native evidence states",
            "",
            "| App | APK export | Runtime export | Static table | Load-scoped | Unattributed | ABI unavailable |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for apk in portfolio["apks"]:
        states = apk.get("native_by_state", {})
        lines.append(
            "| {app} | {apk_export} | {runtime_export} | {static_table} | {load_scoped} | {unattributed} | {abi_unavailable} |".format(
                app=_escape(apk.get("app_name") or apk.get("package") or "unknown"),
                apk_export=states.get("apk-export-resolved", 0),
                runtime_export=states.get("runtime-export-resolved", 0),
                static_table=states.get("static-registration-table-candidate", 0),
                load_scoped=states.get("library-scoped-registration-unresolved", 0)
                + states.get("load-attributed-no-binding-evidence", 0),
                unattributed=states.get("registration-source-unattributed", 0),
                abi_unavailable=states.get("target-abi-unavailable", 0)
                + states.get("target-abi-elf-mismatch", 0),
            )
        )
    lines.extend(["", "## Finding counts", ""])
    for kind, count in metrics.get("findings_by_kind", {}).items():
        lines.append(f"- `{kind}`: {count}")
    lines.extend(["", "## Directly absent classes and members", ""])
    lines.extend(_gap_table([gap for gap in portfolio["gaps"] if gap["kind"].startswith("missing_")], 100))
    lines.extend(
        [
            "",
            "These contracts are absent from the exact runtime index. `C1/C4` still needs the implementation-exists decision; `C9-candidate` here means the containing deployed class or jar is demonstrably hollow/stub-like.",
            "",
            "## Probe-only absence candidates",
            "",
        ]
    )
    lines.extend(_gap_table([gap for gap in portfolio["gaps"] if gap["kind"] == "existence_probe"], 40))
    lines.extend(
        [
            "",
            "These require the strict C8 gate: all supplied/plugin DEX must remain call-free for the type, and runtime evidence must show which presence branch is faithful.",
            "",
            "## Hollow-body heuristic candidates",
            "",
        ]
    )
    lines.extend(_gap_table([gap for gap in portfolio["gaps"] if gap["kind"] == "hollow_method"], 40))
    lines.extend(
        [
            "",
            "Small constant/no-op bodies include legitimate base hooks and defaults. This list is a review queue, not proof that every listed body is a semantic defect.",
        ]
    )
    if metrics.get("score_suppressed"):
        lines.extend(["", "## Prioritization", "", metrics["score_suppressed_reason"]])
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- Missing classes/members are direct static mismatches against the hashed runtime snapshot.",
            "- `C8-candidate` means a missing class name flows into a class-existence API and has no callable use in the scanned input; runtime/plugin proof is still required before adding a presence-only class.",
            "- `C9-candidate` is a generated-small-body or hollow/stub-container heuristic and requires comparison with the matching AOSP contract.",
            "- `CU` native findings may be satisfied by `RegisterNatives`; they are not counted as proven unbound symbols.",
            "- Native results are target-ABI-specific; an unavailable packaged ABI is reported separately instead of borrowing symbols from another ABI.",
            "- Recovered `JNINativeMethod` entries and load-library attribution narrow the registration source but remain unresolved until runtime registration is observed.",
            "- Split APKs and code downloaded after installation must be supplied as additional scan inputs for complete coverage.",
            "",
        ]
    )
    return "\n".join(lines)


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _gap_table(gaps: list[dict[str, Any]], limit: int) -> list[str]:
    rows = [
        "| APKs | Kind | Classification | Contract | References |",
        "|---:|---|---|---|---:|",
    ]
    gaps = sorted(
        gaps,
        key=lambda item: (-item["affected_apk_count"], -item["reference_count"], item["dependency"]["owner"]),
    )
    for gap in gaps[:limit]:
        dep = gap["dependency"]
        contract = dep["owner"]
        if dep.get("name"):
            separator = ":" if gap["kind"] == "missing_field" else ""
            contract += "->" + dep["name"] + separator + (dep.get("signature") or "")
        rows.append(
            f"| {gap['affected_apk_count']} | `{gap['kind']}` | `{','.join(gap['classifications'])}` | `{contract}` | {gap['reference_count']} |"
        )
    return rows
