import json, sys, time, frida

import os

package, seconds, out_path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
PROBE = os.environ.get("PROBE", "probe.js")
dlsym_after = int(sys.argv[4]) if len(sys.argv) > 4 else 20
records, errors = [], []

def on_message(message, data):
    if message["type"] == "send":
        records.append(message["payload"])
    else:
        errors.append(message)

device = frida.get_usb_device(timeout=15)
# enumerate_processes() reports the truncated comm name for app processes on Android;
# enumerate_applications() carries the real package identifier.
pid = None
for _ in range(120):
    for app in device.enumerate_applications():
        if app.identifier == package and app.pid:
            pid = app.pid
            break
    if pid:
        break
    for proc in device.enumerate_processes():
        if proc.name == package:
            pid = proc.pid
            break
    if pid:
        break
    time.sleep(0.25)
if not pid:
    print("process not found; start the app first", flush=True)
    raise SystemExit(1)

session = device.attach(pid)
script = session.create_script(open(PROBE, encoding="utf-8").read())
script.on("message", on_message)
script.load()
print(f"attached to {package} pid={pid}; capturing {seconds}s, dlsym hook at +{dlsym_after}s", flush=True)

start, armed = time.time(), False
while time.time() - start < seconds:
    time.sleep(1)
    if session.is_detached:
        print(f"session detached at +{int(time.time() - start)}s", flush=True)
        break
    if not armed and time.time() - start >= dlsym_after:
        armed = True
        try:
            print("dlsym hook:", script.exports_sync.enabledlsym(), flush=True)
        except Exception as exc:
            print("dlsym hook failed:", exc, flush=True)

try:
    print("stats:", json.dumps(script.exports_sync.stats()), flush=True)
except Exception as exc:
    print("stats unavailable:", exc, flush=True)

with open(out_path, "w", encoding="utf-8") as stream:
    for item in records:
        stream.write(json.dumps(item, ensure_ascii=False) + "\n")
print(f"records={len(records)} errors={len(errors)} -> {out_path}", flush=True)
for item in errors[:3]:
    print("ERR", json.dumps(item)[:300], flush=True)
try:
    session.detach()
except Exception:
    pass
