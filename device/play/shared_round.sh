#!/bin/bash
# shared_round.sh <tag>  -- a round (round.sh) with every app connected to one shared Play services
# process. Starts it (start_play.sh, unless RESUME=1 and it runs already), gives it 4 min to settle,
# then runs the round over LIST (default all of apps.csv). Stops at once if Play services dies, so a
# bad run is never counted: exit 2 and $PLAY_DIR/dead. A watcher records, per app, how many FCM
# registrations its token file holds (counts only: no token leaves the board) in play-tokens.log.
# Exit 3: the launcher refused to start Play services for a reason a retry cannot change.
# PLAY_STORE_SOCKET: also start Google's Play Store host beside it (start_store.sh, tag ${tag}store, data in
# $PLAY_DIR/store), connect every app to it, keep its stage, and stop the same way if it dies.
. "$(dirname "$0")/../config.sh"
PLAY_DIR=${PLAY_DIR:-$IN/play-runs}; PLAY_SOCKET=${PLAY_SOCKET:-wl.play.m1}; mkdir -p $PLAY_DIR
A=$1; O=$PLAY_DIR/round.log; : > $O; rm -f $PLAY_DIR/dead $PLAY_DIR/config-error
if [ -z "${RESUME:-}" ]; then
  rm -f $PLAY_DIR/play.log; nohup setsid $DEVICE/play/start_play.sh > $PLAY_DIR/start_play.out 2>&1 < /dev/null &
  for i in $(seq 1 60); do grep -q started $PLAY_DIR/play.log 2>/dev/null && break; sleep 5; done
  if ! grep -q started $PLAY_DIR/play.log 2>/dev/null; then
    echo "ABORT: Play services did not start: $(tail -1 $PLAY_DIR/play.log 2>/dev/null)" >> $O
    [ -e $PLAY_DIR/config-error ] && exit 3   # the launcher refused: no retry will differ
    exit 1
  fi
  sleep 240
fi
C=$(grep -o 'child [0-9]*' $PLAY_DIR/play.log | head -1 | grep -o '[0-9]*'); echo "play child $C" >> $O
ST=$(grep -o '"stage": "[^"]*"' $WL_SC/logs/${PLAY_TAG:-play}-hk-com.google.android.gms.log | head -1 | sed -E 's/.*a2hlab-app-([0-9a-f]+)".*/\1/')
SC_=""; STORE_ARGS=""
if [ -n "${PLAY_STORE_SOCKET:-}" ]; then
  export PLAY_STORE_DIR=$PLAY_DIR/store PLAY_STORE_TAG=${PLAY_STORE_TAG:-${A}store}; mkdir -p $PLAY_STORE_DIR
  rm -f $PLAY_STORE_DIR/store.log; nohup setsid $DEVICE/play/start_store.sh > $PLAY_STORE_DIR/start.out 2>&1 < /dev/null &
  for i in $(seq 1 90); do grep -q "started\|no child\|no app input\|no Play services" $PLAY_STORE_DIR/store.log 2>/dev/null && break; sleep 5; done
  if ! grep -q started $PLAY_STORE_DIR/store.log 2>/dev/null; then
    echo "ABORT: the Play Store did not start: $(tail -1 $PLAY_STORE_DIR/store.log 2>/dev/null)" >> $O; exit 1
  fi
  SC_=$(grep -o 'child [0-9]*' $PLAY_STORE_DIR/store.log | head -1 | grep -o '[0-9]*'); echo "store child $SC_" >> $O
  ST="$ST $(grep -o '"stage": "[^"]*"' $WL_SC/logs/$PLAY_STORE_TAG-hk-com.android.vending.log | head -1 | sed -E 's/.*a2hlab-app-([0-9a-f]+)".*/\1/')"
  STORE_ARGS="--runtime-env WESTLAKE_PLAY_STORE_CONNECT=$PLAY_STORE_SOCKET"
  sleep 60
fi
# The round runs in its own process group, so a Play services (or Play Store) death stops all of it.
KEEP_STAGE=$ST PLAY=$PLAY_SOCKET ROUND_EXTRA="${ROUND_EXTRA:-} $STORE_ARGS" WAIT=${WAIT:-60} setsid $DEVICE/round.sh $A 1 ${LAST:-100000} > /dev/null 2>&1 & R=$!
( while :; do
    timeout 20 $WHDC -t $T shell 'for f in /data/app/el2/100/base/org.westlake.imehost/files/a2hlab-source-*/app-data/*/shared_prefs/com.google.android.gms.appid.xml; do [ -f "$f" ] && echo "T $f $(grep -c "|T|" "$f") $(grep -c MESSENGER "$f")"; done' 2>/dev/null | sed -E 's|T .*/app-data/([^/]+)/.* ([0-9]+) ([0-9]+)|T \1 \2 \3|' >> $PLAY_DIR/play-tokens.log
    s=$(timeout 15 $WHDC -t $T shell "[ -d /proc/$C ] && echo alive || echo GONE" 2>/dev/null | tr -d '\r')
    if [ "$s" = GONE ]; then echo "PLAY DIED $(date +%H:%M)" >> $O; touch $PLAY_DIR/dead; kill -- -$R 2>/dev/null; exit; fi
    if [ -n "$SC_" ]; then
      s=$(timeout 15 $WHDC -t $T shell "[ -d /proc/$SC_ ] && echo alive || echo GONE" 2>/dev/null | tr -d '\r')
      if [ "$s" = GONE ]; then echo "STORE DIED $(date +%H:%M)" >> $O; touch $PLAY_DIR/dead; kill -- -$R 2>/dev/null; exit; fi
    fi
    sleep 30; done ) &
W=$!
wait $R; kill $W 2>/dev/null
[ -e $PLAY_DIR/dead ] && exit 2
echo "shared done $(date +%H:%M); $(tail -1 $PLAY_DIR/play.log | cut -c1-50)" >> $O
kill $(cat $PLAY_DIR/play.pid) 2>/dev/null; [ -n "$SC_" ] && kill $(cat $PLAY_DIR/store/store.pid) 2>/dev/null; kill_children
