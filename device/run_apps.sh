#!/bin/bash
# run_apps.sh <tag> <app...>  -- launch each app (launch.sh), wait for it, and capture the evidence the
# harness scores (westlake_gap.lifecycle, .evidence) into $WL_SC/inputs/logs/<tag>/: the stderr log,
# a screenshot, the process map, its hilog, its crash dump, and the native libraries it wrote at run
# time (a superpack unpacked into its data directory: no scan of the APK sees them).
# An app key hk-<package> takes its launch remedies (launch_args) from
# $WL_CORPUS/${MAP:-map}/<package>/gap-map.json. RUN_EXTRA: launcher arguments for every app.
# WAIT (30): the most seconds to wait; EARLY=1 (default) moves on sooner, see below.
# WAITS=<file>: lines "<app> <seconds>" (app as hk-<package> or the package), a longer wait for apps
# that need more than WAIT to get past their start (an online game's first downloads).
# EXPLORE=<seconds>: then explore the app that long (Level 2, explore.py).
# CHECKS=<spec.json>: then run the app's functional checks from that spec (checks.py), if it names the app.
# APP_OAT_ROOT=<dir>: launch each app with its host-compiled code from <dir>/<app>/ (install-time dexopt).
. "$(dirname "$0")/config.sh"; cd $IN
tag=$1; shift; mkdir -p logs/$tag
for app in "$@"; do
  X=""; case $app in hk-*) X=$(python3 -c "
import json,sys
try: print(' '.join(json.load(open(sys.argv[1])).get('launch_args', [])))
except Exception: pass" "$WL_CORPUS/${MAP:-map}/${app#hk-}/gap-map.json" 2>/dev/null) ;; esac
  # APP_OAT_ROOT=<dir>: the app's code compiled on the host as Android's install-time dexopt leaves it
  # (<dir>/<app>/<app>.odex and .vdex), staged beside its APK where ART looks first.
  [ -n "${APP_OAT_ROOT:-}" ] && [ -s "$APP_OAT_ROOT/$app/$app.odex" ] && X="$X --app-oat-dir $APP_OAT_ROOT/$app"
  # The process's own crash dump is newer than this mark (below).
  timeout 30 $WHDC -t $T shell "touch /data/local/tmp/ev-launch.mark" >/dev/null 2>&1
  timeout 20 $WHDC -t $T shell "power-shell wakeup >/dev/null; power-shell setmode 602 >/dev/null" >/dev/null 2>&1   # keep the screen on
  # An unattended round forwards nothing from the board's screen: a touch there reached the app under
  # test and closed it (lifecycle's "touched" rows). WL_TOUCH_MODE=tap keeps the forwarder.
  WL_TOUCH_MODE=${WL_TOUCH_MODE:-off} LAUNCH_SETTLE=${LAUNCH_SETTLE:-2} EXTRA="$X ${RUN_EXTRA:-}" $DEVICE/launch.sh $app $tag-$app
  if [ $? -eq 3 ]; then echo "[run_apps] disk guard stopped the run before $app" >&2; break; fi
  L=$WL_SC/logs/$tag-$app.log
  C=$(grep -o '"child": [0-9]*' $L | head -1 | grep -o '[0-9]*')
  # The process map, sampled until the process exits (to place a crash pc in a library), and its hilog.
  [ -n "$C" ] && timeout 30 $WHDC -t $T shell "rm -f /data/local/tmp/ev-$C.*; nohup sh -c 'while [ -d /proc/$C ]; do cat /proc/$C/maps > /data/local/tmp/ev-$C.maps.new 2>/dev/null && [ -s /data/local/tmp/ev-$C.maps.new ] && mv /data/local/tmp/ev-$C.maps.new /data/local/tmp/ev-$C.maps; sleep 0.5; done' >/dev/null 2>&1 & nohup hilog -P $C > /data/local/tmp/ev-$C.hilog 2>/dev/null &" >/dev/null 2>&1
  # Wait up to WAIT seconds, but stop early (EARLY=1) once, at least MINWAIT seconds in, the log shows
  # it drawing (OH_WSA-relayout) AND two screenshots in a row read as the app by the scorer's own
  # host-screen check (screen_ok.py); at once if the process is gone. The first relayout alone came
  # ~10 s before the screen showed anything, and leaving before 20 s missed crashes a 60 s wait sees.
  # A fixed wait spent ~64% of each launch with the app idle.
  W=${WAIT:-30}
  if [ -n "${WAITS:-}" ] && [ -f "$WAITS" ]; then
    w=$(while read -r name seconds _; do [ "$name" = "$app" ] || [ "hk-$name" = "$app" ] && echo "$seconds"; done < "$WAITS" | tail -1)
    [ -n "$w" ] && W=$w
  fi
  if [ "${EARLY:-1}" = 1 ] && [ -n "$C" ]; then
    t0=$(date +%s); drew=""; ok=0
    while [ $(( $(date +%s) - t0 )) -lt $W ]; do
      st=$(timeout 15 $WHDC -t $T shell "[ -d /proc/$C ] && echo A || echo D; grep -c OH_WSA-relayout /data/service/el1/public/appspawnx/adapter_child_$C.stderr 2>/dev/null" 2>/dev/null | tr -d '\r' | tr '\n' ' ')
      case "$st" in D*) echo "[run_apps] $app process gone after $(( $(date +%s) - t0 ))s" >&2; break ;; esac
      n=$(echo "$st" | awk '{print $2+0}')
      [ -z "$drew" ] && [ "$n" -gt 0 ] && drew=$(date +%s)
      if [ -n "$drew" ] && [ $(( $(date +%s) - t0 )) -ge ${MINWAIT:-20} ]; then
        timeout 30 $WHDC -t $T shell "power-shell wakeup >/dev/null; snapshot_display -f /data/local/tmp/rg.jpeg >/dev/null" >/dev/null 2>&1
        rm -f $RECV/rg.jpeg; recv_to /data/local/tmp/rg.jpeg rg.jpeg
        if [ -s $RECV/rg.jpeg ] && [ "$(python3 $DEVICE/screen_ok.py $RECV/rg.jpeg 2>/dev/null)" = app ]; then ok=$((ok+1)); else ok=0; fi
        [ $ok -ge 2 ] && { echo "[run_apps] $app on screen; moving on after $(( $(date +%s) - t0 ))s" >&2; break; }
      fi
      sleep 2
    done
  else
    sleep $W
  fi
  # Level 2 (EXPLORE=<seconds>): use the app like a curious user before the evidence is taken
  # (explore.py: taps unvisited views, scrolls, goes back); its steps land in <tag>/<app>.explore/.
  if [ "${EXPLORE:-0}" -gt 0 ] && [ -n "$C" ]; then
    python3 $DEVICE/explore.py oh --hdc $WHDC --serial $T --child $C --seconds $EXPLORE --out logs/$tag/$app.explore 2>&1 | tail -1 >&2
  fi
  # Functional checks (CHECKS=<spec.json>, checks.py): the app's scripted steps -- its consent notice, its first
  # screen, one interaction -- launched as the round launches it, before the evidence is taken; a screenshot per
  # step and checks.json land in <tag>/<app>.checks/. Apps the spec doesn't name are left alone.
  if [ -n "${CHECKS:-}" ] && [ -n "$C" ]; then
    python3 $DEVICE/checks.py oh --hdc $WHDC --serial $T --child $C --app ${app#hk-} --spec $CHECKS \
      --out logs/$tag/$app.checks 2>&1 | tail -1 >&2
  fi
  timeout 30 $WHDC -t $T shell "power-shell wakeup >/dev/null; power-shell setmode 602 >/dev/null; snapshot_display -f /data/local/tmp/rg.jpeg >/dev/null" >/dev/null 2>&1
  rm -f $RECV/rg.jpeg; recv_to /data/local/tmp/rg.jpeg rg.jpeg
  cp $RECV/rg.jpeg logs/$tag/$app.jpeg 2>/dev/null
  # After the screenshot: ART dumps every thread into the log, which shows what a stalled main thread waits on.
  [ -n "$C" ] && [ "${DUMP:-1}" = 1 ] && timeout 20 $WHDC -t $T shell "[ -d /proc/$C ] && kill -3 $C" >/dev/null 2>&1 && sleep 3
  [ -n "$C" ] && timeout 60 $WHDC -t $T shell "cat /data/service/el1/public/appspawnx/adapter_child_$C.stderr" 2>/dev/null | tr -d '\r' > logs/$tag/$app.stderr
  # The board keeps every child's stderr (it once filled /data): drop its copy after this last read.
  [ -n "$C" ] && [ -s logs/$tag/$app.stderr ] && timeout 60 $WHDC -t $T shell "rm -f /data/service/el1/public/appspawnx/adapter_child_$C.stderr" >/dev/null 2>&1
  timeout 30 $WHDC -t $T shell "ls -t /data/log/faultlog/faultlogger/ | head -3" 2>/dev/null | tr -d '\r' > logs/$tag/$app.faultlogs
  # The process's own crash dump: faultloggerd writes faultlog/temp/cppcrash-<pid>-<ms>, and hiview
  # may or may not move it to faultlogger/. Pids repeat, so only a dump written since the launch counts.
  if [ -n "$C" ]; then
    F=$(timeout 30 $WHDC -t $T shell "for f in \$(find /data/log/faultlog/temp /data/log/faultlog/faultlogger -name 'cppcrash-*' -newer /data/local/tmp/ev-launch.mark 2>/dev/null); do grep -q '^Pid:$C\$' \$f && echo \$f; done" 2>/dev/null | tr -d '\r' | head -1)
    if [ -n "$F" ]; then rm -f $RECV/ev.cppcrash; recv_to "$F" ev.cppcrash; [ -s $RECV/ev.cppcrash ] && cp $RECV/ev.cppcrash logs/$tag/$app.cppcrash; fi
    P=$(timeout 30 $WHDC -t $T shell "ps -ef" 2>/dev/null | tr -d '\r' | awk -v c="$C" '($0 ~ ("hilog -P " c "( |$)") || $0 ~ ("/proc/" c " ")) && !/awk/ {print $2}' | tr '\n' ' ')
    [ -n "$P" ] && timeout 30 $WHDC -t $T shell "kill $P" >/dev/null 2>&1
    for k in maps hilog; do
      rm -f $RECV/ev.$k; recv_to /data/local/tmp/ev-$C.$k ev.$k 120
      [ -s $RECV/ev.$k ] && cp $RECV/ev.$k logs/$tag/$app.$k
    done
    timeout 30 $WHDC -t $T shell "rm -f /data/local/tmp/ev-$C.*" >/dev/null 2>&1
  fi
  # Stop the app and its spawner: left alive, the last app of a run flooded hilogd for hours. SIGTERM first, then
  # SIGKILL what is left, then every process of the app's uid whose parent is now init: Meta AI (com.facebook.stella)
  # outlived its SIGTERM, was re-parented to init with a child of its own, and stayed on screen over the next 45 apps
  # of a round. The IME host and shared Play services keep a live parent, so they are never matched.
  PP=$(grep -o '"parent": [0-9]*' $L | head -1 | grep -o '[0-9]*')
  [ -n "$C" ] && timeout 30 $WHDC -t $T shell "U=\$(grep '^Uid:' /proc/$C/status 2>/dev/null | cut -f2); kill $C $PP; sleep 1; kill -9 $C $PP 2>/dev/null; [ -n \"\$U\" ] && ps -A -o PID,PPID,UID | while read p pp u; do [ \"\$u\" = \"\$U\" ] && [ \"\$pp\" = 1 ] && kill -9 \$p; done" >/dev/null 2>&1
  # The native libraries the app wrote under its data directory (<runtime>/app-data/<pkg>), for the
  # harness's scan --unpacked-libs; Westlake's own copies are left out.
  R=$(grep -o '"runtime": "[^"]*"' $L | head -1 | cut -d'"' -f4)
  if [ -n "$R" ] && [ "${HARVEST:-1}" = 1 ]; then
    timeout 120 $WHDC -t $T shell "rm -f /data/local/tmp/ev-libs.*; cd $R/app-data 2>/dev/null || exit 0; find . -type f \( -name '*.so' -o -name '*.so.[0-9]*' \) ! -path './org.westlake.imehost/*' ! -path '*/code_cache/wl-exec/*' > /data/local/tmp/ev-libs.txt; [ -s /data/local/tmp/ev-libs.txt ] && tar cf /data/local/tmp/ev-libs.tar -T /data/local/tmp/ev-libs.txt" >/dev/null 2>&1
    rm -f $RECV/ev-libs.tar; recv_to /data/local/tmp/ev-libs.tar ev-libs.tar 300
    timeout 30 $WHDC -t $T shell "rm -f /data/local/tmp/ev-libs.*" >/dev/null 2>&1
    if [ -s $RECV/ev-libs.tar ]; then
      rm -rf logs/$tag/$app.libs; mkdir -p logs/$tag/$app.libs
      tar xf $RECV/ev-libs.tar -C logs/$tag/$app.libs && python3 $DEVICE/harvest_manifest.py logs/$tag/$app.libs "$R"
    fi
  fi
  # The launch output (~190 MB) is only needed until its log and screenshot are here.
  [ -s logs/$tag/$app.stderr ] && rm -rf $V/out/$tag-$app
done
cd $HARNESS && python3 -m harness.westlake_gap.lifecycle $IN/logs/$tag
