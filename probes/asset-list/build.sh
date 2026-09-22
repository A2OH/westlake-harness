#!/bin/bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SDK=${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/android-sdk}}
TOOLS="$SDK/build-tools/34.0.0"
ANDROID_JAR="$SDK/platforms/android-34/android.jar"
KEYSTORE=${WESTLAKE_DEBUG_KEYSTORE:-$HOME/.android/debug.keystore}
OUT="$ROOT/out"
BUILD_TMP=$(mktemp -d "$ROOT/.build.XXXXXX")
trap 'rm -rf -- "$BUILD_TMP"' EXIT

for tool in "$TOOLS/aapt" "$TOOLS/aapt2" "$TOOLS/d8" "$TOOLS/zipalign" "$TOOLS/apksigner" \
            "$ANDROID_JAR" "$KEYSTORE"; do
    test -f "$tool" || { echo "missing build input: $tool" >&2; exit 1; }
done

mkdir -p "$BUILD_TMP/classes" "$BUILD_TMP/dex" "$OUT"

javac -source 8 -target 8 -Xlint:-options -cp "$ANDROID_JAR" \
    -d "$BUILD_TMP/classes" \
    "$ROOT/src/org/westlake/probe/assets/MainActivity.java" \

jar cf "$BUILD_TMP/classes.jar" -C "$BUILD_TMP/classes" .
"$TOOLS/d8" --min-api 28 --output "$BUILD_TMP/dex" "$BUILD_TMP/classes.jar"
# aapt1 misclassifies <queries><provider> as an application component and
# incorrectly requires android:name. aapt2 understands the package-visibility
# grammar used by the stock X manifest.
"$TOOLS/aapt2" link -o "$BUILD_TMP/probe-unsigned.apk" -I "$ANDROID_JAR" \
    --manifest "$ROOT/AndroidManifest.xml" -A "$ROOT/assets" \
    --min-sdk-version 28 --target-sdk-version 34
(
    cd "$BUILD_TMP/dex"
    "$TOOLS/aapt" add "$BUILD_TMP/probe-unsigned.apk" classes.dex >/dev/null
)
"$TOOLS/zipalign" -f -p 4 "$BUILD_TMP/probe-unsigned.apk" "$BUILD_TMP/probe-aligned.apk"
"$TOOLS/apksigner" sign --ks "$KEYSTORE" --ks-pass pass:android \
    --key-pass pass:android --out "$BUILD_TMP/asset-list-probe.apk" \
    "$BUILD_TMP/probe-aligned.apk"
"$TOOLS/apksigner" verify --verbose "$BUILD_TMP/asset-list-probe.apk"
cp "$BUILD_TMP/asset-list-probe.apk" "$OUT/asset-list-probe.apk"
sha256sum "$OUT/asset-list-probe.apk"
