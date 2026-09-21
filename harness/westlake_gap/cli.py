"""Command-line interface for the Westlake APK gap harness."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path

from .nativeprov import analyze_library, compare_runtime_capture
from .platformapi import annotate, load_platform_index
from .report import aggregate, markdown_report
from .scanner import (
    build_runtime_index,
    read_elf,
    read_json,
    refresh_scan_summary,
    scan_apk,
    sha256_file,
    write_json,
)
from .trace import (
    build_evidence_ledger,
    build_watchlist,
    markdown_evidence_report,
    parse_trace_files,
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="westlake-apk-gap")
    commands = root.add_subparsers(dest="command", required=True)

    runtime = commands.add_parser("snapshot-runtime", help="index an ordered boot classpath")
    runtime.add_argument("--jar", action="append", default=[], type=Path, help="BCP JAR in load order; repeat")
    runtime.add_argument("--classpath-file", type=Path, help="ordered JAR paths; blank/comment lines ignored")
    runtime.add_argument("--bridge", action="append", default=[], type=Path, help="bridge ELF; repeat")
    runtime.add_argument(
        "--system-lib",
        action="append",
        default=[],
        type=Path,
        help="deployed system ELF the app links against (libc, liblog, libandroid, libjnigraphics, ...); repeat",
    )
    runtime.add_argument("--target-abi", help="Android ABI represented by the runtime, e.g. arm64-v8a")
    runtime.add_argument("--out", required=True, type=Path)
    runtime.add_argument("--summary-out", type=Path, help="write the runtime lock without the class index")

    runtime_summary = commands.add_parser("runtime-summary", help="strip class definitions from an existing runtime index")
    runtime_summary.add_argument("--runtime-index", required=True, type=Path)
    runtime_summary.add_argument("--out", required=True, type=Path)
    runtime_summary.add_argument("--note", help="optional snapshot availability note")

    scan = commands.add_parser("scan", help="scan one APK or DEX against a runtime index")
    scan.add_argument("input", type=Path)
    scan.add_argument("--runtime", required=True, type=Path)
    scan.add_argument("--out", required=True, type=Path)
    scan.add_argument("--target-abi", help="override the runtime target ABI")
    scan.add_argument("--no-elf", action="store_true", help="skip packaged ELF symbol inventory")
    scan.add_argument(
        "--native-reach",
        action="store_true",
        help="attribute unresolved native imports to the JNI methods that reach them (needs llvm-objdump)",
    )

    bench = commands.add_parser("benchmark", help="scan a directory and create portfolio outputs")
    bench.add_argument("input", type=Path, help="directory containing APK files")
    bench.add_argument("--runtime", required=True, type=Path)
    bench.add_argument("--out", required=True, type=Path)
    bench.add_argument("--corpus-manifest", type=Path)
    bench.add_argument("--download-lock", type=Path)
    bench.add_argument("--resume", action="store_true", help="reuse matching completed per-APK scans")
    bench.add_argument("--no-elf", action="store_true")
    bench.add_argument("--target-abi", help="override the runtime target ABI")

    watch = commands.add_parser("trace-watchlist", help="emit native/reflection runtime watchlists")
    watch.add_argument("--scan", action="append", required=True, type=Path, help="per-APK scan JSON; repeat")
    watch.add_argument("--out", required=True, type=Path)

    ingest = commands.add_parser("ingest-trace", help="join Westlake runtime traces to static scans")
    ingest.add_argument("--scan", action="append", required=True, type=Path, help="per-APK scan JSON; repeat")
    ingest.add_argument("--trace", action="append", required=True, type=Path, help="trace/log file; repeat")
    ingest.add_argument("--run-id", required=True)
    ingest.add_argument("--scenario", required=True)
    ingest.add_argument("--out", required=True, type=Path)
    ingest.add_argument("--report-out", type=Path, help="write a concise Markdown evidence report")

    native = commands.add_parser(
        "native-surface",
        help="component provenance and per-method platform-surface reach for packaged ELFs",
    )
    native.add_argument("input", type=Path, help="a .so file, or a directory of .so files")
    native.add_argument("--out", required=True, type=Path)
    native.add_argument("--objdump", help="aarch64-capable llvm-objdump; the NDK ships one")
    native.add_argument("--abi", help="ABI label recorded with each library")

    capture = commands.add_parser(
        "native-capture-diff",
        help="join a runtime JNI capture (harness/jniprobe) to a native-surface scan",
    )
    capture.add_argument("--capture", action="append", required=True, type=Path, help="capture JSONL; repeat")
    capture.add_argument("--surface", required=True, type=Path, help="native-surface.json for the same APK")
    capture.add_argument("--out", required=True, type=Path)

    apis = commands.add_parser(
        "annotate-api-levels",
        help="tag absence findings with the API level that introduced them, and whether a reference device could reach them",
    )
    apis.add_argument("--scan", required=True, type=Path)
    apis.add_argument(
        "--platform-jar",
        action="append",
        required=True,
        metavar="API:PATH",
        help="android.jar for one API level, e.g. 28:/path/android-28/android.jar; repeat",
    )
    apis.add_argument("--reference-api", required=True, type=int, help="API level of a device the app is known to run on")
    apis.add_argument("--out", required=True, type=Path)

    gap = commands.add_parser(
        "gap-map",
        help="one categorized, effort-rated map of where an APK touches OpenHarmony and what shim each gap needs",
    )
    gap.add_argument("--scan", required=True, type=Path, help="scan JSON for the APK (from `scan`)")
    gap.add_argument("--apk", required=True, type=Path, help="the same .apk/.xapk, for manifest facts")
    gap.add_argument("--api-levels", type=Path, help="annotate-api-levels output for the same scan")
    gap.add_argument("--aosp", required=True, type=Path, help="AOSP source root holding frameworks-base and modules-*")
    gap.add_argument("--westlake", required=True, type=Path, help="Westlake source tree (the provider under test)")
    gap.add_argument("--westlake-label", help="provenance label when --westlake is not a git checkout")
    gap.add_argument("--manifest-repo", type=Path, help="launcher repo (tools/prepare_app.py)")
    gap.add_argument("--oh-resolution", required=True, type=Path, help="oh-import-resolution.json from the board")
    gap.add_argument("--app-key", required=True, help="key of this app inside --oh-resolution")
    gap.add_argument("--policy", type=Path, default=Path(__file__).parent / "data" / "oh-app-data-policy.json")
    gap.add_argument("--blockers", type=Path, help="known-blockers JSON: backtest the map against observed failures")
    gap.add_argument("--blockers-status", action="store_true",
                     help="report known blockers as open/closed against this provider instead of as a backtest")
    gap.add_argument("--out", required=True, type=Path, help="output directory")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "gap-map":
        from .contracts import manifest_facts
        from .gapmap import backtest, build_map, markdown
        from .services import aosp_service_table

        scan = read_json(args.scan)
        levels = {}
        if args.api_levels:
            for finding in read_json(args.api_levels).get("findings", []):
                verdict = finding.get("api_verdict")
                if verdict:
                    dep = finding["dependency"]
                    levels[(finding["kind"], dep["owner"], dep.get("name"), dep.get("signature"))] = verdict
        aosp = aosp_service_table(
            args.aosp / "frameworks-base/core/java/android/app/SystemServiceRegistry.java",
            args.aosp / "frameworks-base/core/java/android/content/Context.java",
            [args.aosp / "frameworks-base", *sorted(args.aosp.glob("modules-*"))],
        )
        oh = read_json(args.oh_resolution)["apps"][args.app_key]["missing"]
        gap_map = build_map(scan, manifest_facts(args.apk), levels, aosp, args.westlake, oh,
                            read_json(args.policy), args.manifest_repo)
        if args.westlake_label:
            gap_map["provider"]["westlake"] = {"branch": args.westlake_label, "commit": args.westlake_label, "uncommitted": []}
        results = None
        if args.blockers:
            results = backtest(gap_map, read_json(args.blockers)["blockers"])
            gap_map["backtest"] = results
        args.out.mkdir(parents=True, exist_ok=True)
        write_json(args.out / "gap-map.json", gap_map)
        (args.out / "GAP-MAP.md").write_text(markdown(gap_map, results, status_mode=args.blockers_status))
        gaps = [r for r in gap_map["rows"] if r["verdict"] != "supplied" and r["effort"] != "none"]
        print(f"{len(gap_map['rows'])} rows, {len(gaps)} gaps"
              + (f"; backtest {sum(r['outcome'] == 'predicted' for r in results)}/{len(results)} predicted, "
                 f"{sum(r['outcome'] == 'flagged for verification' for r in results)} flagged" if results else "")
              + f" -> {args.out}")
        return 0
    if args.command == "annotate-api-levels":
        indexes = {}
        for spec in args.platform_jar:
            level, _, path = spec.partition(":")
            if not path:
                raise SystemExit(f"--platform-jar expects API:PATH, got {spec!r}")
            indexes[int(level)] = load_platform_index(Path(path))
        scan = read_json(args.scan)
        summary = annotate(scan.get("findings", []), indexes, args.reference_api)
        scan["api_level_annotation"] = summary
        write_json(args.out, scan)
        verdicts = summary["verdicts"]
        print(
            f"annotated {summary['annotated']} absence findings against API {args.reference_api}: "
            + ", ".join(f"{k}={v}" for k, v in sorted(verdicts.items()))
            + f" -> {args.out}"
        )
        return 0
    if args.command == "native-capture-diff":
        rows = []
        for path in args.capture:
            with path.open(encoding="utf-8") as stream:
                rows.extend(json.loads(line) for line in stream if line.strip())
        diff = compare_runtime_capture(rows, read_json(args.surface))
        write_json(args.out, diff)
        print(
            f"static {diff['static']['methods']} methods / runtime {diff['runtime']['methods']}; "
            f"runtime-only {diff['runtime_only_methods']}, never-exercised {diff['static_only_methods']} -> {args.out}"
        )
        return 0
    if args.command == "native-surface":
        libraries = (
            sorted(path for path in args.input.rglob("*.so") if path.is_file())
            if args.input.is_dir()
            else [args.input]
        )
        if not libraries:
            raise SystemExit(f"no .so inputs found in {args.input}")
        results = []
        for index, library in enumerate(libraries, 1):
            record = read_elf(path=library, abi=args.abi)
            results.append(analyze_library(library, record, objdump=args.objdump))
            print(f"[{index}/{len(libraries)}] {library.name}", flush=True)
        write_json(args.out, {"libraries": results, "library_count": len(results)})
        coupled = sum(
            1
            for item in results
            for method in item.get("method_reach", {}).get("methods", ())
            if method["platform_coupled"]
        )
        methods = sum(len(item.get("method_reach", {}).get("methods", ())) for item in results)
        print(f"{len(results)} libraries, {methods} registered methods, {coupled} platform-coupled -> {args.out}")
        return 0
    if args.command == "trace-watchlist":
        scans = [read_json(path) for path in args.scan]
        write_json(args.out, build_watchlist(scans))
        print(f"watchlist for {len(scans)} scans -> {args.out}")
        return 0
    if args.command == "ingest-trace":
        scans = [read_json(path) for path in args.scan]
        events = parse_trace_files(args.trace)
        ledger = build_evidence_ledger(scans, events, args.run_id, args.scenario)
        write_json(args.out, ledger)
        if args.report_out:
            args.report_out.parent.mkdir(parents=True, exist_ok=True)
            args.report_out.write_text(markdown_evidence_report(ledger), encoding="utf-8")
        print(
            f"ingested {len(events)} events; "
            f"{ledger['metrics']['unmatched_event_count']} unmatched -> {args.out}"
        )
        return 0
    if args.command == "runtime-summary":
        value = read_json(args.runtime_index)
        summary = _runtime_summary(value)
        if args.note:
            summary["snapshot_note"] = args.note
        write_json(args.out, summary)
        print(f"runtime {summary['runtime_lock_id']} summary -> {args.out}")
        return 0
    if args.command == "snapshot-runtime":
        jars = list(args.jar)
        if args.classpath_file:
            for raw_line in args.classpath_file.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if line and not line.startswith("#"):
                    expanded = os.path.expandvars(line)
                    if "$" in expanded:
                        raise SystemExit(f"unresolved environment variable in classpath: {line}")
                    jars.append(Path(expanded))
        if not jars:
            raise SystemExit("snapshot-runtime requires --jar or --classpath-file")
        for path in [*jars, *args.bridge, *args.system_lib]:
            if not path.is_file():
                raise SystemExit(f"input does not exist: {path}")
        value = build_runtime_index(
            jars, args.bridge, target_abi=args.target_abi, system_libraries=args.system_lib
        )
        write_json(args.out, value)
        if args.summary_out:
            summary = _runtime_summary(value)
            write_json(args.summary_out, summary)
        print(f"runtime {value['runtime_lock_id']}: {value['class_count']} classes -> {args.out}")
        return 0

    runtime = read_json(args.runtime)
    if args.command == "scan":
        value = scan_apk(
            args.input,
            runtime,
            include_elf=not args.no_elf,
            target_abi=args.target_abi,
            native_reach=args.native_reach,
        )
        write_json(args.out, value)
        print(f"{value['apk'].get('package')}: {value['summary']['finding_count']} findings -> {args.out}")
        return 0

    apks = sorted(
        path
        for path in args.input.iterdir()
        if path.is_file() and path.suffix.lower() in {".apk", ".xapk", ".apkm"}
    )
    if not apks:
        raise SystemExit(f"no APK/XAPK/APKM inputs found in {args.input}")
    download_lock = read_json(args.download_lock) if args.download_lock else None
    if download_lock:
        by_name = {path.name: path for path in apks}
        expected = [item["filename"] for item in download_lock["artifacts"]]
        missing = [name for name in expected if name not in by_name]
        if missing:
            raise SystemExit(f"download lock inputs missing: {', '.join(missing)}")
        apks = [by_name[name] for name in expected]
    args.out.mkdir(parents=True, exist_ok=True)
    scans = []
    completed: dict[str, dict] = {}
    if args.resume:
        for scan_path in (args.out / "apks").glob("*.json"):
            value = read_json(scan_path)
            if value.get("runtime_lock_id") == runtime["runtime_lock_id"]:
                completed[value.get("apk", {}).get("filename", "")] = value
    for index, apk in enumerate(apks, 1):
        if apk.name in completed and completed[apk.name].get("apk", {}).get("sha256") == sha256_file(apk):
            value = completed[apk.name]
            refresh_scan_summary(value)
            package = value["apk"].get("package") or apk.stem
            write_json(args.out / "apks" / f"{package}.json", value)
            print(f"[{index}/{len(apks)}] reuse {apk.name}", flush=True)
            scans.append(value)
            continue
        print(f"[{index}/{len(apks)}] scanning {apk.name}", flush=True)
        value = scan_apk(
            apk,
            runtime,
            include_elf=not args.no_elf,
            target_abi=args.target_abi,
        )
        scans.append(value)
        package = value["apk"].get("package") or apk.stem
        write_json(args.out / "apks" / f"{package}.json", value)
    corpus_manifest = read_json(args.corpus_manifest) if args.corpus_manifest else None
    corpus = {
        "selection": corpus_manifest,
        "downloads": download_lock,
    } if corpus_manifest or download_lock else None
    portfolio = aggregate(scans, corpus)
    write_json(args.out / "gap-registry.json", portfolio)
    (args.out / "REPORT.md").write_text(markdown_report(portfolio), encoding="utf-8")
    print(f"portfolio: {len(scans)} APKs, {portfolio['metrics']['unique_gap_count']} unique candidates")
    return 0


def _runtime_summary(value: dict) -> dict:
    summary = copy.deepcopy({key: item for key, item in value.items() if key != "classes"})
    roots = [
        ("WESTLAKE_RUNTIME_ROOT", os.environ.get("WESTLAKE_RUNTIME_ROOT")),
        ("BRIDGE_ARM64", os.environ.get("BRIDGE_ARM64")),
    ]
    for variable, root in roots:
        if not root:
            continue
        prefix = str(Path(root).resolve()) + os.sep
        for group in ("boot_classpath", "bridge_libraries"):
            for artifact in summary.get(group, []):
                path = artifact.get("path", "")
                if path.startswith(prefix):
                    artifact["path"] = "${" + variable + "}/" + path[len(prefix) :]
    return summary


if __name__ == "__main__":
    sys.exit(main())
