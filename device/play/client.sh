#!/bin/bash
# client.sh <tag> <package>  -- one app beside the running shared Play services process (start_play.sh),
# which it leaves alone; with PLAY_STORE_SOCKET, beside the Play Store's process too (start_store.sh), where
# the app reaches the Play Store. Waits WAIT (60) seconds, pulls the app's stderr to inputs/logs/<tag>/, and
# stops the app unless KEEP=1.
. "$(dirname "$0")/../config.sh"; need WL_GUESTS
tag=$1; pkg=$2; app=hk-$pkg; mkdir -p $IN/logs/$tag; PLAY_SOCKET=${PLAY_SOCKET:-wl.play.m1}
python3 $DEVICE/prep_apps.py $pkg | tail -1 | cut -c1-80
# The running Play services process's stage stays, as shared_round.sh keeps it: launch.sh deletes every other
# stage, and the process then loses what it opens later (a guest's APK, its own data directory).
stage_of() { grep -o '"stage": "[^"]*"' $WL_SC/logs/$1.log 2>/dev/null | head -1 | sed -E 's/.*a2hlab-app-([0-9a-f]+)".*/\1/'; }
ST=$(stage_of ${PLAY_TAG:-play}-hk-com.google.android.gms); STORE=""
if [ -n "${PLAY_STORE_SOCKET:-}" ]; then
  ST="$ST $(stage_of ${PLAY_STORE_TAG:-store}-hk-com.android.vending)"
  STORE="--runtime-env WESTLAKE_PLAY_STORE_CONNECT=$PLAY_STORE_SOCKET"
fi
KEEP_STAGE=${KEEP_STAGE:-$ST} KEEP_RUNNING=1 PROBE_TIMEOUT=${PROBE_TIMEOUT:-300} EXTRA="--android-native-net-app-libraries $(override_args) --guest-build $V/out/$WL_GUESTS --input-cache --runtime-env WESTLAKE_PLAY_SERVICES_CONNECT=$PLAY_SOCKET $STORE --runtime-env WESTLAKE_PLAY_TRACE=1" $DEVICE/launch.sh $app $tag-$app
find "$IN/prep-$app" -mindepth 1 ! -name app-input.json -delete 2>/dev/null
C=$(grep -o '"child": [0-9]*' $WL_SC/logs/$tag-$app.log | head -1 | grep -o '[0-9]*'); echo "$pkg child $C"
sleep ${WAIT:-60}
timeout 90 $WHDC -t $T shell "cat /data/service/el1/public/appspawnx/adapter_child_$C.stderr" 2>/dev/null | tr -d '\r' > $IN/logs/$tag/$app.stderr
grep -nE "WL-PLAY\]|FATAL" $IN/logs/$tag/$app.stderr | cut -c1-170 | head -20
[ "${KEEP:-}" = 1 ] || timeout 15 $WHDC -t $T shell "kill -9 $C" >/dev/null 2>&1
