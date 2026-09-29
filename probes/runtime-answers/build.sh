#!/bin/bash
# build.sh: builds out/runtime-answers-probe.apk (pure Java; the MediaPlayer tone is generated here).
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SDK=${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/android-sdk}}
TOOLS="$SDK/build-tools/34.0.0"
ANDROID_JAR="$SDK/platforms/android-34/android.jar"
KEYSTORE=${WESTLAKE_DEBUG_KEYSTORE:-$HOME/.android/debug.keystore}
OUT="$ROOT/out"

for tool in "$TOOLS/aapt" "$TOOLS/d8" "$TOOLS/zipalign" "$TOOLS/apksigner" "$ANDROID_JAR" "$KEYSTORE"; do
    test -f "$tool" || { echo "missing build input: $tool" >&2; exit 1; }
done

rm -rf "$OUT"
mkdir -p "$OUT/classes" "$OUT/dex" "$OUT/stage/assets"

NDK=${ANDROID_NDK:-$SDK/ndk/25.2.9519653}
CC="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android30-clang"
mkdir -p "$OUT/lib/arm64-v8a"
"$CC" -shared -fPIC -O2 -Wall -Werror -o "$OUT/lib/arm64-v8a/libprobeanswers.so" "$ROOT/jni/probe_answers.c"

javac -source 8 -target 8 -Xlint:-options -cp "$ANDROID_JAR" -d "$OUT/classes" \
    "$ROOT/src/org/westlake/probe/runtimeanswers/MainActivity.java"
jar cf "$OUT/classes.jar" -C "$OUT/classes" .
"$TOOLS/d8" --min-api 28 --output "$OUT/dex" "$OUT/classes.jar"
"$TOOLS/aapt" package -f -M "$ROOT/AndroidManifest.xml" -I "$ANDROID_JAR" \
    -F "$OUT/probe-unsigned.apk"
(cd "$OUT/dex" && "$TOOLS/aapt" add "$OUT/probe-unsigned.apk" classes.dex >/dev/null)
(cd "$OUT" && zip -q -0 "$OUT/probe-unsigned.apk" lib/arm64-v8a/libprobeanswers.so)
"$TOOLS/zipalign" -f -p 4 "$OUT/probe-unsigned.apk" "$OUT/probe-aligned.apk"
"$TOOLS/apksigner" sign --ks "$KEYSTORE" --ks-pass pass:android \
    --key-pass pass:android --out "$OUT/runtime-answers-probe.apk" "$OUT/probe-aligned.apk"
"$TOOLS/apksigner" verify "$OUT/runtime-answers-probe.apk"
sha256sum "$OUT/runtime-answers-probe.apk"
