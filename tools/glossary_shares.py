"""Split term candidates and speakers into Astra shares for the glossary / voice table (RTKO-13~15).

Writes work/glossary_run/<share>/{input.tsv, brief.md}. Run each share with codex exec (web search allowed).
"""
from __future__ import annotations
import csv, os, re, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'work')
OUT = os.path.join(W, 'glossary_run')
csv.field_size_limit(10 ** 8)


def read_tsv(p):
    return list(csv.reader(open(p, encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))


def style_glossary():
    s = open(os.path.join(ROOT, 'STYLE.md'), encoding='utf-8').read()
    sec = s[s.index('## 6. 용어집'):]
    fixed = set()
    for m in re.finditer(r'([A-Za-z][A-Za-z\'\- ]+?) [가-힣]', sec):
        fixed.add(m.group(1).strip().lower())
    return sec, fixed


def main():
    sec, fixed = style_glossary()
    terms = {}
    for r in read_tsv(os.path.join(W, 'terms_candidates.tsv')):
        if len(r) < 3 or not r[1].isdigit():
            continue
        term, cnt, kind = r[0].strip(), int(r[1]), r[2]
        ex = r[3] if len(r) > 3 else ''
        if kind == 'name' and cnt < 5:
            continue
        k = term.lower()
        if k in fixed or not re.search('[A-Za-z]', term):
            continue
        t = terms.setdefault(k, {'term': term, 'count': 0, 'kinds': set(), 'ex': []})
        t['count'] = max(t['count'], cnt)
        t['kinds'].add(kind)
        if ex and len(t['ex']) < 2:
            t['ex'].append(ex[:140])
    # setting/proper/name first (need lookups), then encyclopedia-only (system)
    lore = sorted([t for t in terms.values() if t['kinds'] != {'encyclopedia'}], key=lambda t: -t['count'])
    sysm = sorted([t for t in terms.values() if t['kinds'] == {'encyclopedia'}], key=lambda t: -t['count'])
    shares = []
    for name, items, n in (('lore', lore, 10), ('system', sysm, 3)):
        size = -(-len(items) // n)
        for i in range(n):
            part = items[i::n]  # interleave so every share gets frequent + rare terms
            if part:
                shares.append(('%s-%d' % (name, i + 1), part))
    os.makedirs(OUT, exist_ok=True)
    head = open(os.path.join(ROOT, 'tools', 'glossary_brief.md'), encoding='utf-8').read()
    for sid, part in shares:
        d = os.path.join(OUT, sid)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'input.tsv'), 'w', encoding='utf-8') as f:
            f.write('english\tcount\tkinds\texample\n')
            for t in part:
                f.write('%s\t%d\t%s\t%s\n' % (t['term'], t['count'], ','.join(sorted(t['kinds'])),
                                             ' | '.join(e.replace('\t', ' ') for e in t['ex'])))
        open(os.path.join(d, 'brief.md'), 'w', encoding='utf-8').write(head + '\n\n## 이미 정한 표기 (바꾸지 말 것)\n\n' + sec)
        print(sid, len(part))
    # voice shares
    spk = [r for r in read_tsv(os.path.join(W, 'speakers.tsv')) if len(r) >= 4 and r[2].isdigit()]
    lines = collections.defaultdict(list)
    import glob
    for f in sorted(glob.glob(os.path.join(W, 'chunks', '*', '*.src.tsv'))):
        for ln in open(f, encoding='utf-8'):
            p = ln.rstrip('\n').split('\t', 2)
            if len(p) == 3 and not ln.startswith('#'):
                lines[p[1]].append(p[2])
    comp = [r for r in spk if r[0].endswith('Companion')] + [['PLAYER', 'n/a', str(len(lines['PLAYER'])), '0']]
    npc = [r for r in spk if not r[0].endswith('Companion') and int(r[2]) >= 20]
    vhead = open(os.path.join(ROOT, 'tools', 'voices_brief.md'), encoding='utf-8').read()
    for sid, rows, k in (('voices-companions', comp, 14), ('voices-npc', npc, 4)):
        d = os.path.join(OUT, sid)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'input.tsv'), 'w', encoding='utf-8') as f:
            f.write('speaker\tgender\tlines\tsample\n')
            for r in rows:
                L = lines.get(r[0], [])
                step = max(1, len(L) // k)
                for s in L[::step][:k]:
                    f.write('%s\t%s\t%s\t%s\n' % (r[0], r[1], r[2], s[:220]))
        open(os.path.join(d, 'brief.md'), 'w', encoding='utf-8').write(vhead + '\n\n---\n\n' + open(os.path.join(ROOT, 'STYLE.md'), encoding='utf-8').read())
        print(sid, len(rows), 'speakers')


if __name__ == '__main__':
    main()
