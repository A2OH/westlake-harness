#!/bin/bash
# netprobe.sh <out.json> -- what the board's network answers for the names in netprobe/names.txt, through the
# resolver apps use, beside what Google's public DNS-over-HTTPS answers the host for the same names.
# An online app that fails while these fail was judged on the network, not on Westlake. netprobe.c is built
# with the OpenHarmony SDK on first use. Writes <out.json>; prints one summary line.
. "$(dirname "$0")/config.sh"
out=$1
[ -n "$out" ] || { echo "usage: netprobe.sh <out.json>" >&2; exit 64; }
SDK=${OHOS_SDK_NATIVE:-$WL_SC/verify/toolchains/ohos-sdk/native}
dir=$IN/.netprobe; mkdir -p "$dir"
if [ ! -x "$dir/netprobe" ] || [ "$DEVICE/netprobe/netprobe.c" -nt "$dir/netprobe" ]; then
  "$SDK/llvm/bin/clang" --target=aarch64-linux-ohos --sysroot="$SDK/sysroot" -O2 -o "$dir/netprobe" \
    "$DEVICE/netprobe/netprobe.c" || { echo "netprobe: build failed" >&2; exit 1; }
fi
# From inside the directory with a relative name, so a Windows hdc works too.
(cd "$dir" && timeout 60 $WHDC -t $T file send netprobe /data/local/tmp/wl-netprobe >/dev/null 2>&1) ||
  { echo "netprobe: send failed" >&2; exit 1; }
names=$(grep -v -e '^#' -e '^$' "$DEVICE/netprobe/names.txt" | tr '\n' ' ')
timeout 600 $WHDC -t $T shell "chmod 755 /data/local/tmp/wl-netprobe && /data/local/tmp/wl-netprobe $names" \
  | tr -d '\r' > "$out.board"
python3 "$DEVICE/netprobe/netprobe.py" "$out.board" "$out" && rm -f "$out.board"
