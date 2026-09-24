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
    RuntimeResolver,
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
        "--platform-jar",
        type=Path,
        help="reference android.jar: find Java APIs that packaged native code calls back into via JNIEnv",
    )
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

    reach_cmd = commands.add_parser(
        "startup-reach",
        help="static call-graph reachability from the manifest entry points: the stage at which each platform contract is first needed",
    )
    reach_cmd.add_argument("input", type=Path, help=".apk/.xapk/.apkm")
    reach_cmd.add_argument("--runtime", type=Path, help="runtime index: platform class hierarchy and members, for precise callbacks")
    reach_cmd.add_argument("--scan", type=Path, help="scan JSON of the same APK: report stages for its call sites and native libraries")
    reach_cmd.add_argument("--graph-cache", type=Path, help="pickle of the call graph: written if absent, reused if present")
    reach_cmd.add_argument("--trace", type=Path, help="ART method trace of the same APK: measure recall and precision against it")
    reach_cmd.add_argument("--out", required=True, type=Path)

    observe_cmd = commands.add_parser(
        "trace-observe",
        help="turn an ART method trace recorded on real Android into the platform touches and libraries of that run",
    )
    observe_cmd.add_argument("input", type=Path, help=".apk/.xapk/.apkm the trace was recorded from")
    observe_cmd.add_argument("--trace", required=True, type=Path)
    observe_cmd.add_argument("--runtime", type=Path, help="runtime index, to match a platform call to the subclass that ran it")
    observe_cmd.add_argument("--loaded-libs", type=Path, help="text file: one app library loaded during the run per line")
    observe_cmd.add_argument("--scenario", default="", help="what the run covered, e.g. 'cold start to sign-in screen'")
    observe_cmd.add_argument("--graph-cache", type=Path)
    observe_cmd.add_argument("--out", required=True, type=Path)

    fw_cmd = commands.add_parser(
        "trace-framework-check",
        help="look up every platform method a recorded run executed in the runtime under test: missing, hollow, or native and unbound",
    )
    fw_cmd.add_argument("input", type=Path, help=".apk/.xapk/.apkm the trace was recorded from")
    fw_cmd.add_argument("--trace", required=True, type=Path)
    fw_cmd.add_argument("--runtime", required=True, type=Path, help="runtime index of the build under test")
    fw_cmd.add_argument("--westlake-libs", required=True, type=Path, help="deployed runtime libraries: the JNI bindings actually available")
    fw_cmd.add_argument("--proven-trace", type=Path, action="append", default=[],
                        help="trace of an app that already runs on the target: what it also executes is proven there; repeat")
    fw_cmd.add_argument("--platform-jar", type=Path, help="reference android.jar: marks which findings are public API (the boundary) rather than internals")
    fw_cmd.add_argument("--frontier", help="method name prefix of the furthest point reached on the target, e.g. 'Landroid/location/LocationManager;-><init>'")
    fw_cmd.add_argument("--graph-cache", type=Path)
    fw_cmd.add_argument("--out", required=True, type=Path)

    res_cmd = commands.add_parser(
        "oh-resolve",
        help="resolve an APK's native imports against the board's libraries and the staged Westlake runtime",
    )
    res_cmd.add_argument("--scan", required=True, type=Path, help="scan JSON for the APK")
    res_cmd.add_argument("--app-key", required=True)
    res_cmd.add_argument("--lib-dir", action="append", type=Path, required=True,
                         help="directory of libraries in the index (OH system libraries pulled from the board, the staged runtime, ...); repeat")
    res_cmd.add_argument("--ndk-api-dir", type=Path, help="NDK stub libraries for one API level: names the NDK library declaring each missing symbol")
    res_cmd.add_argument("--board", default="", help="board description recorded in the output")
    res_cmd.add_argument("--out", required=True, type=Path, help="oh-import-resolution JSON to write")

    dep_cmd = commands.add_parser(
        "deploy-check",
        help="is every library the Westlake runtime asks for deployed, and is each deployed Westlake binary built from today's source",
    )
    dep_cmd.add_argument("--westlake", required=True, type=Path, help="Westlake source tree")
    dep_cmd.add_argument("--report", action="append", type=Path, default=[],
                         help="framework build report and/or app launch report (device-report.json): what was staged, with hashes; repeat")
    dep_cmd.add_argument("--staged-dir", action="append", type=Path, default=[],
                         help="local directory holding staged binaries (runtime package, WebView input, ...), matched by hash; repeat")
    dep_cmd.add_argument("--board-libs", type=Path, help="library paths present on the board, one per line")
    dep_cmd.add_argument("--title", default="Deployment check")
    dep_cmd.add_argument("--out", required=True, type=Path, help="output directory")

    trace_cmd = commands.add_parser(
        "trace-methods",
        help="decode an ART sampling trace from the board and list which of the app's own methods ran",
    )
    trace_cmd.add_argument("--trace", required=True, type=Path,
                           help="trace file pulled from the device (WESTLAKE_METHOD_TRACE=<ms> writes it)")
    trace_cmd.add_argument("--prefix", action="append", default=[],
                           help="class prefix to report, e.g. com.mcdonalds; repeat. Default: every method")
    trace_cmd.add_argument("--out", type=Path, help="write the report here instead of stdout")

    ndk_cmd = commands.add_parser(
        "ndk-coverage",
        help="measure the entire public NDK against a board's libraries and classify how each missing symbol is supplied",
    )
    ndk_cmd.add_argument("--ndk-api-dir", required=True, type=Path,
                         help="NDK sysroot stub directory for one API level, e.g. .../sysroot/usr/lib/aarch64-linux-android/33")
    ndk_cmd.add_argument("--oh-libs", required=True, type=Path, help="directory of OpenHarmony system libraries pulled from the board")
    ndk_cmd.add_argument("--westlake-libs", required=True, type=Path, help="directory of deployed Westlake runtime libraries pulled from the board")
    ndk_cmd.add_argument("--westlake", type=Path, help="Westlake source tree: report which missing symbols already have a build manifest")
    ndk_cmd.add_argument("--model", type=Path, help="weld model JSON (default: data/ndk-weld-model.json)")
    ndk_cmd.add_argument("--title", default="NDK coverage on OpenHarmony")
    ndk_cmd.add_argument("--out", required=True, type=Path, help="output directory")

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
    gap.add_argument("--ndk-coverage", type=Path,
                     help="ndk-coverage.json: classify native gaps by how the NDK supplies them (package / libc-abi / weld / absence)")
    gap.add_argument("--observed", type=Path, help="trace-observe output: mark each gap touched or not on a recorded real-Android run")
    gap.add_argument("--probe-results", type=Path,
                     help="white-box probe results measured on the board: they replace the static verdict of the rows they back, "
                          "for the exact Westlake commit they were measured on")
    gap.add_argument("--board-libs", type=Path,
                     help="library paths present on the board, one per line: finds packaged libraries a board library shadows")
    gap.add_argument("--runtime", type=Path,
                     help="runtime index (snapshot-runtime) of the provider: finds platform classes whose natives "
                          "no deployed library registers")
    gap.add_argument("--runtime-libs", type=Path,
                     help="the staged native runtime: a directory, its artifacts.json, or a listing one per line. "
                          "Finds libraries the runtime ships that its own loader answers without opening")
    gap.add_argument("--policy", type=Path, default=Path(__file__).parent / "data" / "oh-app-data-policy.json")
    gap.add_argument("--blockers", type=Path, help="known-blockers JSON: backtest the map against observed failures")
    gap.add_argument("--blockers-status", action="store_true",
                     help="report known blockers as open/closed against this provider instead of as a backtest")
    gap.add_argument("--out", required=True, type=Path, help="output directory")
    return root



def _runtime_libraries(path: Path | None) -> list[str] | None:
    """Library names the staged native runtime ships, from a directory, an artifacts.json or a listing."""
    if path is None or not path.exists():
        return None
    if path.is_dir():
        report = path / "artifacts.json"
        if report.exists():
            return sorted(read_json(report).get("artifacts", {}))
        return sorted(p.name for p in path.iterdir() if p.suffix == ".so")
    if path.suffix == ".json":
        return sorted(read_json(path).get("artifacts", {}))
    return [line.rsplit("/", 1)[-1] for line in path.read_text().split()]


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "trace-framework-check":
        import pickle

        from . import reach, tracecmp
        from .contracts import manifest_facts
        from .platformapi import load_platform_members

        if args.graph_cache and args.graph_cache.exists():
            graph = pickle.loads(args.graph_cache.read_bytes())
        else:
            facts = manifest_facts(args.input)
            graph = reach.build_graph(args.input, [c["name"] for c in facts["components"] if c.get("name")])
            if args.graph_cache:
                args.graph_cache.write_bytes(pickle.dumps(graph, protocol=pickle.HIGHEST_PROTOCOL))
        app_classes = {graph.cls_names[cid] for cid in graph.defined}
        runtime = read_json(args.runtime)
        order = tracecmp.execution_order(args.trace)
        tables, exports = tracecmp.jni_tables(args.westlake_libs)
        result = tracecmp.framework_check(set(order), app_classes, runtime, RuntimeResolver(runtime), tables, exports, order)
        proven: set[str] = set()
        for path in args.proven_trace:
            proven |= tracecmp.executed_methods(path)
        reference = load_platform_members(args.platform_jar) if args.platform_jar else {}

        def public(key: str) -> bool:
            owner, _, sig = key.partition("->")
            record = reference.get(owner[1:-1])
            name, _, rest = sig.partition("(")
            return bool(record) and any(n == name and d == "(" + rest and a & 5 for n, d, a in record["methods"])

        frontier = min((rank for key, rank in order.items() if args.frontier and key.startswith(args.frontier)), default=None)
        for finding in result["findings"]:
            finding["proven_on_target"] = finding["method"] in proven
            finding["public_api"] = public(finding["method"])
            finding["after_frontier"] = frontier is not None and (finding["first_seen"] or 0) > frontier
        platform_total = sum(result["counts"].values())
        platform_methods = [k for k in order if k.partition("->")[0] not in app_classes]
        result["summary"] = {
            "runtime_lock_id": runtime.get("runtime_lock_id"),
            "methods_executed": len(order), "platform_methods_executed": platform_total,
            "platform_methods_proven_on_target": sum(1 for k in platform_methods if k in proven) if proven else None,
            "frontier_rank": frontier, "jni_tables": len(tables), "jni_exports": len(exports),
            "boundary_failures": [f for f in result["findings"] if not f["proven_on_target"] and (
                f["state"] in {"native-unbound", "hollow"} or (f["state"] in {"member-missing", "class-missing"} and f["public_api"]))],
        }
        write_json(args.out, result)
        print(f"{platform_total} platform methods executed: " + ", ".join(f"{k} {v}" for k, v in sorted(result["counts"].items()))
              + f"; boundary failures not proven on target: {len(result['summary']['boundary_failures'])} -> {args.out}")
        return 0
    if args.command in {"startup-reach", "trace-observe"}:
        import pickle

        from . import reach, tracecmp
        from .contracts import manifest_facts

        facts = manifest_facts(args.input)
        if args.graph_cache and args.graph_cache.exists():
            cached = pickle.loads(args.graph_cache.read_bytes())
            reach.build_graph = lambda _path, _names=(): cached  # type: ignore[assignment]
        elif args.graph_cache:
            built = reach.build_graph(args.input, [c["name"] for c in facts["components"] if c.get("name")])
            args.graph_cache.write_bytes(pickle.dumps(built, protocol=pickle.HIGHEST_PROTOCOL))
            reach.build_graph = lambda _path, _names=(): built  # type: ignore[assignment]
        runtime = read_json(args.runtime) if args.runtime else None
        if args.command == "trace-observe":
            graph = reach.build_graph(args.input, [c["name"] for c in facts["components"] if c.get("name")])
            libs = [line.strip() for line in args.loaded_libs.read_text().splitlines() if line.strip()] if args.loaded_libs else []
            value = tracecmp.observe(graph, tracecmp.executed_methods(args.trace), runtime, libs, args.scenario)
            write_json(args.out, value)
            print(f"{value['executed_methods']} methods executed, {len(value['executed_app_methods'])} the app's own, "
                  f"{len(value['platform_touch'])} platform members touched -> {args.out}")
            return 0
        graph, result, summary = reach.analyse(args.input, facts, runtime)
        value = reach.export(graph, result, summary, read_json(args.scan) if args.scan else None)
        if args.trace:
            value["trace_comparison"] = tracecmp.compare(graph, result, tracecmp.executed_methods(args.trace))
        write_json(args.out, value)
        print(f"{summary['methods_with_code']} methods: " + ", ".join(f"{k} {v}" for k, v in summary["methods_by_stage"].items())
              + f" -> {args.out}")
        return 0
    if args.command == "oh-resolve":
        from . import ohresolve

        provided, libraries = ohresolve.index_exports(args.lib_dir)
        app = ohresolve.resolve(read_json(args.scan), provided, ohresolve.ndk_declarations(args.ndk_api_dir))
        write_json(args.out, {"board": {"description": args.board, "libraries_indexed": libraries},
                              "apps": {args.app_key: app}})
        print(f"{args.app_key}: {app['resolved']}/{app['symbols']} resolved, {len(app['missing'])} missing "
              f"against {len(libraries)} libraries -> {args.out}")
        return 0
    if args.command == "deploy-check":
        from . import deploy

        result = deploy.check(args.westlake, [read_json(r) for r in args.report], args.staged_dir, args.board_libs)
        args.out.mkdir(parents=True, exist_ok=True)
        write_json(args.out / "deploy-check.json", result)
        (args.out / "DEPLOY-CHECK.md").write_text(deploy.markdown(result, args.title))
        summary = result["summary"]
        print(f"{summary['loads']} libraries asked for, {summary['staged_files']} staged: "
              f"missing {summary['missing'] or 'none'}; older than source {summary['older_than_source'] or 'none'} -> {args.out}")
        return 1 if summary["missing"] or summary["older_than_source"] else 0
    if args.command == "ndk-coverage":
        from . import ndk

        model = ndk.load_model(args.model)
        cov = ndk.coverage(
            ndk.ndk_surface(args.ndk_api_dir),
            ndk.library_exports(args.oh_libs),
            ndk.library_exports(args.westlake_libs),
            model,
            ndk.westlake_manifest_index(args.westlake) if args.westlake else None,
        )
        cov["ndk_api_dir"] = args.ndk_api_dir.name
        args.out.mkdir(parents=True, exist_ok=True)
        write_json(args.out / "ndk-coverage.json", cov)
        (args.out / "NDK-COVERAGE.md").write_text(ndk.markdown(cov, model, args.title))
        status = cov["summary"]["status"]
        print(f"{cov['summary']['symbols']} NDK symbols: OH {status.get('oh', 0)}, Westlake {status.get('westlake', 0)}, "
              f"missing {status.get('missing', 0)} -> {args.out}")
        return 0
    if args.command == "trace-methods":
        from .methodtrace import markdown, parse, ran

        trace = parse(args.trace.read_bytes())
        prefixes = args.prefix or [""]
        hits = ran(trace, prefixes)
        report = markdown(trace, hits, prefixes)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(report)
        else:
            print(report, end="")
        print(f"{len(hits)} methods ran from {len(prefixes)} prefix(es), {trace['records']} samples", flush=True)
        return 0
    if args.command == "gap-map":
        from .contracts import manifest_facts
        from .gapmap import backtest, build_map, markdown, runtime_class_strings
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
                            read_json(args.policy), args.manifest_repo,
                            ndk_cov=read_json(args.ndk_coverage) if args.ndk_coverage else None,
                            observed=read_json(args.observed) if args.observed else None,
                            probe_results=read_json(args.probe_results) if args.probe_results else None,
                            board_paths=args.board_libs.read_text().split() if args.board_libs else None,
                            runtime_libraries=_runtime_libraries(args.runtime_libs),
                            runtime_index=read_json(args.runtime) if args.runtime else None,
                            runtime_class_paths=runtime_class_strings(args.runtime_libs)
                            if args.runtime_libs and args.runtime_libs.is_dir() else None,
                            aosp_root=args.aosp)
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
        members = None
        if args.platform_jar:
            from .platformapi import load_platform_members

            members = load_platform_members(args.platform_jar)
        value = scan_apk(
            args.input,
            runtime,
            include_elf=not args.no_elf,
            target_abi=args.target_abi,
            native_reach=args.native_reach,
            platform_members=members,
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
