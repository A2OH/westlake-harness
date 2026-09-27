#!/bin/bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SDK=${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/android-sdk}}
TOOLS="$SDK/build-tools/34.0.0"
ANDROID_JAR="$SDK/platforms/android-34/android.jar"
NDK=${ANDROID_NDK:-$SDK/ndk/25.2.9519653}
CC="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android30-clang"
KEYSTORE=${WESTLAKE_DEBUG_KEYSTORE:-$HOME/.android/debug.keystore}
OUT="$ROOT/out"

for tool in "$TOOLS/aapt" "$TOOLS/d8" "$TOOLS/zipalign" "$TOOLS/apksigner" \
            "$ANDROID_JAR" "$CC" "$KEYSTORE"; do
    test -f "$tool" || { echo "missing build input: $tool" >&2; exit 1; }
done

rm -rf "$OUT"
mkdir -p "$OUT/classes" "$OUT/dex" "$OUT/lib/arm64-v8a" "$OUT/stage/assets"

"$CC" -shared -fPIC -O2 -Wall -Werror -o "$OUT/lib/arm64-v8a/libndkassets.so" \
    "$ROOT/jni/ndk_assets.c" -landroid
javac -source 8 -target 8 -Xlint:-options -cp "$ANDROID_JAR" -d "$OUT/classes" \
    "$ROOT/src/org/westlake/probe/ndkassets/MainActivity.java"
jar cf "$OUT/classes.jar" -C "$OUT/classes" .
"$TOOLS/d8" --min-api 28 --output "$OUT/dex" "$OUT/classes.jar"

# probe.bundle is packaged compressed (as aapt does by default); stored.bundle is the same bytes
# stored uncompressed, the way most bundles ship.
cp "$ROOT/assets/probe.bundle" "$OUT/stage/assets/probe.bundle"
"$TOOLS/aapt" package -f -M "$ROOT/AndroidManifest.xml" -I "$ANDROID_JAR" \
    -A "$OUT/stage/assets" -F "$OUT/probe-unsigned.apk"
(
    cd "$OUT/stage"
    cp assets/probe.bundle assets/stored.bundle
    zip -q -0 "$OUT/probe-unsigned.apk" assets/stored.bundle
    cd "$OUT/dex" && "$TOOLS/aapt" add "$OUT/probe-unsigned.apk" classes.dex >/dev/null
    cd "$OUT" && zip -q -0 "$OUT/probe-unsigned.apk" lib/arm64-v8a/libndkassets.so
)
"$TOOLS/zipalign" -f -p 4 "$OUT/probe-unsigned.apk" "$OUT/probe-aligned.apk"
"$TOOLS/apksigner" sign --ks "$KEYSTORE" --ks-pass pass:android \
    --key-pass pass:android --out "$OUT/ndk-assets-probe.apk" "$OUT/probe-aligned.apk"
"$TOOLS/apksigner" verify "$OUT/ndk-assets-probe.apk"
sha256sum "$OUT/ndk-assets-probe.apk"
