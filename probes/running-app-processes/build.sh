#!/bin/bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SDK=${ANDROID_SDK_ROOT:-/home/dspfac/android-sdk}
TOOLS="$SDK/build-tools/34.0.0"
ANDROID_JAR="$SDK/platforms/android-34/android.jar"
KEYSTORE=${WESTLAKE_DEBUG_KEYSTORE:-/home/dspfac/.android/debug.keystore}
OUT="$ROOT/out"

for tool in "$TOOLS/aapt" "$TOOLS/d8" "$TOOLS/zipalign" "$TOOLS/apksigner" \
            "$ANDROID_JAR" "$KEYSTORE"; do
    test -f "$tool" || { echo "missing build input: $tool" >&2; exit 1; }
done

rm -rf "$OUT"
mkdir -p "$OUT/classes" "$OUT/dex"

javac -source 8 -target 8 -Xlint:-options -cp "$ANDROID_JAR" \
    -d "$OUT/classes" \
    "$ROOT/src/org/westlake/probe/runningprocesses/ProbeApplication.java" \
    "$ROOT/src/org/westlake/probe/runningprocesses/MainActivity.java"

jar cf "$OUT/classes.jar" -C "$OUT/classes" .
"$TOOLS/d8" --min-api 28 --output "$OUT/dex" "$OUT/classes.jar"
"$TOOLS/aapt" package -f -M "$ROOT/AndroidManifest.xml" -I "$ANDROID_JAR" \
    -F "$OUT/probe-unsigned.apk"
(
    cd "$OUT/dex"
    "$TOOLS/aapt" add "$OUT/probe-unsigned.apk" classes.dex >/dev/null
)
"$TOOLS/zipalign" -f -p 4 "$OUT/probe-unsigned.apk" "$OUT/probe-aligned.apk"
"$TOOLS/apksigner" sign --ks "$KEYSTORE" --ks-pass pass:android \
    --key-pass pass:android --out "$OUT/running-app-processes-probe.apk" \
    "$OUT/probe-aligned.apk"
"$TOOLS/apksigner" verify --verbose "$OUT/running-app-processes-probe.apk"
sha256sum "$OUT/running-app-processes-probe.apk"
