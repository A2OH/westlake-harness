#!/bin/bash
# run_all.sh <tag>  -- shared_round.sh until the round finishes, for runs that take a day: it stops
# when Play services dies or the board drops, and round.sh skips apps already captured, so each try
# resumes. Before each try: stop leftover starters here and app processes on the board, and restart
# the local hdc server if the board does not answer. Up to TRIES (40) tries; none after a launcher
# refusal (shared_round.sh exit 3), which every try would repeat. Log: $PLAY_DIR/run_all.log, with the
# board's uptime, load, available memory and free swap at each try, and its network at the start and end. When
# the round is done, each app is set against its earlier rounds (history-<tag>.txt beside the round log).
. "$(dirname "$0")/../config.sh"
PLAY_DIR=${PLAY_DIR:-$IN/play-runs}; mkdir -p $PLAY_DIR; TAG=$1; L=$PLAY_DIR/run_all.log
# The board's network at the round's first try and at its end (netprobe.sh, netprobe-<when>.json beside the
# round's logs): an online app judged while names it needs did not resolve or connect from the board was judged
# on the network, not on Westlake. NETPROBE=0 skips it.
netprobe() { [ "${NETPROBE:-1}" = 0 ] && return 0; mkdir -p $IN/logs/$TAG
  echo "$(date +%H:%M) $1 $($DEVICE/netprobe.sh $IN/logs/$TAG/netprobe-$1.json 2>&1 | tail -1)" >> $L; }
for try in $(seq 1 ${TRIES:-40}); do
  for p in $(pgrep -fx "/bin/bash $DEVICE/play/start_play.sh") $(pgrep -fx "/bin/bash $DEVICE/play/start_store.sh"); do pkill -P $p; kill $p; done 2>/dev/null
  hdc_heal || echo "$(date +%H:%M) hdc server restarted" >> $L
  kill_children
  echo "$(date +%H:%M) try $try" >> $L
  # The board's state, to read the round's results against. After three days up, its swap was full and its WiFi
  # chip in an interrupt storm (load ~12 from threads in D state) while apps that had drawn stopped drawing.
  echo "$(date +%H:%M) board: $(timeout 20 $WHDC -t $T shell 'cat /proc/uptime /proc/loadavg; grep -E "^(MemAvailable|SwapFree):" /proc/meminfo' 2>/dev/null | tr -d '\r' | tr -s ' \n' ' ' | cut -c1-160)" >> $L
  [ $try = 1 ] && netprobe start
  $DEVICE/play/shared_round.sh $TAG > $PLAY_DIR/shared_round.out 2>&1; rc=$?
  cat $PLAY_DIR/round.log >> $L
  echo "$(date +%H:%M) rc=$rc captured=$(ls $IN/logs/$TAG/*.stderr 2>/dev/null | wc -l)" >> $L
  [ $rc -eq 3 ] && { echo "$(date +%H:%M) stopped: the launcher refused to start Play services (see play.log); not retried" >> $L; break; }
  [ ! -e $PLAY_DIR/dead ] && tail -1 $WL_CORPUS/round-$TAG.log | grep -q "$TAG done" && break
  sleep 120
done
echo "$(date +%H:%M) finished" >> $L
netprobe end
# Each app against its own earlier rounds (westlake_gap.history): what regressed, what improved and what is
# flaky, in $WL_CORPUS/history-<tag>.txt (and history.json beside the round's logs), its first line in the log.
if tail -1 $WL_CORPUS/round-$TAG.log 2>/dev/null | grep -q "$TAG done"; then
  (cd "$HARNESS" && PYTHONPATH=harness timeout 600 python3 -m westlake_gap.history $WL_CORPUS $TAG \
    --json $IN/logs/$TAG/history.json) > $WL_CORPUS/history-$TAG.txt 2>&1
  echo "$(date +%H:%M) history: $(head -1 $WL_CORPUS/history-$TAG.txt)" >> $L
fi
