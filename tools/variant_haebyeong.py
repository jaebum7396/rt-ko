"""해병문학체 option (RTKO-38): Astartes lines -> Astra shares; `--collect` builds work/variants/haebyeong/overlay.tsv.

usage: variant_haebyeong.py           write shares under work/variants/haebyeong/run/
       variant_haebyeong.py --collect  validate share outputs and write overlay.tsv (GUID TAB escaped text)
"""
from __future__ import annotations
import collections, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'work')
V = os.path.join(W, 'variants', 'haebyeong')
SPEAKERS = {'UlfarCompanion', 'UlfarInPrison', 'UlfarNPC_Naked', 'Torbald_WarCouncil', 'Uralon_Companion', 'Blood_Raven',
            'DarkApostleVision', 'DarkApostleMob', 'RegindSpacewolfMarine_Ranged', 'RegindSpacewolfMarine_Melee',
            'HalbrandtSpacewolfMarine_WarCouncilKTC', 'HalbrandtSpacewolfMarine', 'ChaosSpacemarine_Preacher_Ranged',
            'HellBrute_UlfarQuest'}
SHARE = 110


FIRST_SCENES = ('Ch3/Chasm/UlfarPrison', 'Ch3/CommorraghStreets/UlfarWhatTheHell')
SCORN = re.compile(r"\b(mortal|pup|whelp|cub|little one|reek|corrupt|heretic|traitor|unwise|warned you|threat|insult|do not utter|comeuppance|arrogant)\b", re.I)
HOSTILE_SCENES = ('ConfrontCorruption',)  # Ulfar turns on a corrupted Rogue Trader


def stage(speaker, path, english):
    """Relationship of the Astartes speaker to the Rogue Trader for this line (drives 반말 vs 다나까)."""
    if speaker.startswith('Ulfar'):
        if speaker == 'UlfarInPrison' or any(x in path for x in FIRST_SCENES):
            return 'first'
        return 'scorn' if SCORN.search(english) or any(x in path for x in HOSTILE_SCENES) else 'superior'
    if speaker.startswith(('Torbald', 'Regind', 'Halbrandt')):
        return 'ally'
    if speaker == 'Blood_Raven':
        return 'aloof'
    if speaker == 'Uralon_Companion':
        return 'reverent'
    return 'hostile'


def lines():
    m = json.load(open(os.path.join(W, 'manifest.json'), encoding='utf-8'))
    for c in m['chunks']:
        g, cid = c['group'], c['id']
        src = {}
        for ln in open(os.path.join(W, 'chunks', g, cid + '.src.tsv'), encoding='utf-8'):
            if not ln.startswith('#'):
                p = ln.rstrip('\n').split('\t', 2)
                src[p[0]] = (p[1], p[2])
        kl = [ln.rstrip('\n').split('\t') for ln in open(os.path.join(W, 'chunks', g, cid + '.keys.tsv'), encoding='utf-8')]
        keys = {r[0]: r[1] for r in kl}
        paths = {r[0]: r[2] for r in kl if len(r) > 2}
        for ln in open(os.path.join(W, 'out', g, cid + '.tsv'), encoding='utf-8'):
            p = ln.rstrip('\n').split('\t', 1)
            if len(p) == 2 and src.get(p[0], ('',))[0] in SPEAKERS:
                yield keys[p[0]], src[p[0]][0], src[p[0]][1], p[1], stage(src[p[0]][0], paths.get(p[0], ''), src[p[0]][1])


def tags(t):
    t = re.sub(r'\{(mf|rt_mf|nc)\|[^}]*\}', r'{\1}', t)
    return sorted(re.findall(r'\{[^}]*\}|<[^>]*>', t)), t.count('\\n')


def main():
    if '--collect' in sys.argv:
        std = {g: (e, k) for g, s, e, k, st in lines()}
        ids = {}
        for d in sorted(x for x in os.listdir(os.path.join(V, 'run')) if os.path.isdir(os.path.join(V, 'run', x))):
            for ln in open(os.path.join(V, 'run', d, 'input.tsv'), encoding='utf-8'):
                p = ln.rstrip('\n').split('\t')
                if p[0] != 'id':
                    ids[p[0]] = p[0]
        good, bad, missing = {}, 0, 0
        for d in sorted(x for x in os.listdir(os.path.join(V, 'run')) if os.path.isdir(os.path.join(V, 'run', x))):
            out = os.path.join(V, 'run', d, 'out.tsv')
            got = {}
            if os.path.exists(out):
                for ln in open(out, encoding='utf-8'):
                    p = ln.rstrip('\n').split('\t', 1)
                    if len(p) == 2:
                        got[p[0]] = p[1]
            for ln in open(os.path.join(V, 'run', d, 'input.tsv'), encoding='utf-8'):
                gid = ln.split('\t')[0]
                if gid == 'id':
                    continue
                if gid not in got:
                    missing += 1
                elif tags(got[gid]) != tags(std[gid][1]):
                    bad += 1  # markup changed -> keep the standard line
                else:
                    good[gid] = got[gid]
        with open(os.path.join(V, 'overlay.tsv'), 'w', encoding='utf-8') as f:
            for gid, t in good.items():
                f.write('%s\t%s\n' % (gid, t))
        print('overlay lines', len(good), '| markup changed (kept standard)', bad, '| missing', missing)
        return
    rows = list(lines())
    run = os.path.join(V, 'run')
    os.makedirs(run, exist_ok=True)
    brief = open(os.path.join(ROOT, 'tools', 'variant_brief_haebyeong.md'), encoding='utf-8').read()
    for i in range(0, len(rows), SHARE):
        d = os.path.join(run, 's%02d' % (i // SHARE + 1))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'input.tsv'), 'w', encoding='utf-8') as f:
            f.write('id\tspeaker\tstage\tenglish\tkorean\n')
            for g, s, e, k, st in rows[i:i + SHARE]:
                f.write('%s\t%s\t%s\t%s\t%s\n' % (g, s, st, e, k))
        open(os.path.join(d, 'brief.md'), 'w', encoding='utf-8').write(brief)
    print('lines', len(rows), 'shares', -(-len(rows) // SHARE), collections.Counter(st for *_, st in rows).most_common())


if __name__ == '__main__':
    main()
