#!/usr/bin/env python3
"""prep_apps.py <package> [...] -- stage corpus apps for a device launch as $WL_SC/inputs/prep-hk-<package>.

Per app: unpack its download ($WL_CORPUS/dl/<package>@*: an APK, or an XAPK's base and split APKs), verify each
APK's signature with apksigner and require one certificate across base and splits, pin it in the
manifest's app-inputs.lock.json under the key hk-<package> (original-apk or
original-apk-with-splits, at the launch activity its scan ($WL_CORPUS/$MAP/<package>/scan.json) resolved), then stage it with
prepare_app.py. The unpacked copy is deleted afterwards; prepare_app.py's copy is the only one left.
Records each app in downloads-hk.json. An app already pinned with other bytes is refused."""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

SC = Path(os.environ['WL_SC'])
HERE = Path(os.environ.get('WL_CORPUS') or SC / 'inputs/corpus-hk')
M = Path(os.environ.get('WL_MANIFEST') or SC / 'workspace/manifest')
MAP = os.environ.get('MAP', 'map')
TOOLS = Path(os.environ.get('ANDROID_BUILD_TOOLS') or Path.home() / 'android-sdk/build-tools/34.0.0')
SOURCE = {'apkpure': 'APKPure', 'apkpure-variant': 'APKPure (older arm64 build)', 'apkpure-no-arm64': 'APKPure',
          'play': 'Google Play', 'play-only': 'Google Play', 'huawei': 'Huawei AppGallery'}


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def cert(apk):
    # Verified as the platform Westlake reports (API 34) verifies an install: APK Signature Scheme v2/v3 is
    # enough there. Left to its default, apksigner verifies down to the APK's own minSdk, and a split that
    # declares none (Play's config.arm64_v8a.apk for Outlook) is then asked for a v1 JAR signature that
    # Play's splits do not carry.
    out = subprocess.run([str(TOOLS / 'apksigner'), 'verify', '--min-sdk-version', '34', '--print-certs', str(apk)],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise ValueError(f'{apk.name}: signature does not verify: {out.stderr.strip()[:200]}')
    return re.search(r'certificate SHA-256 digest: ([0-9a-f]+)', out.stdout).group(1)


def unpack(download, package, out):
    if download.suffix != '.xapk':
        base = out / (package + '.apk')
        shutil.copyfile(download, base)
        return base, []
    with zipfile.ZipFile(download) as z:
        apks = [n for n in z.namelist() if n.endswith('.apk') and '/' not in n]
        for name in apks:
            z.extract(name, out)
        manifest = json.loads(z.read('manifest.json')) if 'manifest.json' in z.namelist() else {}
    base = out / (manifest.get('package_name', package) + '.apk')
    if not base.exists():
        base = next(out / n for n in apks if not n.startswith(('config.', 'split_')))
    return base, [out / n for n in apks if out / n != base]


def main():
    sources = {}
    for line in (HERE / 'sources.csv').read_text().splitlines()[1:]:
        p, s = line.split(',')[:2]
        sources[p] = s
    record_path = HERE / 'downloads-hk.json'
    records = json.loads(record_path.read_text()) if record_path.exists() else {}
    lock_path = M / 'app-inputs.lock.json'
    for package in sys.argv[1:]:
        key = 'hk-' + package
        download = next(iter(sorted((HERE / 'dl').glob(f'{package}@*'))), None)
        if download is None:
            print(key, 'NO DOWNLOAD'); continue
        scan = json.loads((HERE / MAP / package / 'scan.json').read_text())['apk']
        if not scan.get('main_activities'):   # e.g. Chrome: the launcher is in an isolated split's manifest
            print(key, 'NO LAUNCH ACTIVITY'); continue
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            base, splits = unpack(download, package, Path(tmp))
            try:
                certs = {p.name: cert(p) for p in [base, *splits]}
            except ValueError as e:   # one app's refusal must not stop the batch's other apps
                print(key, 'SIGNATURE', str(e)[:200], flush=True); continue
            if len(set(certs.values())) != 1:
                print(key, 'CERT MISMATCH', certs); continue
            d = {'package': package, 'version_name': scan.get('version_name'), 'version_code': int(scan.get('version_code') or 0),
                 'download': download.name, 'source': sources.get(package, '?'), 'base_sha256': sha(base),
                 'bytes': base.stat().st_size, 'certificate': next(iter(certs.values())),
                 'splits': [{'name': p.name, 'sha256': sha(p), 'bytes': p.stat().st_size} for p in splits]}
            text = lock_path.read_text()
            lock = json.loads(text)
            apps = lock['applications']
            if key in apps and apps[key]['sha256'] != d['base_sha256']:
                print(key, 'PINNED WITH OTHER BYTES'); continue
            entry = {'kind': 'original-apk-with-splits' if splits else 'original-apk', 'package': package,
                     'version_name': d['version_name'], 'version_code': d['version_code'], 'abi': 'arm64-v8a',
                     'bytes': d['bytes'], 'sha256': d['base_sha256']}
            if splits:
                entry['splits'] = [{'name': s['name'], 'bytes': s['bytes'], 'sha256': s['sha256']} for s in d['splits']]
            entry.update({
                'delivery': f"{SOURCE.get(d['source'], d['source'])} {'XAPK' if splits else 'APK'}, arm64-v8a; "
                            f"{'base and splits verify' if splits else 'verifies'} with one signing certificate "
                            f"({d['certificate'][:8]}...{d['certificate'][-4:]})",
                'reference': f"harness device round: {scan.get('app_name') or package}",
                'rebuild': False, 'modify_or_resign': False, 'launch_activity': scan['main_activities'][0]})
            if not scan.get('native_abis'):
                entry['pure_java'] = True
            apps[key] = entry
            lock_path.write_text(json.dumps(lock, indent=1) + ('\n' if text.endswith('\n') else ''))
            out = SC / 'inputs' / f'prep-{key}'
            shutil.rmtree(out, ignore_errors=True)
            cmd = ['python3', 'tools/prepare_app.py', '--apk', str(base), '--app', key, '--out', str(out)]
            for s in splits:
                cmd += ['--split', str(s)]
            r = subprocess.run(cmd, cwd=M, capture_output=True, text=True)
        records[key] = d
        record_path.write_text(json.dumps(records, indent=1) + '\n')
        print(key, 'OK' if r.returncode == 0 else 'PREPARE FAILED: ' + (r.stderr.strip().splitlines() or ['?'])[-1][:120],
              f"splits={len(splits)}", flush=True)


if __name__ == '__main__':
    main()
