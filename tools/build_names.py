"""Names dictionary from wave-1 results (RTKO-23): item/ability/unit/place names English -> our Korean,
so dialogue chunks (w2) use the same names as the menus. Writes glossary/names.tsv, then run extract.py --terms-only."""
from __future__ import annotations
import csv, glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from merge_glossary import STOP, proper_noun_ratio  # noqa: E402

csv.field_size_limit(10 ** 8)


def unesc(s):
    return re.sub(r'\\(\\|n)', lambda m: '\\' if m.group(1) == '\\' else '\n', s)


def main():
    m = json.load(open(os.path.join(ROOT, 'work', 'manifest.json'), encoding='utf-8'))
    by_path, ko = {}, {}
    for c in m['chunks']:
        if c['status'] not in ('done', 'checked') or not c['group'].startswith('w1-'):
            continue
        d = os.path.join(ROOT, 'work')
        keys = os.path.join(d, 'chunks', c['group'], c['id'] + '.keys.tsv')
        out = os.path.join(d, 'out', c['group'], c['id'] + '.tsv')
        tr = {}
        for ln in open(out, encoding='utf-8'):
            p = ln.rstrip('\n').split('\t', 1)
            if len(p) == 2:
                tr[p[0]] = unesc(p[1])
        for ln in open(keys, encoding='utf-8'):
            n, guid, path = ln.rstrip('\n').split('\t')[:3]
            if n in tr:
                by_path[path] = guid
                ko[guid] = tr[n]
    known = set()
    for fn in ('setting.tsv', 'system.tsv', 'system.w1.tsv'):
        for r in csv.reader(open(os.path.join(ROOT, 'glossary', fn), encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE):
            if r:
                known.add(r[0].strip().lower())
    sec = open(os.path.join(ROOT, 'STYLE.md'), encoding='utf-8').read()
    known |= {x.strip().lower() for x in re.findall(r"([A-Za-z][A-Za-z'\- ]+?) [가-힣]", sec[sec.index('## 6.'):])}
    cands = []
    for r in csv.reader(open(os.path.join(ROOT, 'work', 'terms_candidates.tsv'), encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE):
        if len(r) >= 4 and r[2] == 'name':
            cands.append((r[0].strip(), r[3].strip()))
    singles = proper_noun_ratio([e for e, _ in cands if ' ' not in e])
    rows, seen = [], set()
    for eng, ex in cands:
        low = eng.lower()
        if low in known or low in seen or len(eng.split()) > 6 or low in STOP:
            continue
        if ' ' not in eng and singles.get(low, 1.0) < 0.6:
            continue  # common word, not a proper noun in dialogue
        guid = next((g for p, g in by_path.items() if p.endswith(ex)), None) if ex else None
        k = ko.get(guid, '').strip() if guid else ''
        if not k or '{' in k or '\n' in k or len(k) > 40 or not re.search('[가-힣]', k):
            continue
        seen.add(low)
        rows.append('%s\t%s\tname|w1\n' % (eng, k))
    with open(os.path.join(ROOT, 'glossary', 'names.tsv'), 'w', encoding='utf-8') as f:
        f.write('english\tkorean\tnote\n')
        f.writelines(rows)
    print('names', len(rows), 'from', len(cands), 'candidates;', len(ko), 'translated w1 strings')


if __name__ == '__main__':
    main()
