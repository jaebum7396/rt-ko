"""해병문학체판 검수 (RTKO-41): overlay lines + standard + context -> Astra reviewer -> fixes.tsv -> review.tsv -> overlay.

usage: variant_review.py prepare | run [--jobs N] | apply
"""
from __future__ import annotations
import collections, concurrent.futures as cf, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'work')
V = os.path.join(W, 'variants', 'haebyeong')
X = os.path.join(W, 'review', '_haebyeong')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from review_run import manifest, run_one  # noqa: E402
from variant_haebyeong import stage, tags  # noqa: E402

PER_JOB = 90


def tsv(path):
    return {ln.split('\t', 1)[0]: ln.split('\t', 1)[1] for ln in open(path, encoding='utf-8').read().split('\n') if '\t' in ln}


def items():
    overlay = tsv(os.path.join(V, 'overlay.tsv'))
    for c in manifest():
        g, cid = c['group'], c['id']
        keys = {}
        for ln in open(os.path.join(W, 'chunks', g, cid + '.keys.tsv'), encoding='utf-8'):
            p = ln.rstrip('\n').split('\t')
            keys[p[0]] = (p[1], p[2] if len(p) > 2 else '')
        if not any(k[0] in overlay for k in keys.values()):
            continue
        out = tsv(os.path.join(W, 'out', g, cid + '.tsv'))
        rows, scene = [], ''
        for ln in open(os.path.join(W, 'chunks', g, cid + '.src.tsv'), encoding='utf-8'):
            if ln.startswith('# scene:'):
                scene = ln[8:].strip()
                continue
            if ln.startswith('#'):
                continue
            n, s, e = ln.rstrip('\n').split('\t', 2)
            rows.append((n, s, e, scene))
        for i, (n, s, e, sc) in enumerate(rows):
            gid, path = keys[n]
            if gid not in overlay:
                continue
            ctx = ['%s [%s] %s' % ('앞' if j < i else '뒤', rows[j][1], rows[j][2][:150])
                   for j in range(max(0, i - 3), min(len(rows), i + 2)) if j != i and rows[j][3] == sc]
            yield dict(id=gid, speaker=s, stage=stage(s, path, e), scene=sc, en=e, std=out.get(n, ''), hb=overlay[gid], ctx=ctx)


def prepare():
    rows = list(items())
    style = open(os.path.join(ROOT, 'tools', 'variant_brief_haebyeong.md'), encoding='utf-8').read()
    style = style[style.index('## 누가 위인가'):]
    style = '\n'.join(l for l in style.split('\n') if 'DONE' not in l)
    brief = open(os.path.join(ROOT, 'tools', 'variant_review_brief.md'), encoding='utf-8').read() + style
    for k in range(0, len(rows), PER_JOB):
        d = os.path.join(X, 'j%02d' % (k // PER_JOB))
        os.makedirs(d, exist_ok=True)
        body = ['### %s · %s · %s · %s\n%s\nEN: %s\n일반판: %s\n해병: %s\n' % (
            r['id'], r['speaker'], r['stage'], r['scene'], '\n'.join(r['ctx']), r['en'], r['std'], r['hb']) for r in rows[k:k + PER_JOB]]
        open(os.path.join(d, 'input.md'), 'w', encoding='utf-8').write('\n'.join(body))
        open(os.path.join(d, 'brief.md'), 'w', encoding='utf-8').write(brief)
        if os.path.exists(os.path.join(d, 'fixes.tsv')):
            os.remove(os.path.join(d, 'fixes.tsv'))
    print('lines', len(rows), 'jobs', -(-len(rows) // PER_JOB), collections.Counter(r['stage'] for r in rows).most_common())


def run(jobs):
    ids = sorted(j for j in os.listdir(X) if j.startswith('j') and not os.path.exists(os.path.join(X, j, 'fixes.tsv')))
    with cf.ThreadPoolExecutor(jobs) as ex:
        for cid, ok, n, sec in ex.map(lambda j: run_one(os.path.join('_haebyeong', j)), ids):
            print(cid, 'ok' if ok else 'FAIL', 'fixes=%d' % n, '%ds' % sec, flush=True)


def apply():
    std = {r['id']: r for r in items()}
    review_p = os.path.join(V, 'review.tsv')
    review = tsv(review_p) if os.path.exists(review_p) else {}
    reasons, bad, long_ = collections.Counter(), 0, 0
    for j in sorted(os.listdir(X)):
        fx = os.path.join(X, j, 'fixes.tsv')
        if not j.startswith('j') or not os.path.exists(fx):
            continue
        for ln in open(fx, encoding='utf-8'):
            p = ln.rstrip('\n').split('\t')
            if len(p) < 2 or p[0] not in std or not p[1].strip() or p[1] == std[p[0]]['hb']:
                continue
            if tags(p[1]) != tags(std[p[0]]['std']):
                bad += 1
                continue
            long_ += len(p[1]) > 2 * max(len(std[p[0]]['std']), 1)
            review[p[0]] = p[1]
            reasons[p[2].strip() if len(p) > 2 else '기타'] += 1
    with open(review_p, 'w', encoding='utf-8') as f:
        f.writelines('%s\t%s\n' % kv for kv in review.items())
    overlay = tsv(os.path.join(V, 'overlay.tsv'))
    overlay.update({k: v for k, v in review.items() if k in overlay})
    with open(os.path.join(V, 'overlay.tsv'), 'w', encoding='utf-8') as f:
        f.writelines('%s\t%s\n' % kv for kv in overlay.items())
    summary = {'applied': sum(reasons.values()), 'markup_rejected': bad, 'over_2x': long_, 'reasons': reasons}
    json.dump(summary, open(os.path.join(X, 'summary.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(summary)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'prepare':
        prepare()
    elif cmd == 'run':
        run(int(sys.argv[sys.argv.index('--jobs') + 1]) if '--jobs' in sys.argv else 10)
    elif cmd == 'apply':
        apply()
    else:
        print(__doc__)
