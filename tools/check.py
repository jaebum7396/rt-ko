#!/usr/bin/env python3
"""check.py - verify Astra translation output chunk by chunk (RTKO-10).

Python 3.8, stdlib only, no LLM tokens.  Rules follow docs/PIPELINE.md ("검사") and docs/FORMAT.md section 4.

  check.py [CHUNK_ID ...] [--group G] [--all] [--root DIR] [-v]     check
  check.py ... --retry [--with-warnings code,code]                  check, then write retry inputs
  check.py ... --merge                                              apply retry outputs, then re-check
  exit code: 0 all pass, 1 some chunk has errors, 2 usage / missing file / unreadable file

Files (relative to --root, default = the repo root; CHUNK_ID = <group>-<NNN>):
  work/chunks/<group>/<chunk>.src.tsv      input   n TAB speaker TAB english, '# scene:' headers
  work/chunks/<group>/<chunk>.terms.tsv    input   english TAB korean[/variant] TAB note
  work/out/<group>/<chunk>.tsv             checked n TAB korean
  work/check/<chunk>.json                  result  {"errors": [{"n","code","detail"}], "warnings": [...]}
  work/check/summary.tsv                   chunk lines errors warnings pass(1|0), one row per chunk, rows refreshed in place
  work/manifest.json                       status: pass -> checked, errors -> done (only a checked chunk is moved back);
                                           a running chunk is left alone; only the status text is edited
  work/retry/<chunk>-r<N>.src.tsv          --retry  failing lines only (original n, scene headers kept)
  work/retry/<chunk>-r<N>.terms.tsv        --retry  copy of <chunk>.terms.tsv
  work/retry/<chunk>-r<N>.out.tsv          the retranslation (n TAB korean), written by the runner, read by --merge
  work/retry/<chunk>-r<N>.merged           marker written by --merge once the answer is applied (delete it to merge again)
  Round N is reused until it is merged, then N+1.  --retry refuses a chunk that has an answer not merged yet.
  --merge rewrites work/out/<group>/<chunk>.tsv in source order: an answer line replaces the line(s) of its n (an empty
  answer, an answer for an n outside the retry input and unparseable answer lines are ignored); lines whose n is not in
  the source and unparseable lines (the extra / bad_line errors, which no retry can fix) are dropped; duplicates stay
  until answered.  With no answer it still drops those stray lines.

Errors (a chunk passes at 0 errors; n is null for bad_line):
  missing    n in the source has no output line
  duplicate  n appears more than once (content checks run on the first copy)
  extra      n not in the source
  empty      empty / blank translation
  markup     {...} mismatch.  Every {...} token is compared as a multiset (this covers the tags of {g|X}..{/g},
             {d|X}..{/d} and {n}..{/n}; the text between them is free).  {mf|a|b}, {rt_mf|a|b} and {nc|a|b} (the same
             kind of gender switch, 4 lines in the game) compare kind and part count only.  Also: stray { or },
             paired tags no longer nested, a pair that became empty (only if the source is not like that itself)
  html       <...> tags differ as a multiset, or stray < / > differ
  newline    number of \\n (line break) escapes differs.  Escapes are read in ONE left-to-right pass (PIPELINE.md):
             \\\\ is a backslash, \\n a line break, so a literal backslash + n (TSV \\\\n) counts 0
  escape     backslash escape other than \\\\ and \\n
  columns    more than 2 TAB columns (e.g. speaker copied from src.tsv)
  bad_line   output line without TAB / numeric n (scene header, comment, wrapped line)
Warnings (never fail a chunk; --with-warnings sends them to --retry):
  no_hangul  no Hangul although the source has letters
  english    3+ consecutive English words outside markup (ALL-CAPS tokens - single capitals except A and I - and
             words of terms whose Korean is Latin are skipped)
  glossary   a term's English is in the source but none of its Korean variants is in the output (whitespace and case
             ignored; a term inside a longer matched term is not required)
  length     Korean chars / English chars (markup removed, source >= RATIO_MIN_CHARS) outside RATIO_MIN..RATIO_MAX
  bracket    source starts with a [prefix] but the output has none, or its prefix has no Hangul (STYLE.md section 5)
"""
import argparse
import collections
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(HERE)

RATIO_MIN, RATIO_MAX = 0.25, 1.6
RATIO_MIN_CHARS = 15          # shorter source texts (one-word item names ...) vary too much for a ratio
RESIDUE_RUN = 3

ERROR_CODES = ('bad_line', 'missing', 'duplicate', 'extra', 'columns', 'empty', 'markup', 'html', 'newline', 'escape')
WARN_CODES = ('no_hangul', 'english', 'glossary', 'length', 'bracket')
RETRYABLE = frozenset(ERROR_CODES) - frozenset(['bad_line', 'extra'])   # codes tied to a source n
CODE_ORDER = dict((c, i) for i, c in enumerate(ERROR_CODES + WARN_CODES))
PART_KINDS = frozenset(['mf', 'rt_mf', 'nc'])     # {kind|a|b}: the parts are translated text

BOM = chr(0xFEFF)
APOS = "'" + chr(0x2019)
HANGUL_RANGES = ((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7A3))    # Jamo, compatibility Jamo, syllables

TOKEN = re.compile(r'\{[^{}]*\}')
HTML = re.compile(r'<[^<>]*>')
PAIR = re.compile(r'\{(?:g|d)\|[^{}]*\}|\{n\}|\{/(?:g|d|n)\}')
ESC = re.compile(r'\\(.?)')
MARK = re.compile(r'\{(?:mf|rt_mf|nc)\|([^{}|]*)\|([^{}|]*)\}|\{[^{}]*\}|<[^<>]*>')
WORD = re.compile(r"[A-Za-z]+(?:[%s\-][A-Za-z]+)*" % APOS)
W = re.compile(r'\w+')
HANGUL = re.compile('[%s]' % ''.join('%s-%s' % (chr(a), chr(b)) for a, b in HANGUL_RANGES))
LETTER = re.compile(r'[^\W\d_]')
PREFIX = re.compile(r'\s*\[[^\]]*\]')


class ChunkError(Exception):
    """A chunk that cannot be checked at all (missing or unreadable file)."""


# ---------------------------------------------------------------- io

def read_text(path):
    with open(path, 'rb') as f:
        data = f.read()
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError as e:
        raise ChunkError('%s: not valid UTF-8 (%s)' % (path, e))


def split_lines(text):
    lines = text.split('\n')                       # only LF: Korean/English text may hold other separators
    if lines and lines[-1] == '':
        lines.pop()
    return [x[:-1] if x.endswith('\r') else x for x in lines]


def atomic_write(path, text):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    tmp = '%s.tmp%d' % (path, os.getpid())
    with open(tmp, 'wb') as f:
        f.write(text.encode('utf-8'))
    os.replace(tmp, path)


def clip(s, n=200):
    return s if len(s) <= n else s[:n - 3] + '...'


class Src(object):
    __slots__ = ('items', 'order', 'by_n')

    def __init__(self):
        self.items = []      # ('H', raw) | ('L', n, raw)
        self.order = []      # n in file order
        self.by_n = {}       # n -> english text (still escaped)


def load_src(path):
    src = Src()
    if not os.path.exists(path):
        raise ChunkError('no source file %s' % path)
    for i, line in enumerate(split_lines(read_text(path)), 1):
        if not line.strip():
            continue
        if line.startswith('#'):
            src.items.append(('H', line))
            continue
        p = line.split('\t', 2)
        if len(p) < 3 or not re.match(r'^[0-9]+$', p[0]):
            raise ChunkError('%s line %d: not "n<TAB>speaker<TAB>text"' % (path, i))
        n = int(p[0])
        if n in src.by_n:
            raise ChunkError('%s line %d: n %d repeated in the source' % (path, i, n))
        src.by_n[n] = p[2]
        src.order.append(n)
        src.items.append(('L', n, line))
    return src


def load_out(path):
    """-> (entries [(n, text, lineno, columns)], junk [(lineno, why, raw)])"""
    entries, junk = [], []
    if not os.path.exists(path):
        return entries, junk
    for i, line in enumerate(split_lines(read_text(path)), 1):
        if not line.strip():
            continue
        t = line.find('\t')
        if t < 0:
            junk.append((i, 'no TAB', line))
            continue
        head = line[:t].strip()
        if not re.match(r'^[0-9]+$', head):
            junk.append((i, 'n is not a number', line))
            continue
        entries.append((int(head), line[t + 1:], i, 2 + line.count('\t', t + 1)))
    return entries, junk


class Terms(object):
    def __init__(self):
        self.index = {}          # first word -> [(english_low, english, korean_display, [normalized variants])]
        self.latin_ok = set()    # lowercase words that may stay Latin (terms whose Korean is Latin)

    @staticmethod
    def load(path):
        t = Terms()
        if not os.path.exists(path):
            return t
        merged = collections.OrderedDict()
        for line in split_lines(read_text(path)):
            if not line.strip() or line.startswith('#'):
                continue
            p = line.split('\t')
            if len(p) < 2:
                continue
            eng, ko = p[0].strip(), p[1].strip()
            if not eng or not ko or (eng.lower() == 'english' and ko.lower() == 'korean'):
                continue
            low = ' '.join(eng.lower().split())
            ent = merged.get(low)
            if ent is None:
                ent = merged[low] = [eng, []]
            ent[1].extend(v.strip() for v in ko.split('/') if v.strip())
        for low, (eng, variants) in merged.items():
            m = W.search(low)
            if not m or not variants:
                continue
            norm = [''.join(v.lower().split()) for v in variants]
            t.index.setdefault(m.group(), []).append((low, eng, '/'.join(variants), norm))
            for v in variants:
                if LETTER.search(v) and not HANGUL.search(v):
                    t.latin_ok.update(w.lower() for w in WORD.findall(eng))
                    t.latin_ok.update(w.lower() for w in WORD.findall(v))
        return t

    def misses(self, src_low, out_norm):
        """Terms whose English is in src_low (collapsed lowercase) but no Korean variant is in out_norm."""
        if not self.index:
            return []
        cands = []
        for w in set(W.findall(src_low)):
            lst = self.index.get(w)
            if lst:
                cands.extend(lst)
        if not cands:
            return []
        n = len(src_low)
        found = []
        for t in cands:
            el, ln = t[0], len(t[0])
            pos = src_low.find(el)
            while pos >= 0:
                end = pos + ln
                if (pos == 0 or not (src_low[pos - 1].isalnum() or src_low[pos - 1] == '_')) and \
                   (end == n or not (src_low[end].isalnum() or src_low[end] == '_')):
                    found.append((pos, end, t))
                pos = src_low.find(el, pos + 1)
        found.sort(key=lambda f: f[0] - f[1])          # longest first
        kept, need = [], []
        for pos, end, t in found:
            if any(k[0] <= pos and end <= k[1] and (k[1] - k[0]) > (end - pos) for k in kept):
                continue                               # inside a longer matched term
            kept.append((pos, end))
            if t not in need:
                need.append(t)
        return [(t[1], t[2]) for t in need if not any(v in out_norm for v in t[3])]


# ---------------------------------------------------------------- text analysis

def sig(tok):
    i = tok.find('|')
    if i > 0 and tok[1:i] in PART_KINDS:
        return '{%s|%s}' % (tok[1:i], '|'.join(['*'] * tok.count('|')))
    return tok


def scan_pairs(text):
    """-> (properly nested, number of pairs with no text inside) for {g|..}{/g}, {d|..}{/d}, {n}{/n}."""
    stack, empty = [], 0
    for m in PAIR.finditer(text):
        s = m.group()
        if s.startswith('{/'):
            if not stack or stack[-1][0] != s[2:-1]:
                return False, 0
            _, start = stack.pop()
            if not text[start:m.start()].strip():
                empty += 1
        else:
            stack.append(('n' if s == '{n}' else s[1], m.end()))
    return (not stack), empty


class Info(object):
    __slots__ = ('toks', 'ex', 'html', 'nl', 'bad_esc', 'brace', 'angle', 'nested', 'empty_pairs')

    def __init__(self, text):
        self.nl, self.bad_esc = 0, ()
        if '\\' in text:
            bad = []
            for m in ESC.finditer(text):
                g = m.group(1)
                if g == 'n':
                    self.nl += 1
                elif g != '\\':
                    bad.append('\\' + g)
            self.bad_esc = tuple(bad)
        self.toks, self.ex, self.brace = collections.Counter(), {}, (0, 0)
        self.nested, self.empty_pairs = True, 0
        if '{' in text or '}' in text:
            raw = TOKEN.findall(text)
            for t in raw:
                k = sig(t)
                self.toks[k] += 1
                self.ex.setdefault(k, t)
            self.brace = (text.count('{') - len(raw), text.count('}') - len(raw))
            if raw:
                self.nested, self.empty_pairs = scan_pairs(text)
        self.html, self.angle = collections.Counter(), (0, 0)
        if '<' in text or '>' in text:
            tags = HTML.findall(text)
            self.html.update(tags)
            self.angle = (text.count('<') - len(tags), text.count('>') - len(tags))


def _show(tok, c):
    return tok if c == 1 else '%s x%d' % (tok, c)


def diff_detail(sc, oc, sex, oex):
    parts = []
    miss, extra = sc - oc, oc - sc
    if miss:
        parts.append('missing ' + ', '.join(_show(sex[k] if sex else k, c) for k, c in sorted(miss.items())))
    if extra:
        parts.append('unexpected ' + ', '.join(_show(oex[k] if oex else k, c) for k, c in sorted(extra.items())))
    return '; '.join(parts)


def content_errors(s, o):
    out = []
    if s.nl != o.nl:
        out.append(('newline', 'source has %d line break(s), output has %d' % (s.nl, o.nl)))
    if o.bad_esc and o.bad_esc != s.bad_esc:
        out.append(('escape', 'invalid escape ' + ' '.join(sorted(set(o.bad_esc)))))
    m = []
    if s.toks != o.toks:
        m.append(diff_detail(s.toks, o.toks, s.ex, o.ex))
    elif s.nested and not o.nested:
        m.append('paired tags {g}/{d}/{n} are not properly nested')
    elif o.empty_pairs > s.empty_pairs:
        m.append('a paired tag has no text inside')
    if s.brace != o.brace:
        m.append('stray { or } (source %s, output %s)' % (s.brace, o.brace))
    if m:
        out.append(('markup', clip('; '.join(m))))
    h = []
    if s.html != o.html:
        h.append(diff_detail(s.html, o.html, None, None))
    if s.angle != o.angle:
        h.append('stray < or > (source %s, output %s)' % (s.angle, o.angle))
    if h:
        out.append(('html', clip('; '.join(h))))
    return out


def _unesc(m):
    g = m.group(1)
    return ' ' if g == 'n' else g


def _expand(m):
    a = m.group(1)
    return ' ' if a is None else ' %s | %s ' % (a, m.group(2))


def plain(text):
    """Text without markup: tokens and tags become a blank, {mf|a|b} becomes 'a | b', \\n a blank."""
    if '\\' in text:
        text = ESC.sub(_unesc, text)
    if '{' in text or '<' in text:
        text = MARK.sub(_expand, text)
    return text


def residue(text, allowed):
    """Runs of >= RESIDUE_RUN consecutive English words in plain text."""
    runs, run, prev = [], [], 0
    for m in WORD.finditer(text):
        w = m.group()
        if run and text[prev:m.start()].strip():
            if len(run) >= RESIDUE_RUN:
                runs.append(' '.join(run))
            run = []
        prev = m.end()
        if w.lower() in allowed or (w.isupper() and (len(w) >= 2 or w not in ('A', 'I'))):
            if len(run) >= RESIDUE_RUN:
                runs.append(' '.join(run))
            run = []
        else:
            run.append(w)
    if len(run) >= RESIDUE_RUN:
        runs.append(' '.join(run))
    return runs


def soft_checks(s_text, o_text, terms):
    out = []
    sp, op = plain(s_text), plain(o_text)
    if LETTER.search(sp) and not HANGUL.search(op):
        out.append(('no_hangul', 'no Hangul in the output'))
    for run in residue(op, terms.latin_ok)[:3]:
        out.append(('english', clip('English left: ' + run, 100)))
    s_col, o_col = ' '.join(sp.split()), ' '.join(op.split())
    if terms.index:
        for eng, ko in terms.misses(s_col.lower(), ''.join(o_col.lower().split())):
            out.append(('glossary', clip('%s -> %s not found' % (eng, ko), 120)))
    if len(s_col) >= RATIO_MIN_CHARS:
        r = len(o_col) / float(len(s_col))
        if r < RATIO_MIN or r > RATIO_MAX:
            out.append(('length', 'ratio %.2f (ko %d / en %d chars, allowed %.2f-%.2f)'
                        % (r, len(o_col), len(s_col), RATIO_MIN, RATIO_MAX)))
    pm = PREFIX.match(sp)
    if pm:
        om = PREFIX.match(op)
        if not om:
            out.append(('bracket', 'prefix %s not kept' % pm.group().strip()))
        elif LETTER.search(pm.group()) and not HANGUL.search(om.group()):
            out.append(('bracket', 'prefix %s not translated' % om.group().strip()))
    return out


# ---------------------------------------------------------------- chunk check

class Result(object):
    __slots__ = ('chunk', 'group', 'lines', 'errors', 'warnings')

    def __init__(self, chunk, group, lines, errors, warnings):
        self.chunk, self.group, self.lines = chunk, group, lines
        self.errors, self.warnings = errors, warnings

    @property
    def ok(self):
        return not self.errors


def _sort_key(e):
    return (e[0] if e[0] is not None else 0, CODE_ORDER.get(e[1], 99))


def check_chunk(root, chunk, group):
    src = load_src(os.path.join(root, 'work', 'chunks', group, chunk + '.src.tsv'))
    entries, junk = load_out(os.path.join(root, 'work', 'out', group, chunk + '.tsv'))
    terms = Terms.load(os.path.join(root, 'work', 'chunks', group, chunk + '.terms.tsv'))
    errors, warnings = [], []
    for lineno, why, raw in junk:
        errors.append((None, 'bad_line', clip('line %d: %s: %s' % (lineno, why, raw[:60]), 120)))
    seen = collections.OrderedDict()
    for e in entries:
        seen.setdefault(e[0], []).append(e)
    for n, ents in seen.items():
        if n not in src.by_n:
            errors.append((n, 'extra', 'n not in the source (line %d)' % ents[0][2]))
    for n in src.order:
        ents = seen.get(n)
        if not ents:
            errors.append((n, 'missing', 'no output line'))
            continue
        if len(ents) > 1:
            errors.append((n, 'duplicate', 'appears %d times (lines %s)' % (len(ents), ', '.join(str(e[2]) for e in ents))))
        _, text, _, cols = ents[0]
        if cols > 2:
            errors.append((n, 'columns', '%d TAB columns, expected 2' % cols))
        if not text.strip():
            errors.append((n, 'empty', 'empty translation'))
            continue
        s_text = src.by_n[n]
        for code, detail in content_errors(Info(s_text), Info(text)):
            errors.append((n, code, detail))
        for code, detail in soft_checks(s_text, text, terms):
            warnings.append((n, code, detail))
    errors.sort(key=_sort_key)
    warnings.sort(key=_sort_key)
    return Result(chunk, group, len(src.order), errors, warnings)


def write_result(root, r):
    def block(items):
        if not items:
            return '[]'
        return '[\n' + ',\n'.join(' ' + json.dumps({'n': n, 'code': c, 'detail': d}, ensure_ascii=False)
                                  for n, c, d in items) + '\n]'
    atomic_write(os.path.join(root, 'work', 'check', r.chunk + '.json'),
                 '{"errors": %s,\n"warnings": %s}\n' % (block(r.errors), block(r.warnings)))


def update_summary(root, results):
    path = os.path.join(root, 'work', 'check', 'summary.tsv')
    rows = {}
    if os.path.exists(path):
        for line in split_lines(read_text(path))[1:]:
            p = line.split('\t')
            if len(p) == 5:
                rows[p[0]] = p
    for r in results:
        rows[r.chunk] = [r.chunk, str(r.lines), str(len(r.errors)), str(len(r.warnings)), '1' if r.ok else '0']
    atomic_write(path, 'chunk\tlines\terrors\twarnings\tpass\n'
                 + ''.join('\t'.join(rows[k]) + '\n' for k in sorted(rows)))


def update_manifest(root, results):
    """Set status checked / done; edits only the status text so the file keeps whatever layout its writer uses."""
    path = os.path.join(root, 'work', 'manifest.json')
    if not os.path.exists(path):
        return {}
    with open(path, 'rb') as f:
        text = f.read().decode('utf-8')
    data = json.loads(text.lstrip(BOM))
    cur = dict((c.get('id'), c.get('status')) for c in data.get('chunks', []))
    changes = {}
    for r in results:
        old = cur.get(r.chunk)
        if old is None or old == 'running':
            continue
        new = 'checked' if r.ok else ('done' if old == 'checked' else old)
        if new != old:
            changes[r.chunk] = new
    if not changes:
        return changes
    patched = text
    for chunk, new in changes.items():
        pat = re.compile(r'\{[^{}]*"id"\s*:\s*"%s"[^{}]*\}' % re.escape(chunk))
        m = pat.search(patched)
        obj = m and re.sub(r'("status"\s*:\s*)"[^"]*"', lambda x: x.group(1) + '"%s"' % new, m.group(), count=1)
        if not m or obj == m.group():
            patched = None
            break
        patched = patched[:m.start()] + obj + patched[m.end():]
    ok = False
    if patched is not None:
        try:
            chk = dict((c.get('id'), c.get('status')) for c in json.loads(patched.lstrip(BOM)).get('chunks', []))
            ok = all(chk.get(c) == s for c, s in changes.items())
        except ValueError:
            ok = False
    if not ok:                                         # unusual layout: rewrite the whole file
        for c in data['chunks']:
            if c.get('id') in changes:
                c['status'] = changes[c['id']]
        patched = json.dumps(data, ensure_ascii=False, indent=1) + '\n'
    atomic_write(path, patched)
    return changes


# ---------------------------------------------------------------- retry / merge

def retry_dir(root):
    return os.path.join(root, 'work', 'retry')


def retry_rounds(root, chunk):
    d = retry_dir(root)
    pat = re.compile(r'^%s-r(\d+)\.src\.tsv$' % re.escape(chunk))
    rounds = []
    if os.path.isdir(d):
        for f in os.listdir(d):
            m = pat.match(f)
            if m:
                rounds.append(int(m.group(1)))
    return sorted(rounds)


def write_retry(root, r, want_warnings):
    """-> (message, written)"""
    ns = set(n for n, c, _ in r.errors if c in RETRYABLE)
    ns.update(n for n, c, _ in r.warnings if c in want_warnings)
    skipped = sum(1 for n, c, _ in r.errors if c not in RETRYABLE)
    if not ns:
        return ('nothing to retry' + (' (%d error(s) not tied to a source line: --merge drops those lines)' % skipped
                                      if skipped else '')), False
    d = retry_dir(root)
    pend = pending_answers(root, r.chunk)
    if pend:
        return 'r%d answer not merged yet (run --merge first)' % pend[0][0], False
    rounds = retry_rounds(root, r.chunk)
    n_round = rounds[-1] if rounds else 1
    if os.path.exists(merged_marker(root, r.chunk, n_round)):
        n_round += 1
    base = os.path.join(d, '%s-r%d' % (r.chunk, n_round))
    src = load_src(os.path.join(root, 'work', 'chunks', r.group, r.chunk + '.src.tsv'))
    lines, header, shown = [], None, None
    for idx, it in enumerate(src.items):
        if it[0] == 'H':
            header = idx
        elif it[1] in ns:
            if header is not None and header != shown:
                lines.append(src.items[header][1])
                shown = header
            lines.append(it[2])
    atomic_write(base + '.src.tsv', '\n'.join(lines) + '\n')
    terms = os.path.join(root, 'work', 'chunks', r.group, r.chunk + '.terms.tsv')
    if os.path.exists(terms):
        shutil.copyfile(terms, base + '.terms.tsv')
    return 'r%d: %d line(s) -> %s' % (n_round, len(ns & set(src.by_n)), os.path.relpath(base + '.src.tsv', root)), True


def merged_marker(root, chunk, n_round):
    return os.path.join(retry_dir(root), '%s-r%d.merged' % (chunk, n_round))


def pending_answers(root, chunk):
    """[(round, path)] of retry answers that exist and are not merged yet, oldest round first."""
    found = []
    for n in retry_rounds(root, chunk):
        a = os.path.join(retry_dir(root), '%s-r%d.out.tsv' % (chunk, n))
        if os.path.exists(a) and not os.path.exists(merged_marker(root, chunk, n)):
            found.append((n, a))
    return found


def merge_chunk(root, chunk, group):
    """Apply pending retry answers and drop lines that cannot belong to the chunk (extra n, unparseable lines).
    -> message, or None when there is nothing to do."""
    pend = pending_answers(root, chunk)
    src = load_src(os.path.join(root, 'work', 'chunks', group, chunk + '.src.tsv'))
    out_path = os.path.join(root, 'work', 'out', group, chunk + '.tsv')
    entries, junk = load_out(out_path)
    stray = len(junk) + sum(1 for e in entries if e[0] not in src.by_n)
    if not pend and not stray:
        return None
    copies = {}
    for e in entries:
        copies.setdefault(e[0], []).append(e[1])
    repl, ignored = {}, 0
    for n_round, ans in pend:
        rsrc = load_src(os.path.join(retry_dir(root), '%s-r%d.src.tsv' % (chunk, n_round)))
        got, bad = load_out(ans)
        ignored += len(bad)
        for n, text, _, _ in got:
            if n in rsrc.by_n and n in src.by_n and text.strip():
                repl[n] = text
            else:
                ignored += 1
    lines = []
    for n in src.order:
        if n in repl:
            lines.append('%d\t%s' % (n, repl[n]))
        else:
            lines.extend('%d\t%s' % (n, t) for t in copies.get(n, ()))      # duplicates stay until answered
    atomic_write(out_path, ''.join(x + '\n' for x in lines))
    msg = 'merge %s: replaced %d line(s), dropped %d extra/unparseable line(s), ignored %d answer line(s)' % (
        '+'.join('r%d' % n for n, _ in pend) or '(no answer)', len(repl), stray, ignored)
    for n_round, _ in pend:
        atomic_write(merged_marker(root, chunk, n_round), msg + '\n')
    return msg


# ---------------------------------------------------------------- cli

def group_of_chunk(chunk):
    m = re.match(r'^(.+)-\d+$', chunk)
    return m.group(1) if m else None


def select_chunks(root, args, say):
    sel, seen, hard = [], set(), 0

    def add(chunk, group):
        if chunk not in seen:
            seen.add(chunk)
            sel.append((chunk, group))
    for c in args.chunks:
        g = group_of_chunk(c)
        if g is None:
            say('error: %s is not <group>-<NNN>' % c)
            hard += 1
        else:
            add(c, g)
    out_root = os.path.join(root, 'work', 'out')
    groups = list(args.group)
    if args.all:
        if os.path.isdir(out_root):
            groups.extend(sorted(d for d in os.listdir(out_root) if os.path.isdir(os.path.join(out_root, d))))
    for g in groups:
        d = os.path.join(out_root, g)
        if not os.path.isdir(d):
            say('error: no output folder %s' % os.path.relpath(d, root))
            hard += 1
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith('.tsv') and not f.startswith('.'):
                add(f[:-4], g)
    return sel, hard


def build_parser():
    ap = argparse.ArgumentParser(prog='check.py', description='Check Astra translation output (RTKO-10). See the module docstring.')
    ap.add_argument('chunks', nargs='*', metavar='CHUNK_ID')
    ap.add_argument('--group', action='append', default=[], metavar='G', help='every chunk with an output in this group (repeatable)')
    ap.add_argument('--all', action='store_true', help='every chunk with an output file')
    ap.add_argument('--root', default=DEFAULT_ROOT, metavar='DIR', help='folder that holds work/ (default: repo root)')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--retry', action='store_true', help='write work/retry/<chunk>-r<N>.src.tsv for failing lines')
    mode.add_argument('--merge', action='store_true', help='apply work/retry/<chunk>-r<N>.out.tsv, then re-check')
    ap.add_argument('--with-warnings', default='', metavar='CODES', help='with --retry: also retry these warning codes (%s)' % ','.join(WARN_CODES))
    ap.add_argument('-v', '--verbose', action='store_true', help='list every error and warning')
    return ap


def _tail(r):
    codes = collections.Counter(c for _, c, _ in r.errors)
    wcodes = collections.Counter(c for _, c, _ in r.warnings)
    parts = [', '.join('%s %d' % kv for kv in sorted(cs.items(), key=lambda kv: CODE_ORDER[kv[0]]))
             for cs in (codes, wcodes) if cs]
    return '  [%s]' % ' | '.join(parts) if parts else ''


def _print_capped(lines, limit, what):
    for x in lines[:limit]:
        print(x)
    if len(lines) > limit:
        print('... %d more %s (-v for all, work/check/summary.tsv for the list)' % (len(lines) - limit, what))


def main(argv=None):
    t0 = time.time()
    try:
        sys.stdout.reconfigure(errors='replace')
    except Exception:
        pass
    args = build_parser().parse_intermixed_args(argv)
    root = os.path.abspath(args.root)
    want = [c for c in args.with_warnings.split(',') if c]
    if [c for c in want if c not in WARN_CODES] or (want and not args.retry):
        sys.stderr.write('error: --with-warnings takes %s and needs --retry\n' % '|'.join(WARN_CODES))
        return 2
    if not (args.chunks or args.group or args.all):
        sys.stderr.write('error: give CHUNK_ID, --group or --all\n')
        return 2
    sel, hard = select_chunks(root, args, lambda m: sys.stderr.write(m + '\n'))
    if not sel and not hard:
        sys.stderr.write('nothing to check: no output files under %s\n' % os.path.join(root, 'work', 'out'))
        return 2 if not os.path.isdir(os.path.join(root, 'work', 'out')) else 0
    results, notes, skipped = [], [], 0
    for chunk, group in sel:
        try:
            if args.merge:
                msg = merge_chunk(root, chunk, group)
                if msg is None:
                    skipped += 1
                    if len(sel) <= 30:
                        print('skip %s: no retry answer to merge, no stray lines' % chunk)
                    continue
                notes.append('%s: %s' % (chunk, msg))
            elif not os.path.exists(os.path.join(root, 'work', 'out', group, chunk + '.tsv')):
                print('skip %s: no output file' % chunk)
                hard += 1
                continue
            r = check_chunk(root, chunk, group)
            write_result(root, r)
            results.append(r)
            if args.retry:
                msg, written = write_retry(root, r, want)
                if written or r.errors:
                    notes.append('retry %s: %s' % (chunk, msg))
        except ChunkError as e:
            sys.stderr.write('error %s: %s\n' % (chunk, e))
            hard += 1
    changed = {}
    if results:
        try:
            update_summary(root, results)
            changed = update_manifest(root, results)
        except (OSError, ValueError, ChunkError) as e:
            sys.stderr.write('error: summary / manifest not updated: %s\n' % e)
            hard += 1
    rows = []
    for r in results:
        if len(results) > 30 and r.ok and not args.verbose:
            continue
        rows.append('%s %s  lines %d  errors %d  warnings %d%s' % (
            'PASS' if r.ok else 'FAIL', r.chunk, r.lines, len(r.errors), len(r.warnings), _tail(r)))
        if args.verbose:
            rows.extend('  E n=%s %s: %s' % e for e in r.errors)
            rows.extend('  W n=%s %s: %s' % e for e in r.warnings)
    limit = len(rows) + len(notes) if args.verbose else 25
    _print_capped(notes, limit, 'merge/retry message(s)')
    _print_capped(rows, limit, 'chunk line(s)')
    npass = sum(1 for r in results if r.ok)
    if results or skipped:
        print('%d chunk(s): %d pass, %d fail, %d error(s), %d warning(s)%s; manifest %d changed; %.2fs' % (
            len(results), npass, len(results) - npass, sum(len(r.errors) for r in results),
            sum(len(r.warnings) for r in results), ', %d skipped' % skipped if skipped else '', len(changed),
            time.time() - t0))
    if hard:
        return 2
    return 0 if npass == len(results) else 1


if __name__ == '__main__':
    try:
        import signal
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except Exception:
        pass
    sys.exit(main())
