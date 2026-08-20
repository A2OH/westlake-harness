#!/bin/bash
# Copy to env.sh and set for your machine. Nothing in this repo hardcodes local paths.
export WESTLAKE_ROOT="${WESTLAKE_ROOT:-$HOME}"        # parent of the working trees
export OHOS_ROOT="$WESTLAKE_ROOT/openharmony"          # OpenHarmony source tree
export OHOS_SDK="$WESTLAKE_ROOT/ohos-sdk-6.1/linux/native"
export BRIDGE_SRC="$WESTLAKE_ROOT/bridge-build"        # adapter/bridge sources
export BRIDGE_ARM64="$WESTLAKE_ROOT/bridge-build-arm64" # arm64 build + artifacts
export ART_LATEST="$WESTLAKE_ROOT/art-latest"          # ART build tree
export AOSP_ART15="$WESTLAKE_ROOT/aosp-art-15"         # AOSP 15 ART sources
export AOSP14_BASE="$WESTLAKE_ROOT/aosp-14-base"       # AOSP 14 libs/hwui baseline
export WL_KIT="$WESTLAKE_ROOT/westlake-arm64/<session>" # reproduction kit (recipes/, tools/)
export WL_SCRATCH="${TMPDIR:-/tmp}/westlake-scratch"    # scratch for captures/logs
export HDC="/path/to/hdc"                              # OpenHarmony device client
export BOARD_SERIAL="<your-board-serial>"              # target device
# dexlib2 classpath for harness/tools/*.java
export DEXLIB_CP="/path/to/smali-dexlib2.jar:/path/to/smali-util.jar:/path/to/guava.jar"
