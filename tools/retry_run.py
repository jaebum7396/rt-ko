"""Re-translate only selected lines (check errors + an optional extra list) with Astra, then merge (RTKO-29).

usage: retry_run.py [--extra FILE] [--jobs N]
  FILE: TSV `chunk<TAB>n` — extra lines to re-translate (e.g. a voice fix). Check errors are always included.
"""
from __future__ import annotations
import json, os, shutil, subprocess, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'work')
TMP = '/data2/rt-ko/scratch/retry-run'


def py(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT)


def main():
    extra = collections.defaultdict(set)
    if '--extra' in sys.argv:
        for ln in open(sys.argv[sys.argv.index('--extra') + 1], encoding='utf-8'):
            p = ln.rstrip('\n').split('\t')
            if len(p) >= 2:
                extra[p[0]].add(p[1])
    jobs = sys.argv[sys.argv.index('--jobs') + 1] if '--jobs' in sys.argv else '30'
    py('tools/check.py', '--all', '--retry')
    man = {c['id']: c for c in json.load(open(os.path.join(W, 'manifest.json'), encoding='utf-8'))['chunks']}
    rdir = os.path.join(W, 'retry')
    os.makedirs(rdir, exist_ok=True)
    # add extra lines to the open (unmerged) round of each chunk, or open round 1
    for cid, ns in extra.items():
        rounds = sorted(f for f in os.listdir(rdir) if f.startswith(cid + '-r') and f.endswith('.src.tsv'))
        open_r = [f for f in rounds if not os.path.exists(os.path.join(rdir, f[:-8] + '.merged'))]
        name = open_r[-1][:-8] if open_r else '%s-r%d' % (cid, len(rounds) + 1)
        src = os.path.join(W, 'chunks', man[cid]['group'], cid + '.src.tsv')
        have = set()
        path = os.path.join(rdir, name + '.src.tsv')
        if os.path.exists(path):
            have = {ln.split('\t')[0] for ln in open(path, encoding='utf-8') if not ln.startswith('#')}
        header, add = None, []
        for ln in open(src, encoding='utf-8'):
            if ln.startswith('#'):
                header = ln
            elif ln.split('\t')[0] in ns and ln.split('\t')[0] not in have:
                if header:
                    add.append(header)
                    header = None
                add.append(ln)
        with open(path, 'a', encoding='utf-8') as f:
            f.writelines(add)
        tsrc = os.path.join(W, 'chunks', man[cid]['group'], cid + '.terms.tsv')
        if not os.path.exists(os.path.join(rdir, name + '.terms.tsv')) and os.path.exists(tsrc):
            shutil.copy(tsrc, os.path.join(rdir, name + '.terms.tsv'))
    # open rounds -> temporary work tree for run_astra.py
    todo = [f[:-8] for f in os.listdir(rdir) if f.endswith('.src.tsv') and not os.path.exists(os.path.join(rdir, f[:-8] + '.merged'))
            and not os.path.exists(os.path.join(rdir, f[:-8] + '.out.tsv'))]
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(os.path.join(TMP, 'chunks', 'retry'))
    chunks = []
    for name in sorted(todo):
        for ext in ('.src.tsv', '.terms.tsv'):
            if os.path.exists(os.path.join(rdir, name + ext)):
                shutil.copy(os.path.join(rdir, name + ext), os.path.join(TMP, 'chunks', 'retry', name + ext))
        lines = sum(1 for ln in open(os.path.join(rdir, name + '.src.tsv'), encoding='utf-8') if not ln.startswith('#'))
        chunks.append({'id': name, 'group': 'retry', 'words': lines, 'strings': lines, 'scenes': 1, 'hash': '', 'status': 'new'})
    json.dump({'version': 1, 'chunks': chunks}, open(os.path.join(TMP, 'manifest.json'), 'w', encoding='utf-8'))
    print('retry rounds to run:', len(chunks), 'lines:', sum(c['strings'] for c in chunks))
    if not chunks:
        return
    py('tools/run_astra.py', '--root', TMP, '--status', 'new', '--jobs', jobs, '--global-max', '40')
    for c in chunks:
        out = os.path.join(TMP, 'out', 'retry', c['id'] + '.tsv')
        if os.path.exists(out):
            shutil.copy(out, os.path.join(rdir, c['id'] + '.out.tsv'))
    py('tools/check.py', '--all', '--merge')


if __name__ == '__main__':
    main()
