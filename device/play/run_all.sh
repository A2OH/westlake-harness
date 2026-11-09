#!/bin/bash
# run_all.sh <tag>  -- shared_round.sh until the round finishes, for runs that take a day: it stops
# when Play services dies or the board drops, and round.sh skips apps already captured, so each try
# resumes. Before each try: stop leftover starters here and app processes on the board, and restart
# the local hdc server if the board does not answer. Up to TRIES (40) tries; none after a launcher
# refusal (shared_round.sh exit 3), which every try would repeat. Log: $PLAY_DIR/run_all.log.
. "$(dirname "$0")/../config.sh"
PLAY_DIR=${PLAY_DIR:-$IN/play-runs}; mkdir -p $PLAY_DIR; TAG=$1; L=$PLAY_DIR/run_all.log
for try in $(seq 1 ${TRIES:-40}); do
  for p in $(pgrep -fx "/bin/bash $DEVICE/play/start_play.sh"); do pkill -P $p; kill $p; done 2>/dev/null
  hdc_heal || echo "$(date +%H:%M) hdc server restarted" >> $L
  kill_children
  echo "$(date +%H:%M) try $try" >> $L
  $DEVICE/play/shared_round.sh $TAG > $PLAY_DIR/shared_round.out 2>&1; rc=$?
  cat $PLAY_DIR/round.log >> $L
  echo "$(date +%H:%M) rc=$rc captured=$(ls $IN/logs/$TAG/*.stderr 2>/dev/null | wc -l)" >> $L
  [ $rc -eq 3 ] && { echo "$(date +%H:%M) stopped: the launcher refused to start Play services (see play.log); not retried" >> $L; break; }
  [ ! -e $PLAY_DIR/dead ] && tail -1 $WL_CORPUS/round-$TAG.log | grep -q "$TAG done" && break
  sleep 120
done
echo "$(date +%H:%M) finished" >> $L
