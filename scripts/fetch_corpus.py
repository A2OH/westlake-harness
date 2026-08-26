#!/usr/bin/env python3
"""Download a corpus with EFF apkeep and write a content-addressed lock file."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from androguard.core.apk import APK
from loguru import logger


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("corpus/top10.json"))
    parser.add_argument("--out", type=Path, default=Path("corpus/apks"))
    parser.add_argument("--apkeep", type=Path, required=True)
    parser.add_argument("--lock", type=Path, default=Path("corpus/downloads.lock.json"))
    parser.add_argument("--abi", help="request and verify one Android ABI, e.g. arm64-v8a")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    logger.remove()
    args = arguments()
    corpus = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    for app in corpus["apps"]:
        package = app["package"]
        existing = package_artifacts(args.out, package)
        if existing:
            print(f"skip {package}: {existing[0].name}", flush=True)
            continue
        requested_version = app.get("version")
        app_id = f"{package}@{requested_version}" if requested_version else package
        command = [str(args.apkeep), "-a", app_id, "-d", "apk-pure", "-r", "1"]
        if args.abi:
            command.extend(["-o", f"arch={args.abi}"])
        command.append(str(args.out))
        subprocess.run(command, check=True)

    records = []
    for app in corpus["apps"]:
        matches = package_artifacts(args.out, app["package"])
        if len(matches) != 1:
            raise SystemExit(f"expected one download for {app['package']}, found {len(matches)}")
        path = matches[0]
        if not zipfile.is_zipfile(path):
            raise SystemExit(f"download is not an APK-compatible ZIP: {path}")
        container_manifest = None
        with zipfile.ZipFile(path) as archive:
            if "manifest.json" in archive.namelist():
                try:
                    container_manifest = json.loads(archive.read("manifest.json"))
                except json.JSONDecodeError:
                    pass
        native_abis = container_native_abis(path)
        split_artifacts, native_libraries = container_contents(path)
        if args.abi and native_abis and args.abi not in native_abis:
            raise SystemExit(
                f"requested {args.abi} for {path}, but container has: {', '.join(native_abis)}"
            )
        if container_manifest:
            actual_package = container_manifest.get("package_name")
            version_code = container_manifest.get("version_code")
            version_name = container_manifest.get("version_name")
        else:
            apk = APK(str(path), skip_analysis=False)
            actual_package = apk.get_package()
            version_code = apk.get_androidversion_code()
            version_name = apk.get_androidversion_name()
        if actual_package != app["package"]:
            raise SystemExit(
                f"package mismatch for {path}: expected {app['package']}, got {actual_package}"
            )
        requested_version = app.get("version")
        if requested_version and str(version_name) != str(requested_version):
            raise SystemExit(
                f"version mismatch for {path}: expected {requested_version}, got {version_name}"
            )
        records.append(
            {
                "eligible_rank": app["eligible_rank"],
                "chart_rank": app["chart_rank"],
                "name": app["name"],
                "package": app["package"],
                "filename": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "version_code": version_code,
                "version_name": version_name,
                "requested_version": requested_version,
                "container_format": path.suffix.lower().lstrip("."),
                "split_count": len((container_manifest or {}).get("split_apks", [])) or 1,
                "split_artifacts": split_artifacts,
                "native_abis": native_abis,
                "native_libraries": native_libraries,
                "requested_abi": args.abi,
            }
        )
    lock = {
        "schema_version": "westlake-download-lock/v0.2",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "corpus_manifest_sha256": sha256_file(args.manifest),
        "download_source": corpus["download"],
        "requested_abi": args.abi,
        "artifacts": records,
    }
    args.lock.parent.mkdir(parents=True, exist_ok=True)
    args.lock.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"locked {len(records)} APK containers -> {args.lock}")
    return 0


def container_native_abis(path: Path) -> list[str]:
    abis: set[str] = set()

    def collect(archive: zipfile.ZipFile) -> None:
        for name in archive.namelist():
            parts = name.split("/")
            if len(parts) >= 3 and parts[0] == "lib" and name.endswith(".so"):
                abis.add(parts[1])

    with zipfile.ZipFile(path) as archive:
        if path.suffix.lower() in {".xapk", ".apkm"}:
            for name in archive.namelist():
                if not name.lower().endswith(".apk"):
                    continue
                with zipfile.ZipFile(io.BytesIO(archive.read(name))) as inner:
                    collect(inner)
        else:
            collect(archive)
    return sorted(abis)


def container_contents(path: Path) -> tuple[list[dict], list[dict]]:
    """Return content-addressed inner APKs and their packaged native libraries."""
    split_artifacts: list[dict] = []
    native_libraries: list[dict] = []

    def inventory_apk(name: str, payload: bytes) -> None:
        split_artifacts.append(
            {
                "filename": name,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
        with zipfile.ZipFile(io.BytesIO(payload)) as apk:
            for member in apk.infolist():
                parts = member.filename.split("/")
                if len(parts) < 3 or parts[0] != "lib" or not member.filename.endswith(".so"):
                    continue
                library = apk.read(member)
                native_libraries.append(
                    {
                        "split": name,
                        "path": member.filename,
                        "abi": parts[1],
                        "bytes": len(library),
                        "sha256": hashlib.sha256(library).hexdigest(),
                    }
                )

    if path.suffix.lower() in {".xapk", ".apkm"}:
        with zipfile.ZipFile(path) as container:
            for member in sorted(container.namelist()):
                if member.lower().endswith(".apk"):
                    inventory_apk(member, container.read(member))
    else:
        inventory_apk(path.name, path.read_bytes())
    return split_artifacts, sorted(
        native_libraries,
        key=lambda item: (item["abi"], item["split"], item["path"]),
    )


def package_artifacts(directory: Path, package: str) -> list[Path]:
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.suffix.lower() in {".apk", ".xapk", ".apkm"}
        and (path.stem == package or path.stem.startswith(package + "@"))
    )


if __name__ == "__main__":
    raise SystemExit(main())
