#!/bin/bash
# start_play.sh  -- start the shared Play services process on the board and watch it for up to 24 h.
# One Play services process (Google's own GmsCore, staged from $WL_CORPUS/dl like any app, never
# from this repo) serves every app over the socket $PLAY_SOCKET, the way GrapheneOS runs Play
# services as an ordinary unprivileged app; no activity of its own. Apps connect with round.sh PLAY=.
# Writes $PLAY_DIR/play.log ("child <pid> started", then a line every 5 min), play.pid (this
# script) and, at the end, the tail of the process's stderr.
. "$(dirname "$0")/../config.sh"; need WL_PLAY_GUESTS
PLAY_DIR=${PLAY_DIR:-$IN/play-runs}; PLAY_SOCKET=${PLAY_SOCKET:-wl.play.m1}; mkdir -p $PLAY_DIR
app=hk-com.google.android.gms; tag=${PLAY_TAG:-play}; OUT=$PLAY_DIR/play.log
python3 $DEVICE/prep_apps.py com.google.android.gms | tail -1
kill_children
PROBE_TIMEOUT=${PROBE_TIMEOUT:-300} EXTRA="--android-native-net-app-libraries $(override_args) --guest-build $V/out/$WL_PLAY_GUESTS --input-cache --runtime-env WESTLAKE_PLAY_SERVICES_SERVE=$PLAY_SOCKET --runtime-env WESTLAKE_NO_ACTIVITY=1" $DEVICE/launch.sh $app $tag-$app
C=$(grep -o '"child": [0-9]*' $WL_SC/logs/$tag-$app.log | head -1 | grep -o '[0-9]*')
if [ -z "$C" ]; then
  # A refusal by the launcher itself is the same on every try: an app the lock file does not pin
  # (a tools copy whose app-inputs.lock.json lacks the corpus entries), an output that exists. Say
  # so; shared_round.sh then stops instead of having run_all.sh retry it for hours.
  bad=$(grep -m1 -E "ValueError: Unknown application: |error: Use a new output" $WL_SC/logs/$tag-$app.log 2>/dev/null)
  if [ -n "$bad" ]; then echo "launcher refused: $bad" | tee $OUT; touch $PLAY_DIR/config-error; exit 1; fi
  echo "no child" | tee $OUT; exit 1
fi
echo $$ > $PLAY_DIR/play.pid; echo "child $C started $(date)" > $OUT
start=$(date +%s); gone=0
while [ $(( $(date +%s) - start )) -lt $(( ${PLAY_HOURS:-24} * 3600 )) ]; do
  sleep 300
  S=$(timeout 40 $WHDC -t $T shell "if [ -d /proc/$C ]; then echo alive \$(grep VmRSS /proc/$C/status | grep -o '[0-9]*'); else echo gone; fi" 2>/dev/null | tr -d '\r' | tr '\n' ' ')
  echo "$(( ($(date +%s) - start) / 60 )) min: $S" >> $OUT
  case "$S" in alive*) gone=0 ;; gone*) gone=$((gone+1)); [ $gone -ge 3 ] && { echo "process gone" >> $OUT; break; } ;; esac
done
echo "finished $(date)" >> $OUT
timeout 120 $WHDC -t $T shell "tail -c 20000 /data/service/el1/public/appspawnx/adapter_child_$C.stderr" 2>/dev/null | tr -d '\r' > $PLAY_DIR/play.stderr-tail
