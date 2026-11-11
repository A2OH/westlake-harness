# config.sh -- sourced by every script here. Nothing machine-specific is in this repo: set these in
# env.sh (see env.sample.sh) or the environment. Each script stops at once if one it needs is unset.
#
#   WL_SC        source-closure root: verify/ (builds, launcher outputs), workspace/ (manifest,
#                westlake), inputs/ (prep-<app> stages, logs/<tag>/ per-app evidence), logs/
#   HDC          the OpenHarmony device client (Linux build, or Windows hdc.exe under WSL)
#   HDC_TARGET   the board: ip:port for a TCP link, or a USB serial
#   WL_FW        framework deploy under $WL_SC/verify/out (holds device-report.json)
#   WL_SHIM      Bionic shim build under $WL_SC/verify/out
#   WL_OVERRIDE  runtime-library override build under $WL_SC/verify/out
#   WL_GUESTS    guest-package build staged beside each app (microG GmsCore + Companion)
#   WL_PLAY_GUESTS  guest build for the shared Play services process (play/ only)
# Optional:
#   WL_CORPUS    corpus directory: apps.csv (one package per line, in rank order), sources.csv,
#                dl/<package>@<version>.(apk|xapk), <map>/<package>/{scan,gap-map}.json
#                (default $WL_SC/inputs/corpus-hk)
#   WL_MANIFEST_TOOLS  launcher tools (default $WL_SC/workspace/manifest/tools)
#   WL_WESTLAKE_SOURCE westlake tree whose native/ helpers the launcher compiles per launch
#                (source_app_namespace, host_spawn, touchfwd; default $WL_SC/workspace/westlake)
#   ANDROID_BUILD_TOOLS  holds apksigner (default ~/android-sdk/build-tools/34.0.0)
DEVICE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); HARNESS=$(dirname "$DEVICE")
[ -f "$HARNESS/env.sh" ] && . "$HARNESS/env.sh"
need() { for v in "$@"; do [ -n "${!v:-}" ] || { echo "$(basename "$0"): set $v (see device/config.sh)" >&2; exit 64; }; done; }
need WL_SC HDC HDC_TARGET
IN=$WL_SC/inputs; V=$WL_SC/verify; T=$HDC_TARGET; WHDC=$HDC
# A Windows hdc (the board on USB under WSL) goes through hdc_wsl.sh, which finds an interop socket that works.
case $HDC in *.exe) export HDC_EXE=$HDC; WHDC=$DEVICE/hdc_wsl.sh ;; esac
export WL_SC HDC HDC_TARGET; export WL_CORPUS=${WL_CORPUS:-$IN/corpus-hk}; M=${WL_MANIFEST_TOOLS:-$WL_SC/workspace/manifest/tools}
WS=${WL_WESTLAKE_SOURCE:-$WL_SC/workspace/westlake}
RECV=$IN/.recv; mkdir -p "$RECV" "$IN/logs" "$WL_SC/logs"
# From inside $RECV with a relative name, so a Windows hdc (the board on USB under WSL) works too.
recv_to() { (cd "$RECV" && timeout "${3:-60}" $WHDC -t $T file recv "$1" "$2" >/dev/null 2>&1); }
hdc_reconnect() { timeout 60 $WHDC tconn $T >/dev/null 2>&1; }
# A hung local hdc server still lists the board but times out every shell call (a big file send
# beside other transfers left it at 100% CPU). Restart it when the board does not answer.
hdc_heal() { timeout 20 $WHDC -t $T shell echo ok 2>/dev/null | grep -q ok && return 0
  timeout 20 $WHDC kill -r >/dev/null 2>&1; sleep 3; hdc_reconnect; return 1; }
# The host app's uid on the board: every Westlake process runs under it.
host_uid() { timeout 20 $WHDC -t $T shell "ps -ef" 2>/dev/null | tr -d '\r' | awk '$8=="org.westlake.imehost" {print $1; exit}'; }
# Stop every Westlake process but the host app. The board has no awk: grep, sed and cut only.
kill_children() { local u=${1:-$(host_uid)}; [ -n "$u" ] || return 0
  timeout 30 $WHDC -t $T shell "for p in \$(ps -ef | grep '^$u ' | grep -v org.westlake.imehost | grep -v grep | sed 's/  */ /g' | cut -d' ' -f2); do kill -9 \$p; done" >/dev/null 2>&1; }
# launcher arguments for the runtime-library override every launch uses
# WL_RUNTIME_ADD: libraries of the override build the framework stage lacks, added for this launch,
# space-separated. Unset, it is the platform Cronet library (libmainlinecronet.<version>.so, which the
# framework's HttpEngine loads) when the override build has one: that build's natives report the S
# extension level that promises HttpEngine, so every app gets its library. Set empty for none. Needs a
# manifest tools copy with --runtime-library-add.
override_args() { local add=${WL_RUNTIME_ADD-$(ls $V/out/$WL_OVERRIDE/lib 2>/dev/null | grep -E '^libmainlinecronet\..*\.so$')}
  echo "--runtime-library-build $V/out/$WL_OVERRIDE --runtime-library libandroid_native_network_compat.so --runtime-library libwl_missing_natives.so --runtime-library libart.so$(for l in $add; do printf ' --runtime-library-add %s' "$l"; done)"; }
