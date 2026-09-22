#!/bin/bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SDK=${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/android-sdk}}
TOOLS="$SDK/build-tools/34.0.0"
ANDROID_JAR="$SDK/platforms/android-34/android.jar"
KEYSTORE=${WESTLAKE_DEBUG_KEYSTORE:-$HOME/.android/debug.keystore}
OUT="$ROOT/out"
# The two typefaces are McDonald's own and are not redistributed here: they are taken from the
# McDonald's base APK being studied (assets/fonts/), so the probe draws with exactly its fonts.
MCDONALDS_APK=${MCDONALDS_APK:?set MCDONALDS_APK to the base.apk being studied}
FONTS="assets/fonts/Speedee-Bold.ttf assets/fonts/LovinSans-Regular.otf"

for tool in "$TOOLS/aapt" "$TOOLS/d8" "$TOOLS/zipalign" "$TOOLS/apksigner" \
            "$ANDROID_JAR" "$KEYSTORE" "$MCDONALDS_APK"; do
    test -f "$tool" || { echo "missing build input: $tool" >&2; exit 1; }
done

rm -rf "$OUT"
mkdir -p "$OUT/classes" "$OUT/dex" "$OUT/assets/fonts"
unzip -q -j -o "$MCDONALDS_APK" $FONTS -d "$OUT/assets/fonts"

javac -source 8 -target 8 -Xlint:-options -cp "$ANDROID_JAR" \
    -d "$OUT/classes" \
    "$ROOT/src/org/westlake/probe/signinlayout/ProbeApplication.java" \
    "$ROOT/src/org/westlake/probe/signinlayout/MainActivity.java"

jar cf "$OUT/classes.jar" -C "$OUT/classes" .
"$TOOLS/d8" --min-api 28 --output "$OUT/dex" "$OUT/classes.jar"
"$TOOLS/aapt" package -f -M "$ROOT/AndroidManifest.xml" -A "$OUT/assets" -I "$ANDROID_JAR" \
    -F "$OUT/probe-unsigned.apk"
(
    cd "$OUT/dex"
    "$TOOLS/aapt" add "$OUT/probe-unsigned.apk" classes.dex >/dev/null
)
"$TOOLS/zipalign" -f -p 4 "$OUT/probe-unsigned.apk" "$OUT/probe-aligned.apk"
"$TOOLS/apksigner" sign --ks "$KEYSTORE" --ks-pass pass:android \
    --key-pass pass:android --out "$OUT/signin-layout-probe.apk" \
    "$OUT/probe-aligned.apk"
"$TOOLS/apksigner" verify --verbose "$OUT/signin-layout-probe.apk"
sha256sum "$OUT/signin-layout-probe.apk"
