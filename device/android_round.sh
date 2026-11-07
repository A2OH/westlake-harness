#!/bin/bash
# android_round.sh <tag> <package...>  -- Level 2 on the Android reference phone: for each package,
# install the same download the board runs ($WL_CORPUS/dl/<package>@*: an APK, or an XAPK's base and
# splits), explore it with explore.py for EXPLORE seconds (default 180), keep the crash buffer, and
# uninstall it. Results in $WL_SC/inputs/logs/<tag>/<package>.explore/ beside the board's, for
# compare_explore.py.
#   ADB (required)        adb; a Windows adb.exe works too (file arguments are converted)
#   ANDROID_SERIAL        the phone (default: the only one attached)
#   ANDROID_STAGE         a directory adb can read (default $WL_SC/inputs/.android-stage; under WSL with
#                         a Windows adb, a directory on a Windows drive)
# The phone needs "Install via USB" allowed. Apps are installed with -g (runtime permissions granted),
# matching Westlake, which grants what an app declares.
. "$(dirname "$0")/config.sh"; need ADB
tag=$1; shift; mkdir -p $IN/logs/$tag
STAGE=${ANDROID_STAGE:-$IN/.android-stage}; mkdir -p "$STAGE"
S=${ANDROID_SERIAL:-$($ADB devices | tr -d '\r' | awk 'NR>1 && $2=="device" {print $1; exit}')}
[ -n "$S" ] || { echo "no Android phone attached" >&2; exit 2; }
winpath() { case $ADB in *.exe) wslpath -w "$1" ;; *) echo "$1" ;; esac; }
for pkg in "$@"; do
  out=$IN/logs/$tag/$pkg.explore; [ -s $out/explore.json ] && continue
  dl=$(ls $WL_CORPUS/dl/$pkg@* 2>/dev/null | head -1); [ -n "$dl" ] || { echo "$pkg: no download"; continue; }
  rm -rf "$STAGE"/*; files=()
  case $dl in
    *.xapk) (cd "$STAGE" && unzip -q -o "$dl" '*.apk' -x '*/*'); for f in "$STAGE"/*.apk; do files+=("$(winpath "$f")"); done ;;
    *) cp "$dl" "$STAGE/$pkg.apk"; files=("$(winpath "$STAGE/$pkg.apk")") ;;
  esac
  if ! timeout 300 $ADB -s $S install-multiple -r -g "${files[@]}" > $STAGE/install.log 2>&1; then
    echo "$pkg: install failed: $(tr -d '\r' < $STAGE/install.log | tail -1)"; continue
  fi
  $ADB -s $S logcat -c 2>/dev/null
  mkdir -p $out
  python3 $DEVICE/explore.py android --adb $ADB --serial $S --package $pkg --seconds ${EXPLORE:-180} --out $out | tail -1
  $ADB -s $S logcat -d -b crash 2>/dev/null | tr -d '\r' > $out/crash.log
  $ADB -s $S logcat -d -s ActivityManager:E AndroidRuntime:E 2>/dev/null | tr -d '\r' | tail -200 > $out/errors.log
  $ADB -s $S uninstall $pkg >/dev/null 2>&1
done
rm -rf "$STAGE"/*
