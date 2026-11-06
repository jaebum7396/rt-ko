#!/usr/bin/env python3
"""name_clash.py - 한 화면에 같이 나오는 이름이 한국어로 겹치는지 찾는다 (11/06).

같은 묶음(아키타입 하나, 배경 하나, 함선 능력, 기술 목록, 백과사전 장 하나) 안에서
영어 이름은 다른데 한국어가 같은 것을 보고한다. 계기: 대전략가 구역 Backline·Rear가 둘 다 '후방'.

  name_clash.py [--root DIR]     exit 0 = 겹침 없음, 1 = 겹침 있음
Python 3.8, 표준 라이브러리만. 일부러 같게 둔 것은 아래 ALLOW에 이유와 함께 적는다.
"""
import collections
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = re.compile(r'(DisplayName|_Title|Name_String|\.Name\.json)')
SCOPE = re.compile(r'Mechanics/Blueprints/(Classes/[^/]+|Backgrounds/[^/]+/[^/]+|Spacecombat/Abilities'
                   r'|Root/Strings/Glossaries|Encyclopedia/[^/]+)')
ALLOW = {
    ('Classes/Master', '재배치'): '까마귀·서보스컬이 같은 명령 (Relocate / Relocation)',
    ('Encyclopedia/MechanicalGlossary', '기절'): '같은 상태 (Stun / Stunned)',
    ('Encyclopedia/MechanicalGlossary', '사거리'): '지상·함선의 같은 개념 (Range / Firing Range)',
    ('Encyclopedia/Tutorial', '우선권'): '지상·함선의 같은 개념 (Initiative / Priority)',
}


def norm(e):
    e = re.sub(r'[^a-z0-9 ]+', ' ', e.lower().replace('&', 'and'))
    return re.sub(r's\b', '', re.sub(r'\s+', ' ', e).strip())


def tsv(path, cols):
    out = {}
    if os.path.exists(path):
        for ln in open(path, encoding='utf-8'):
            if ln.startswith('#'):
                continue
            p = ln.rstrip('\n').split('\t', cols - 1)
            if len(p) == cols:
                out[p[0]] = p[1:]
    return out


def main():
    root = sys.argv[sys.argv.index('--root') + 1] if '--root' in sys.argv else ROOT
    groups = collections.defaultdict(dict)
    for keys in sorted(glob.glob(os.path.join(root, 'work', 'chunks', '*', '*.keys.tsv'))):
        grp, cid = os.path.basename(os.path.dirname(keys)), os.path.basename(keys)[:-len('.keys.tsv')]
        src = tsv(os.path.join(root, 'work', 'chunks', grp, cid + '.src.tsv'), 3)
        out = tsv(os.path.join(root, 'work', 'out', grp, cid + '.tsv'), 2)
        for n, (guid, path) in tsv(keys, 3).items():
            m = SCOPE.match(path)
            if not m or not NAME.search(path) or n not in out or n not in src:
                continue
            en, ko = src[n][1], out[n][0].strip()
            if ko and len(en) <= 60:
                groups[(m.group(1), ko)].setdefault(norm(en), en)
    bad = [(k, v) for k, v in sorted(groups.items()) if len(v) > 1 and k not in ALLOW]
    for (scope, ko), ens in bad:
        print('%s  %s  <-  %s' % (scope, ko, ' / '.join(sorted(ens.values()))))
    print('겹침 %d건 (허용 %d건 제외)' % (len(bad), len(ALLOW)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
