"""Full review (RTKO-30): every chunk -> Astra reviewer -> fixes.tsv -> apply only lines that keep the markup.

usage: review_run.py prepare | run [--jobs N] [ids...] | apply
"""
from __future__ import annotations
import concurrent.futures as cf, csv, json, os, shutil, subprocess, sys, time, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'work')
R = os.path.join(W, 'review')
csv.field_size_limit(10 ** 8)
sys.path.insert(0, os.path.join(ROOT, 'tools'))


def manifest():
    return json.load(open(os.path.join(W, 'manifest.json'), encoding='utf-8'))['chunks']


def voices():
    v = {}
    for r in csv.reader(open(os.path.join(ROOT, 'glossary', 'voices.tsv'), encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE):
        if len(r) >= 2 and r[0] != 'speaker':
            v[r[0]] = r[1]
    return v


def prepare():
    style = open(os.path.join(ROOT, 'STYLE.md'), encoding='utf-8').read()
    head = open(os.path.join(ROOT, 'tools', 'review_brief.md'), encoding='utf-8').read()
    vv = voices()
    for c in manifest():
        g, cid = c['group'], c['id']
        d = os.path.join(R, cid)
        os.makedirs(d, exist_ok=True)
        out = {}
        for ln in open(os.path.join(W, 'out', g, cid + '.tsv'), encoding='utf-8'):
            p = ln.rstrip('\n').split('\t', 1)
            if len(p) == 2:
                out[p[0]] = p[1]
        spk = set()
        with open(os.path.join(d, 'review.tsv'), 'w', encoding='utf-8') as f:
            f.write('n\tspeaker\tenglish\tkorean\n')
            for ln in open(os.path.join(W, 'chunks', g, cid + '.src.tsv'), encoding='utf-8'):
                if ln.startswith('#'):
                    f.write(ln)
                    continue
                n, s, e = ln.rstrip('\n').split('\t', 2)
                spk.add(s)
                f.write('%s\t%s\t%s\t%s\n' % (n, s, e, out.get(n, '')))
        shutil.copy(os.path.join(W, 'out', g, cid + '.tsv'), os.path.join(d, 'before.tsv'))
        tsrc = os.path.join(W, 'chunks', g, cid + '.terms.tsv')
        terms = open(tsrc, encoding='utf-8').read() if os.path.exists(tsrc) else ''
        hints = []
        ck = os.path.join(W, 'check', cid + '.json')
        if os.path.exists(ck):
            for w in json.load(open(ck, encoding='utf-8')).get('warnings', [])[:300]:
                hints.append('%s\t%s\t%s\n' % (w.get('n'), w.get('code'), str(w.get('detail'))[:120]))
        open(os.path.join(d, 'hints.tsv'), 'w', encoding='utf-8').writelines(hints)
        vtxt = ''.join('| %s | %s |\n' % (s, vv[s]) for s in sorted(spk) if s in vv)
        brief = head + '\n\n## 이 청크의 용어\n\n```\n' + terms + '```\n'
        if vtxt:
            brief += '\n## 이 청크의 화자 말투\n\n| 화자 | 말투 |\n|---|---|\n' + vtxt
        brief += '\n---\n\n' + style
        open(os.path.join(d, 'brief.md'), 'w', encoding='utf-8').write(brief)
    print('prepared', len(manifest()))


def run_one(cid):
    d = os.path.join(R, cid)
    env = dict(os.environ, CODEX_HOME=os.path.expanduser('~/.codex'),
               PATH='/home/jaebeom/.nvm/versions/node/v22.22.0/bin:' + os.environ.get('PATH', ''))
    t0 = time.time()
    with open(os.path.join(d, 'brief.md'), 'rb') as bi, open(os.path.join(d, 'events.jsonl'), 'wb') as ev, \
            open(os.path.join(d, 'stderr.log'), 'wb') as er:
        subprocess.run(['codex', 'exec', '-C', d, '-m', 'gpt-6-astra', '-c', 'model_reasoning_effort="medium"', '--approve-for-me',
                        '--skip-git-repo-check', '--color', 'never', '--json', '-o', os.path.join(d, 'last.md'), '-'],
                       stdin=bi, stdout=ev, stderr=er, env=env, timeout=3600)
    ok = b'"turn.completed"' in open(os.path.join(d, 'events.jsonl'), 'rb').read()
    n = sum(1 for _ in open(os.path.join(d, 'fixes.tsv'), encoding='utf-8')) if os.path.exists(os.path.join(d, 'fixes.tsv')) else -1
    return cid, ok, n, int(time.time() - t0)


def run(ids, jobs):
    ids = ids or [c['id'] for c in manifest() if not os.path.exists(os.path.join(R, c['id'], 'fixes.tsv'))]
    done = 0
    with cf.ThreadPoolExecutor(jobs) as ex:
        for cid, ok, n, sec in ex.map(run_one, ids):
            done += 1
            print('%s [%d/%d] %s %s fixes=%d %ds' % (time.strftime('%H:%M:%S'), done, len(ids), cid, 'ok' if ok else 'FAIL', n, sec), flush=True)


def apply():
    reasons, applied, rejected = collections.Counter(), 0, 0
    for c in manifest():
        g, cid = c['group'], c['id']
        fx = os.path.join(R, cid, 'fixes.tsv')
        if not os.path.exists(fx):
            continue
        outp = os.path.join(W, 'out', g, cid + '.tsv')
        lines = open(outp, encoding='utf-8').read().split('\n')
        idx = {ln.split('\t', 1)[0]: i for i, ln in enumerate(lines) if '\t' in ln}
        for ln in open(fx, encoding='utf-8'):
            p = ln.rstrip('\n').split('\t')
            if len(p) < 2 or p[0] not in idx or not p[1].strip():
                continue
            lines[idx[p[0]]] = p[0] + '\t' + p[1]
            reasons[p[2].strip() if len(p) > 2 else '기타'] += 1
            applied += 1
        open(outp, 'w', encoding='utf-8').write('\n'.join(lines))
    # revert lines that now fail the markup checks
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'check.py'), '--all'], cwd=ROOT, stdout=subprocess.DEVNULL)
    for c in manifest():
        g, cid = c['group'], c['id']
        ck = os.path.join(W, 'check', cid + '.json')
        errs = {str(e['n']) for e in json.load(open(ck, encoding='utf-8')).get('errors', [])} if os.path.exists(ck) else set()
        if not errs:
            continue
        before = {ln.split('\t', 1)[0]: ln for ln in open(os.path.join(R, cid, 'before.tsv'), encoding='utf-8').read().split('\n') if '\t' in ln}
        outp = os.path.join(W, 'out', g, cid + '.tsv')
        lines = [before.get(ln.split('\t', 1)[0], ln) if ln.split('\t', 1)[0] in errs else ln
                 for ln in open(outp, encoding='utf-8').read().split('\n')]
        rejected += len(errs)
        open(outp, 'w', encoding='utf-8').write('\n'.join(lines))
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'check.py'), '--all'], cwd=ROOT)
    print('applied', applied, '| reverted for markup', rejected, '| by reason', dict(reasons.most_common()))
    json.dump({'applied': applied, 'reverted': rejected, 'reasons': reasons}, open(os.path.join(R, 'summary.json'), 'w', encoding='utf-8'), ensure_ascii=False)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'prepare':
        prepare()
    elif cmd == 'run':
        jobs = int(sys.argv[sys.argv.index('--jobs') + 1]) if '--jobs' in sys.argv else 30
        ids = [a for a in sys.argv[2:] if not a.startswith('--') and not a.isdigit()]
        run(ids, jobs)
    elif cmd == 'apply':
        apply()
    else:
        print(__doc__)
