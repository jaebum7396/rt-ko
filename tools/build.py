#!/usr/bin/env python3
"""번역 결과를 게임 파일로 만든다 (RTKO-11). 규격: docs/PIPELINE.md '만들기'. Python 3.8, 표준 라이브러리만.

  build.py enGB [--fallback patch|english] [--root DIR] [--out FILE]
      원본 enGB.json에서 시작해 work/out의 번역으로 Text만 바꾼 build/enGB.json을 만든다.
  build.py zip  [--root DIR] [--engb FILE] [--out FILE]
      build/enGB.json + FontKorean 모드 + 설치방법.txt -> build/rt-ko-YYYYMMDD.zip
  build.py diff OLD.json NEW.json [--out DIR]
      게임 업데이트 비교 -> changed_keys.txt (새 줄 + 바뀐 줄 GUID, extract.py --keys 입력)

--root 는 work/ 가 들어 있는 폴더 (기본: 저장소 루트). work/ 폴더 자체를 줘도 알아본다.
원본·한글패치·글꼴 모드는 항상 저장소의 src/ 에서 읽는다 (--orig, --patch 로 바꿀 수 있다).
쓰는 청크: work/manifest.json 이 있으면 상태가 done·checked 인 청크만 (--status 로 바꿈, any = 전부), 없으면 work/out 전부.
같은 GUID가 여러 청크에 있으면 경로 순서가 뒤인 것이 이긴다.

원본 enGB.json 의 모양 (직접 확인한 것):
  BOM 없음, CRLF, 들여쓰기 2칸, "키": 값 (콜론 뒤 공백 하나), 항목 하나 = 4줄 (GUID / Offset / Text / 닫는 괄호),
  글 안에서 이스케이프된 것은 \\" \\\\ \\n 뿐 (\\uXXXX 없음, 비ASCII·< > & ' 는 그대로 UTF-8), 마지막 줄 뒤에 줄바꿈 없음.
  이 모양은 파이썬 json 의 문자열 이스케이프(ensure_ascii=False)와 같아서, 항목을 직접 찍고 원본을
  그대로 다시 찍어 바이트가 같은지 검사한다 (다르면 경고).
"""
import argparse
import codecs
import collections
import datetime
import hashlib
import json
import re
import sys
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GAME_ENGB = Path('src/game/WH40KRT_Data/StreamingAssets/Localization/enGB.json')
PATCH_ENGB = Path('src/ref/korean-patch/enGB.json')
FONT_MOD = Path('src/ref/korean-patch/font/FontKorean')
NL = '\r\n'
HANGUL_RANGES = ((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7A3), (0xD7B0, 0xD7FF))  # 자모 · 호환 자모 · 음절 · 자모 확장-B
HANGUL = re.compile('[' + ''.join(chr(a) + '-' + chr(b) for a, b in HANGUL_RANGES) + ']')
UMM_DIR = r'%USERPROFILE%\AppData\LocalLow\Owlcat Games\Warhammer 40000 Rogue Trader\UnityModManager'
MAX_NOTES = 8

_enc = json.JSONEncoder(ensure_ascii=False).encode


def die(msg):
    sys.stdout.flush()
    sys.stderr.write('오류: %s\n' % msg)
    sys.exit(1)


def warn(msg):
    sys.stdout.flush()
    sys.stderr.write('경고: %s\n' % msg)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def human(n):
    n = float(n)
    for unit in ('B', 'KB', 'MB'):
        if n < 1000:
            return ('%d %s' % (n, unit)) if unit == 'B' else ('%.1f %s' % (n, unit))
        n /= 1000
    return '%.1f GB' % n


# ---------------------------------------------------------------- JSON (원본 모양 그대로)

def load_strings(path):
    """(파일 바이트, {GUID: 항목}) — 키 순서는 파일 순서. BOM은 읽을 때만 허용한다."""
    path = Path(path)
    if not path.is_file():
        die('파일이 없다: %s' % path)
    raw = path.read_bytes()
    try:
        data = json.loads(raw.decode('utf-8-sig'))
    except (UnicodeDecodeError, ValueError) as e:
        die('JSON을 읽을 수 없다: %s (%s)' % (path, e))
    strings = data.get('strings') if isinstance(data, dict) else None
    if not isinstance(strings, dict):
        die('{"strings": {...}} 형식이 아니다: %s' % path)
    return raw, strings


def render_entry(guid, obj):
    if not obj:
        return '    ' + _enc(guid) + ': {}'
    body = (',' + NL).join('      ' + _enc(k) + ': ' + _enc(v) for k, v in obj.items())
    return '    ' + _enc(guid) + ': {' + NL + body + NL + '    }'


def wrap(pieces):
    if not pieces:
        return '{' + NL + '  "strings": {}' + NL + '}'
    return '{' + NL + '  "strings": {' + NL + (',' + NL).join(pieces) + NL + '  }' + NL + '}'


def first_diff(a, b):
    n = min(len(a), len(b))
    lo, hi = 0, n
    while lo < hi:  # 앞에서부터 같은 길이를 이진 탐색
        mid = (lo + hi) // 2
        if a[:mid] == b[:mid]:
            lo = mid + 1
        else:
            hi = mid
    return max(lo - 1, 0)


# ---------------------------------------------------------------- 번역 읽기 (work/out + keys.tsv)

_UNESC = re.compile(r'\\(.)', re.S)


def unescape(s, bad=None):
    """TSV 이스케이프 풀기. 왼쪽에서 오른쪽으로 한 번에 훑는다: \\\\ -> \\, \\n -> 줄바꿈.
    (\\n 을 먼저 바꾸고 \\\\ 를 나중에 바꾸면 글자 그대로의 '\\' + 'n' (원문에 실제로 있다)이 줄바꿈으로 깨진다.)
    모르는 이스케이프는 그대로 두고 bad 에 모은다."""
    if '\\' not in s:
        return s

    def sub(m):
        c = m.group(1)
        if c == 'n':
            return '\n'
        if c == '\\':
            return '\\'
        if bad is not None:
            bad.append(c)
        return m.group(0)
    return _UNESC.sub(sub, s)


def read_lines(path):
    """줄 목록 (BOM·CRLF 허용). str.splitlines 는 U+2028 같은 글자에서도 잘라서 쓰지 않는다."""
    text = Path(path).read_bytes().decode('utf-8-sig')
    return [ln[:-1] if ln.endswith('\r') else ln for ln in text.split('\n')]


def read_keys(path):
    keys = {}
    for ln in read_lines(path):
        if not ln.strip() or ln.startswith('#'):
            continue
        p = ln.split('\t')
        try:
            keys[int(p[0])] = p[1].strip()
        except (ValueError, IndexError):
            raise ValueError('keys.tsv 줄 형식 오류: %r' % ln[:60])
    return keys


def locate(root):
    """(base, work): base = build/ 가 놓일 곳, work = work/ 폴더."""
    root = Path(root)
    if (root / 'work').is_dir():
        return root, root / 'work'
    if (root / 'out').is_dir() or (root / 'chunks').is_dir() or (root / 'manifest.json').is_file():
        return root.parent, root  # work/ 자체를 준 경우
    return root, root / 'work'


def load_manifest(work):
    p = work / 'manifest.json'
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_bytes().decode('utf-8-sig'))
    except (UnicodeDecodeError, ValueError):
        warn('manifest.json 을 읽을 수 없다: %s' % p)
        return None


def load_translations(work, statuses=None):
    """work/out/<묶음>/<청크>.tsv 와 work/chunks/<묶음>/<청크>.keys.tsv -> ({GUID: 한국어}, 통계, 메모, 건너뜀).
    같은 GUID가 여러 청크에 있으면 경로 순서가 뒤인 것이 이긴다 (겹침은 센다).

    statuses: manifest 상태 필터. None = manifest 가 있으면 done·checked 만 (new·running·failed·limit 청크의 out 은
    낡았거나 미완이다: 다시 뽑아 n 번호가 바뀐 청크의 옛 out 을 쓰면 엉뚱한 줄에 번역이 붙는다), 없으면 전부.
    'any' = 필터 없음. 집합 = 그 상태만."""
    out_root, keys_root = work / 'out', work / 'chunks'
    st = collections.Counter()
    skipped = collections.Counter()
    notes = []
    tr, owner = {}, {}

    def note(msg):
        if len(notes) < MAX_NOTES:
            notes.append(msg)

    man = load_manifest(work)
    status_of = None
    if statuses != 'any':
        if statuses is None and man is not None:
            statuses = {'done', 'checked'}
        if statuses is not None:
            if man is None:
                die('--status 를 쓰려면 %s 가 필요하다 (필터 없이 쓰려면 --status any)' % (work / 'manifest.json'))
            status_of = {c.get('id'): c.get('status') for c in man.get('chunks', [])}

    files = sorted(out_root.rglob('*.tsv')) if out_root.is_dir() else []
    for p in files:
        if p.name.endswith(('.keys.tsv', '.src.tsv', '.terms.tsv')):
            continue
        chunk = p.stem
        if status_of is not None and status_of.get(chunk) not in statuses:
            skipped[status_of.get(chunk) or 'manifest에 없음'] += 1
            continue
        kp = keys_root / p.parent.relative_to(out_root) / (chunk + '.keys.tsv')
        if not kp.is_file():
            st['no_keys'] += 1
            note('keys.tsv 없음 (번역 못 씀): %s' % chunk)
            continue
        try:
            keys = read_keys(kp)
            lines = read_lines(p)
        except (UnicodeDecodeError, ValueError) as e:
            st['bad_file'] += 1
            note('읽을 수 없음: %s (%s)' % (chunk, e))
            continue
        seen = set()
        for ln in lines:
            if not ln.strip():
                continue
            n_s, tab, ko = ln.partition('\t')
            try:
                n = int(n_s)
            except ValueError:
                n = None
            guid = keys.get(n)
            if guid is None:
                st['bad_row'] += 1
                note('%s: 줄 번호를 모르겠다 %r' % (chunk, ln[:40]))
                continue
            if n in seen:
                st['dup_n'] += 1
                note('%s: n=%d 가 두 번 나온다 (뒤의 것 사용)' % (chunk, n))
            seen.add(n)
            if not tab or not ko.strip():
                st['empty'] += 1
                note('%s: n=%d 빈 번역 (폴백 사용)' % (chunk, n))
                continue
            bad = []
            ko = unescape(ko, bad)
            if bad:
                st['bad_escape'] += 1
                note('%s: n=%d 모르는 이스케이프 \\%s (그대로 둠)' % (chunk, n, bad[0]))
            if '\t' in ko:
                st['tab'] += 1
                note('%s: n=%d 번역에 탭이 있다' % (chunk, n))
            if guid in tr and tr[guid] != ko and owner[guid] != chunk:
                st['conflict'] += 1
                note('%s: %s 가 %s 와 겹침 (뒤의 것 사용)' % (chunk, guid, owner[guid]))
            tr[guid] = ko
            owner[guid] = chunk
            st['rows'] += 1
        missing = len(set(keys) - seen)
        if missing:
            st['partial'] += 1
            st['missing'] += missing
        st['chunks'] += 1
    return tr, st, notes, skipped


def game_version(orig_path, work):
    """StreamingAssets/Version.info 의 a.b.c.d -> 없으면 manifest 의 source_build."""
    vi = Path(orig_path).parent.parent / 'Version.info'
    try:
        m = re.search(r'\b\d+\.\d+\.\d+\.\d+\b', vi.read_text(encoding='utf-8', errors='replace'))
        if m:
            return m.group(0)
    except OSError:
        pass
    man = load_manifest(work)
    return man.get('source_build') if man else None


def meta_path(out):
    return Path(out).with_suffix('.meta.json')


# ---------------------------------------------------------------- enGB

def cmd_enGB(a):
    base, work = locate(a.root if a.root else REPO)
    orig_path = Path(a.orig) if a.orig else REPO / GAME_ENGB
    patch_path = Path(a.patch) if a.patch else REPO / PATCH_ENGB
    out = Path(a.out) if a.out else base / 'build' / 'enGB.json'
    statuses = None
    if a.status:
        statuses = 'any' if a.status.strip().lower() == 'any' else set(s.strip() for s in a.status.split(',') if s.strip())

    raw, strings = load_strings(orig_path)
    notdict = [g for g, o in strings.items() if not isinstance(o, dict)]
    if notdict:
        die('원본 항목이 {"Offset", "Text"} 객체가 아니다: %s 외 %d개' % (notdict[0], len(notdict) - 1))
    guids = list(strings)
    pieces = [render_entry(g, strings[g]) for g in guids]
    ident = wrap(pieces).encode('utf-8') == raw
    if not ident:
        at = first_diff(wrap(pieces).encode('utf-8'), raw)
        warn('원본을 다시 찍은 결과가 원본과 바이트가 다르다 (처음 다른 곳 %d바이트). 원본 형식이 바뀐 듯 — 출력 형식을 확인할 것' % at)

    tr, st, notes, skipped = load_translations(work, statuses)
    orphans = [g for g in tr if g not in strings]
    patch = None
    if a.fallback == 'patch':
        _, pstr = load_strings(patch_path)
        patch = {g: o.get('Text') for g, o in pstr.items() if isinstance(o, dict)}

    n_ours = n_patch = n_en = 0
    for i, g in enumerate(guids):
        obj = strings[g]
        if g in tr:
            text = tr[g]
            n_ours += 1
        else:
            pt = patch.get(g) if patch is not None else None
            if isinstance(pt, str) and HANGUL.search(pt):
                text = pt
                n_patch += 1
            else:
                n_en += 1
                continue
        if obj.get('Text') != text:
            new = dict(obj)
            new['Text'] = text
            pieces[i] = render_entry(g, new)
    data = wrap(pieces).encode('utf-8')

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + '.tmp')
    tmp.write_bytes(data)
    tmp.replace(out)
    digest = sha256(data)
    meta = {'built_at': datetime.datetime.now().isoformat(timespec='seconds'), 'fallback': a.fallback,
            'game_version': game_version(orig_path, work), 'strings': len(guids), 'translated': n_ours,
            'from_patch': n_patch, 'english': n_en, 'chunks': st['chunks'], 'sha256': digest}
    meta_path(out).write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print('%s  %s줄  %s  sha256 %s' % (out, format(len(guids), ','), human(len(data)), digest[:16]))
    print('  번역 %s · 한글패치 %s · 영어 %s  (fallback=%s, 원본 재현 %s)'
          % (format(n_ours, ','), format(n_patch, ','), format(n_en, ','), a.fallback, '일치' if ident else '불일치'))
    print('  번역 읽음: 청크 %d · 줄 %s%s' % (st['chunks'], format(st['rows'], ','),
                                       (' · 건너뜀(manifest 상태) ' + ' '.join('%s %d' % kv for kv in sorted(skipped.items())))
                                       if skipped else ''))
    if not st['chunks']:
        warn('쓸 수 있는 번역이 하나도 없다 (찾은 곳: %s) — --root 를 확인할 것%s'
             % (work / 'out', ' (상태 필터를 끄려면 --status any)' if skipped else ''))
    flags = [('keys.tsv 없는 청크', st['no_keys']), ('못 읽은 청크', st['bad_file']), ('알 수 없는 줄', st['bad_row']),
             ('빈 번역', st['empty']), ('겹친 n', st['dup_n']), ('모르는 이스케이프', st['bad_escape']),
             ('탭 든 번역', st['tab']), ('겹친 GUID(내용 다름)', st['conflict']),
             ('원본에 없는 GUID', len(orphans)), ('빠진 줄이 있는 청크', st['partial']),
             ('번역에서 빠진 줄', st['missing'])]
    flags = ['%s %d' % (k, v) for k, v in flags if v]
    if flags:
        warn(' · '.join(flags))
        for m in notes:
            sys.stderr.write('  - %s\n' % m)
        if orphans:
            sys.stderr.write('  - 원본에 없는 GUID 예: %s\n' % ', '.join(orphans[:3]))
    return 0


# ---------------------------------------------------------------- zip

def install_text(date, meta):
    ver = (meta or {}).get('game_version')
    head = '빌드: %s' % date + (' · 게임 버전: %s' % ver if ver else '')
    lines = ['로그 트레이더 한글패치 (rt-ko) 설치 방법', '=' * 40, head]
    if meta:
        lines.append('번역 %s줄 · 기존 한글패치 문장 %s줄 · 영어 그대로 %s줄 (전체 %s줄)' % (
            format(meta['translated'], ','), format(meta['from_patch'], ','), format(meta['english'], ','),
            format(meta['strings'], ',')))
    lines += [
        '',
        '1. 맨 먼저, 자동 갱신 모드(KoreanPatch_AutoUpdate)를 지웁니다.',
        '   아래 폴더를 통째로 삭제하세요. (탐색기 주소창에 붙여 넣으면 바로 열립니다.)',
        '',
        '     %s\\KoreanPatch_AutoUpdate' % UMM_DIR,
        '',
        '   이 모드는 게임을 켤 때마다 자기 enGB.json 을 새로 내려받아 게임의 enGB.json 을 덮어씁니다.',
        '   지우지 않으면 아래 4번에서 넣은 번역이 게임을 켜는 순간 사라집니다.',
        '   폴더가 없으면(기존 한글패치를 쓴 적이 없으면) 이 단계는 건너뜁니다.',
        '',
        '2. 게임을 완전히 종료합니다.',
        '',
        '3. 원본 enGB.json 을 백업합니다.',
        '   Steam 라이브러리에서 게임을 우클릭 -> 관리 -> 로컬 파일 탐색. 열린 폴더 안의',
        '     WH40KRT_Data\\StreamingAssets\\Localization',
        '   로 들어가 enGB.json 의 이름을 enGB.json.bak 으로 바꿉니다.',
        "   (확장자가 안 보이면 탐색기 '보기' 메뉴에서 '파일 확장명'을 켭니다.)",
        '   * 이미 enGB.json.bak 이 있으면 전에 이 패치를 넣은 적이 있다는 뜻입니다. 그 파일이 진짜 원본이니',
        '     건드리지 말고, 지금의 enGB.json 은 그냥 지웁니다.',
        '',
        '4. 파일을 복사합니다.',
        '   (가) 이 압축 파일의 enGB.json  ->  위 Localization 폴더',
        '   (나) 이 압축 파일의 UnityModManager\\FontKorean 폴더  ->',
        '        %s\\' % UMM_DIR,
        '        이미 있으면 덮어씁니다. 한글 글꼴을 보충하는 Unity Mod Manager 모드이며,',
        '        기존 한글패치를 쓰던 PC에는 이미 설치돼 있습니다.',
        '',
        '5. 게임을 켭니다. 언어 설정은 English(영어) 그대로 둡니다.',
        '   이 번역은 영어 칸(enGB)을 한국어로 바꿔치기한 것이라서, 다른 언어를 고르면 적용되지 않습니다.',
        '',
        '[되돌리기]',
        ' - Localization 폴더의 enGB.json 을 지우고 enGB.json.bak 의 이름을 enGB.json 으로 되돌립니다.',
        " - 백업이 없으면 Steam 에서 게임 우클릭 -> 속성 -> 설치된 파일 -> '게임 파일 무결성 검사'로 원본을 복구합니다.",
        ' - FontKorean 모드는 그대로 둬도 영어 화면에는 영향이 없습니다. 지우려면 UnityModManager\\FontKorean 폴더를 삭제합니다.',
        '',
        '[게임이 업데이트되면]',
        ' Steam 이 게임을 업데이트하면(무결성 검사도 마찬가지) enGB.json 이 원래의 영어 파일로 돌아갑니다.',
        ' 번역이 사라진 것이니 패치를 다시 넣어야 합니다. 이때 enGB.json.bak 은 낡은 원본이므로 지우고 3번부터 다시 합니다.',
    ]
    if ver:
        lines.append(' 이 압축 파일은 게임 %s 기준입니다. 새 버전에서 생긴 줄은 들어 있지 않으니, 가능하면 새 버전용 압축 파일을 받아 쓰세요.' % ver)
    return NL.join(lines) + NL


def cmd_zip(a):
    base, _ = locate(a.root if a.root else REPO)
    en = Path(a.engb) if a.engb else base / 'build' / 'enGB.json'
    if not en.is_file():
        die('%s 가 없다 — 먼저 build.py enGB 를 돌릴 것' % en)
    font = REPO / FONT_MOD
    font_files = sorted(p for p in font.rglob('*') if p.is_file())
    if not (font / 'Info.json').is_file() or not font_files:
        die('글꼴 모드가 없다: %s' % font)

    data = en.read_bytes()
    if data[:3] == b'\xef\xbb\xbf':
        die('%s 에 BOM 이 있다 — 원본은 BOM 이 없다' % en)
    try:
        n_keys = len(json.loads(data.decode('utf-8'))['strings'])
    except (UnicodeDecodeError, ValueError, KeyError, TypeError) as e:
        die('%s 가 올바른 enGB.json 이 아니다 (%s)' % (en, e))
    meta = None
    mp = meta_path(en)
    if mp.is_file():
        try:
            meta = json.loads(mp.read_text(encoding='utf-8'))
        except ValueError:
            meta = None
        if meta and not all(k in meta for k in ('strings', 'translated', 'from_patch', 'english', 'sha256')):
            meta = None
        if meta and meta.get('sha256') != sha256(data):
            warn('%s 가 이 enGB.json 과 맞지 않아 설치방법.txt 에 통계를 넣지 않는다 (enGB 를 다시 돌릴 것)' % mp)
            meta = None

    today = datetime.date.today()
    out = Path(a.out) if a.out else base / 'build' / ('rt-ko-%s.zip' % today.strftime('%Y%m%d'))
    out.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.localtime()[:6]
    # 설치방법.txt 는 BOM + CRLF — 메모장이 한글을 바로 알아본다 (enGB.json 은 BOM 없음)
    guide = codecs.BOM_UTF8 + install_text(today.isoformat(), meta).encode('utf-8')
    members = [('설치방법.txt', guide), ('enGB.json', data)]
    for p in font_files:
        members.append(('UnityModManager/FontKorean/' + p.relative_to(font).as_posix(), p.read_bytes()))
    tmp = out.with_name(out.name + '.tmp')
    with zipfile.ZipFile(str(tmp), 'w') as z:
        for name, blob in members:
            zi = zipfile.ZipInfo(name, stamp)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, blob, compresslevel=9)
    tmp.replace(out)

    print('%s  %s  (enGB.json 키 %s개)' % (out, human(out.stat().st_size), format(n_keys, ',')))
    for name, blob in members:
        print('  %-44s %10s' % (name, human(len(blob))))
    return 0


# ---------------------------------------------------------------- diff

def cmd_diff(a):
    _, old = load_strings(a.old)
    _, new = load_strings(a.new)

    def text(o):
        return o.get('Text') if isinstance(o, dict) else None
    added = [g for g in new if g not in old]
    changed = [g for g in new if g in old and text(new[g]) != text(old[g])]
    removed = [g for g in old if g not in new]
    flagged = set(added) | set(changed)
    keys = [g for g in new if g in flagged]  # NEW 의 순서대로

    out = Path(a.out) if a.out else REPO / 'build' / 'diff'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'changed_keys.txt').write_text(''.join(g + '\n' for g in keys), encoding='utf-8')
    (out / 'removed_keys.txt').write_text(''.join(g + '\n' for g in removed), encoding='utf-8')
    report = ('이전 %s줄 -> 새 %s줄\n새 줄 %d · 바뀐 줄 %d · 사라진 줄 %d (그대로 %s)\n'
              'changed_keys.txt = 새 줄 + 바뀐 줄 %d개 (extract.py --keys), removed_keys.txt = 사라진 줄 %d개\n'
              % (format(len(old), ','), format(len(new), ','), len(added), len(changed), len(removed),
                 format(len(new) - len(added) - len(changed), ','), len(keys), len(removed)))
    (out / 'diff_report.txt').write_text(report, encoding='utf-8')
    sys.stdout.write('%s\n%s' % (out, report))
    return 0


# ---------------------------------------------------------------- main

def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(errors='replace')
        except Exception:
            pass
    ap = argparse.ArgumentParser(description='번역 결과 -> enGB.json · 설치 zip · 게임 업데이트 비교 (RTKO-11)')
    sub = ap.add_subparsers(dest='cmd')
    sub.required = True

    p = sub.add_parser('enGB', help='build/enGB.json 만들기')
    p.add_argument('--fallback', choices=('patch', 'english'), default='patch',
                   help='번역 없는 줄: patch = 한글패치 문장(한글 있을 때) 아니면 영어 (기본) / english = 영어')
    p.add_argument('--root', help='work/ 가 든 폴더 (기본: 저장소 루트)')
    p.add_argument('--out', help='출력 파일 (기본: <root>/build/enGB.json)')
    p.add_argument('--orig', help='원본 enGB.json (기본: src/game/.../enGB.json)')
    p.add_argument('--patch', help='한글패치 enGB.json (기본: src/ref/korean-patch/enGB.json)')
    p.add_argument('--status', help='쓸 청크의 manifest 상태 (쉼표로 여러 개, 예: checked). any = 전부. '
                                    '기본: manifest 가 있으면 done,checked / 없으면 out 의 청크 전부')
    p.set_defaults(func=cmd_enGB)

    p = sub.add_parser('zip', help='설치 zip 만들기')
    p.add_argument('--root', help='work/ 가 든 폴더 (기본: 저장소 루트)')
    p.add_argument('--engb', help='넣을 enGB.json (기본: <root>/build/enGB.json)')
    p.add_argument('--out', help='출력 zip (기본: <root>/build/rt-ko-YYYYMMDD.zip)')
    p.set_defaults(func=cmd_zip)

    p = sub.add_parser('diff', help='게임 업데이트 비교')
    p.add_argument('old', metavar='OLD.json')
    p.add_argument('new', metavar='NEW.json')
    p.add_argument('--out', help='출력 폴더 (기본: build/diff)')
    p.set_defaults(func=cmd_diff)

    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == '__main__':
    sys.exit(main())
