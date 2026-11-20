"""Connectors: one function per source. Each pulls only what changed (watermark = mtime:size, or Gmail historyId),
dates every row, is idempotent via replace_rows, and keeps a pointer back to the original."""
import base64, glob, html, json, os, re, shutil, subprocess, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import kb

PROJECTS = os.path.expanduser(os.environ.get("KB_CLAUDE_PROJECTS", "~/.claude/projects"))
CHUNK = 4000

SECRET = re.compile(
    r"(sk-ant-[\w-]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|AIza[\w-]{30,}"
    r"|xox[abpr]-[\w-]{10,}|eyJ[\w-]{20,}\.[\w-]{20,}\.[\w-]{10,}"
    r"|(?i:(?:api[_-]?key|secret|token|password|passwd)\s*[:=]\s*['\"]?)[^\s'\"]{8,})")


def mask(s):
    """Anything that looks like an API key or password is masked before it is stored."""
    return SECRET.sub(lambda m: m.group(0)[:6] + "…[masked]", s)


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def domain_of(rel, cfg):
    top = rel.split(os.sep)[0] if os.sep in rel else "(root)"
    return cfg["domains"].get(top, top)


def replace_rows(con, source, source_id, rows):
    con.execute("DELETE FROM docs WHERE source=? AND source_id=?", (source, source_id))
    con.executemany(
        "INSERT INTO docs(kind,source,source_id,ts,title,content,metadata) VALUES (?,?,?,?,?,?,?)",
        [(r["kind"], source, source_id, r["ts"], r["title"], mask(r["content"]), json.dumps(r["meta"])) for r in rows])


def changed(con, source, key, mark):
    old = con.execute("SELECT watermark FROM ingest_state WHERE source=? AND key=?", (source, key)).fetchone()
    return not old or old[0] != mark


def stamp(con, source, key, mark):
    con.execute("INSERT OR REPLACE INTO ingest_state VALUES (?,?,?)", (source, key, mark))


def chunks(text):
    """4,000-char raw chunks, split on line boundaries; yields (start_line, text)."""
    buf, start, line_no, size = [], 1, 1, 0
    for line in text.split("\n"):
        if size + len(line) > CHUNK and buf:
            yield start, "\n".join(buf)
            buf, size, start = [], 0, line_no
        while len(line) > CHUNK:  # one giant line
            yield line_no, line[:CHUNK]; line = line[CHUNK:]
        buf.append(line); size += len(line) + 1; line_no += 1
    if buf: yield start, "\n".join(buf)


# ---------------------------------------------------------------- project files
def files(con):
    cfg = kb.config()
    root, n, live = kb.ROOT, 0, set()
    skip_dirs = set(cfg["skip_dirs"])
    skip_paths = [p.strip("/") for p in cfg["skip_paths"]]
    exts = tuple(cfg["extensions"])
    own = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # never index this skill's own docs
    for here, dirs, names in os.walk(root):
        rel_here = os.path.relpath(here, root)
        dirs[:] = [d for d in dirs if d not in skip_dirs and os.path.join(here, d) != own
                   and not any(os.path.normpath(os.path.join(rel_here, d)).startswith(p) for p in skip_paths)]
        for f in names:
            if not f.endswith(exts): continue
            full = os.path.join(here, f)
            rel = os.path.relpath(full, root)
            if any(rel.startswith(p) for p in skip_paths): continue
            live.add(rel)
            st = os.stat(full)
            if st.st_size > cfg["max_file_bytes"]: continue
            mark = f"{st.st_mtime}:{st.st_size}"
            if not changed(con, "files", rel, mark): continue
            try: text = open(full, encoding="utf-8", errors="ignore").read()
            except OSError: continue
            h1 = re.search(r"^#\s+(.+)$", text, re.M)
            title = (h1.group(1) if h1 else f) + "  (" + rel + ")"
            meta = {"path": full, "domain": domain_of(rel, cfg)}
            ts = iso(st.st_mtime)
            if len(text) <= CHUNK:
                rows = [{"kind": "note", "ts": ts, "title": title, "content": text, "meta": meta}]
            else:
                # no-LLM stand-in for a summary: opening + headings
                heads = "\n".join(re.findall(r"^#{1,3}\s+.+$", text, re.M)[:40])
                rows = [{"kind": "note", "ts": ts, "title": title, "content": text[:1500] + "\n" + heads, "meta": meta}]
                rows += [{"kind": "raw", "ts": ts, "title": title, "content": c, "meta": {**meta, "line": ln}}
                         for ln, c in chunks(text)]
            replace_rows(con, "files", rel, rows); stamp(con, "files", rel, mark); n += 1
    # hygiene: drop rows for files that no longer exist (or are now excluded)
    gone = [k for (k,) in con.execute("SELECT key FROM ingest_state WHERE source='files'") if k not in live]
    for k in gone:
        con.execute("DELETE FROM docs WHERE source='files' AND source_id=?", (k,))
        con.execute("DELETE FROM ingest_state WHERE source='files' AND key=?", (k,))
    return n, len(gone)


# ---------------------------------------------------------------- Claude Code sessions
REMIND = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


def project_folder(path):
    """Claude Code stores a project's sessions in ~/.claude/projects/<path with every non-alphanumeric char as '-'>."""
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def _text(content):
    if isinstance(content, str): return content
    out = []
    for b in content or []:
        if not isinstance(b, dict): continue
        t = b.get("type")
        if t == "text": out.append(b.get("text", ""))
        elif t == "tool_use":
            inp = b.get("input") or {}
            brief = inp.get("command") or inp.get("file_path") or inp.get("pattern") or inp.get("query") or inp.get("description") or ""
            out.append(f"[tool {b.get('name')}] {str(brief)[:400]}")
        elif t == "tool_result":
            c = b.get("content")
            if isinstance(c, list): c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
            out.append("[result] " + str(c or "")[:2000])
    return "\n".join(out)


def sessions(con):
    cfg = kb.config()
    scope = cfg["sessions"]
    if scope == "off": return 0, 0
    mine = project_folder(kb.ROOT)
    home_prefix = project_folder(os.path.expanduser("~")) + "-"
    n = 0
    for f in glob.glob(PROJECTS + "/*/*.jsonl") + glob.glob(PROJECTS + "/*/*/subagents/*.jsonl"):
        proj = f[len(PROJECTS) + 1:].split("/")[0]
        if scope == "this-project" and not (proj == mine or proj.startswith(mine + "-")): continue
        if any(s in proj for s in cfg["skip_projects"]): continue
        sid = os.path.relpath(f, PROJECTS)
        st = os.stat(f)
        mark = f"{st.st_mtime}:{st.st_size}"
        if not changed(con, "sessions", sid, mark): continue
        title, prompts, lines, first_ts = None, [], [], None
        for raw in open(f, encoding="utf-8", errors="ignore"):
            try: d = json.loads(raw)
            except ValueError: continue
            typ = d.get("type")
            if typ == "custom-title": title = d.get("customTitle") or title
            if typ == "ai-title" and not title: title = d.get("aiTitle")
            if typ == "summary" and not title: title = d.get("summary")
            if typ not in ("user", "assistant") or d.get("isMeta"): continue
            ts = d.get("timestamp") or iso(st.st_mtime)
            first_ts = first_ts or ts
            body = REMIND.sub("", _text((d.get("message") or {}).get("content"))).strip()
            if not body: continue
            who = "USER" if typ == "user" and not body.startswith("[result]") else ("CLAUDE" if typ == "assistant" else "")
            if who == "USER": prompts.append(body[:600])
            lines.append((ts, f"{who + ': ' if who else ''}{body}"))
        if not lines: stamp(con, "sessions", sid, mark); continue
        kind_tag = "subagent" if "/subagents/" in sid else "session"
        title = f"{title or (prompts[0][:80] if prompts else 'untitled')} [{kind_tag} {proj.replace(home_prefix, '')}]"
        meta = {"path": f, "domain": "session", "project": proj}
        rows = [{"kind": "session", "ts": first_ts, "title": title, "content": "\n".join(prompts)[:CHUNK], "meta": meta}]
        buf, size, start_ts = [], 0, lines[0][0]
        for ts, ln in lines:
            if size + len(ln) > CHUNK and buf:
                rows.append({"kind": "raw", "ts": start_ts, "title": title, "content": "\n".join(buf), "meta": meta})
                buf, size, start_ts = [], 0, ts
            buf.append(ln[:CHUNK]); size += min(len(ln), CHUNK)
        if buf: rows.append({"kind": "raw", "ts": start_ts, "title": title, "content": "\n".join(buf), "meta": meta})
        replace_rows(con, "sessions", sid, rows); stamp(con, "sessions", sid, mark); n += 1
    # Claude Code deletes old session files (cleanupPeriodDays, default 30). Their rows are KEPT on purpose:
    # the index is the long-term memory. Only rows for sessions now excluded by config are removed.
    gone = 0
    for (k,) in con.execute("SELECT key FROM ingest_state WHERE source='sessions'").fetchall():
        if _in_scope(k, scope, mine, cfg): continue
        con.execute("DELETE FROM docs WHERE source='sessions' AND source_id=?", (k,))
        con.execute("DELETE FROM ingest_state WHERE source='sessions' AND key=?", (k,)); gone += 1
    return n, gone


def _in_scope(sid, scope, mine, cfg):
    proj = sid.split("/")[0]
    if scope == "this-project" and not (proj == mine or proj.startswith(mine + "-")): return False
    return not any(s in proj for s in cfg["skip_projects"])


# ---------------------------------------------------------------- Gmail (optional, read-only, via the gws CLI)
GMAIL_CFG = os.path.join(kb.DATA, "gmail.json")
QUOTE = re.compile(r"(?m)^(On .{5,200}wrote:|Le .{5,200}a écrit\s?:|-----Original Message-----|From: .+\nSent: ).*", re.S)
DISCLAIMER = re.compile(r"(?i).{0,300}(should not be construed|not (be )?(construed as )?(constituting )?legal advice|"
                        r"intended (solely )?(for the )?(named )?recipient|privileged and confidential|confidentiality notice|"
                        r"this (e-?mail|message) (and any attachments )?(is|are|may be) confidential).{0,600}")
NEVER = r"(?!x)x"  # a regex that matches nothing


def gmail_enabled():
    if not os.path.exists(GMAIL_CFG): return False, "no .kb/gmail.json (optional add-on, see README)"
    cfg = json.load(open(GMAIL_CFG))
    if not cfg.get("accounts"): return False, "gmail.json has no accounts"
    if not (os.environ.get("GWS_BIN") or shutil.which("gws")): return False, "gws command not found"
    return True, ""


def _gws(cfg_dir, *args):
    env = {**os.environ}
    if cfg_dir: env["GOOGLE_WORKSPACE_CLI_CONFIG_DIR"] = os.path.expanduser(cfg_dir)
    r = subprocess.run([os.environ.get("GWS_BIN") or shutil.which("gws"), *args], capture_output=True, text=True,
                       env=env, timeout=120)
    if r.returncode or not r.stdout.strip():  # a broken gws must fail loudly, never look like "no new mail"
        raise RuntimeError(f"gws {' '.join(args[:4])} exit {r.returncode}: {(r.stderr or 'no output').strip()[-300:]}")
    if "--page-all" in args:
        return [json.loads(l) for l in r.stdout.splitlines() if l.strip().startswith("{")]
    d = json.loads(r.stdout or "{}")
    if "error" in d: raise RuntimeError(f"gws {args[2]}: {d['error'].get('message', d['error'])}")
    return d


def _body(payload):
    """Plain text of a message: text/plain parts first, else de-tagged html, quoted older replies dropped."""
    plain, htm = [], []
    def walk(p):
        mt, data = p.get("mimeType", ""), (p.get("body") or {}).get("data")
        if data and not p.get("filename"):
            txt = base64.urlsafe_b64decode(data + "===").decode("utf-8", "ignore")
            (plain if mt == "text/plain" else htm if mt == "text/html" else []).append(txt)
        for c in p.get("parts") or []: walk(c)
    walk(payload)
    if plain: text = "\n".join(plain)
    else:
        text = re.sub(r"(?is)<(style|script)[^>]*>.*?</\1>", " ", "\n".join(htm))
        text = html.unescape(re.sub(r"(?s)<br\s*/?>|</p>|</div>", "\n", text))
        text = re.sub(r"<[^>]+>", " ", text)
    text = QUOTE.split(text)[0]
    text = re.sub(r"(?m)^>.*$", "", text)
    return re.sub(r"[ \t ]+", " ", re.sub(r"\n\s*\n+", "\n\n", text)).strip()


def _addr(h):
    return [a.lower() for a in re.findall(r"[\w.+'-]+@[\w-]+\.[\w.-]+", h or "")]


def gmail(con):
    ok, why_not = gmail_enabled()
    if not ok:
        print("gmail: skipped,", why_not); return 0, 0
    cfg = json.load(open(GMAIL_CFG))
    skip_subj = re.compile(cfg.get("skip_subject") or NEVER, re.I)
    wall = re.compile(cfg.get("never_store") or NEVER, re.I)
    allow = tuple(cfg.get("allow_sender_domains") or [])
    keep_hdr = re.compile(cfg.get("keep_header_pattern") or NEVER, re.I)
    keep_subj = re.compile(cfg.get("keep_subject") or NEVER, re.I)
    n, report = 0, []
    for acct in cfg["accounts"]:
        cd, me = acct.get("gws_config"), acct["name"].lower()
        last = con.execute("SELECT watermark FROM ingest_state WHERE source='gmail' AND key=?", ("__last__" + me,)).fetchone()
        started = int(time.time())
        window = f"after:{int(last[0]) - 2 * 86400}" if last else cfg.get("backfill", "newer_than:180d")
        # who you write to = who matters (learned from your own sent mail, remembered)
        known = set(json.loads((con.execute("SELECT watermark FROM ingest_state WHERE source='gmail' AND key=?",
                                            ("__people__" + me,)).fetchone() or ["[]"])[0]))
        threads = []
        for page in _gws(cd, "gmail", "users", "threads", "list", "--params",
                         json.dumps({"userId": "me", "q": f"{window} {cfg.get('base_query', '')}", "maxResults": 500}),
                         "--page-all", "--page-limit", "50"):
            threads += page.get("threads", [])
        todo = [t for t in threads if changed(con, "gmail", me + ":" + t["id"], t["historyId"])]

        def fetch(t):
            try: return t, _gws(cd, "gmail", "users", "threads", "get", "--params",
                                json.dumps({"userId": "me", "id": t["id"], "format": "full"}))
            except Exception as e: return t, e
        with ThreadPoolExecutor(8) as pool: got = list(pool.map(fetch, todo))
        for t, th in got:  # pass 1: learn correspondents from your own messages
            if isinstance(th, Exception): continue
            for m in th.get("messages", []):
                h = {x["name"].lower(): x["value"] for x in m["payload"].get("headers", [])}
                if me in _addr(h.get("from")) or "SENT" in m.get("labelIds", []):
                    known.update(a for a in _addr(h.get("to", "") + "," + h.get("cc", "")) if a != me)
        kept = failed = 0
        dropped = {}
        for t, th in got:
            key = me + ":" + t["id"]
            if isinstance(th, Exception): failed += 1; continue
            msgs, lines, why = th.get("messages", []), [], None
            hs = [{x["name"].lower(): x["value"] for x in m["payload"].get("headers", [])} for m in msgs]
            subject = next((h.get("subject") for h in hs if h.get("subject")), "(no subject)")
            senders = [a for h in hs for a in _addr(h.get("from"))]
            wrote = any(a == me for a in senders) or any("SENT" in m.get("labelIds", []) for m in msgs)
            from_known = any(a in known for a in senders)
            allowed = any(a.split("@")[-1] == d or a.split("@")[-1].endswith("." + d) for a in senders for d in allow)
            client = any(keep_hdr.search(" ".join(h.get(k, "") for k in ("from", "to", "cc", "delivered-to", "reply-to",
                                                                          "x-forwarded-for", "x-forwarded-to"))) for h in hs)
            bulk = any("list-unsubscribe" in h for h in hs)
            updates = any("CATEGORY_UPDATES" in m.get("labelIds", []) for m in msgs)
            for m, h in zip(msgs, hs):
                lines.append(f"FROM: {h.get('from','')} | TO: {h.get('to','')} | {h.get('date','')}\n{_body(m['payload'])[:6000]}")
            # newest message first, so a quick read sees the latest reply, not the thread opener
            last_h, last_m = (hs[-1], msgs[-1]) if hs else ({}, {})
            last_mine = me in _addr(last_h.get("from")) or "SENT" in last_m.get("labelIds", [])
            text = (f"SUBJECT: {subject}\nLATEST ({len(msgs)} msgs, newest first): "
                    f"{'you sent last' if last_mine else 'REPLY FROM ' + (last_h.get('from') or '?')}\n\n"
                    + "\n\n---\n\n".join(reversed(lines)))
            marketing = any(re.match(r"(e-?news|news|info|marketing|promo|offers|email|m|mail|em)\.", a.split("@")[-1]) for a in senders)
            action = bool(keep_subj.search(subject))
            keep = wrote or client or action or (allowed and not (bulk and marketing)) or (not bulk and (from_known or not updates))
            if skip_subj.search(subject): why = "login/2FA"
            elif wall.search(subject + "\n" + " ".join(h.get("from", "") for h in hs) + "\n"
                             + DISCLAIMER.sub(" ", re.sub(r"\s+", " ", text))): why = "never-store"
            elif not keep: why = "bulk/automated"
            if why:
                con.execute("DELETE FROM docs WHERE source='gmail' AND source_id=?", (key,))
                stamp(con, "gmail", key, t["historyId"]); dropped[why] = dropped.get(why, 0) + 1; continue
            ts = datetime.fromtimestamp(int(msgs[-1]["internalDate"]) / 1000, timezone.utc).isoformat(timespec="seconds")
            meta = {"path": f"https://mail.google.com/mail/u/{me}/#all/{t['id']}", "domain": acct.get("domain", "email"),
                    "account": me, "from": senders[0] if senders else "", "bulk": bulk,
                    "why": "mine" if wrote else "client" if client else "action" if action else "known" if from_known
                    else "allow" if allowed else "primary",
                    "last_from": "me" if last_mine else (_addr(last_h.get("from")) or ["?"])[0], "msgs": len(msgs)}
            title = f"{subject}  (email {me.split('@')[0]}, {senders[0] if senders else '?'})"
            rows = [{"kind": "thread", "ts": ts, "title": title, "content": text[:CHUNK], "meta": meta}]
            if len(text) > CHUNK:
                rows += [{"kind": "raw", "ts": ts, "title": title, "content": c, "meta": meta} for _, c in chunks(text)]
            replace_rows(con, "gmail", key, rows); stamp(con, "gmail", key, t["historyId"]); kept += 1; n += 1
        stamp(con, "gmail", "__people__" + me, json.dumps(sorted(known)))
        if not failed: stamp(con, "gmail", "__last__" + me, str(started))
        report.append(f"{me}: {len(threads)} listed, {len(todo)} changed, {kept} kept, filtered {dropped or 0}, {failed} failed")
    print("gmail: " + " | ".join(report))
    return n, 0


CONNECTORS = {"files": files, "sessions": sessions, "gmail": gmail}
