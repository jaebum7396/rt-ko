"""Merge Astra glossary/voice shares into glossary/*.tsv and write the one-page review (RTKO-13~16).

usage: merge_glossary.py [--review glossary/REVIEW.md]
"""
from __future__ import annotations
import csv, glob, html, json, os, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, 'work', 'glossary_run')
GL = os.path.join(ROOT, 'glossary')
csv.field_size_limit(10 ** 8)
SRC_RANK = {'style': 0, 'namu': 1, 'community': 2, 'translated': 3, 'translit': 4}
CONF_RANK = {'high': 0, 'mid': 1, 'low': 2}


def rows(p):
    with open(p, encoding='utf-8') as f:
        r = list(csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE))
    return r[1:] if r and r[0] and r[0][0] in ('english', 'speaker') else r


STOP = set("""a an the of in on at to for with by from as is be are was were this that these those it its
he him his she her hers they them their you your we our us i me my mine up down out over under all any some one more most
no not yes something nothing everything anything someone anyone everyone none here there now then""".split())


def proper_noun_ratio(words):
    """Share of each word's dialogue occurrences that are capitalised mid-sentence (proper-noun use)."""
    import re as _re
    want = {w.lower() for w in words}
    tot, cap = collections.Counter(), collections.Counter()
    for f in glob.glob(os.path.join(ROOT, 'work', 'chunks', 'w2-*', '*.src.tsv')):
        for ln in open(f, encoding='utf-8'):
            if ln.startswith('#'):
                continue
            text = ln.rstrip('\n').split('\t', 2)[-1]
            for m in _re.finditer(r"[A-Za-z][A-Za-z'\-]*", text):
                lw = m.group(0).lower()
                if lw not in want:
                    continue
                tot[lw] += 1
                before = text[:m.start()].rstrip()
                if m.group(0)[0].isupper() and before and before[-1] not in '.!?"\u201c>}:' and not before.endswith('\\n'):
                    cap[lw] += 1
    return {w: cap[w] / tot[w] for w in tot}


def main():
    review = sys.argv[sys.argv.index('--review') + 1] if '--review' in sys.argv else None
    want, got, problems = {}, {}, []
    for d in sorted(glob.glob(os.path.join(RUN, 'lore-*')) + glob.glob(os.path.join(RUN, 'system-*'))):
        for r in rows(os.path.join(d, 'input.tsv')):
            want[r[0].strip().lower()] = (r[0].strip(), int(r[1]) if r[1].isdigit() else 0)
        out = os.path.join(d, 'glossary.tsv')
        if not os.path.exists(out):
            problems.append('%s: glossary.tsv 없음' % os.path.basename(d))
            continue
        for r in rows(out):
            if len(r) < 5 or not r[0].strip() or not r[1].strip():
                problems.append('%s: 형식 이상 %r' % (os.path.basename(d), r[:2]))
                continue
            e, k, cat, src, conf = (x.strip() for x in r[:5])
            key = e.lower()
            rank = (SRC_RANK.get(src.split(':')[0], 5), CONF_RANK.get(conf, 3))
            if key not in got or rank < got[key][-1]:
                got[key] = (e, k, cat, src, conf, rank)
    tov = os.path.join(GL, 'terms.override.tsv')  # hand decisions win over Astra (e.g. Warrant of Trade = 무역 영장)
    if os.path.exists(tov):
        for r in rows(tov):
            if len(r) >= 2 and r[0].strip() and r[0].strip().lower() in got:
                e, _, cat, _, _, rank = got[r[0].strip().lower()]
                got[r[0].strip().lower()] = (e, r[1].strip(), cat, 'style', 'high', rank)
    missing = [want[k][0] for k in want if k not in got]
    os.makedirs(GL, exist_ok=True)
    # Single words: keep for dialogue only when the dialogue uses them as proper nouns (capitalised mid-sentence);
    # otherwise ("Power", "order", "turn") they are game terms for system text only -> system.w1.tsv. Pronouns etc. drop.
    proper = proper_noun_ratio([g[0] for g in got.values() if ' ' not in g[0].strip()])
    def target(e, cat):
        w = e.strip()
        if ' ' not in w:
            if w.lower() in STOP:
                return None
            if proper.get(w.lower(), 1.0) < 0.6:
                return 'system.w1.tsv'
        return 'setting.tsv' if cat not in ('system', 'item', 'ability') else 'system.tsv'
    out = collections.defaultdict(list)
    for key in sorted(got, key=lambda k: -want.get(k, ('', 0))[1]):
        e, k, cat, src, conf, _ = got[key]
        t = target(e, cat)
        if t:
            out[t].append('%s\t%s\t%s|%s|%s\n' % (e, k, cat, src, conf))
    count = collections.Counter()
    for fn in ('setting.tsv', 'system.tsv', 'system.w1.tsv'):
        with open(os.path.join(GL, fn), 'w', encoding='utf-8') as f:
            f.write('english\tkorean\tnote\n')
            f.writelines(out[fn])
        count[fn] = len(out[fn])
    voices, vex = {}, []
    for d in sorted(glob.glob(os.path.join(RUN, 'voices-*'))):
        p = os.path.join(d, 'voices.tsv')
        if not os.path.exists(p):
            problems.append('%s: voices.tsv 없음' % os.path.basename(d))
            continue
        for r in rows(p):
            if len(r) >= 2 and r[0].strip():
                voices[r[0].strip()] = r[1].strip()
                vex.append((os.path.basename(d), r[0].strip(), r[1].strip(), r[2].strip() if len(r) > 2 else '', r[3].strip() if len(r) > 3 else ''))
    ov = os.path.join(GL, 'voices.override.tsv')  # hand decisions (e.g. Astartes never use honorifics to mortals)
    if os.path.exists(ov):
        for r in rows(ov):
            if len(r) >= 2 and r[0].strip():
                voices[r[0].strip()] = r[1].strip()
                vex = [v if v[1] != r[0].strip() else (v[0], v[1], r[1].strip(), v[3], '') for v in vex]
    with open(os.path.join(GL, 'voices.tsv'), 'w', encoding='utf-8') as f:
        f.write('speaker\tvoice\n')
        for s, v in voices.items():
            f.write('%s\t%s\n' % (s, v))
    print('terms in %d / got %d / missing %d | %s | voices %d' % (len(want), len(got), len(missing), dict(count), len(voices)))
    for p in problems[:10]:
        print('  !', p)
    if missing:
        print('  missing e.g.', missing[:10])
    if review:
        write_review(review, got, want, vex)


def write_review(path, got, want, vex):
    """One Markdown page (GitHub renders it): companion voices, unsure terms, top terms."""
    def cell(x):
        return str(x).replace('|', '\\|').replace('\n', ' ')
    def table(head, body):
        out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
        out += ['| ' + ' | '.join(cell(c) for c in r) + ' |' for r in body]
        return '\n'.join(out)
    n = lambda g: want.get(g[0].lower(), ('', 0))[1]
    comp = [v for v in vex if v[0] == 'voices-companions']
    unsure = sorted((g for g in got.values() if g[4] != 'high'), key=lambda g: -n(g))[:200]
    top = sorted(got.values(), key=lambda g: -n(g))[:120]
    doc = '\n\n'.join([
        '# 용어집·말투 확인 (RTKO-16)',
        '바꿀 것만 "영어 → 원하는 표기" 또는 "화자 → 원하는 말투"로 알려 주세요. 나머지는 이대로 번역합니다.',
        '## 1. 동료·플레이어 말투 (%d)' % len(comp),
        table(['화자', '말투', '예문', '번역 예'], [(c[1], c[2], c[3], c[4]) for c in comp]),
        '## 2. 확신이 낮은 용어 (자주 나오는 순 %d개) — 전체 목록은 setting.tsv · system.tsv' % len(unsure),
        table(['영어', '한국어', '분류', '근거', '확신', '횟수'], [(g[0], g[1], g[2], g[3], g[4], n(g)) for g in unsure]),
        '## 3. 가장 자주 나오는 용어 120개',
        table(['영어', '한국어', '분류', '근거', '횟수'], [(g[0], g[1], g[2], g[3], n(g)) for g in top]),
    ]) + '\n'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').write(doc)
    print('review page', path, len(doc), 'bytes, unsure', len(unsure))


if __name__ == '__main__':
    main()
