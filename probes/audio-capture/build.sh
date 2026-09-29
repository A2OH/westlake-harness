#!/bin/bash
# build.sh <oh-sdk-native>: builds out/oh_record for the arm64 OH board.
set -e
SDK=$1; HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p $HERE/out
$SDK/llvm/bin/clang --target=aarch64-linux-ohos --sysroot=$SDK/sysroot -O2 -Wall -Wextra -Werror \
  $HERE/oh_record.c -lohaudio -o $HERE/out/oh_record
echo "built $HERE/out/oh_record"
