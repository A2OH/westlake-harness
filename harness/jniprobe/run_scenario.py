import json, subprocess, sys, time, frida

import os

ADB = os.environ.get("ADB", "adb")
PKG = os.environ.get("PKG", "com.ss.android.article.news")
ACT = os.environ.get("ACT", PKG + "/com.ss.android.article.news.activity.MainActivity")
PROBE = os.environ.get("PROBE", "probe.js")
out_path = sys.argv[1]
records, errors, marks = [], [], []

def adb(*args):
    subprocess.run([ADB, "shell", *args], capture_output=True, timeout=60)

def on_message(message, data):
    (records if message["type"] == "send" else errors).append(
        message.get("payload", message))

subprocess.run([ADB, "shell", "am", "force-stop", PKG], capture_output=True, timeout=60)
time.sleep(1)
subprocess.Popen([ADB, "shell", "am", "start", "-n", ACT],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

device = frida.get_usb_device(timeout=15)
pid = None
for _ in range(200):
    for app in device.enumerate_applications():
        if app.identifier == PKG and app.pid:
            pid = app.pid
            break
    if pid:
        break
    time.sleep(0.2)
if not pid:
    raise SystemExit("app did not appear")

session = device.attach(pid)
script = session.create_script(open(PROBE, encoding="utf-8").read())
script.on("message", on_message)
script.load()
print(f"attached pid={pid}", flush=True)

def mark(label):
    marks.append((label, len(records), round(time.time() - t0, 1)))
    print(f"  [{round(time.time()-t0):>3}s] {label}: {len(records)} records", flush=True)

t0 = time.time()
time.sleep(12)                                    # let the feed settle
mark("startup")

for i in range(4):                                 # scroll the feed
    adb("input", "swipe", "540", "1700", "540", "600", "250")
    time.sleep(2)
mark("scrolled-feed")

for label, x in (("video", 324), ("task", 540), ("mall", 756), ("mine", 972)):
    adb("input", "tap", str(x), "2250")            # bottom navigation
    time.sleep(6)
    mark("tab-" + label)

adb("input", "tap", "108", "2250")                 # back to home
time.sleep(4)
adb("input", "swipe", "540", "1700", "540", "600", "250")
time.sleep(3)
mark("back-home")

try:
    print("dlsym hook:", script.exports_sync.enabledlsym(), flush=True)
except Exception as exc:
    print("dlsym hook failed:", exc, flush=True)
for i in range(3):
    adb("input", "swipe", "540", "1700", "540", "600", "250")
    time.sleep(2)
mark("with-dlsym")

try:
    print("stats:", json.dumps(script.exports_sync.stats()), flush=True)
except Exception as exc:
    print("stats unavailable:", exc, flush=True)

with open(out_path, "w", encoding="utf-8") as stream:
    for item in records:
        stream.write(json.dumps(item, ensure_ascii=False) + "\n")
print(f"records={len(records)} errors={len(errors)} -> {out_path}", flush=True)
print("marks:", json.dumps(marks), flush=True)
try:
    session.detach()
except Exception:
    pass
