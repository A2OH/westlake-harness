#!/bin/bash
# Capture from the OS, not from the app: a small AF_PACKET writer, not a port of tcpdump.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SDK=${OHOS_SDK_NATIVE:?set OHOS_SDK_NATIVE to the OH SDK native directory}
mkdir -p "$ROOT/out"
"$SDK/llvm/bin/clang" --target=aarch64-linux-ohos --sysroot="$SDK/sysroot" \
    -O2 -Wall -Wextra -o "$ROOT/out/wl-netcap" "$ROOT/netcap.c"
sha256sum "$ROOT/out/wl-netcap"
