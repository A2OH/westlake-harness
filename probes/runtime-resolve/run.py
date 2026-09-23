#!/usr/bin/env python3
"""Resolve an app's runtime-looked-up symbols on the board, inside the app's own namespace.

The static row (sym:runtime-resolved) can only report that a public NDK name appears as a string
in a library. Whether the lookup succeeds depends on the loader: on which directories the search
path names, in which order, and on what the winning file's dependency tree exports. None of that
is in any symbol table, so it has to be asked on the device.

Two details decide whether the answer is the app's answer or a different process's:

  * the search path is taken from the launch's own run.sh, not reconstructed, and the in-namespace
    runtime prefix is left as-is when running inside the namespace;
  * the child runs in a private mount namespace, so /data/local/tmp/asx is the staged runtime
    there and something else entirely outside it. Running outside and substituting the real path
    is supported, and reported as such, because it measures a different process's view: a stale
    copy of that directory outside the namespace answered a different set of symbols than the
    staged one, which is exactly the mistake this field exists to make visible.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

IN_NAMESPACE_ROOT = "/data/local/tmp/asx"


def host_readable(local: Path, staging: str | None) -> str:
    """A path the hdc binary itself can open.

    A Windows hdc driving the device cannot read a WSL path, and reports it as a missing file
    rather than as a path it does not understand. Copying into a directory both sides can see, and
    naming it the way that hdc expects, keeps the failure from looking like a missing input.
    """
    if not staging:
        return str(local)
    target = Path(staging) / local.name
    if target.resolve() != local.resolve():
        target.write_bytes(local.read_bytes())
    text = str(target)
    if text.startswith("/mnt/") and len(text) > 6 and text[6] == "/":
        return f"{text[5].upper()}:\\" + text[7:].replace("/", "\\")
    return text


def shell(hdc: str, serial: str, command: str, timeout: int = 180) -> str:
    result = subprocess.run([hdc, "-t", serial, "shell", command],
                            capture_output=True, text=True, timeout=timeout, check=False)
    return result.stdout


def search_path(run_sh: Path) -> str:
    match = re.search(r"^export LD_LIBRARY_PATH=(.+)$", run_sh.read_text(), re.M)
    if not match:
        raise SystemExit(f"no LD_LIBRARY_PATH in {run_sh}")
    return match.group(1).strip()


#: The resolver's own header. Recognised rather than skipped by position: the namespace helper
#: prints a line of its own first, so dropping the first line drops that and lets the header
#: through as a row -- one phantom symbol named "symbol", with status "status".
HEADER = ["library", "symbol", "status", "provider"]


def parse(text: str) -> list[dict[str, str]]:
    rows = []
    for line in text.splitlines():
        parts = line.rstrip("\n").split("\t")
        if len(parts) != 4 or parts == HEADER:
            continue
        rows.append(dict(zip(HEADER, parts)))
    return rows


def summarise(rows: list[dict[str, str]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_library: dict[str, dict[str, int]] = {}
    providers: dict[str, int] = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        library = by_library.setdefault(row["library"], {})
        library[row["status"]] = library.get(row["status"], 0) + 1
        if row["status"] == "resolved":
            providers[row["provider"]] = providers.get(row["provider"], 0) + 1
    return {"by_status": by_status, "by_library": by_library, "resolved_from": providers}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-sh", required=True, type=Path,
                        help="run.sh from the launch whose search path is being measured")
    parser.add_argument("--runtime", required=True,
                        help="the staged runtime directory on the device, which is "
                             f"{IN_NAMESPACE_ROOT} inside the app's namespace")
    parser.add_argument("--candidates", required=True, type=Path,
                        help="TSV of <library><TAB><symbol>, from the sym:runtime-resolved rows")
    parser.add_argument("--resolver", type=Path,
                        default=Path(__file__).resolve().parent / "out" / "wl-resolve")
    parser.add_argument("--namespace-helper",
                        help="source_app_namespace on the device: runs the resolver in the app's "
                             "mount namespace and uid, so it sees what the app sees")
    parser.add_argument("--uid", default="20010054", help="app uid for --namespace-helper")
    parser.add_argument("--host-staging",
                        help="a directory the hdc binary can read, when it cannot see this "
                             "filesystem (a Windows hdc driving the device from WSL)")
    parser.add_argument("--hdc", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    path = search_path(args.run_sh)
    for local in (args.resolver, args.candidates):
        if not local.is_file():
            raise SystemExit(f"missing input: {local}")
        # The runtime lives under /data/app/el2, which hdc cannot write into: stage through
        # /data/local/tmp and copy as root, the same way the launcher stages the runtime itself.
        staged = f"/data/local/tmp/{local.name}"
        sent = subprocess.run([args.hdc, "-t", args.serial, "file", "send",
                               host_readable(local, args.host_staging), staged],
                              capture_output=True, text=True, check=False)
        if "FileTransfer finish" not in (sent.stdout or ""):
            raise SystemExit(f"could not send {local.name} to the device: "
                             f"{(sent.stdout or sent.stderr).strip()[:300]}")
        shell(args.hdc, args.serial,
              f"cp {staged} {args.runtime}/{local.name} && "
              f"chown {args.uid}:{args.uid} {args.runtime}/{local.name}")
        landed = shell(args.hdc, args.serial,
                       f"test -s {args.runtime}/{local.name} && echo ok").strip()
        if "ok" not in landed:
            raise SystemExit(f"{local.name} did not land in {args.runtime}; "
                             "the runtime directory may belong to a finished launch")
    resolver = f"{args.runtime}/{args.resolver.name}"
    shell(args.hdc, args.serial, f"chmod 755 {resolver}")

    if args.namespace_helper:
        # Inside the namespace the runtime is at its in-namespace prefix, so the recorded search
        # path is used verbatim -- the whole point of entering it.
        inner = (f"LD_LIBRARY_PATH='{path}' {IN_NAMESPACE_ROOT}/{args.resolver.name} "
                 f"{IN_NAMESPACE_ROOT}/{args.candidates.name} 2>{IN_NAMESPACE_ROOT}/wl-resolve.err")
        command = (f"{args.namespace_helper} {args.runtime} {args.uid} "
                   f"/system/bin/sh -c \"{inner}\"")
        view = "app-namespace"
    else:
        # Outside it, the same prefix names a different directory, so it is rewritten to the real
        # staged one. Still a different process's view: root, and not the app's mounts.
        command = (f"LD_LIBRARY_PATH='{path.replace(IN_NAMESPACE_ROOT, args.runtime)}' "
                   f"{resolver} {args.runtime}/{args.candidates.name} "
                   f"2>{args.runtime}/wl-resolve.err")
        view = "global-namespace-with-substituted-runtime"

    text = shell(args.hdc, args.serial, command)
    rows = parse(text)
    expected = len([line for line in args.candidates.read_text().splitlines() if "\t" in line])
    if rows and len(rows) != expected:
        raise SystemExit(f"resolver returned {len(rows)} rows for {expected} candidates; "
                         "output was truncated or interleaved, so the counts would understate")
    if not rows:
        raise SystemExit(f"resolver produced no rows; device said:\n{text[:800]}")
    report = {
        "schema": "westlake-runtime-resolve/v1",
        "view": view,
        "note": ("what the loader returns for this search path. A resolved symbol is not proof "
                 "the app asks for it, and an unresolved one is only a gap if it does."),
        "runtime": args.runtime,
        "search_path": path,
        "candidates": len(rows),
        "summary": summarise(rows),
        "symbols": rows,
    }
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    summary = report["summary"]
    print(f"RUNTIME_RESOLVE {view} candidates={len(rows)} " +
          " ".join(f"{k}={v}" for k, v in sorted(summary["by_status"].items())))
    for provider, count in sorted(summary["resolved_from"].items(), key=lambda kv: -kv[1]):
        print(f"  {count:>4} resolved from {provider}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
