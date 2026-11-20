#!/usr/bin/env python3
"""Knowledge base: one local SQLite/FTS5 search over your project's notes and your past Claude Code sessions
(and, optionally, the email that matters). Design after Nick Saraev's personal knowledge-base prompt.

  kb.py setup                                   create .kb/ (database + config), gitignore it
  kb.py search "query" [--after YYYY-MM-DD] [--source files|sessions|gmail] [--domain NAME] [--limit N] [--json] [--plain]
  kb.py recent [--source gmail] [--hours 36] [--limit 40]   newest items first, no query
  kb.py note "Title" "text"                     save a quick capture into the notes inbox
  kb.py stats                                   row counts + last refresh
"""
import argparse, json, math, os, re, sqlite3, subprocess, sys, time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))


def _project_root():
    """<root>/.claude/skills/knowledge-base/scripts/kb.py -> <root>. Override with KB_ROOT."""
    if os.environ.get("KB_ROOT"):
        return os.path.abspath(os.path.expanduser(os.environ["KB_ROOT"]))
    parts = HERE.split(os.sep)
    if len(parts) >= 4 and parts[-3] == "skills" and parts[-4] == ".claude":
        root = os.sep.join(parts[:-4]) or os.sep
        if os.path.abspath(root) != os.path.expanduser("~"):
            return root
    # installed globally (~/.claude/skills): use the git root of where Claude is working, else the current folder
    try:
        return subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return os.getcwd()


ROOT = _project_root()
DATA = os.environ.get("KB_HOME", os.path.join(ROOT, ".kb"))
DB = os.environ.get("KB_DB", os.path.join(DATA, "kb.sqlite"))
CONFIG_PATH = os.path.join(DATA, "config.json")

DEFAULTS = {
    "_doc": "Knowledge base settings. Edit freely; every key is optional. See the skill's README.md.",
    "extensions": [".md", ".txt"],
    "skip_dirs": ["node_modules", ".git", ".kb", ".tmp", "tmp", "cache", ".cache", ".venv", "venv",
                  "__pycache__", "dist", "build", ".next", ".playwright-mcp"],
    "skip_paths": [],
    "max_file_bytes": 1000000,
    "domains": {},
    "reference_paths": "swipe|/transcripts?/|course-library|/references?/|/vendor/",
    "sessions": "this-project",
    "skip_projects": [],
    "summaries": True,
    "summary_model": "haiku",
    "notes_dir": "notes",
}


def config():
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        cfg.update(json.load(open(CONFIG_PATH)))
    return cfg


SCHEMA = """
CREATE TABLE IF NOT EXISTS docs(
  id INTEGER PRIMARY KEY,
  kind TEXT, source TEXT, source_id TEXT, ts TEXT, title TEXT, content TEXT,
  metadata TEXT, superseded_by INTEGER);
CREATE INDEX IF NOT EXISTS docs_src ON docs(source, source_id);
CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
  title, content, content='docs', content_rowid='id', tokenize='porter unicode61');
CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON docs BEGIN
  INSERT INTO docs_fts(rowid, title, content) VALUES (new.id, new.title, new.content); END;
CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON docs BEGIN
  INSERT INTO docs_fts(docs_fts, rowid, title, content) VALUES ('delete', old.id, old.title, old.content); END;
CREATE TRIGGER IF NOT EXISTS docs_au AFTER UPDATE ON docs BEGIN
  INSERT INTO docs_fts(docs_fts, rowid, title, content) VALUES ('delete', old.id, old.title, old.content);
  INSERT INTO docs_fts(rowid, title, content) VALUES (new.id, new.title, new.content); END;
CREATE TABLE IF NOT EXISTS ingest_state(source TEXT, key TEXT, watermark TEXT, PRIMARY KEY(source, key));
"""

STOP = set("a an and are as at be by can do does for from has have how i in is it its me my of on or our so that the "
           "this to was we were what when where which who why will with you your did".split())
LOW_CONF = 0.5


def connect():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    return con


def _words(q):
    return [w for w in re.findall(r"[\w$]+", q.lower()) if w not in STOP and len(w) > 1]


def fts_query(q):
    return " OR ".join('"%s"' % w.replace('"', "") for w in _words(q))


def run(con, match, raw, args, pool):
    sql = """SELECT d.id, d.kind, d.source, d.source_id, d.ts, d.title, d.metadata, d.superseded_by,
                    bm25(docs_fts) AS r, snippet(docs_fts, 1, '[', ']', ' … ', 24)
             FROM docs_fts JOIN docs d ON d.id = docs_fts.rowid
             WHERE docs_fts MATCH ? AND d.kind %s 'raw'""" % ("=" if raw else "!=")
    params = [match]
    if args.after: sql += " AND d.ts >= ?"; params.append(args.after)
    if args.source: sql += " AND d.source = ?"; params.append(args.source)
    if args.domain: sql += " AND json_extract(d.metadata,'$.domain') = ?"; params.append(args.domain)
    sql += " ORDER BY r LIMIT ?"; params.append(pool)
    return con.execute(sql, params).fetchall()


def confidence(con, n, query, top):
    """Share of the query's distinctive weight (IDF) that the best of the top-3 results actually contains."""
    words = _words(query)
    if not words or not top: return 0.0
    idf = {}
    for w in set(words):
        df = con.execute("SELECT count(*) FROM docs_fts WHERE docs_fts MATCH ?", ('"%s"' % w,)).fetchone()[0]
        idf[w] = math.log((n + 1) / (df + 1))
    total = sum(idf.values()) or 1
    best = 0.0
    for row in top:
        body = con.execute("SELECT title || ' ' || content FROM docs WHERE id=?", (row[0],)).fetchone()[0].lower()
        got = sum(v for w, v in idf.items() if re.search(r"\b" + re.escape(w[:max(4, len(w) - 2)]), body))
        best = max(best, got / total)
    return best


def search(args):
    t0 = time.time()
    con = connect()
    ref = re.compile(config()["reference_paths"] or r"(?!x)x")
    n = con.execute("SELECT count(*) FROM docs").fetchone()[0]
    last = con.execute("SELECT max(watermark) FROM ingest_state WHERE key='__last_run__'").fetchone()[0]
    match = fts_query(args.query)
    if not match:
        print("empty query"); return
    now = datetime.now(timezone.utc)
    scores, rows, rawbest = {}, {}, {}
    # two ranked lists (item headers/summaries, and raw chunks at half weight), merged by reciprocal rank fusion
    for raw, weight in ((False, 1.0), (True, 0.5)):
        seen, rank = set(), 0
        for row in run(con, match, raw, args, 200):
            key = (row[2], row[3])  # one hit per original item
            if key in seen: continue
            seen.add(key); rank += 1
            scores[key] = scores.get(key, 0) + weight / (60 + rank)
            if key not in rows or not raw: rows[key] = row
            if raw and key not in rawbest: rawbest[key] = row
    if not args.plain:
        # a short note IS its own raw text: give it the raw-list credit too, or long docs always outrank it
        for key, row in rows.items():
            if key not in rawbest and row[1] in ("note", "thread"):
                scores[key] *= 1.5
    out = []
    for key, s in scores.items():
        row = rows[key]
        try:
            age = max(0, (now - datetime.fromisoformat(row[4].replace("Z", "+00:00"))).days)
        except Exception:
            age = 3650
        s *= 1 + 0.5 * math.exp(-age / 180)  # recency bonus
        if row[7]: s *= 0.5
        if not args.plain:
            row = rawbest.get(key, row)  # evidence = the best raw chunk (what actually happened)
            if ref.search(json.loads(row[6] or "{}").get("path", "")): s *= 0.4  # reference libraries rank below your own work
        out.append((s, row))
    out.sort(key=lambda x: -x[0])
    conf = confidence(con, n, args.query, [r for _, r in out[:3]])
    ms = (time.time() - t0) * 1000
    if args.json:
        res = []
        for sc, row in out[: args.limit]:
            body = con.execute("SELECT content FROM docs WHERE id=?", (row[0],)).fetchone()[0]
            res.append({"score": sc, "id": row[0], "kind": row[1], "source": row[2], "source_id": row[3], "ts": row[4],
                        "title": row[5], "meta": json.loads(row[6] or "{}"), "snippet": row[9], "content": body})
        print(json.dumps({"ms": ms, "rows": n, "conf": conf, "results": res})); return
    print(f"# kb: {n} rows | last refresh: {last or 'never'} | {ms:.0f} ms | match strength {conf:.2f}")
    if n == 0:
        print("# EMPTY: nothing indexed yet. Run: python3 " + os.path.join(HERE, "ingest_all.py"))
    elif conf < LOW_CONF:
        print("# LOW CONFIDENCE: the top results miss most of your distinctive words. "
              "The answer may not exist here; try other words.")
    for s, row in out[: args.limit]:
        meta = json.loads(row[6] or "{}")
        ptr = meta.get("path") or meta.get("url") or ""
        print(f"\n[{row[4][:10]}] {row[2]} · {meta.get('domain','')} · {row[5]}")
        print("  " + re.sub(r"\s+", " ", row[9])[:300])
        print("  -> " + ptr + (f" (line {meta['line']})" if meta.get("line") else ""))


def recent(args):
    """Newest items first (one per original item): what arrived or changed lately."""
    con = connect()
    since = datetime.fromtimestamp(time.time() - args.hours * 3600, timezone.utc).isoformat(timespec="seconds")
    sql = "SELECT source, ts, title, content, metadata FROM docs WHERE kind != 'raw' AND kind != 'summary' AND ts >= ?"
    params = [since]
    if args.source: sql += " AND source = ?"; params.append(args.source)
    sql += " ORDER BY ts DESC LIMIT ?"; params.append(args.limit)
    rows = con.execute(sql, params).fetchall()
    print(f"# {len(rows)} items since {since[:16]}Z" + (f" from {args.source}" if args.source else ""))
    for src, ts, title, content, meta in rows:
        meta = json.loads(meta or "{}")
        body = re.sub(r"\s+", " ", re.sub(r"(?m)^(SUBJECT|FROM|LATEST)\b.*$", "", content))[:240]
        tag = f" · kept: {meta['why']}" if meta.get("why") else ""
        if meta.get("last_from"):  # who holds the ball
            robot = meta.get("bulk") or meta.get("why") == "allow" or re.match(
                r"(no-?reply|do-?not-?reply|donotreply|notify|notifications?|alerts?|service)\b", meta["last_from"])
            tag += (" · you sent last" if meta["last_from"] == "me" else f" · last from {meta['last_from']}" if robot
                    else f" · REPLY WAITING from {meta['last_from']}") + f" · {meta.get('msgs')} msgs"
        print(f"\n[{ts[:16]}] {src} · {meta.get('domain','')}{tag} · {title}\n  {body}\n  -> {meta.get('path','')}")


def stats(_):
    con = connect()
    last = con.execute("SELECT max(watermark) FROM ingest_state WHERE key='__last_run__'").fetchone()[0]
    print(f"project: {ROOT}\ndb: {DB} ({os.path.getsize(DB)/1e6:.1f} MB) | last refresh: {last or 'never'}")
    for r in con.execute("SELECT source, kind, count(*), min(ts), max(ts) FROM docs GROUP BY 1,2 ORDER BY 1,2"):
        print("  %-10s %-8s %7d  %s → %s" % (r[0], r[1], r[2], (r[3] or "")[:10], (r[4] or "")[:10]))


def setup(_):
    os.makedirs(DATA, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        json.dump(DEFAULTS, open(CONFIG_PATH, "w"), indent=2)
        print("wrote", CONFIG_PATH)
    connect().close()
    os.makedirs(os.path.join(ROOT, config()["notes_dir"]), exist_ok=True)
    gi = os.path.join(ROOT, ".gitignore")
    lines = open(gi).read().splitlines() if os.path.exists(gi) else []
    if not any(l.strip().rstrip("/") in (".kb", "/.kb") for l in lines):
        with open(gi, "a") as f:
            f.write(("\n" if lines and lines[-1] else "") + "# knowledge base: local index of notes + Claude sessions (private)\n.kb/\n")
        print("added .kb/ to", gi)
    print(f"ok. project: {ROOT}\nnext: python3 {os.path.join(HERE, 'ingest_all.py')}")


def note(args):
    folder = os.path.join(ROOT, config()["notes_dir"])
    os.makedirs(folder, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-")[:60] or "note"
    path = os.path.join(folder, f"{datetime.now():%Y-%m-%d}-{slug}.md")
    with open(path, "a") as f:
        f.write(f"# {args.title}\n\n{args.text.strip()}\n\n_Captured {datetime.now():%Y-%m-%d %H:%M}. "
                "Inbox: move to its real home at the weekly review._\n")
    print("saved", path, "(searchable after the next refresh: ingest_all.py --only files)")


def main():
    p = argparse.ArgumentParser(description="Local knowledge base over your notes and Claude Code sessions.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup"); sub.add_parser("init"); sub.add_parser("stats")
    r = sub.add_parser("recent")
    r.add_argument("--source"); r.add_argument("--hours", type=float, default=36); r.add_argument("--limit", type=int, default=40)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--after"); s.add_argument("--source"); s.add_argument("--domain")
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--json", action="store_true")
    s.add_argument("--plain", action="store_true", help="plain ranking, no tunings (for comparison)")
    nt = sub.add_parser("note"); nt.add_argument("title"); nt.add_argument("text")
    a = p.parse_args()
    if a.cmd in ("setup", "init"): setup(a)
    elif a.cmd == "stats": stats(a)
    elif a.cmd == "recent": recent(a)
    elif a.cmd == "note": note(a)
    else: search(a)


if __name__ == "__main__":
    main()
