#!/bin/bash
# round.sh <tag> <first-rank> <last-rank>  -- a device round over $WL_CORPUS/apps.csv in rank order,
# five apps at a time: stage them (prep_apps.py), launch them (run_apps.sh), then delete the staged
# APKs (keeping app-input.json) so the disk holds only a few apps. Apps marked missing in sources.csv,
# or already captured under <tag>, are skipped, so running it again resumes. LIST=<file>: only these
# packages. Each app gets the microG guests ($WL_GUESTS); PLAY=<socket> instead connects it to the
# running shared Play services process (play/). ROUND_EXTRA: more launcher arguments for every app.
# Log: $WL_CORPUS/round-<tag>.log.
. "$(dirname "$0")/config.sh"; need WL_GUESTS; cd $WL_CORPUS
tag=$1; first=$2; last=$3
OV="$(override_args) --guest-build $V/out/$WL_GUESTS"
if [ -n "${PLAY:-}" ]; then
  OV="$OV --runtime-env WESTLAKE_PLAY_SERVICES_CONNECT=$PLAY --runtime-env WESTLAKE_PLAY_TRACE=1"; export KEEP_RUNNING=1
fi
# ROUND_EXTRA: more launcher arguments for every app of the round (a --runtime-env, say), after these.
OV="$OV ${ROUND_EXTRA:-}"
todo=()
while read -r rank pkg; do
  [ "$rank" -lt "$first" ] || [ "$rank" -gt "$last" ] && continue
  [ -n "${LIST:-}" ] && ! grep -qx "$pkg" "$LIST" && continue
  grep -q "^$pkg,missing," sources.csv 2>/dev/null && continue
  [ -s "$IN/logs/$tag/hk-$pkg.stderr" ] && continue
  todo+=("$pkg")
done < <(nl -ba -w1 -s' ' apps.csv)
# A resumed tag's log holds the guard line of the run it resumes: look only at this run's lines.
start=$(($(cat round-$tag.log 2>/dev/null | wc -l) + 1))
echo "$(date) $tag ranks $first-$last: ${#todo[@]} to launch" >> round-$tag.log
pf=""
for ((i = 0; i < ${#todo[@]}; i += 5)); do
  batch=("${todo[@]:i:5}")
  # The next batch is staged on the host while this one runs on the board (PREFETCH=0 turns it off).
  # PUSH_AHEAD=1 also sends it to the board's input cache; off by default: one big send beside the
  # launch's own transfers hung the local hdc server.
  if [ -n "$pf" ]; then wait $pf; else python3 $DEVICE/prep_apps.py "${batch[@]}" >> round-$tag.log 2>&1; fi
  pf=""; nxt=("${todo[@]:i+5:5}")
  [ "${PREFETCH:-1}" = 1 ] && [ ${#nxt[@]} -gt 0 ] && { (python3 $DEVICE/prep_apps.py "${nxt[@]}"; [ "${PUSH_AHEAD:-0}" = 1 ] && python3 $DEVICE/prefetch_board.py "${nxt[@]}") >> round-$tag.log 2>&1 & pf=$!; }
  keys=(); for p in "${batch[@]}"; do [ -f "$IN/prep-hk-$p/app-input.json" ] && keys+=("hk-$p"); done
  WAIT=${WAIT:-45} RUN_EXTRA="--android-native-net-app-libraries $OV --input-cache" $DEVICE/run_apps.sh $tag "${keys[@]}" >> round-$tag.log 2>&1
  for k in "${keys[@]}"; do find "$IN/prep-$k" -mindepth 1 ! -name app-input.json -delete 2>/dev/null; done
  tail -n +$start round-$tag.log | grep -q "disk guard stopped" && { [ -n "$pf" ] && wait $pf; echo "$(date) disk guard: stopping" >> round-$tag.log; exit 3; }
done
echo "$(date) $tag done" >> round-$tag.log
