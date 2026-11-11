"""netprobe.py <board.jsonl> <out.json> -- the board's answers (netprobe.c) beside the host's reference.

For each name the board resolved, the host asks Google's public DNS-over-HTTPS for the same A records.
A board answer counts as usable when its TLS hello got a TLS record back (handshake or alert): the path
to a server for that name works, whatever its address. Otherwise the line says what failed: the
lookup, the connect, or the TLS hello (reset or no answer), and whether the board's address is one the
reference also gives (same /24) or a different one, which is how a substituted answer shows.
"""
import ipaddress
import json
import sys
import time
import urllib.parse
import urllib.request


def reference(name):
    url = 'https://dns.google/resolve?' + urllib.parse.urlencode({'name': name, 'type': 'A'})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'netprobe'}), timeout=8) as r:
            data = json.load(r)
        return [a['data'] for a in data.get('Answer', []) if a.get('type') == 1]
    except Exception:  # noqa: BLE001 -- any failure is "no reference"
        return None


def net24(address):
    try:
        return ipaddress.ip_network(address + '/24', strict=False)
    except ValueError:
        return None


def main():
    board_path, out_path = sys.argv[1], sys.argv[2]
    rows = []
    for line in open(board_path, errors='replace'):
        line = line.strip()
        if not line.startswith('{'):
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    summary = classify(rows, reference)
    json.dump({'time': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'summary': summary, 'names': rows},
              open(out_path, 'w'), indent=1)
    failed = ', '.join(f'{n} {v}' for n, v in summary['failed'].items()) or 'none'
    print(f"network: {summary['ok']}/{summary['names']} names usable from the board; not usable: {failed}")


def classify(rows, reference):
    """Adds verdict (and answer, against reference(name)) to each row; returns the summary."""
    for row in rows:
        ref = reference(row['name'])
        row['reference'] = ref
        usable = row.get('tls') in ('handshake', 'alert')
        if row.get('gai', 0) != 0:
            row['verdict'] = 'lookup-failed'
        elif not row.get('v4'):
            row['verdict'] = 'no-ipv4'
        elif usable:
            row['verdict'] = 'ok'
        elif row.get('connect') != 'ok':
            row['verdict'] = 'connect-' + str(row.get('connect'))
        else:
            row['verdict'] = 'tls-' + str(row.get('tls'))
        if ref and row.get('v4'):
            mine = {net24(a) for a in row['v4']}
            theirs = {net24(a) for a in ref}
            row['answer'] = 'same' if set(row['v4']) & set(ref) else 'same-24' if mine & theirs else 'different'
    bad = [r for r in rows if r['verdict'] != 'ok']
    return {
        'names': len(rows),
        'ok': len(rows) - len(bad),
        'failed': {r['name']: r['verdict'] + ('/' + r['answer'] if r.get('answer') else '') for r in bad},
        'different_answers_ok': sorted(r['name'] for r in rows if r['verdict'] == 'ok' and r.get('answer') == 'different'),
    }


if __name__ == '__main__':
    main()
