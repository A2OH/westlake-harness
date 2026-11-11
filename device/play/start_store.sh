#!/bin/bash
# start_store.sh  -- start Google's Play Store as a second shared process beside the running Play services
# process (start_play.sh), as GrapheneOS runs both as ordinary unprivileged apps (ADR-0001, "the Play Store as
# a second shared process"). It serves apps on $PLAY_STORE_SOCKET and is itself a client of Play services on
# $PLAY_SOCKET, where its account manager, Gservices and check-in are. No activity of its own; STORE_ACTIVITY=1
# opens its main screen instead, for a look. Apps reach it with client.sh PLAY_STORE_SOCKET=. Google's APK is
# staged like Play services' (inputs/prep-hk-com.android.vending, from a local pin), never from this repo.
# Writes $PLAY_STORE_DIR/store.log ("child <pid> started", then a line every 5 min). STORE_EXTRA: more launcher
# arguments, e.g. --runtime-env WESTLAKE_CRONET_NETLOG=/data/data/com.android.vending/cache for its Cronet NetLogs.
. "$(dirname "$0")/../config.sh"
PLAY_SOCKET=${PLAY_SOCKET:-wl.play.m1}; PLAY_STORE_SOCKET=${PLAY_STORE_SOCKET:-wl.store.m1}
PLAY_STORE_DIR=${PLAY_STORE_DIR:-$IN/store-runs}; mkdir -p $PLAY_STORE_DIR
app=hk-com.android.vending; tag=${PLAY_STORE_TAG:-store}; OUT=$PLAY_STORE_DIR/store.log
[ -s $IN/prep-$app/app-input.json ] || { echo "no app input $IN/prep-$app (prepare_app.py with the Play Store's pin)" | tee $OUT; exit 1; }
# The Play services process keeps running, and its stage stays: launch.sh deletes every stage it isn't told to keep.
ST=$(grep -o '"stage": "[^"]*"' $WL_SC/logs/${PLAY_TAG:-play}-hk-com.google.android.gms.log 2>/dev/null | head -1 | sed -E 's/.*a2hlab-app-([0-9a-f]+)".*/\1/')
[ -n "$ST" ] || { echo "no Play services process to stand beside (start_play.sh, PLAY_TAG)" | tee $OUT; exit 1; }
ACTIVITY="--runtime-env WESTLAKE_NO_ACTIVITY=1"; [ -n "${STORE_ACTIVITY:-}" ] && ACTIVITY=""
KEEP_STAGE=$ST KEEP_RUNNING=1 PROBE_TIMEOUT=${PROBE_TIMEOUT:-300} EXTRA="--android-native-net-app-libraries $(override_args) --input-cache --runtime-env WESTLAKE_PLAY_STORE_SERVE=$PLAY_STORE_SOCKET --runtime-env WESTLAKE_PLAY_SERVICES_CONNECT=$PLAY_SOCKET --runtime-env WESTLAKE_PLAY_TRACE=1 $ACTIVITY ${STORE_EXTRA:-}" $DEVICE/launch.sh $app $tag-$app
C=$(grep -o '"child": [0-9]*' $WL_SC/logs/$tag-$app.log | head -1 | grep -o '[0-9]*')
[ -n "$C" ] || { echo "no child" | tee $OUT; exit 1; }
echo $$ > $PLAY_STORE_DIR/store.pid; echo "child $C started $(date)" > $OUT
start=$(date +%s); gone=0
while [ $(( $(date +%s) - start )) -lt $(( ${PLAY_HOURS:-24} * 3600 )) ]; do
  sleep 300
  S=$(timeout 40 $WHDC -t $T shell "if [ -d /proc/$C ]; then echo alive \$(grep VmRSS /proc/$C/status | grep -o '[0-9]*'); else echo gone; fi" 2>/dev/null | tr -d '\r' | tr '\n' ' ')
  echo "$(( ($(date +%s) - start) / 60 )) min: $S" >> $OUT
  case "$S" in alive*) gone=0 ;; gone*) gone=$((gone+1)); [ $gone -ge 3 ] && { echo "process gone" >> $OUT; break; } ;; esac
done
echo "finished $(date)" >> $OUT
timeout 120 $WHDC -t $T shell "tail -c 20000 /data/service/el1/public/appspawnx/adapter_child_$C.stderr" 2>/dev/null | tr -d '\r' > $PLAY_STORE_DIR/store.stderr-tail
