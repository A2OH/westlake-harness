#!/bin/bash
# The runtime half of sym:runtime-resolved: a standalone binary, not an APK probe, because the
# question is what the loader answers for a given search path and that needs no app.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SDK=${OHOS_SDK_NATIVE:?set OHOS_SDK_NATIVE to the OH SDK native directory}
mkdir -p "$ROOT/out"
"$SDK/llvm/bin/clang" --target=aarch64-linux-ohos --sysroot="$SDK/sysroot" \
    -O2 -Wall -Wextra -o "$ROOT/out/wl-resolve" "$ROOT/resolve.c"
sha256sum "$ROOT/out/wl-resolve"
