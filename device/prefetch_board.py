#!/usr/bin/env python3
"""prefetch_board.py <pkg>...: push the staged files of these apps ($WL_SC/inputs/prep-hk-<pkg>/) into the board's
input cache (one file per sha256, the layout probe_source_app.py --input-cache reads), so their
launch later copies them on the board instead of sending them over the link. round.sh runs it for
the next batch when PUSH_AHEAD=1. Over a wireless link it gains nothing (the link is the limit) and
its one big send beside a launch's own transfers hung the local hdc server; with a fast link and no
launch running it fills the cache ahead. Files arrive in their own directory, are hash-checked
there, and only then move into the cache; the launcher's own .incoming directory is left alone."""
import hashlib, os, shlex, subprocess, sys, tarfile, tempfile, time
from pathlib import Path
IN = Path(os.environ['WL_SC']) / 'inputs'
HDC = os.environ['HDC']
T = os.environ['HDC_TARGET']
CACHE = '/data/local/tmp/a2hlab-input-cache'
SPOOL = CACHE + '/.prefetch-%d' % os.getpid()

def shell(cmd, timeout=120):
    out = subprocess.run([HDC, '-t', T, 'shell', cmd + '; echo __RC$?'], capture_output=True, text=True, timeout=timeout).stdout
    if '__RC0' not in out: raise RuntimeError(cmd[:80] + ': ' + out[-200:])
    return out.rsplit('__RC', 1)[0]

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def main(pkgs):
    t0 = time.time(); files = {}
    for pkg in pkgs:
        d = IN / ('prep-hk-' + pkg)
        for p in d.rglob('*'):
            if p.is_file() and not p.is_symlink() and p.name != 'app-input.json':
                files.setdefault(sha(p), p)
    if not files: return
    # Room on the board: keep 8 GB free whatever happens.
    free_kb = int(shell("df -k /data | tail -1").split()[3])
    present = set(shell('ls -1 ' + CACHE).split())
    missing = {h: p for h, p in files.items() if h not in present}
    size = sum(p.stat().st_size for p in missing.values())
    if size // 1024 > free_kb - 8 * 1024 * 1024:
        print('prefetch: skipped, %d MB would leave the board under 8 GB free' % (size >> 20)); return
    if missing:
        with tempfile.TemporaryDirectory(dir=IN) as tmp:
            bundle = Path(tmp) / 'prefetch.tar'
            with tarfile.open(bundle, 'w') as tar:
                for h, p in sorted(missing.items()): tar.add(p, arcname=h, recursive=False)
            shell('mkdir -p ' + SPOOL)
            subprocess.run([HDC, '-t', T, 'file', 'send', str(bundle), SPOOL + '/b.tar'], check=True,
                           capture_output=True, timeout=max(120, bundle.stat().st_size // (512 * 1024) + 60))
        try:
            shell('cd %s && tar -xf b.tar && rm -f b.tar' % SPOOL, timeout=600)
            names = sorted(missing)
            got = {}
            for i in range(0, len(names), 24):
                for line in shell('cd %s && sha256sum %s' % (SPOOL, ' '.join(names[i:i + 24])), timeout=600).splitlines():
                    v, n = line.split(None, 1); got[n.strip()] = v
            good = [h for h in names if got.get(h) == h]
            for i in range(0, len(good), 40):
                shell('cd %s && mv %s %s/' % (SPOOL, ' '.join(good[i:i + 40]), CACHE))
            bad = len(names) - len(good)
        finally:
            shell('rm -rf ' + SPOOL)
    else:
        bad = 0
    print('prefetch: %d apps, %d files, %d already cached, sent %d MB in %.0f s%s' % (
        len(pkgs), len(files), len(files) - len(missing), size >> 20, time.time() - t0,
        (', %d failed their hash check' % bad) if bad else ''))

if __name__ == '__main__':
    try: main(sys.argv[1:])
    except Exception as e: print('prefetch: failed (the launch will send these itself):', str(e)[:200])
