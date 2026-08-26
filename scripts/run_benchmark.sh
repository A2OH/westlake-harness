#!/bin/bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
: "${BRIDGE_ARM64:?set BRIDGE_ARM64 to the active arm64 Westlake build directory}"
OUT=${1:-"$ROOT/benchmark/$(date +%F)"}
TARGET_ABI=${TARGET_ABI:-arm64-v8a}
CORPUS_DIR=${CORPUS_DIR:-"$ROOT/corpus/apks"}
DOWNLOAD_LOCK=${DOWNLOAD_LOCK:-"$ROOT/corpus/downloads.lock.json"}

mkdir -p "$OUT"
export PYTHONPATH="$ROOT/harness${PYTHONPATH:+:$PYTHONPATH}"

python3 -m westlake_gap.cli snapshot-runtime \
  --classpath-file "$ROOT/runtime/westlake-arm64-current.txt" \
  --bridge "$BRIDGE_ARM64/out/liboh_adapter_bridge.so" \
  --target-abi "$TARGET_ABI" \
  --out "$OUT/runtime-index.json" \
  --summary-out "$OUT/runtime-lock.json"

python3 -m westlake_gap.cli benchmark "$CORPUS_DIR" \
  --runtime "$OUT/runtime-index.json" \
  --out "$OUT" \
  --corpus-manifest "$ROOT/corpus/top10.json" \
  --download-lock "$DOWNLOAD_LOCK" \
  --resume
