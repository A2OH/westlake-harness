#!/usr/bin/env python3
"""harvest_manifest.py <app.libs dir> <runtime>  -- describe a run4.sh library harvest for the harness.

The directory holds what the app wrote under its data directory, as <pkg>/<path> (the staged
runtime's app-data/<pkg>/<path>, which the app sees as /data/data/<pkg>/<path>). harvest.json lists
each file with the path the app loads it from, its hash and size, and whether it is an ELF file:
a superpack or extractor can leave compressed or partial files under a .so name.
"""
import hashlib
import json
import sys
from pathlib import Path


def main():
    root, runtime = Path(sys.argv[1]), sys.argv[2]
    libraries = []
    for path in sorted(p for p in root.rglob('*') if p.is_file() and p.name != 'harvest.json'):
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        libraries.append({'file': relative, 'device_path': '/data/data/' + relative,
                          'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
                          'elf': data[:4] == b'\x7fELF'})
    (root / 'harvest.json').write_text(json.dumps({'runtime': runtime, 'libraries': libraries}, indent=1) + '\n')
    print('harvested %d files (%d ELF) into %s' % (len(libraries), sum(l['elf'] for l in libraries), root))


if __name__ == '__main__':
    main()
