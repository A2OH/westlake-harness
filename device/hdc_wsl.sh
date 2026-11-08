#!/bin/bash
# hdc_wsl.sh <hdc args...> -- the Windows hdc ($HDC_EXE) run from WSL through an interop socket that works.
# A WSL session's interop socket ($WSL_INTEROP) can stay connectable while dead: the Windows side never
# connects back ("UtilAcceptVsock ... accept4 failed 110"), and every Windows program launched through it
# fails. Background rounds inherit the socket of the terminal that started them, so one closed terminal
# stopped every launch of a round ("EXIT=1 child=NONE", then "Play services did not start"). A socket is
# proven by launching whoami.exe (exit 0); the proven one is cached for two minutes.
cache=${XDG_RUNTIME_DIR:-/tmp}/wl-wsl-interop-$(id -u)
good=$(cat "$cache" 2>/dev/null)
if [ -n "$good" ] && [ -S "$good" ] && [ $(( $(date +%s) - $(stat -c %Y "$cache" 2>/dev/null || echo 0) )) -lt 120 ]; then
  export WSL_INTEROP=$good
else
  for s in $good $(ls -t /run/WSL/*_interop 2>/dev/null) "$WSL_INTEROP"; do
    [ -S "$s" ] || continue
    if WSL_INTEROP=$s timeout 15 /mnt/c/Windows/System32/whoami.exe >/dev/null 2>&1; then
      export WSL_INTEROP=$s; echo "$s" > "$cache.$$" && mv "$cache.$$" "$cache"; break
    fi
  done
fi
exec "$HDC_EXE" "$@"
