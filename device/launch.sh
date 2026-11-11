#!/bin/bash
# launch.sh <app> <outname>  -- one app (staged at $WL_SC/inputs/prep-<app>) on the board through the
# launcher (probe_source_app.py). Prints the child pid; pulls its stderr to inputs/logs/<outname>.stderr.
# EXTRA: more launcher arguments. KEEP_RUNNING=1 leaves other Westlake processes alone (a client beside
# the shared Play services process); KEEP_STAGE names the app stage to keep then. Exit 3: disk guard.
. "$(dirname "$0")/config.sh"; need WL_FW WL_SHIM
app=$1; out=$2; fw=$WL_FW; shim=$WL_SHIM; cd $WL_SC
# Free space on the board's /data in GB, empty when the board did not answer: hdc's error line is not
# a df line, and read as one it gave 0 GB, which stopped a test while the board was only out of reach.
board_free() { timeout 60 $WHDC -t $T shell "df -k /data | tail -1" 2>/dev/null | tr -d '\r' | awk '$1 ~ /^\// && $4 ~ /^[0-9]+$/ {print int($4/1048576)}'; }
FREE=$(board_free)
for try in 1 2 3 4 5 6 7 8 9 10; do
  [ -n "$FREE" ] && break
  hdc_heal; sleep 25; FREE=$(board_free)
done
# App data that outlives a stage, as /data/data/<package> survives an update on Android: the shared Play
# services process's account, check-in values and guests (and the Play Store's, once it has a process). Before
# old stages go, each one's app-data/<package> for these packages moves to $KEEP_DATA_DIR, oldest stage first
# so the newest wins, on the same filesystem; the launcher moves it into the new stage (--carried-app-data).
# PERSIST_DATA= (set, empty) gives a fresh data directory; delete $KEEP_DATA_DIR/<package> to forget one.
PERSIST_DATA=${PERSIST_DATA-com.google.android.gms com.android.vending}
HOST_FILES=/data/app/el2/100/base/org.westlake.imehost/files; KEEP_DATA_DIR=$HOST_FILES/a2hlab-data
# keep_data <stage pattern to leave alone>: board shell code moving the persisted packages' data out
# (tests/test_keep_data.py runs it on a local tree).
keep_data() {
  [ -n "$PERSIST_DATA" ] || return 0
  echo "mkdir -p $KEEP_DATA_DIR; for d in \$(ls -dtr $HOST_FILES/a2hlab-source-* 2>/dev/null); do case \$d in *$1*) continue ;; esac; for p in $PERSIST_DATA; do if [ -d \$d/app-data/\$p ]; then rm -rf $KEEP_DATA_DIR/\$p && mv \$d/app-data/\$p $KEEP_DATA_DIR/\$p; fi; done; done;"
}
# One app at a time: drop old app stages and source runtimes (~290 MB each), or /data fills.
if [ -n "${KEEP_RUNNING:-}" ]; then
  timeout 120 $WHDC -t $T shell "$(keep_data ${KEEP_STAGE:-@none@}) for d in /data/local/tmp/a2hlab-app-* /data/app/el2/100/base/org.westlake.imehost/files/a2hlab-source-*; do case \$d in *${KEEP_STAGE:-@none@}*) ;; *) rm -rf \$d ;; esac; done" >/dev/null 2>&1
else
  timeout 300 $WHDC -t $T shell 'P=$(pidof appspawn-x); [ -n "$P" ] && kill $P; sleep 1; '"$(keep_data @none@)"' for d in /data/local/tmp/a2hlab-app-* /data/app/el2/100/base/org.westlake.imehost/files/a2hlab-source-*; do [ -e "$d" ] && rm -rf "$d"; done' >/dev/null 2>&1; sleep 1
fi
# A launcher that knows the option moves the kept data in; an older one gets a fresh directory, and the kept
# data waits for a launcher that does.
CARRY=""
[ -n "$PERSIST_DATA" ] && grep -q -- '--carried-app-data' $M/probe_source_app.py 2>/dev/null && CARRY="--carried-app-data $KEEP_DATA_DIR"
# Disk guard: a launch needs ~2 GB on the board. Prune stale framework stages if low, and refuse to
# launch (exit 3) rather than fill either disk. LOCAL_DISKS: local filesystems that must keep
# MIN_LOCAL_GB free (under WSL add the Windows drive holding the virtual disk, e.g. /mnt/c).
MIN_BOARD_GB=${MIN_BOARD_GB:-8}; MIN_LOCAL_GB=${MIN_LOCAL_GB:-30}
if [ -n "$FREE" ] && [ "$FREE" -lt "$MIN_BOARD_GB" ]; then
  KEEP=$(python3 -c "import json;print(json.load(open('$V/out/$fw/device-report.json'))['stage'])" 2>/dev/null)
  timeout 600 $WHDC -t $T shell "for d in /data/local/tmp/a2hlab-framework-*; do [ \"\$d\" = \"$KEEP\" ] || rm -rf \"\$d\"; done" >/dev/null 2>&1
  FREE=$(board_free)
fi
LOCAL=$(df -k $WL_SC ${LOCAL_DISKS:-} 2>/dev/null | tail -n +2 | awk '{print int($4/1048576)}' | sort -n | head -1)
if [ -z "$FREE" ] || [ "$FREE" -lt "$MIN_BOARD_GB" ] || [ "$LOCAL" -lt "$MIN_LOCAL_GB" ]; then
  echo "$app DISK-GUARD board_free=${FREE:-unknown}G local_free=${LOCAL}G: not launching" | tee $IN/logs/$out.stderr
  exit 3
fi
# Link gate (on while inputs/LINK-GATE exists; it holds the minimum MB/s, default 0.5): over a slow
# wireless spell the launcher's file sends time out and the app is lost. A board reboot ended
# slow spells that hours of waiting did not, so two slow tests in a row reboot it.
link_rate() {
  F=$(mktemp); head -c 10000000 /dev/urandom > $F; s=$(date +%s.%N)
  if timeout 60 $WHDC -t $T file send $F /data/local/tmp/link10m.bin >/dev/null 2>&1; then
    echo "10 / ($(date +%s.%N) - $s)" | bc -l
  else echo 0; hdc_reconnect; fi
  timeout 20 $WHDC -t $T shell 'rm -f /data/local/tmp/link10m.bin' >/dev/null 2>&1; rm -f $F
}
slow=0
while [ -f $IN/LINK-GATE ]; do
  min=$(head -c 8 $IN/LINK-GATE | tr -dc '0-9.'); rate=$(link_rate)
  [ "$(echo "$rate >= ${min:-0.5}" | bc -l)" = 1 ] && break
  slow=$((slow + 1))
  if [ $slow -ge 2 ]; then
    echo "[launch.sh] $(date +%H:%M) link ${rate:0:5} MB/s < ${min:-0.5}: rebooting the board" >&2
    timeout 30 $WHDC -t $T shell reboot >/dev/null 2>&1; slow=0; sleep 90; hdc_reconnect; sleep 30
  else
    echo "[launch.sh] $(date +%H:%M) link ${rate:0:5} MB/s < ${min:-0.5}: waiting" >&2; sleep 300
  fi
done
probe() {
  rm -rf $V/out/$out
  timeout ${PROBE_TIMEOUT:-600} python3 $M/probe_source_app.py --workspace $V --westlake-source $WS \
    --framework-report $V/out/$fw/device-report.json \
    --app-input $IN/prep-$app --app $app --webview-input $IN/webview-input \
    --bionic-shim-build $V/out/$shim --touch-mode ${WL_TOUCH_MODE:-tap} \
    --hdc $WHDC --serial $T $CARRY ${EXTRA:-} --out $V/out/$out > $WL_SC/logs/$out.log 2>&1
}
probe; rc=$?
# The board's hdc link drops under load: reconnect and launch again, twice at most.
for retry in 1 2; do
  grep -q "Device is not connected\|connect failed status" $WL_SC/logs/$out.log 2>/dev/null || break
  echo "[launch.sh] board disconnected; reconnecting (retry $retry)" >&2
  hdc_heal; sleep 20; probe; rc=$?
done
C=$(grep -o '"child": [0-9]*' $WL_SC/logs/$out.log | head -1 | grep -o '[0-9]*')
sleep ${LAUNCH_SETTLE:-12}   # run_apps.sh sets this low: it waits for the app itself
[ -n "$C" ] && timeout 60 $WHDC -t $T shell "cat /data/service/el1/public/appspawnx/adapter_child_$C.stderr" 2>/dev/null | tr -d '\r' > $IN/logs/$out.stderr
echo "$app EXIT=$rc child=${C:-NONE} lines=$(wc -l < $IN/logs/$out.stderr 2>/dev/null)"
