"""Register pass after the full review (RTKO-30): the reviewer pushed some speakers' lines to 하십시오체.
Every named-speaker line whose speech level changed in review -> Astra with strict per-speaker rules -> apply.

usage: register_fix.py prepare | run [--jobs N] | apply
"""
from __future__ import annotations
import concurrent.futures as cf, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'work')
R = os.path.join(W, 'review')
X = os.path.join(R, '_register')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from review_run import manifest, voices, run_one  # noqa: E402

PER_JOB = 80
# 검토 뒤 검수본을 그대로 두는 줄: 설명문인데 화자가 붙은 시험 대화, 적이 아닌 상대에게 반말이 된 줄
KEEP_SCENES = ('UI_TestPolygon',)
KEEP_IDS = {'w1-ship-010:137', 'w2-companions-021:44'}


def level(t):
    t = re.sub(r'\{n\}.*?\{/n\}', ' ', t)
    e = re.findall(r'([가-힣]{1,3})\s*[.!?…"”]+(?=\s|$)', t)
    if not e:
        return None
    w = e[-1]
    if re.search(r'(니다|니까|십시오)$', w):
        return '하십시오체'
    if w.endswith('요'):
        return '해요체'
    if re.search(r'(소|오|구려)$', w) and not w.endswith('도'):
        return '하오체'
    if re.search(r'(네|게|는가|일세|나)$', w):
        return '하게체'
    return '반말'


def tsv(path):
    return {ln.split('\t', 1)[0]: ln.split('\t', 1)[1] for ln in open(path, encoding='utf-8').read().split('\n') if '\t' in ln}


def prepare():
    vv, items, spk = voices(), [], set()
    for c in manifest():
        g, cid = c['group'], c['id']
        fx = os.path.join(R, cid, 'fixes.tsv')
        if not os.path.exists(fx):
            continue
        rows, scene = [], ''
        for ln in open(os.path.join(R, cid, 'review.tsv'), encoding='utf-8'):
            ln = ln.rstrip('\n')
            if ln.startswith('# scene:'):
                scene = ln[8:].strip()
                rows.append(None)
                continue
            p = ln.split('\t')
            if len(p) >= 4 and p[0] != 'n':
                rows.append((p[0], p[1], p[2], p[3], scene))
        pos = {r[0]: i for i, r in enumerate(rows) if r}
        cur = tsv(os.path.join(W, 'out', g, cid + '.tsv'))
        for ln in open(fx, encoding='utf-8'):
            p = ln.rstrip('\n').split('\t')
            if len(p) < 3 or p[2] not in ('높임', '말투') or p[0] not in pos:
                continue
            n, s, en, before, scene = rows[pos[p[0]]]
            if s in ('-', '?') or level(before) == level(p[1]):
                continue
            ctx = []
            for j in range(pos[n] - 4, pos[n] + 3):
                if j == pos[n] or j < 0 or j >= len(rows) or rows[j] is None:
                    continue
                ctx.append('%s [%s] %s' % ('앞' if j < pos[n] else '뒤', rows[j][1], rows[j][2][:160]))
            items.append(dict(id='%s:%s' % (cid, n), speaker=s, scene=scene, en=en, before=before, current=cur.get(n, ''), ctx=ctx))
            spk.add(s)
    head = open(os.path.join(ROOT, 'tools', 'register_brief.md'), encoding='utf-8').read()
    vtxt = ''.join('| %s | %s |\n' % (s, vv[s]) for s in sorted(spk) if s in vv)
    jobs = [items[i:i + PER_JOB] for i in range(0, len(items), PER_JOB)]
    for k, job in enumerate(jobs):
        d = os.path.join(X, 'j%02d' % k)
        os.makedirs(d, exist_ok=True)
        body = []
        for it in job:
            body.append('### %s · %s · %s\n%s\nEN: %s\nbefore: %s\ncurrent: %s\n' % (
                it['id'], it['speaker'], it['scene'], '\n'.join(it['ctx']), it['en'], it['before'], it['current']))
        open(os.path.join(d, 'input.md'), 'w', encoding='utf-8').write('\n'.join(body))
        brief = head + '\n\n## 화자 말투표 (이번 묶음)\n\n| 화자 | 말투 |\n|---|---|\n' + vtxt
        open(os.path.join(d, 'brief.md'), 'w', encoding='utf-8').write(brief)
        for f in ('fixes.tsv', 'out.tsv'):
            if os.path.exists(os.path.join(d, f)):
                os.remove(os.path.join(d, f))
    print('items', len(items), 'jobs', len(jobs))


def run(jobs):
    ids = sorted(j for j in os.listdir(X) if j.startswith('j') and not os.path.exists(os.path.join(X, j, 'out.tsv')))
    with cf.ThreadPoolExecutor(jobs) as ex:
        for cid, ok, _, sec in ex.map(lambda j: run_one(os.path.join('_register', j)), ids):
            out = os.path.join(R, cid, 'out.tsv')
            n = sum(1 for _ in open(out, encoding='utf-8')) if os.path.exists(out) else -1
            print(cid, 'ok' if ok else 'FAIL', 'lines=%d' % n, '%ds' % sec, flush=True)


def apply():
    by_chunk = {}
    for j in sorted(os.listdir(X)):
        out = os.path.join(X, j, 'out.tsv')
        if not os.path.exists(out):
            continue
        keep = set(KEEP_IDS)
        for hdr in re.findall(r'^### (.+)$', open(os.path.join(X, j, 'input.md'), encoding='utf-8').read(), re.M):
            iid, _, scene = hdr.split(' · ', 2)
            if any(s in scene for s in KEEP_SCENES):
                keep.add(iid)
        for ln in open(out, encoding='utf-8'):
            p = ln.rstrip('\n').split('\t', 1)
            if len(p) == 2 and ':' in p[0] and p[1].strip() and p[0] not in keep:
                cid, n = p[0].rsplit(':', 1)
                by_chunk.setdefault(cid, {})[n] = p[1]
    group = {c['id']: c['group'] for c in manifest()}
    changed, saved = 0, {}
    for cid, fix in by_chunk.items():
        outp = os.path.join(W, 'out', group[cid], cid + '.tsv')
        lines = open(outp, encoding='utf-8').read().split('\n')
        saved[cid] = list(lines)
        for i, ln in enumerate(lines):
            n = ln.split('\t', 1)[0]
            if n in fix and '\t' in ln and ln.split('\t', 1)[1] != fix[n]:
                lines[i] = n + '\t' + fix[n]
                changed += 1
        open(outp, 'w', encoding='utf-8').write('\n'.join(lines))
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'check.py'), '--all'], cwd=ROOT, stdout=subprocess.DEVNULL)
    reverted = 0
    for cid, old in saved.items():
        ck = os.path.join(W, 'check', cid + '.json')
        errs = {str(e['n']) for e in json.load(open(ck, encoding='utf-8')).get('errors', [])} if os.path.exists(ck) else set()
        if not errs:
            continue
        prev = {ln.split('\t', 1)[0]: ln for ln in old if '\t' in ln}
        outp = os.path.join(W, 'out', group[cid], cid + '.tsv')
        lines = [prev.get(ln.split('\t', 1)[0], ln) if ln.split('\t', 1)[0] in errs else ln
                 for ln in open(outp, encoding='utf-8').read().split('\n')]
        reverted += len(errs)
        open(outp, 'w', encoding='utf-8').write('\n'.join(lines))
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'check.py'), '--all'], cwd=ROOT)
    print('changed', changed, '| reverted for markup', reverted)


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
