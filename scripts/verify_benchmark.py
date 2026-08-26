#!/usr/bin/env python3
"""Verify that a benchmark is complete, content-locked, and internally consistent."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--benchmark", type=Path, default=Path("benchmark/2026-08-20"))
    parser.add_argument("--corpus-manifest", type=Path, default=Path("corpus/top10.json"))
    parser.add_argument("--download-lock", type=Path, default=Path("corpus/downloads.lock.json"))
    parser.add_argument("--corpus-dir", type=Path, default=Path("corpus/apks"))
    parser.add_argument("--allow-subset", action="store_true", help="verify an ABI cohort that is a ranked corpus subset")
    return parser.parse_args()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main() -> int:
    args = arguments()
    root = args.root.resolve()
    benchmark = args.benchmark if args.benchmark.is_absolute() else root / args.benchmark
    corpus_path = args.corpus_manifest if args.corpus_manifest.is_absolute() else root / args.corpus_manifest
    lock_path = args.download_lock if args.download_lock.is_absolute() else root / args.download_lock
    corpus_dir = args.corpus_dir if args.corpus_dir.is_absolute() else root / args.corpus_dir
    corpus = load(corpus_path)
    lock = load(lock_path)
    runtime = load(benchmark / "runtime-lock.json")
    registry = load(benchmark / "gap-registry.json")

    require(len(corpus["apps"]) == 10, "corpus selection must contain exactly ten apps")
    corpus_packages = [item["package"] for item in corpus["apps"]]
    locked_packages = [item["package"] for item in lock["artifacts"]]
    if args.allow_subset:
        require(locked_packages, "subset download lock is empty")
        require(
            locked_packages == [package for package in corpus_packages if package in locked_packages],
            "subset download lock must preserve ranked corpus order",
        )
        expected_packages = locked_packages
    else:
        require(len(lock["artifacts"]) == 10, "download lock must contain exactly ten artifacts")
        expected_packages = corpus_packages
        require(locked_packages == expected_packages, "download lock package order must match the ranked corpus")
    expected_count = len(expected_packages)

    lock_by_package = {}
    for artifact in lock["artifacts"]:
        path = corpus_dir / artifact["filename"]
        require(path.is_file(), f"download missing: {path}")
        require(path.stat().st_size == artifact["bytes"], f"size mismatch: {path.name}")
        require(sha256_file(path) == artifact["sha256"], f"SHA-256 mismatch: {path.name}")
        lock_by_package[artifact["package"]] = artifact

    scan_paths = sorted((benchmark / "apks").glob("*.json"))
    require(len(scan_paths) == expected_count, f"benchmark must contain exactly {expected_count} per-app scans")
    seen_packages = set()
    for scan_path in scan_paths:
        scan = load(scan_path)
        package = scan["apk"]["package"]
        seen_packages.add(package)
        require(package in lock_by_package, f"scan package not present in lock: {package}")
        require(
            scan["apk"]["sha256"] == lock_by_package[package]["sha256"],
            f"scan/download hash mismatch: {package}",
        )
        require(
            scan["runtime_lock_id"] == runtime["runtime_lock_id"],
            f"runtime mismatch: {package}",
        )
        require(
            scan["inventory"].get("native_resolution", {}).get("target_abi")
            == runtime.get("target_abi"),
            f"native target ABI mismatch: {package}",
        )
    require(seen_packages == set(expected_packages), "per-app scans do not cover the exact corpus")

    require(runtime["class_count"] > 0, "runtime class index is empty")
    require(len(runtime["boot_classpath"]) == 10, "runtime lock must contain ten boot JARs")
    if runtime.get("schema_version") == "westlake-apk-gap/v0.2":
        require(runtime.get("target_abi"), "v0.2 runtime lock has no target ABI")
    if lock.get("requested_abi"):
        require(
            lock["requested_abi"] == runtime["target_abi"],
            "download lock ABI does not match runtime ABI",
        )
        for artifact in lock["artifacts"]:
            if artifact.get("native_abis"):
                require(
                    runtime["target_abi"] in artifact["native_abis"],
                    f"locked artifact lacks target ABI: {artifact['package']}",
                )
    require(registry["runtime_lock_id"] == runtime["runtime_lock_id"], "registry/runtime mismatch")
    require(registry["metrics"]["apk_count"] == expected_count, "registry APK count is wrong")
    require(registry["metrics"]["scan_success_count"] == expected_count, "not every scan succeeded")
    require(registry["metrics"]["unique_gap_count"] == len(registry["gaps"]), "gap count mismatch")
    require(
        all("CU" not in gap["classifications"] for gap in registry["gaps"]),
        "unresolved findings leaked into the gap registry",
    )
    require((benchmark / "REPORT.md").stat().st_size > 0, "Markdown report is missing or empty")
    print(
        f"PASS: {expected_count} locked downloads, {expected_count} matching scans, "
        f"{registry['metrics']['unique_gap_count']} unique candidates, "
        f"ABI {runtime.get('target_abi', 'legacy-unspecified')}, runtime {runtime['runtime_lock_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
