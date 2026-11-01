#!/usr/bin/env python3
"""run_astra.py - translate chunks with Astra: one `codex exec` (gpt-6-astra) process per chunk (RTKO-12).

    python3 tools/run_astra.py --status new --jobs 6          # every chunk still `new`
    python3 tools/run_astra.py w2-act01-004 w2-act01-005      # named chunks
    python3 tools/run_astra.py --group w2-act01 --max 3 --dry-run

Contract: docs/PIPELINE.md (chunk files, manifest, usage.tsv, out/).  Python 3.8, stdlib only.

Per chunk: <root>/run/<chunk>/{src.tsv, terms.tsv, brief.md} -> codex -> out.tsv -> <root>/out/<group>/<chunk>.tsv.
The JSONL event stream decides success (turn.completed / turn.failed); the exit status is only a hint.
Only the main thread writes manifest.json and usage.tsv; worker threads run codex and report back.

New launches stop on a usage limit, on --stop-at-pct, after --max-fails failures in a row, and on a
signal (SIGINT/SIGTERM/SIGHUP once = let running chunks finish; again = kill them, status goes back).
"""

import argparse
import collections
import datetime
import fcntl
import glob
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE_BIN = '/home/jaebeom/.nvm/versions/node/v22.22.0/bin'   # codex is a node CLI installed here
DEFAULT_CODEX_HOME = os.path.join(os.path.expanduser('~'), '.codex')
STATUSES = ('new', 'running', 'done', 'failed', 'limit', 'checked')
PROTECTED = ('done', 'checked')            # finished work: only re-run with --force
WEEK_MINUTES = 7 * 24 * 60
INTERPRETERS = ('node', 'nodejs', 'bash', 'sh', 'python', 'python3')

BRIEF_HEADER = (
    '# Task: translate chunk %s into Korean\n'
    '\n'
    'Translate `src.tsv` (columns: n, speaker, English text) into Korean for a Warhammer 40,000: Rogue Trader '
    'fan patch, following the style guide below exactly. Lines starting with `#` are scene headers: do not '
    'translate them and do not put them in the output. Speaker `PLAYER` = a player line or choice, '
    '`?` = unknown speaker, `-` = not a spoken line (names, UI, descriptions).\n'
    '\n'
    'Output: write `out.tsv` in the current directory, one line per n, same order as `src.tsv`: '
    '`n<TAB>Korean`. Every n exactly once, no header, no notes. Keep the escapes exactly as in the input '
    '(`\\n` = line break, `\\\\` = backslash) and keep every `{...}` and `<...>` markup as STYLE §5 says. '
    'No other files, no scripts, no self-check runs. When done, reply only `DONE <line count>`.\n'
)


def log(msg):
    line = '%s %s' % (time.strftime('%H:%M:%S'), msg)
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        try:
            print(line.encode('ascii', 'replace').decode('ascii'), flush=True)
        except OSError:
            pass
    except OSError:              # terminal gone (SIGHUP): keep running, nobody is reading
        pass


def die(msg, code=2):
    sys.stderr.write('run_astra: %s\n' % msg)
    sys.exit(code)


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


# ---------------------------------------------------------------- manifest

def manifest_path(root):
    return os.path.join(root, 'manifest.json')


def load_manifest(root):
    with open(manifest_path(root), encoding='utf-8') as f:
        return json.load(f)


def save_manifest(root, m):
    """Atomic rewrite, key order kept, one chunk per line (readable git diffs)."""
    parts = []
    for k, v in m.items():
        if k == 'chunks':
            body = ',\n'.join('  ' + json.dumps(c, ensure_ascii=False) for c in v)
            parts.append(' "chunks": [\n%s\n ]' % body if v else ' "chunks": []')
        else:
            parts.append(' %s: %s' % (json.dumps(k), json.dumps(v, ensure_ascii=False)))
    path = manifest_path(root)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write('{\n' + ',\n'.join(parts) + '\n}\n')
    os.replace(tmp, path)


def set_status(root, cid, status):
    """Re-read, change one status, write back (never overwrite what another tool added meanwhile)."""
    m = load_manifest(root)
    for c in m['chunks']:
        if c['id'] == cid:
            c['status'] = status
            break
    else:
        raise KeyError(cid)
    save_manifest(root, m)


def select_chunks(m, args):
    by_id = collections.OrderedDict((c['id'], c) for c in m['chunks'])
    if args.ids:
        sel = []
        for cid in args.ids:
            if cid not in by_id:
                die('unknown chunk: %s' % cid)
            if by_id[cid] not in sel:
                sel.append(by_id[cid])
    else:
        sel = list(by_id.values())
    if args.group:
        sel = [c for c in sel if c.get('group') == args.group]
    statuses = args.status
    if statuses is None and not args.ids:
        statuses = ['new']
    if statuses is not None:
        sel = [c for c in sel if c.get('status') in statuses]
    if not args.force:
        for c in [c for c in sel if c.get('status') in PROTECTED]:
            log('skip %s: status %s (use --force to run it again)' % (c['id'], c['status']))
        sel = [c for c in sel if c.get('status') not in PROTECTED]
    if args.max is not None:
        sel = sel[:args.max]
    return sel


# ---------------------------------------------------------------- brief / run dir

def read_tsv(path):
    rows = []
    try:
        f = open(path, encoding='utf-8')
    except OSError:
        return rows
    with f:
        for line in f:
            line = line.rstrip('\r\n')
            if line.strip() and not line.startswith('#'):
                rows.append(line.split('\t'))
    return rows


def read_src(path):
    """-> (n strings in file order, distinct speakers in order of appearance); `#` scene headers skipped."""
    ns, speakers, seen = [], [], set()
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\r\n')
            if not line.strip() or line.startswith('#'):
                continue
            parts = line.split('\t', 2)
            ns.append(parts[0].strip())
            if len(parts) > 1 and parts[1] not in seen:
                seen.add(parts[1])
                speakers.append(parts[1])
    return ns, speakers


def md_cell(s):
    return s.replace('|', '\\|').replace('\n', ' ').strip()


def md_table(header, rows):
    out = ['| %s |' % ' | '.join(header), '|' + '---|' * len(header)]
    for r in rows:
        out.append('| %s |' % ' | '.join(md_cell(c) for c in r))
    return '\n'.join(out)


def build_brief(cid, style_text, terms, voices):
    """terms: rows english/korean/memo; voices: rows speaker/description (already limited to this chunk)."""
    blocks = [(BRIEF_HEADER % cid).rstrip(), '---', style_text.strip(), '---']
    sec = ['## 이 청크의 용어', '']
    if terms:
        sec += ['이 표가 위 용어집과 다르면 이 표를 따른다.', '',
                md_table(['English', '한국어', '메모'], [(r + ['', '', ''])[:3] for r in terms])]
    else:
        sec.append('(없음)')
    blocks.append('\n'.join(sec))
    if voices:
        blocks.append('## 화자 말투\n\n' + md_table(['화자', '말투'], voices))
    return '\n\n'.join(blocks) + '\n'


def is_terms_header(row):
    return len(row) > 1 and row[0].strip().lower() == 'english' and row[1].strip().lower() == 'korean'


def voice_rows(voices, speakers):
    want = set(speakers)
    want_ci = set(s.lower() for s in speakers)
    out = []
    for r in voices:
        key = r[0].strip()
        if not key or key.lower() == 'speaker':           # blank or header row
            continue
        if key in want or key.lower() in want_ci:
            out.append([key, ' · '.join(c.strip() for c in r[1:] if c.strip())])
    return out


class PrepError(Exception):
    pass


Job = collections.namedtuple('Job', 'id group words rundir ns brief_bytes')


def prepare(args, root, chunk):
    """Fill <root>/run/<chunk>/ with src.tsv, terms.tsv, brief.md."""
    cid, group = chunk['id'], chunk['group']
    src = os.path.join(root, 'chunks', group, cid + '.src.tsv')
    terms_path = os.path.join(root, 'chunks', group, cid + '.terms.tsv')
    if not os.path.isfile(src):
        raise PrepError('missing %s' % src)
    try:
        with open(args.style, encoding='utf-8') as f:
            style = f.read()
    except OSError as e:
        raise PrepError('cannot read style guide: %s' % e)
    rundir = os.path.join(root, 'run', cid)
    os.makedirs(rundir, exist_ok=True)
    shutil.copyfile(src, os.path.join(rundir, 'src.tsv'))
    if os.path.isfile(terms_path):
        shutil.copyfile(terms_path, os.path.join(rundir, 'terms.tsv'))
    else:
        open(os.path.join(rundir, 'terms.tsv'), 'w').close()
    ns, speakers = read_src(src)
    terms = [r for r in read_tsv(terms_path) if not is_terms_header(r)]
    brief = build_brief(cid, style, terms, voice_rows(read_tsv(args.voices), speakers))
    with open(os.path.join(rundir, 'brief.md'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(brief)
    return Job(cid, group, chunk.get('words', 0), rundir, ns, len(brief.encode('utf-8')))


# ---------------------------------------------------------------- system state: weekly quota, codex processes

def _snapshot(ev):
    """Weekly rate-limit numbers from one rollout `token_count` event, or None."""
    p = ev.get('payload')
    if not isinstance(p, dict) or p.get('type') != 'token_count':
        return None
    rl = p.get('rate_limits')
    if not isinstance(rl, dict):
        return None
    cands = [c for c in (rl.get('primary'), rl.get('secondary'))
             if isinstance(c, dict) and c.get('used_percent') is not None]
    if not cands:
        return None
    weekly = [c for c in cands if (c.get('window_minutes') or 0) >= WEEK_MINUTES]
    w = (weekly or cands)[0]
    try:
        pct = float(w['used_percent'])
    except (TypeError, ValueError):
        return None
    return {'pct': pct, 'resets_at': w.get('resets_at'), 'ts': str(ev.get('timestamp') or '')}


def last_snapshot(path, max_bytes=128 << 20):
    """Last usable `token_count` line of a (big) rollout file, found by reading backwards."""
    block = 1 << 18
    try:
        f = open(path, 'rb')
    except OSError:
        return None
    with f:
        pos = f.seek(0, os.SEEK_END)
        buf, scanned = b'', 0
        while pos > 0 and scanned < max_bytes:
            step = min(block, pos)
            pos -= step
            f.seek(pos)
            buf = f.read(step) + buf
            scanned += step
            lines = buf.split(b'\n')
            if pos > 0:
                buf, lines = lines[0], lines[1:]      # first piece may be a cut-off line: keep for next round
            else:
                buf = b''
            for line in reversed(lines):
                if b'"token_count"' not in line:
                    continue
                try:
                    snap = _snapshot(json.loads(line.decode('utf-8', 'replace')))
                except ValueError:
                    continue
                if snap:
                    return snap
    return None


def weekly_status(codex_home=DEFAULT_CODEX_HOME):
    """Weekly quota from the newest Codex rollouts of today/yesterday: {pct, resets_at, ts, stale} or None."""
    now = time.time()
    days = set()
    for t in (now, now - 86400):
        days.add(time.strftime('%Y/%m/%d', time.localtime(t)))
        days.add(time.strftime('%Y/%m/%d', time.gmtime(t)))
    files = []
    for d in days:
        for p in glob.glob(os.path.join(codex_home, 'sessions', d, 'rollout-*.jsonl')):
            try:
                files.append((os.path.getmtime(p), p))
            except OSError:
                pass
    files.sort(reverse=True)
    best, found = None, 0
    for _, p in files[:12]:
        snap = last_snapshot(p)
        if snap:
            found += 1
            if best is None or snap['ts'] > best['ts']:
                best = snap
            if found >= 3:
                break
    if best is not None:
        ra = best.get('resets_at')
        best['stale'] = isinstance(ra, (int, float)) and ra < now - 60   # that window has already reset
    return best


def fmt_pct(w):
    return '?' if not w or w.get('stale') else '%.1f%%' % w['pct']


def fmt_reset(w):
    ra = w.get('resets_at') if w else None
    return time.strftime('%m-%d %H:%M', time.localtime(ra)) if isinstance(ra, (int, float)) else '?'


def _is_codex_exec(argv):
    base = [os.path.basename(a.decode('utf-8', 'replace')) for a in argv[:3]]
    if not base:
        return False
    if base[0] == 'codex':                                    # native binary
        return len(base) > 1 and base[1] == 'exec'
    if base[0] in INTERPRETERS or base[0].startswith('python3'):   # node launcher / script wrapper
        return len(base) > 2 and base[1] == 'codex' and base[2] == 'exec'
    return False


def count_codex_exec():
    """Running `codex exec` sessions on this machine (any project). The node launcher and the native binary
    it spawns are one session, so a match whose parent is also a match is not counted."""
    found = {}
    try:
        names = os.listdir('/proc')
    except OSError:
        return 0
    for name in names:
        if not name.isdigit():
            continue
        try:
            with open('/proc/%s/cmdline' % name, 'rb') as f:
                argv = f.read(4096).split(b'\0')
            if not _is_codex_exec(argv):
                continue
            with open('/proc/%s/stat' % name) as f:
                found[int(name)] = int(f.read().rsplit(')', 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
    return sum(1 for ppid in found.values() if ppid not in found)


# ---------------------------------------------------------------- one codex run (worker thread)

Result = collections.namedtuple('Result', 'kind rc seconds usage note try_again')
# kind: ok | failed | limit | interrupted


def parse_events(path):
    r = {'usage': None, 'failed': None, 'error': None, 'events': 0}
    try:
        f = open(path, 'rb')
    except OSError:
        return r
    with f:
        for line in f:
            line = line.strip()
            if not line.startswith(b'{'):
                continue
            try:
                ev = json.loads(line.decode('utf-8', 'replace'))
            except ValueError:
                continue
            if not isinstance(ev, dict):
                continue
            r['events'] += 1
            t = ev.get('type')
            if t == 'turn.completed':
                r['usage'] = ev.get('usage') or {}
            elif t == 'turn.failed':
                err = ev.get('error')
                r['failed'] = str((err.get('message') if isinstance(err, dict) else err) or 'turn.failed')
            elif t == 'error':                                # also used for harmless "Reconnecting..." notes
                r['error'] = str(ev.get('message') or '')
    return r


def try_again_text(msg):
    m = re.search(r'try again at\s+(.+?)\s*\.?\s*$', msg, re.I | re.S)
    return m.group(1).strip() if m else None


def tail_text(path, n=300):
    try:
        with open(path, 'rb') as f:
            size = f.seek(0, os.SEEK_END)
            f.seek(max(0, size - n))
            return f.read().decode('utf-8', 'replace').strip()
    except OSError:
        return ''


def kill_group(proc, sig):
    try:
        os.killpg(proc.pid, sig)          # children run in their own session: pid == pgid (node launcher + native)
    except (ProcessLookupError, PermissionError):
        pass


def stop_process(proc, grace=15):
    kill_group(proc, signal.SIGTERM)
    try:
        return proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        kill_group(proc, signal.SIGKILL)
        return proc.wait()


def run_codex(rn, job):
    args, rundir = rn.args, job.rundir
    ev_path = os.path.join(rundir, 'events.jsonl')
    err_path = os.path.join(rundir, 'stderr.log')
    cmd = [rn.codex_bin, 'exec', '-C', rundir, '-m', args.model,
           '-c', 'model_reasoning_effort="%s"' % args.effort,
           '--approve-for-me', '--skip-git-repo-check', '--color', 'never', '--json',
           '-o', os.path.join(rundir, 'last.md'), '-']
    t0 = time.monotonic()
    timed_out = False
    with open(os.path.join(rundir, 'brief.md'), 'rb') as fin, \
            open(ev_path, 'wb') as fev, open(err_path, 'wb') as ferr:
        proc = subprocess.Popen(cmd, stdin=fin, stdout=fev, stderr=ferr, cwd=rundir, env=rn.env,
                                start_new_session=True)
        rn.procs[job.id] = proc
        try:
            if rn.killing:                                    # second signal arrived while we were starting
                rc = stop_process(proc)
            else:
                rc = proc.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            rc = stop_process(proc)
        finally:
            rn.procs.pop(job.id, None)
    seconds = time.monotonic() - t0

    ev = parse_events(ev_path)
    out_path = os.path.join(rundir, 'out.tsv')
    out_ok = os.path.isfile(out_path) and os.path.getsize(out_path) > 0
    usage, failed, error = ev['usage'], ev['failed'], ev['error']
    if failed is not None:                                    # turn.failed wins over everything, exit code or not
        if 'usage limit' in failed.lower():
            return Result('limit', rc, seconds, usage, failed, try_again_text(failed))
        return Result('failed', rc, seconds, usage, 'turn.failed: ' + failed, None)
    if usage is not None:
        if out_ok:
            note = '' if rc == 0 else 'exit status %s after turn.completed' % rc
            return Result('ok', rc, seconds, usage, note, None)
        return Result('failed', rc, seconds, usage, 'turn.completed but out.tsv is missing or empty', None)
    if rn.killing:
        return Result('interrupted', rc, seconds, None, 'killed by signal', None)
    if timed_out:
        return Result('failed', rc, seconds, None, 'timeout after %ds' % args.timeout, None)
    if error and 'usage limit' in error.lower():
        return Result('limit', rc, seconds, None, error, try_again_text(error))
    detail = error or tail_text(err_path)
    note = 'no turn.completed/turn.failed in events.jsonl (%d events, exit %s)' % (ev['events'], rc)
    if detail:
        note += ': ' + ' '.join(detail.split())[:200]
    return Result('failed', rc, seconds, None, note, None)


# ---------------------------------------------------------------- the queue (main thread)

class Runner(object):
    def __init__(self, args, root, chunks):
        self.args, self.root = args, root
        self.pending = collections.deque(chunks)
        self.total = len(chunks)
        self.env = dict(os.environ)
        self.env['CODEX_HOME'] = args.codex_home
        self.env['PATH'] = NODE_BIN + os.pathsep + self.env.get('PATH', '')
        self.codex_bin = args.codex_bin or shutil.which('codex', path=self.env['PATH']) or 'codex'
        self.q = queue.Queue()
        self.procs = {}                  # chunk id -> Popen, for the kill path
        self.running = 0
        self.finished = 0
        self.counts = collections.Counter()
        self.prev_status = {}
        self.stop_reason = None
        self.limit_text = None
        self.consec_fail = 0
        self.interrupts = 0
        self.killing = False
        self.last_wait_log = 0.0

    # -- signals
    def on_signal(self, signum, frame):
        self.interrupts += 1
        if self.interrupts == 1:
            self.stop_reason = self.stop_reason or 'interrupted'
            log('signal %d: no new launches; waiting for %d running chunk(s) (signal again to kill them)'
                % (signum, self.running))
        else:
            self.killing = True
            log('signal again: killing %d running codex process(es)' % len(self.procs))
            for p in list(self.procs.values()):
                kill_group(p, signal.SIGTERM)

    # -- launching
    def stopping(self):
        return bool(self.stop_reason)

    def check_launch(self):
        """'ok' | 'wait' | 'stop' for starting one more codex process."""
        if self.stopping():
            return 'stop'
        pct = self.args.stop_at_pct
        if pct is not None:
            w = weekly_status(self.args.codex_home)
            if w and not w.get('stale') and w['pct'] >= pct:
                self.stop_reason = 'weekly quota %.1f%% >= --stop-at-pct %g' % (w['pct'], pct)
                return 'stop'
        n = count_codex_exec()
        if n >= self.args.global_max:
            if time.monotonic() - self.last_wait_log >= 60:
                self.last_wait_log = time.monotonic()
                log('waiting: %d codex exec running on this machine (--global-max %d)' % (n, self.args.global_max))
            return 'wait'
        return 'ok'

    def launch(self, chunk):
        cid = chunk['id']
        try:
            job = prepare(self.args, self.root, chunk)
        except (PrepError, OSError) as e:
            self.finished += 1
            self.counts['skipped'] += 1
            log('[%d/%d] %s SKIPPED :: %s' % (self.finished, self.total, cid, e))
            return
        for stale in ('out.tsv', 'last.md', 'result.json'):
            try:
                os.remove(os.path.join(job.rundir, stale))
            except OSError:
                pass
        prev = chunk.get('status', 'new')
        self.prev_status[cid] = 'new' if prev == 'running' else prev      # stale `running` goes back to new
        set_status(self.root, cid, 'running')
        self.running += 1
        threading.Thread(target=self.worker, args=(job,), name=cid, daemon=True).start()

    def worker(self, job):
        try:
            res = run_codex(self, job)
        except Exception as e:                                # a worker must always report back
            res = Result('failed', None, 0.0, None, 'runner error: %r' % (e,), None)
        self.q.put((job, res))

    # -- finishing (the only place that touches manifest / usage / out)
    def reap(self, timeout):
        got = False
        while True:
            try:
                job, res = self.q.get(timeout=timeout) if timeout and not got else self.q.get_nowait()
            except queue.Empty:
                return got
            got = True
            self.running -= 1
            self.finish(job, res)

    def publish(self, job):
        src = os.path.join(job.rundir, 'out.tsv')
        dst = os.path.join(self.root, 'out', job.group, job.id + '.tsv')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst + '.tmp')
        os.replace(dst + '.tmp', dst)

    def shape_warning(self, job):
        out_ns = []
        with open(os.path.join(job.rundir, 'out.tsv'), encoding='utf-8', errors='replace') as f:
            for line in f:
                if line.strip():
                    out_ns.append(line.split('\t', 1)[0].strip())
        if out_ns == job.ns:
            return ''
        return ' WARN out.tsv has %d lines, src has %d (n list differs; check.py will list it)' % (
            len(out_ns), len(job.ns))

    def append_usage(self, job, res, w):
        u = res.usage or {}
        row = [job.id, str(job.words)]
        row += [str(u.get(k, 0)) for k in ('input_tokens', 'cached_input_tokens', 'output_tokens',
                                           'reasoning_output_tokens')]
        row += [str(int(round(res.seconds))), '' if not w or w.get('stale') else '%.1f' % w['pct'], now_iso()]
        with open(os.path.join(self.root, 'usage.tsv'), 'a', encoding='utf-8', newline='\n') as f:
            f.write('\t'.join(row) + '\n')

    def finish(self, job, res):
        self.finished += 1
        cid = job.id
        w = weekly_status(self.args.codex_home)
        pct = fmt_pct(w)
        tag = '[%d/%d] %s' % (self.finished, self.total, cid)
        secs = int(round(res.seconds))
        if res.kind == 'ok':
            try:
                self.publish(job)
            except OSError as e:
                res = res._replace(kind='failed', note='copy to out/ failed: %s' % e)
        if res.kind == 'ok':
            set_status(self.root, cid, 'done')
            self.append_usage(job, res, w)
            self.counts['done'] += 1
            self.consec_fail = 0
            log('%s done %ds out=%s wk=%s%s' % (tag, secs, (res.usage or {}).get('output_tokens', '?'), pct,
                                                self.shape_warning(job)))
        elif res.kind == 'limit':
            set_status(self.root, cid, 'limit')
            self.counts['limit'] += 1
            self.limit_text = self.limit_text or res.try_again or res.note
            self.stop_reason = 'usage limit'
            with open(os.path.join(self.root, 'run', 'limit.txt'), 'w', encoding='utf-8') as f:
                f.write('%s %s\ntry again at: %s\n%s\n' % (now_iso(), cid, res.try_again or '?', res.note))
            log('%s LIMIT %ds wk=%s :: try again at %s' % (tag, secs, pct, res.try_again or '(see events.jsonl)'))
        elif res.kind == 'interrupted':
            set_status(self.root, cid, self.prev_status.get(cid, 'new'))
            self.counts['interrupted'] += 1
            log('%s INTERRUPTED %ds (status back to %s)' % (tag, secs, self.prev_status.get(cid, 'new')))
        else:
            set_status(self.root, cid, 'failed')
            self.counts['failed'] += 1
            self.consec_fail += 1
            if self.consec_fail >= self.args.max_fails and not self.stopping():
                self.stop_reason = '%d chunks failed in a row' % self.consec_fail
            log('%s FAILED %ds wk=%s :: %s' % (tag, secs, pct, ' '.join(res.note.split())[:200]))
        record = {'id': cid, 'result': res.kind, 'exit_status': res.rc, 'seconds': round(res.seconds, 1),
                  'usage': res.usage, 'weekly_pct': None if not w or w.get('stale') else w['pct'],
                  'note': res.note, 'finished_at': now_iso()}
        with open(os.path.join(job.rundir, 'result.json'), 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=1)

    # -- main loop
    def run(self):
        old = {}
        for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            old[s] = signal.signal(s, self.on_signal)
        try:
            while True:
                can_try = bool(self.pending) and self.running < self.args.jobs and not self.stopping()
                if can_try and self.check_launch() == 'ok':
                    self.launch(self.pending.popleft())
                    self.reap(self.args.stagger)              # spacing; the new process shows up in /proc
                    continue
                if self.running == 0 and (not self.pending or self.stopping()):
                    break
                self.reap(2.0 if can_try else 1.0)
        except BaseException:                                     # never leave unharvested codex runs behind
            self.killing = True
            for p in list(self.procs.values()):
                kill_group(p, signal.SIGTERM)
            raise
        finally:
            for s, h in old.items():
                signal.signal(s, h)
        return self.summary()

    def summary(self):
        c = self.counts
        w = weekly_status(self.args.codex_home)
        log('finished: done=%d failed=%d limit=%d interrupted=%d skipped=%d not-started=%d | weekly %s (resets %s)'
            % (c['done'], c['failed'], c['limit'], c['interrupted'], c['skipped'], len(self.pending),
               fmt_pct(w), fmt_reset(w)))
        if self.stop_reason:
            log('stopped early: %s%s' % (self.stop_reason,
                                         ' -- try again at %s' % self.limit_text if self.limit_text else ''))
        bad = c['failed'] + c['limit'] + c['interrupted'] + c['skipped']
        return 0 if not bad and not self.pending and not self.stop_reason else 1


# ---------------------------------------------------------------- entry

def acquire_lock(root):
    """One runner per work tree (the manifest has a single writer)."""
    os.makedirs(os.path.join(root, 'run'), exist_ok=True)
    fd = os.open(os.path.join(root, 'run', '.runner.lock'), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        die('another run_astra.py is already working on %s' % root, 1)
    os.ftruncate(fd, 0)
    os.write(fd, ('%d\n' % os.getpid()).encode())
    return fd


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        prog='run_astra.py', formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Translate chunks with Astra (codex exec, one process per chunk). See docs/PIPELINE.md.',
        epilog='Selection: CHUNK ids, or --group / --status (default status: new). Chunks that are done/checked\n'
               'are skipped unless --force. Exit status: 0 = everything selected is done, 1 = anything failed,\n'
               'hit the limit, was interrupted or never started, 2 = usage error.')
    ap.add_argument('ids', nargs='*', metavar='CHUNK', help='chunk ids to run')
    ap.add_argument('--group', metavar='G', help='only chunks of this group')
    ap.add_argument('--status', metavar='S[,S]', help='manifest status to run: %s (default: new)' % '|'.join(STATUSES))
    ap.add_argument('--max', type=int, metavar='N', help='run at most N chunks')
    ap.add_argument('--root', default=os.path.join(REPO, 'work'), metavar='DIR',
                    help='work tree with manifest.json (default: <repo>/work)')
    ap.add_argument('--jobs', type=int, default=6, help='parallel codex runs (default 6)')
    ap.add_argument('--global-max', type=int, default=10, metavar='M',
                    help='wait while M `codex exec` run on this machine, any project (default 10)')
    ap.add_argument('--stop-at-pct', type=float, metavar='P', help='launch nothing once weekly usage >= P percent')
    ap.add_argument('--dry-run', action='store_true', help='prepare run dirs and print the plan; never call codex')
    ap.add_argument('--force', action='store_true', help='also run chunks that are done/checked')
    ap.add_argument('--timeout', type=int, default=7200, metavar='SEC', help='kill one codex run after SEC (7200)')
    ap.add_argument('--max-fails', type=int, default=3, metavar='K', help='stop launching after K failures in a row (3)')
    ap.add_argument('--stagger', type=float, default=2.0, metavar='SEC', help='pause between launches (2)')
    ap.add_argument('--model', default='gpt-6-astra')
    ap.add_argument('--effort', default='medium', help='model_reasoning_effort (medium)')
    ap.add_argument('--codex-bin', metavar='PATH', help='codex executable (default: first `codex` on the node PATH)')
    ap.add_argument('--codex-home', default=DEFAULT_CODEX_HOME, metavar='DIR', help='default ~/.codex')
    ap.add_argument('--style', default=os.path.join(REPO, 'STYLE.md'), metavar='FILE')
    ap.add_argument('--voices', default=os.path.join(REPO, 'glossary', 'voices.tsv'), metavar='FILE',
                    help='speaker voices table; skipped when the file does not exist')
    args = ap.parse_args(argv)
    if args.status is not None:
        args.status = [s.strip() for s in args.status.split(',') if s.strip()]
        bad = [s for s in args.status if s not in STATUSES]
        if bad:
            ap.error('unknown status %s (one of %s)' % (','.join(bad), ', '.join(STATUSES)))
    if not (args.ids or args.group or args.status):
        ap.error('nothing selected: give CHUNK ids, --group or --status')
    if args.jobs < 1 or args.global_max < 1 or args.max_fails < 1 or args.timeout < 1:
        ap.error('--jobs, --global-max, --max-fails and --timeout must be at least 1')
    if args.stagger < 0:
        ap.error('--stagger must not be negative')
    args.root = os.path.abspath(args.root)
    return args


def dry_run(args, chunks):
    root = args.root
    log('dry-run: %d chunk(s) from %s' % (len(chunks), root))
    for c in chunks:
        try:
            job = prepare(args, root, c)
        except (PrepError, OSError) as e:
            log('  %-16s SKIPPED :: %s' % (c['id'], e))
            continue
        log('  %-16s status=%-7s words=%-5s strings=%-4s brief=%d bytes  %s'
            % (c['id'], c.get('status'), c.get('words', '?'), len(job.ns), job.brief_bytes, job.rundir))
    w = weekly_status(args.codex_home)
    log('weekly usage %s (resets %s); codex exec running now: %d (global-max %d, jobs %d); nothing launched'
        % (fmt_pct(w), fmt_reset(w), count_codex_exec(), args.global_max, args.jobs))
    return 0


def main(argv=None):
    args = parse_args(argv)
    if not os.path.isfile(manifest_path(args.root)):
        die('no manifest at %s (use --root)' % manifest_path(args.root))
    if args.dry_run:
        return dry_run(args, select_chunks(load_manifest(args.root), args))
    acquire_lock(args.root)                                    # the fd stays open: flock held until exit
    m = load_manifest(args.root)
    chunks = select_chunks(m, args)
    if not chunks:
        log('nothing to run')
        return 0
    stuck = [c['id'] for c in m['chunks'] if c.get('status') == 'running' and c not in chunks]
    if stuck:
        log('note: %d chunk(s) still marked running by an earlier run that died (re-run them with '
            '--status running): %s' % (len(stuck), ', '.join(stuck[:5]) + (' ...' if len(stuck) > 5 else '')))
    rn = Runner(args, args.root, chunks)
    w = weekly_status(args.codex_home)
    log('start: %d chunk(s), jobs=%d, global-max=%d, codex exec running now=%d, weekly %s (resets %s)%s'
        % (len(chunks), args.jobs, args.global_max, count_codex_exec(), fmt_pct(w), fmt_reset(w),
           '' if args.stop_at_pct is None else ', stop at %g%%' % args.stop_at_pct))
    return rn.run()


if __name__ == '__main__':
    sys.exit(main())
