#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract.py -- RTKO-9: Strings template + enGB.json -> translation chunks (contract: docs/PIPELINE.md).

  python3 tools/extract.py                         full run: work/chunks/<group>/<chunk>.{src,keys,terms}.tsv,
                                                   work/manifest.json, work/terms_candidates.tsv, work/speakers.tsv
  python3 tools/extract.py --terms-only            rewrite only the *.terms.tsv of the existing chunks
  python3 tools/extract.py --keys FILE --prefix P  chunk only the GUIDs listed in FILE (game-update diffs)
                                                   -> work/chunks/P/P-NNN.*  (manifest entries of other groups stay)

Python 3.8, stdlib only.  Deterministic: same inputs -> byte-identical outputs (files are rewritten only when
their content changes; manifest `status` of a chunk is kept while its `hash` is unchanged).

Rules implemented (docs/PIPELINE.md is the contract):
  eligible : group != skip, enGB.json text not '' / 'Placeholder' / 'draft', and at least one ASCII letter.
             Of duplicate GUIDs (Credits only) the first path in sorted order is canonical.
  scene    : deepest folder (header = path below Mechanics/Blueprints/). Order inside: numbered Cue_/Answer_ files by
             (number, Cue before Answer), then un-numbered Cue_/Answer_ files, then every other file, natural order.
  packing  : a scene above 9,000 words is cut into balanced pieces at line boundaries (later pieces get ' (2부)'...);
             scenes/pieces are then packed in path order by dynamic programming: every chunk <= 9,000 words,
             minimising sum((words - 6,000)^2).  Words = len(text.split()).
  speaker  : Answer_* (not SoulMarkShift) -> PLAYER; else the Strings speaker as-is; Cue_* or a quoted line without one -> ?; else -.
  terms    : glossary/*.tsv rows (english, korean, note) whose english term is in the chunk text (case-insensitive,
             word boundary).  names.tsv only for chunks holding w2-* text; voices.tsv is ignored unless it has an
             `english` header row (it is a per-speaker table).
  extras   : terms_candidates.tsv count = link tags (encyclopedia) | exact-case phrase occurrences in all text (name) |
             occurrences in w2-* text, >= 5 (proper).  speakers.tsv covers Strings speakers of chunked lines.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from groups import GROUPS, SKIP, group_of  # noqa: E402

GROUP_IDS = [g[0] for g in GROUPS]
GROUP_RANK = {g: i for i, g in enumerate(GROUP_IDS)}

TARGET = 6000                      # words per chunk we aim for
MAXW = 9000                        # words per chunk, hard cap (only one oversized single line could break it)
EMPTY_TEXTS = ('', 'Placeholder', 'draft')
BP_PREFIX = 'Mechanics/Blueprints/'
DEFAULT_BUILD = '1.6.1.514'

LETTER = re.compile(r'[A-Za-z]')
TOKEN = re.compile(r'[A-Za-z0-9]+')
DIALOG_FILE = re.compile(r'^(Cue|Answer)_(\d+)(.*)\.json$')
TSV_HOSTILE = re.compile('[\t\r\x0b\x0c\x1c-\x1e\x85' + chr(0x2028) + chr(0x2029) + ']')   # would break TSV / splitlines() readers
DIGITS = re.compile(r'(\d+)')


def die(msg):
    sys.stderr.write('extract.py: ERROR: %s\n' % msg)
    sys.exit(2)


def check(cond, msg):
    if not cond:
        die(msg)


# ---------------------------------------------------------------------------------------------- small helpers
def esc(s: str) -> str:
    """TSV cell escape: backslash -> \\\\, newline -> \\n."""
    return s.replace('\\', '\\\\').replace('\n', '\\n')


_UNESC = re.compile(r'\\(.)', re.S)


def unesc(s: str) -> str:
    return _UNESC.sub(lambda m: '\n' if m.group(1) == 'n' else m.group(1), s)


def natkey(s: str):
    """Natural sort key (digit runs compare as numbers); list positions alternate str/int so it is comparable."""
    return [int(p) if i & 1 else p.lower() for i, p in enumerate(DIGITS.split(s))]


def path_key(folder: str):
    return ([natkey(c) for c in folder.split('/')], folder)


def write_file(path: str, text: str) -> bool:
    """Write UTF-8 text (LF) atomically; skip when the content is already identical. Returns True if written."""
    data = text.encode('utf-8')
    try:
        with open(path, 'rb') as f:
            if f.read() == data:
                return False
    except IOError:
        pass
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)
    return True


def read_text(path: str) -> str:
    with open(path, 'rb') as f:
        return f.read().decode('utf-8-sig')


# ---------------------------------------------------------------------------------------------- loading
class Rec(object):
    """One eligible string."""
    __slots__ = ('key', 'rel', 'group', 'spk', 'raw_spk', 'gender', 'text', 'words', 'sk')


def order_key(rel: str):
    """Order inside a scene: numbered Cue/Answer files by (number, Cue before Answer); then Cue_/Answer_ files with a
    custom (un-numbered) name; then every other kind in natural name order."""
    fn = rel.rsplit('/', 1)[-1]
    m = DIALOG_FILE.match(fn)
    if m:
        return (0, int(m.group(2)), 0 if m.group(1) == 'Cue' else 1, natkey(m.group(3)), rel)
    if fn.startswith('Cue_') or fn.startswith('Answer_'):
        return (0, 10 ** 9, natkey(fn[:-len('.json')].split('_', 1)[1]), 0 if fn.startswith('Cue_') else 1, rel)
    return (1, 0, 0, natkey(fn), rel)


class Corpus(object):
    def __init__(self):
        self.recs = []                                   # eligible strings, Strings-path order
        self.reason = {}                                 # key.lower() -> '' (eligible) | skip | no-enGB | empty | letterless
        self.dropped = collections.defaultdict(lambda: [0, 0])   # (reason, group) -> [strings, words]
        self.n_files = 0
        self.n_unique = 0
        self.n_dup = 0
        self.n_bad = 0
        self.n_speaker_fixed = 0


def load_engb(path: str):
    d = json.loads(read_text(path))
    return {k: (v.get('Text') if isinstance(v, dict) else None) for k, v in d['strings'].items()}


def scan_strings(root: str):
    out, bad = [], 0
    for dp, dns, fns in os.walk(root):
        dns.sort()
        for fn in fns:
            if not fn.endswith('.json'):
                continue
            full = os.path.join(dp, fn)
            try:
                d = json.loads(read_text(full))
            except (IOError, ValueError):
                bad += 1
                continue
            key = d.get('key') if isinstance(d, dict) else None
            if not isinstance(key, str) or not key:
                bad += 1
                continue
            rel = os.path.relpath(full, root).replace(os.sep, '/')
            spk, gen = d.get('speaker'), d.get('speakerGender')
            out.append((rel, key, spk if isinstance(spk, str) else '', gen if isinstance(gen, str) else ''))
    out.sort()
    return out, bad


def build_corpus(strings_dir: str, engb_path: str) -> Corpus:
    en = load_engb(engb_path)
    raw, bad = scan_strings(strings_dir)
    c = Corpus()
    c.n_files, c.n_bad = len(raw), bad
    seen = set()
    for rel, key, speaker, gender in raw:            # path order; of duplicate GUIDs the first path is canonical
        if key in seen:
            c.n_dup += 1
            continue
        seen.add(key)
        g = group_of(rel)
        text = en.get(key)
        if g == SKIP:
            why = 'skip'
        elif not isinstance(text, str):
            why = 'no-enGB'
        elif text.strip() in EMPTY_TEXTS:
            why = 'empty'
        elif not LETTER.search(text):
            why = 'letterless'
        else:
            why = ''
        c.reason[key.lower()] = why
        if why:
            d = c.dropped[(why, g)]
            d[0] += 1
            d[1] += len(text.split()) if isinstance(text, str) else 0
            continue
        r = Rec()
        r.key, r.rel, r.group, r.text, r.gender = key, rel, g, text, gender
        r.words = len(text.split())
        base = rel.rsplit('/', 1)[-1]
        raw_spk = speaker if speaker.strip() else ''
        if TSV_HOSTILE.search(raw_spk):
            raw_spk = TSV_HOSTILE.sub(' ', raw_spk)
            c.n_speaker_fixed += 1
        r.raw_spk = raw_spk
        low = base.lower()
        is_answer = low.startswith('answer_') or '_answer_' in low
        is_cue = low.startswith('cue_') or '_cue_' in low
        if is_answer and 'soulmarkshift' not in low:
            r.spk = 'PLAYER'                         # SoulMarkShift descriptions are 3rd-person text
        elif raw_spk:
            r.spk = raw_spk                          # Strings speaker as-is
        elif is_cue or text.lstrip().startswith('"'):
            r.spk = '?'                              # dialogue line (incl. barks) without a known speaker
        else:
            r.spk = '-'                              # non-dialogue text
        r.sk = order_key(rel)
        c.recs.append(r)
    c.n_unique = len(seen)
    bad_text = [r for r in c.recs if TSV_HOSTILE.search(r.text)]
    check(not bad_text, '%d texts contain TAB/CR/other TSV-hostile characters (first key %s); the escape contract '
                        'only covers backslash and newline -- extend PIPELINE.md first' % (len(bad_text), bad_text[0].key if bad_text else ''))
    bad_rt = [r for r in c.recs if unesc(esc(r.text)) != r.text]
    check(not bad_rt, 'escape round-trip is not lossless for %d texts' % len(bad_rt))
    return c


# ---------------------------------------------------------------------------------------------- chunking
class Unit(object):
    """A scene (or one piece of an oversized scene) -- the atom of packing."""
    __slots__ = ('label', 'part', 'recs', 'words')

    def __init__(self, label, part, recs):
        self.label, self.part, self.recs = label, part, recs
        self.words = sum(r.words for r in recs)


class Chunk(object):
    __slots__ = ('id', 'group', 'units', 'words', 'strings')

    def __init__(self, cid, group, units):
        self.id, self.group, self.units = cid, group, units
        self.words = sum(u.words for u in units)
        self.strings = sum(len(u.recs) for u in units)

    def uses_names(self) -> bool:
        return any(r.group.startswith('w2-') for u in self.units for r in u.recs)


def scene_label(folder: str) -> str:
    if folder == BP_PREFIX.rstrip('/'):
        return '.'
    return folder[len(BP_PREFIX):] if folder.startswith(BP_PREFIX) else folder


def _split_lines(rs, total, k):
    pieces, cur, cum, i = [], [], 0, 1
    for r in rs:
        if cur and i < k and abs(cum + r.words - total * i / float(k)) > abs(cum - total * i / float(k)):
            pieces.append(cur)
            cur, i = [], i + 1
        cur.append(r)
        cum += r.words
    pieces.append(cur)
    return pieces


def split_scene(rs, total):
    """Cut a scene of more than MAXW words into balanced pieces at line boundaries (none above MAXW)."""
    k = max(2, int(round(total / float(TARGET))))
    while True:
        pieces = _split_lines(rs, total, k)
        if max(sum(r.words for r in p) for p in pieces) <= MAXW or k >= len(rs):
            return pieces
        k += 1


def make_units(recs):
    scenes = collections.defaultdict(list)
    for r in recs:
        scenes[r.rel.rpartition('/')[0]].append(r)
    units = []
    for folder in sorted(scenes, key=path_key):
        rs = sorted(scenes[folder], key=lambda r: r.sk)
        total = sum(r.words for r in rs)
        label = scene_label(folder)
        if total <= MAXW:
            units.append(Unit(label, 1, rs))
        else:
            for i, piece in enumerate(split_scene(rs, total), 1):
                units.append(Unit(label, i, piece))
    return units


def pack(units):
    """Cut the unit sequence into consecutive chunks, each <= MAXW, minimising sum((words - TARGET)^2)."""
    n = len(units)
    pre = [0]
    for u in units:
        pre.append(pre[-1] + u.words)
    best = [0] + [None] * n
    back = [0] * (n + 1)
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            w = pre[j] - pre[i]
            if w > MAXW and i < j - 1:
                break                                  # only a lone oversized unit may exceed the cap
            cost = best[i] + (w - TARGET) ** 2
            if best[j] is None or cost < best[j]:
                best[j], back[j] = cost, i
    cuts, j = [], n
    while j > 0:
        cuts.append((back[j], j))
        j = back[j]
    cuts.reverse()
    return [units[a:b] for a, b in cuts]


def make_chunks(recs, name_of_group):
    """recs: eligible records of ONE chunk family. Returns Chunk list numbered <name>-001..."""
    chunks = []
    for idx, us in enumerate(pack(make_units(recs)), 1):
        chunks.append(Chunk('%s-%03d' % (name_of_group, idx), name_of_group, us))
    return chunks


def render(chunk):
    src, keys, texts, n = [], [], [], 0
    for u in chunk.units:
        src.append('# scene: %s%s' % (u.label, '' if u.part == 1 else ' (%d부)' % u.part))
        for r in u.recs:
            n += 1
            src.append('%d\t%s\t%s' % (n, r.spk, esc(r.text)))
            keys.append('%d\t%s\t%s' % (n, r.key, r.rel))
            texts.append(r.text)
    return '\n'.join(src) + '\n', '\n'.join(keys) + '\n', '\n'.join(texts)


def verify_chunks(chunks, expected):
    """Every expected (eligible) key in exactly one chunk, nothing else; size cap respected."""
    seen = collections.Counter(r.key for c in chunks for u in c.units for r in u.recs)
    dup = [k for k, v in seen.items() if v != 1]
    exp = set(r.key for r in expected)
    check(not dup, '%d keys appear in more than one chunk' % len(dup))
    check(not (exp - set(seen)), '%d eligible keys are in no chunk' % len(exp - set(seen)))
    check(not (set(seen) - exp), '%d chunked keys are not eligible' % len(set(seen) - exp))
    for c in chunks:
        check(c.words <= MAXW or (len(c.units) == 1 and len(c.units[0].recs) == 1),
              'chunk %s has %d words (cap %d)' % (c.id, c.words, MAXW))


# ---------------------------------------------------------------------------------------------- terms
class Glossary(object):
    """glossary/*.tsv rows (english, korean, note). voices.tsv is a per-speaker table and is only read when it
    carries an `english` header; names.tsv is used for chunks that hold wave-2 (w2-*) text only."""

    def __init__(self, gdir: str):
        self.rows = []                       # (file, english, korean, note, tokens)
        if os.path.isdir(gdir):
            for fn in sorted(os.listdir(gdir)):
                if fn.endswith('.tsv'):
                    self._load(os.path.join(gdir, fn), fn)
        freq = collections.Counter(t for row in self.rows for t in row[4])
        self.index = collections.defaultdict(list)   # rarest token of the term -> row numbers
        self.untokenised = []
        for n, row in enumerate(self.rows):
            if row[4]:
                self.index[min(row[4], key=lambda t: (freq[t], t))].append(n)
            else:
                self.untokenised.append(n)
        self.rx = {}

    def _load(self, path, fn):
        lines = [ln.rstrip('\r') for ln in read_text(path).split('\n')]
        lines = [ln for ln in lines if ln.strip() and not ln.startswith('#')]
        header = bool(lines) and lines[0].split('\t')[0].strip().lower().startswith('english')
        if fn == 'voices.tsv' and not header:
            return
        for ln in lines[1 if header else 0:]:
            cells = ln.split('\t')
            eng = cells[0].strip()
            if eng:
                self.rows.append((fn, eng, cells[1] if len(cells) > 1 else '', cells[2] if len(cells) > 2 else '',
                                  tuple(t.lower() for t in TOKEN.findall(eng))))

    def terms_for(self, blob: str, use_names: bool):
        blob = blob.replace('\xa0', ' ')
        toks = set(t.lower() for t in TOKEN.findall(blob))
        cand = list(self.untokenised)
        for t in toks:
            cand.extend(self.index.get(t, ()))
        hits, seen = [], set()
        for n in sorted(cand):
            fn, eng, kor, note, rtoks = self.rows[n]
            if fn == 'names.tsv' and not use_names:
                continue
            if not all(t in toks for t in rtoks):
                continue
            rx = self.rx.get(n)
            if rx is None:
                rx = self.rx[n] = re.compile(r'(?<![A-Za-z0-9])' + re.escape(eng) + r'(?![A-Za-z0-9])', re.I)
            if rx.search(blob):
                line = '%s\t%s\t%s' % (eng, kor, note)
                if line not in seen:
                    seen.add(line)
                    hits.append(line)
        return ''.join(h + '\n' for h in hits)


# ---------------------------------------------------------------------------------------------- manifest
def read_manifest(path: str):
    try:
        d = json.loads(read_text(path))
        if isinstance(d, dict) and isinstance(d.get('chunks'), list):
            return d
    except (IOError, ValueError):
        pass
    return {'version': 1, 'chunks': []}


def source_build(engb_path: str, old) -> str:
    vi = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(engb_path))), 'Version.info')
    try:
        m = re.search(r'\b(\d+\.\d+\.\d+\.\d+)\b', read_text(vi))
        if m:
            return m.group(1)
    except IOError:
        pass
    return old.get('source_build') or DEFAULT_BUILD


def write_manifest(path, build, entries):
    lines = [json.dumps(e, ensure_ascii=False) for e in entries]
    body = '{"version": 1, "source_build": %s,\n "chunks": [\n  %s\n ]}\n' % (
        json.dumps(build), ',\n  '.join(lines)) if lines else '{"version": 1, "source_build": %s,\n "chunks": []}\n' % json.dumps(build)
    write_file(path, body)


def merge_entries(old, fresh, replaced_groups):
    """fresh: new chunk entries. Keeps status (and any extra fields) of old entries whose hash is unchanged,
    and old entries of groups this run does not own."""
    old_by_id = {c.get('id'): c for c in old['chunks'] if isinstance(c, dict)}
    out = []
    for e in fresh:
        o = old_by_id.get(e['id'])
        if o is not None and o.get('hash') == e['hash']:
            e = dict(e)
            e['status'] = o.get('status', e['status'])
            for k, v in o.items():
                e.setdefault(k, v)
        out.append(e)
    out.extend(c for c in old['chunks'] if isinstance(c, dict) and c.get('group') not in replaced_groups)
    out.sort(key=lambda c: (GROUP_RANK.get(c.get('group'), len(GROUP_RANK)), c.get('group', ''), c.get('id', '')))
    return out


# ---------------------------------------------------------------------------------------------- writing chunks
CHUNK_SUFFIXES = ('.src.tsv', '.keys.tsv', '.terms.tsv')


def write_chunks(chunks, chunk_root, gloss):
    entries, n_terms_rows, changed = [], 0, 0
    expected = collections.defaultdict(set)
    for c in chunks:
        src, keys, blob = render(c)
        terms = gloss.terms_for(blob, c.uses_names())
        n_terms_rows += terms.count('\n')
        base = os.path.join(chunk_root, c.group, c.id)
        for suffix, body in (('.src.tsv', src), ('.keys.tsv', keys), ('.terms.tsv', terms)):
            changed += write_file(base + suffix, body)
            expected[c.group].add(c.id + suffix)
        entries.append({'id': c.id, 'group': c.group, 'words': c.words, 'strings': c.strings,
                        'scenes': len(c.units), 'hash': hashlib.sha1(src.encode('utf-8')).hexdigest(), 'status': 'new'})
    return entries, expected, n_terms_rows, changed


def remove_stale(chunk_root, groups, expected):
    removed = 0
    for g in groups:
        d = os.path.join(chunk_root, g)
        if os.path.isdir(d):
            for fn in os.listdir(d):
                if fn.endswith(CHUNK_SUFFIXES) and fn not in expected.get(g, ()):
                    os.remove(os.path.join(d, fn))
                    removed += 1
    return removed


def run_terms_only(args):
    t0 = time.time()
    chunk_root = os.path.join(args.work, 'chunks')
    gloss = Glossary(args.glossary)
    n = rows = changed = 0
    for g in sorted(os.listdir(chunk_root)) if os.path.isdir(chunk_root) else []:
        if args.prefix and g != args.prefix:
            continue
        d = os.path.join(chunk_root, g)
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.src.tsv'):
                continue
            base = os.path.join(d, fn[:-len('.src.tsv')])
            texts = []
            for ln in read_text(os.path.join(d, fn)).split('\n'):
                if ln and not ln.startswith('#'):
                    cells = ln.split('\t', 2)
                    check(len(cells) == 3, '%s/%s: malformed line %r' % (g, fn, ln[:60]))
                    texts.append(unesc(cells[2]))
            use_names = g.startswith('w2-')
            if not use_names and g not in GROUP_RANK and os.path.exists(base + '.keys.tsv'):    # prefix chunk: look at its strings
                use_names = any(group_of(ln.split('\t')[2]).startswith('w2-')
                                for ln in read_text(base + '.keys.tsv').split('\n') if ln.count('\t') >= 2)
            terms = gloss.terms_for('\n'.join(texts), use_names)
            changed += write_file(base + '.terms.tsv', terms)
            n += 1
            rows += terms.count('\n')
    print('terms-only: %d chunks, %d term rows (%d glossary rows loaded), %d files rewritten, %.1fs'
          % (n, rows, len(gloss.rows), changed, time.time() - t0))


# ---------------------------------------------------------------------------------------------- byproducts
_ENC = re.compile(r'\{g\|Encyclopedia:([^}|]*)\}(.*?)\{/g\}', re.S)
_T_NARR = re.compile(r'\{/?n\}')
_T_KEEP = re.compile(r'\{(?:g|d)\|[^}]*\}|\{/(?:g|d)\}')
_T_BRACE = re.compile(r'\{[^{}]*\}')
_T_HTML = re.compile(r'</?[A-Za-z][^>]*>')
_NARR_BLOCK = re.compile(r'\{n\}.*?\{/n\}', re.S)
VAR = '\x01'


def plain(t: str) -> str:
    """Strip markup for term mining: {n} -> sentence break, {g|..}/{d|..} unwrapped, other {vars} -> VAR, HTML dropped."""
    t = _T_NARR.sub('\n', t)
    t = _T_KEEP.sub('', t)
    t = _T_BRACE.sub(' ' + VAR + ' ', t)
    return _T_HTML.sub('', t)


STOP = frozenset("""The A An My Your His Her Their Our Its This That These Those I You We He She They It What Who Why How When
Where Which But And Or If So Then Yes No Do Does Did Is Are Was Were Be Have Has Had Can Could Will Would Shall Should May
Might Must Not There Here Now Let Please Thank Well Oh Ah Perhaps Maybe Of To In On At By For With From As All Any Some Every
Each One Two Three Another Other Such Only Just Even Still Also Again Never Always Once After Before Because Since Until
While Though Although Unless Whether Both Either Neither""".split())
JOINERS = frozenset('of the de van von der di da du la le'.split())
_CAPW = r"[A-Z][a-z][A-Za-z'’\-]*"
_PHRASE = re.compile(r"(?<![A-Za-z0-9'’\-])" + _CAPW + r"(?:[ ]+(?:(?:" + '|'.join(sorted(JOINERS)) + r")[ ]+)?" + _CAPW + r")+")
_LOWER = re.compile(r"(?<![A-Za-z0-9'’\-])[a-z][a-z'’\-]*")
_POSS = re.compile(r"(?:['’]s|['’]|-)$")


def _sentence_start(p: str, pos: int) -> bool:
    j = pos - 1
    while j >= 0 and p[j] in ' \t':
        j -= 1
    return j < 0 or p[j] in '\n.!?…:"“”—(['


def snippet(p: str, s: int, e: int, width: int = 30) -> str:
    a, b = max(0, s - width), min(len(p), e + width)
    while 0 < a < s and not p[a - 1].isspace():
        a += 1
    while e < b < len(p) and not p[b].isspace():
        b -= 1
    return ' '.join(p[a:b].replace(VAR, ' ').split())


def mine_proper(plains, min_count=5):
    lower = set()
    for p in plains:
        lower.update(_LOWER.findall(p))
    cnt, ex = collections.Counter(), {}
    for p in plains:
        for m in _PHRASE.finditer(p):
            words = m.group(0).split()
            i, opens = 0, _sentence_start(p, m.start())
            while i < len(words):
                w = words[i]
                if w in STOP or w in JOINERS or (i == 0 and opens and w.lower() in lower):
                    i += 1                              # stop word, joiner, or a capital that only opens the sentence
                else:
                    break
            words = words[i:]
            if words:
                words[-1] = _POSS.sub('', words[-1])
            if len(words) < 2 or not words[-1]:
                continue
            phrase = ' '.join(words)
            cnt[phrase] += 1
            if phrase not in ex:
                ex[phrase] = snippet(p, m.start(), m.end())
    return [(ph, n, ex[ph]) for ph, n in cnt.items() if n >= min_count]


def is_name_file(rel: str) -> bool:
    """Display-name strings: <x>.DisplayName*, <x>_Name_String, .Name, m_Name ...; plus Encyclopedia page titles."""
    fn = rel.rsplit('/', 1)[-1][:-len('.json')]
    if fn.startswith(('Cue_', 'Answer_')):
        return False
    toks = set(t.lower() for t in re.split(r'[^A-Za-z]+', fn) if t)
    return 'displayname' in toks or 'name' in toks or ('title' in toks and rel.startswith(BP_PREFIX + 'Encyclopedia/'))


def count_phrases(plains, phrases):
    """Case-sensitive whole-word occurrences of token-tuple phrases."""
    first = collections.defaultdict(set)
    for tup in phrases:
        first[tup[0]].add(len(tup))
    wanted, cnt = set(phrases), collections.Counter()
    for p in plains:
        toks = TOKEN.findall(p)
        for i, tok in enumerate(toks):
            lens = first.get(tok)
            if lens:
                for n in lens:
                    tup = tuple(toks[i:i + n])
                    if tup in wanted:
                        cnt[tup] += 1
    return cnt


def write_candidates(recs, path):
    plains = [plain(r.text) for r in recs]
    rows = []
    # encyclopedia: display text of {g|Encyclopedia:KEY}display{/g}
    enc = {}
    for r in recs:
        for m in _ENC.finditer(r.text):
            disp = ' '.join(plain(m.group(2)).replace(VAR, '').split())
            if disp:
                e = enc.setdefault(disp.casefold(), [0, collections.Counter(), collections.Counter()])
                e[0] += 1
                e[1][disp] += 1
                e[2][m.group(1)] += 1
    for e in enc.values():
        surface = sorted(e[1].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        keys = sorted(e[2].items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        rows.append((surface, e[0], 'encyclopedia', '|'.join(k for k, _ in keys)))
    # name: display names of items / weapons / abilities / classes / units / backgrounds / places ...
    names = {}
    for r in recs:
        if is_name_file(r.rel):
            nm = plain(r.text)
            if VAR in nm:
                continue
            nm = ' '.join(nm.split()).strip('"\u201c\u201d')
            if nm and LETTER.search(nm) and len(nm.split()) <= 10:
                e = names.get(nm)
                if e is None:
                    names[nm] = [r.rel[len(BP_PREFIX):] if r.rel.startswith(BP_PREFIX) else r.rel, 1]
                else:
                    e[1] += 1
    tup = dict((nm, tuple(TOKEN.findall(nm))) for nm in names)
    cnt = count_phrases(plains, set(tup.values()))
    for nm, (example, ndef) in names.items():
        rows.append((nm, max(cnt.get(tup[nm], 0), ndef), 'name', example))
    # proper: capitalised multi-word phrases >= 5 times in wave-2 (dialogue) text
    for ph, n, example in mine_proper([p for r, p in zip(recs, plains) if r.group.startswith('w2-')]):
        rows.append((ph, n, 'proper', example))
    kind_rank = {'encyclopedia': 0, 'name': 1, 'proper': 2}
    rows.sort(key=lambda x: (-x[1], kind_rank[x[2]], x[0]))
    write_file(path, ''.join('%s\t%d\t%s\t%s\n' % (esc(t), n, k, esc(ex)) for t, n, k, ex in rows))
    return collections.Counter(k for _, _, k, _ in rows)


def pick_samples(texts):
    pool = [t for t in texts if '{n}' not in t and 20 <= len(t) <= 120]
    if len(pool) < 2:                                   # fall back to the spoken part of lines that mix narration
        for t in texts:
            s = _NARR_BLOCK.sub('', t).strip()
            if 20 <= len(s) <= 120:
                pool.append(s)
    pool = list(collections.OrderedDict.fromkeys(pool))
    for t in texts:                                     # still short of two: truncated lines (never above 120 chars)
        if len(pool) >= min(2, len(texts)):
            break
        s = t if len(t) <= 120 else t[:117] + '...'
        if s not in pool:
            pool.append(s)
    picks = [pool[len(pool) // 3]]
    if len(pool) > 1:
        picks.append(pool[(2 * len(pool)) // 3])
    return picks


def write_speakers(recs, path):
    by = collections.OrderedDict()
    for r in recs:
        if r.raw_spk:
            by.setdefault(r.raw_spk, []).append(r)
    rows = []
    for spk, rs in by.items():
        gen = collections.Counter(r.gender for r in rs if r.gender)
        gender = sorted(gen.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if gen else '?'
        grp = collections.Counter(r.group for r in rs)
        groups = ','.join(g for g, _ in sorted(grp.items(), key=lambda kv: (-kv[1], GROUP_RANK.get(kv[0], 99))))
        samples = [esc(s) for s in pick_samples([r.text for r in rs])]
        samples += [''] * (2 - len(samples))
        rows.append((spk, gender, len(rs), sum(r.words for r in rs), groups, samples[0], samples[1]))
    rows.sort(key=lambda x: (-x[2], x[0]))
    write_file(path, ''.join('%s\t%s\t%d\t%d\t%s\t%s\t%s\n' % row for row in rows))
    return len(rows)


# ---------------------------------------------------------------------------------------------- main
def read_keys_file(path):
    keys = []
    for ln in read_text(path).split('\n'):
        s = ln.strip()
        if s and not s.startswith('#'):
            keys.append(re.split(r'[\s,;]+', s, 1)[0].lower())
    return keys


def run_full(args, corpus, gloss, t0):
    chunk_root = os.path.join(args.work, 'chunks')
    by_group = collections.OrderedDict((g, []) for g in GROUP_IDS)
    for r in corpus.recs:
        by_group[r.group].append(r)
    chunks = []
    for g, rs in by_group.items():
        if rs:
            chunks.extend(make_chunks(rs, g))
    verify_chunks(chunks, corpus.recs)
    entries, expected, n_rows, changed = write_chunks(chunks, chunk_root, gloss)
    removed = remove_stale(chunk_root, GROUP_IDS, expected)
    mpath = os.path.join(args.work, 'manifest.json')
    old = read_manifest(mpath)
    write_manifest(mpath, source_build(args.engb, old), merge_entries(old, entries, set(GROUP_IDS)))
    kinds = collections.Counter()
    if not args.no_extras:
        kinds = write_candidates(corpus.recs, os.path.join(args.work, 'terms_candidates.tsv'))
        n_spk = write_speakers(corpus.recs, os.path.join(args.work, 'speakers.tsv'))
    # report
    stat = collections.OrderedDict((g, [0, 0, 0, 0, 0]) for g in GROUP_IDS)    # strings words chunks max-words dropped
    for r in corpus.recs:
        stat[r.group][0] += 1
        stat[r.group][1] += r.words
    for c in chunks:
        stat[c.group][2] += 1
        stat[c.group][3] = max(stat[c.group][3], c.words)
    print('%-14s %7s %9s %6s %7s %6s  %s' % ('group', 'strings', 'words', 'chunks', 'mean', 'max', 'dropped(letterless)'))
    for g, (s, w, n, mx, _) in stat.items():
        dl = corpus.dropped.get(('letterless', g), [0, 0])
        print('%-14s %7d %9d %6d %7d %6d  %d / %d words' % (g, s, w, n, w // n if n else 0, mx, dl[0], dl[1]))
    tot_s, tot_w = sum(v[0] for v in stat.values()), sum(v[1] for v in stat.values())
    print('total          %7d %9d %6d' % (tot_s, tot_w, len(chunks)))
    why = collections.Counter()
    for (reason, _), (n, _) in corpus.dropped.items():
        why[reason] += n
    print('not chunked: %s | files %d, unique keys %d, duplicate-GUID files %d, unreadable %d, speaker fixes %d'
          % (', '.join('%s %d' % kv for kv in sorted(why.items())), corpus.n_files, corpus.n_unique, corpus.n_dup,
             corpus.n_bad, corpus.n_speaker_fixed))
    print('terms rows %d (%d glossary rows) | files written %d, stale removed %d | candidates %s | speakers %s | %.1fs'
          % (n_rows, len(gloss.rows), changed, removed, dict(kinds) or '-', n_spk if not args.no_extras else '-', time.time() - t0))


def run_prefix(args, corpus, gloss, t0):
    check(re.match(r'^[A-Za-z0-9_.\-]+$', args.prefix) and args.prefix not in GROUP_RANK,
          '--prefix must be [A-Za-z0-9_.-]+ and not a group id (%s)' % ', '.join(GROUP_IDS))
    wanted = read_keys_file(args.keys)
    uniq = list(collections.OrderedDict.fromkeys(wanted))
    why = collections.Counter(corpus.reason.get(k, 'unknown-GUID') for k in uniq)
    keyset = set(k for k in uniq if corpus.reason.get(k) == '')
    selected = [r for r in corpus.recs if r.key.lower() in keyset]
    check(len(selected) == len(keyset), 'internal: selected %d of %d eligible keys' % (len(selected), len(keyset)))
    chunk_root = os.path.join(args.work, 'chunks')
    chunks = make_chunks(selected, args.prefix) if selected else []
    verify_chunks(chunks, selected)
    entries, expected, n_rows, changed = write_chunks(chunks, chunk_root, gloss)
    removed = remove_stale(chunk_root, [args.prefix], expected)
    mpath = os.path.join(args.work, 'manifest.json')
    old = read_manifest(mpath)
    write_manifest(mpath, source_build(args.engb, old), merge_entries(old, entries, {args.prefix}))
    print('%s: %d GUIDs listed -> %d chunked in %d chunks (%d words); not chunked: %s | terms rows %d | files written %d, '
          'stale removed %d | %.1fs'
          % (args.prefix, len(uniq), len(selected), len(chunks), sum(c.words for c in chunks),
             ', '.join('%s %d' % kv for kv in sorted(why.items()) if kv[0] != '') or 'none', n_rows, changed, removed,
             time.time() - t0))


def main():
    ap = argparse.ArgumentParser(description='Build translation chunks from Strings + enGB.json (RTKO-9).')
    ap.add_argument('--terms-only', action='store_true', help='only regenerate <chunk>.terms.tsv (optionally limited by --prefix)')
    ap.add_argument('--keys', help='file with GUIDs (one per line) -> chunk only those, needs --prefix')
    ap.add_argument('--prefix', help='chunk family name for --keys: work/chunks/<NAME>/<NAME>-NNN.*')
    ap.add_argument('--strings', default=os.path.join(REPO, 'src', 'template', 'Strings'))
    ap.add_argument('--engb', default=os.path.join(REPO, 'src', 'game', 'WH40KRT_Data', 'StreamingAssets', 'Localization', 'enGB.json'))
    ap.add_argument('--glossary', default=os.path.join(REPO, 'glossary'))
    ap.add_argument('--work', default=os.path.join(REPO, 'work'))
    ap.add_argument('--no-extras', action='store_true', help='full run: skip terms_candidates.tsv / speakers.tsv')
    args = ap.parse_args()
    if args.terms_only:
        check(not args.keys, '--terms-only cannot be combined with --keys')
        return run_terms_only(args)
    check(bool(args.keys) == bool(args.prefix), '--keys and --prefix go together')
    t0 = time.time()
    corpus = build_corpus(args.strings, args.engb)
    gloss = Glossary(args.glossary)
    if args.keys:
        run_prefix(args, corpus, gloss, t0)
    else:
        run_full(args, corpus, gloss, t0)


if __name__ == '__main__':
    main()
