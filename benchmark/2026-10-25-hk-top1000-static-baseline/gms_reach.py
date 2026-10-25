#!/usr/bin/env python3
"""gms_reach.py <corpus-hk dir> [workers] -- which Google service clients each downloaded app's dex
code references (type table, every dex of the APK and of the APKs an XAPK nests). Reach = the app
ships code that can call the family; R8 can rename some client classes, so counts are a lower bound.
Writes baseline/gms-reach.json and prints the per-family counts."""
import csv, io, json, struct, sys, zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

C = Path(sys.argv[1])
FAMILIES = {
    "gms:any": ["Lcom/google/android/gms/"],
    "gms:availability": ["Lcom/google/android/gms/common/GoogleApiAvailability;", "Lcom/google/android/gms/common/GooglePlayServicesUtil;"],
    "gms:sign-in": ["Lcom/google/android/gms/auth/api/signin/", "Lcom/google/android/gms/auth/api/identity/",
                    "Lcom/google/android/libraries/identity/googleid/"],
    "gms:auth-other": ["Lcom/google/android/gms/auth/api/phone/", "Lcom/google/android/gms/auth/api/credentials/"],
    "gms:fido-passkeys": ["Lcom/google/android/gms/fido/"],
    "fcm": ["Lcom/google/firebase/messaging/"],
    "firebase:any": ["Lcom/google/firebase/"],
    "firebase:auth": ["Lcom/google/firebase/auth/"],
    "firebase:analytics": ["Lcom/google/firebase/analytics/"],
    "firebase:crashlytics": ["Lcom/google/firebase/crashlytics/"],
    "gms:location": ["Lcom/google/android/gms/location/"],
    "gms:maps": ["Lcom/google/android/gms/maps/"],
    "gms:places": ["Lcom/google/android/libraries/places/"],
    "gms:ads": ["Lcom/google/android/gms/ads/"],
    "gms:ads-identifier": ["Lcom/google/android/gms/ads/identifier/"],
    "gms:safetynet": ["Lcom/google/android/gms/safetynet/"],
    "play:integrity": ["Lcom/google/android/play/core/integrity/"],
    "recaptcha": ["Lcom/google/android/recaptcha/"],
    "play:billing": ["Lcom/android/billingclient/"],
    "play:in-app-update": ["Lcom/google/android/play/core/appupdate/"],
    "play:review": ["Lcom/google/android/play/core/review/"],
    "play:asset-delivery": ["Lcom/google/android/play/core/assetpacks/", "Lcom/google/android/play/core/splitinstall/"],
    "gms:wallet-pay": ["Lcom/google/android/gms/wallet/", "Lcom/google/android/gms/pay/"],
    "gms:cast": ["Lcom/google/android/gms/cast/"],
    "gms:mlkit": ["Lcom/google/mlkit/", "Lcom/google/android/gms/vision/"],
    "gms:wearable": ["Lcom/google/android/gms/wearable/"],
    "gms:nearby": ["Lcom/google/android/gms/nearby/"],
    "gms:fitness": ["Lcom/google/android/gms/fitness/"],
    "gms:games": ["Lcom/google/android/gms/games/"],
}


def uleb(data, pos):
    result = shift = 0
    while True:
        b = data[pos]; pos += 1
        result |= (b & 0x7F) << shift
        if b < 0x80:
            return result, pos
        shift += 7


def dex_types(data):
    string_ids_off = struct.unpack_from("<I", data, 0x3C)[0]
    type_ids_size, type_ids_off = struct.unpack_from("<II", data, 0x40)
    out = []
    for i in range(type_ids_size):
        sidx = struct.unpack_from("<I", data, type_ids_off + 4 * i)[0]
        off = struct.unpack_from("<I", data, string_ids_off + 4 * sidx)[0]
        _, pos = uleb(data, off)
        out.append(data[pos:data.index(b"\x00", pos)].decode("utf-8", "replace"))
    return out


def inner(z, name):
    if z.getinfo(name).file_size <= 256 * 1024 * 1024:
        return zipfile.ZipFile(io.BytesIO(z.read(name)))
    return zipfile.ZipFile(z.open(name))


def dex_blobs(apk):
    with zipfile.ZipFile(apk) as z:
        for name in z.namelist():
            if name.startswith("classes") and name.endswith(".dex"):
                yield z.read(name)
            elif name.endswith(".apk"):
                with inner(z, name) as i:
                    for n in i.namelist():
                        if n.startswith("classes") and n.endswith(".dex"):
                            yield i.read(n)


def scan(item):
    pkg, apk = item
    found, ndex = set(), 0
    try:
        for blob in dex_blobs(apk):
            ndex += 1
            for t in dex_types(blob):
                if not t.startswith(("Lcom/google/", "Lcom/android/billingclient/")):
                    continue
                for fam, prefixes in FAMILIES.items():
                    if fam not in found and t.startswith(tuple(prefixes)):
                        found.add(fam)
    except Exception as e:
        return pkg, None, f"{type(e).__name__}: {e}"[:200]
    return (pkg, sorted(found), None) if ndex else (pkg, None, "no dex")


def main():
    src = {r["package"]: r["source"] for r in csv.DictReader((C / "sources.csv").open())}
    items = []
    for pkg in (C / "apps.csv").read_text().split():
        if src.get(pkg, "missing") == "missing":
            continue
        apk = next(iter(sorted((C / "dl").glob(f"{pkg}@*"))), None)
        if apk:
            items.append((pkg, apk))
    with ProcessPoolExecutor(int(sys.argv[2]) if len(sys.argv) > 2 else 3) as pool:
        results = list(pool.map(scan, items, chunksize=4))
    per_app = {p: f for p, f, e in results if f is not None}
    failed = {p: e for p, f, e in results if f is None}
    counts = {fam: sum(fam in f for f in per_app.values()) for fam in FAMILIES}
    (C / "baseline/gms-reach.json").write_text(json.dumps(
        {"apps": len(per_app), "failed": failed, "counts": counts, "per_app": per_app}, indent=1) + "\n")
    for fam, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"{fam:22} {n:4} of {len(per_app)}")
    print("failed:", failed)


if __name__ == "__main__":
    main()
