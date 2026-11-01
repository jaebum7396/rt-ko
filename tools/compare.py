"""Old community patch vs this patch — objective comparisons for the public README (RTKO-39).

usage: compare.py   (prints Markdown sections; reads work/out for translated chunks)
"""
from __future__ import annotations
import collections, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def unesc(s):
    return re.sub(r'\\(\\|n)', lambda m: '\\' if m.group(1) == '\\' else '\n', s)


def load(path):
    return {k: v.get('Text') or '' for k, v in json.load(open(path, encoding='utf-8-sig'))['strings'].items()}


def ours():
    """GUID -> (speaker, Korean) for every translated chunk."""
    out = {}
    m = json.load(open(os.path.join(ROOT, 'work', 'manifest.json'), encoding='utf-8'))
    for c in m['chunks']:
        if c['status'] not in ('done', 'checked'):
            continue
        base = os.path.join(ROOT, 'work')
        tr = {}
        for ln in open(os.path.join(base, 'out', c['group'], c['id'] + '.tsv'), encoding='utf-8'):
            p = ln.rstrip('\n').split('\t', 1)
            if len(p) == 2:
                tr[p[0]] = unesc(p[1])
        spk = {}
        for ln in open(os.path.join(base, 'chunks', c['group'], c['id'] + '.src.tsv'), encoding='utf-8'):
            if not ln.startswith('#'):
                p = ln.split('\t', 2)
                spk[p[0]] = p[1]
        for ln in open(os.path.join(base, 'chunks', c['group'], c['id'] + '.keys.tsv'), encoding='utf-8'):
            n, g = ln.split('\t')[:2]
            if n in tr:
                out[g] = (spk.get(n, ''), tr[n])
    return out


def register(t):
    """Dominant speech level of a line's spoken part (narration {n} and [choice tags] removed)."""
    t = re.sub(r'\{n\}.*?\{/n\}', ' ', t, flags=re.S)
    t = re.sub(r'\[[^\]]*\]', ' ', t)
    c = collections.Counter()
    for m in re.finditer(r'([가-힣]{1,3})\s*[.!?…"”]+(?=\s|$)', t):
        w = m.group(1)
        if re.search(r'(니다|니까|십시오|시오)$', w):
            c['하십시오체'] += 1
        elif w.endswith('요'):
            c['해요체'] += 1
        elif w[-1] in '오소' or w.endswith('구려'):
            c['하오체'] += 1
        elif w[-1] in '네게' or w.endswith('는가') or w.endswith('나'):
            c['하게체'] += 1
        else:
            c['반말·해라체'] += 1
    return c.most_common(1)[0][0] if c else None


def dist(texts):
    c = collections.Counter(r for r in map(register, texts) if r)
    n = sum(c.values())
    return n, ', '.join('%s %d%%' % (k, v * 100 // n) for k, v in c.most_common()) if n else '-'


def main():
    en = load(os.path.join(ROOT, 'src/game/WH40KRT_Data/StreamingAssets/Localization/enGB.json'))
    old = load(os.path.join(ROOT, 'src/ref/korean-patch/enGB.json'))
    new = ours()
    print('번역된 줄 %d / 기존 패치와 겹치는 줄 %d' % (len(new), sum(1 for k in new if k in old)))
    print('\n## 말투 (대사 끝맺음 분포)\n\n| 화자 | 줄 | 기존 패치 | 새 패치 |\n|---|---|---|---|')
    by = collections.defaultdict(list)
    for g, (s, t) in new.items():
        by[s].append(g)
    for s in ['PLAYER', 'AbelardCompanion', 'ArgentaCompanion', 'HeinrixCompanion', 'CassiaCompanion', 'PascalCompanion',
              'JaeCompanion', 'IdiraCompanion', 'YrlietCompanion', 'MarazhaiCompanion', 'UlfarCompanion', 'KibellahCompanion']:
        keys = [g for g in by.get(s, []) if g in old]
        if len(keys) >= 20:
            print('| %s | %d | %s | %s |' % (s, len(keys), dist(old[k] for k in keys)[1], dist(new[k][1] for k in keys)[1]))
    tag = re.compile(r'\{(?:mf|rt_mf)\|')
    mf = [g for g in new if g in old and tag.search(en[g])]
    lost_old = sum(1 for g in mf if len(tag.findall(old[g])) < len(tag.findall(en[g])))
    lost_new = sum(1 for g in mf if len(tag.findall(new[g][1])) < len(tag.findall(en[g])))
    print('\n## 성별 태그\n\n성별 태그가 있는 줄 %d줄 중 태그가 빠진 줄: 기존 패치 %d줄, 새 패치 %d줄' % (len(mf), lost_old, lost_new))


if __name__ == '__main__':
    main()
