#!/usr/bin/env python3
"""Refresh the knowledge base: run every connector, then session summaries. One failing step is logged and the
rest continue. Safe to run any time; only what changed is re-read. Log: .kb/ingest.log

  ingest_all.py                 everything
  ingest_all.py --only files    just one connector (files, sessions, gmail), no summaries
  ingest_all.py --no-summaries  skip the summary step this run
"""
import os, subprocess, sys, time, traceback
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kb, connectors

LOG = os.path.join(kb.DATA, "ingest.log")


def log(msg):
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line)
    os.makedirs(kb.DATA, exist_ok=True)
    with open(LOG, "a") as f: f.write(line + "\n")


ONLY = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
con = kb.connect()
log(f"refresh {kb.ROOT}")
for name, fn in connectors.CONNECTORS.items():
    if ONLY and name not in ONLY: continue
    t0 = time.time()
    try:
        n, gone = fn(con)
        con.commit()
        log(f"{name}: {n} items updated, {gone} removed ({time.time()-t0:.1f}s)")
    except Exception:
        con.rollback()
        log(f"{name}: FAILED\n{traceback.format_exc()}")
if ONLY:  # a targeted refresh skips summaries and leaves the full-run stamp alone
    sys.exit(0)
if kb.config()["summaries"] and "--no-summaries" not in sys.argv:
    t0 = time.time()
    r = subprocess.run([sys.executable, os.path.join(HERE, "summarize.py")], capture_output=True, text=True)
    out = r.stdout.strip().splitlines()
    log(f"summaries: {(out or ['no output'])[-1]} ({time.time()-t0:.1f}s)"
        + "".join("\n  " + l for l in out if l.startswith("FAILED")) + (f"\n{r.stderr[-1500:]}" if r.returncode else ""))
con.execute("INSERT OR REPLACE INTO ingest_state VALUES ('_all','__last_run__',?)",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"),))
con.commit()
