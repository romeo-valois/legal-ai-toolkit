# Knowledge Base for Claude Code

A local search box over everything your Claude Code project knows: every note and doc in the folder, and every past Claude conversation, with a short summary of each one. There's an optional add-on for the email that matters. Ask "what did we decide about X?" and Claude finds it in about half a second instead of grepping around or guessing.

Think of it as Google for your own project's memory, running privately on your machine.

The design follows Nick Saraev's personal knowledge-base prompt (SQLite + full-text search + connectors), tuned and benchmarked on a real working codebase.

## What you get

- **Search** over notes, docs and past sessions. Ranking favours recent items and your own work over reference material.
- **An honesty check.** When the best results miss most of your words, the search says `LOW CONFIDENCE`, so Claude says "not here" instead of making something up.
- **Session summaries.** Each finished Claude session gets a short summary (goal, decisions, facts, open items), made by Claude Haiku through your normal Claude login.
- **Long-term memory.** Claude Code deletes old session files after 30 days by default. The index keeps their text, at about 1% of the size.
- **Auto-refresh** every 6 hours. It only re-reads what changed.
- **Memory rules** for your `CLAUDE.md`: search first, open the file second; one fact, one home; a `notes/` inbox for quick captures.
- **Safety.** Anything that looks like an API key or password is masked before it's stored. The index lives in `.kb/`, which is git-ignored.

## Install

You need Python 3.8+ (macOS and most Linux systems already have it) and Claude Code. Nothing to `pip install`.

1. Copy the `knowledge-base` folder into your project at `.claude/skills/knowledge-base`:
   ```bash
   git clone https://github.com/romeo-valois/legal-ai-toolkit /tmp/lat
   mkdir -p .claude/skills && cp -R /tmp/lat/second-brain/knowledge-base .claude/skills/
   ```
2. Open Claude Code in your project and say: **"Install the knowledge base skill."**

Claude walks through setup with you. It builds the index, runs a test search, and asks before each optional step: summaries, the memory rules in `CLAUDE.md`, and the 6-hour auto-refresh.

Prefer to do it by hand?
```bash
python3 .claude/skills/knowledge-base/scripts/kb.py setup
python3 .claude/skills/knowledge-base/scripts/ingest_all.py
python3 .claude/skills/knowledge-base/scripts/kb.py search "something you worked on"
bash    .claude/skills/knowledge-base/scripts/schedule.sh install     # optional auto-refresh
```

## Everyday use

You mostly don't run anything. Once the memory rules are in `CLAUDE.md`, Claude searches by itself. You can also ask directly: "search the knowledge base for the pricing decision", or "what did we do last week about the login bug?"

```bash
kb.py search "query" [--source files|sessions|gmail] [--after 2026-01-01] [--domain NAME] [--limit 10]
kb.py recent --hours 48      # what changed lately
kb.py note "Title" "text"    # quick capture into notes/
kb.py stats                  # what's indexed
```

## How it works

| Piece | Job |
|---|---|
| `scripts/kb.py` | The database and search: SQLite FTS5, BM25 over item summaries and raw chunks, merged by reciprocal rank fusion, plus a recency bonus |
| `scripts/connectors.py` | One reader per source (`files`, `sessions`, `gmail`). Each reads only what changed, dates every row and keeps a pointer to the original |
| `scripts/summarize.py` | Sends each finished session (idle 2+ hours) to Haiku via `claude -p`, with no tools and no session saved. The transcript is treated as data, never as instructions |
| `scripts/ingest_all.py` | Runs everything. If one source fails, the rest still run. Log: `.kb/ingest.log` |
| `scripts/schedule.sh` | Turns the 6-hourly refresh on or off (launchd on macOS, cron line on Linux) |
| `templates/CLAUDE-memory-rules.md` | The habits block for your `CLAUDE.md` |

**Privacy.** Files, sessions and email stay on your machine. The only thing sent anywhere is session text for summaries, which goes to Claude the same way your normal Claude Code use does. Turn it off with `"summaries": false` in `.kb/config.json`. Email is never summarized and never leaves the machine.

## Email add-on (optional)

This adds your important Gmail threads to the search, read-only. It's off unless you set it up.

1. Install and log in to the `gws` Google Workspace CLI (`npm install -g @googleworkspace/cli`) with Gmail read access.
2. `cp .claude/skills/knowledge-base/templates/gmail.example.json .kb/gmail.json` and put your address under `accounts`.
3. Run `python3 .claude/skills/knowledge-base/scripts/ingest_all.py --only gmail`.

What gets in: threads you wrote in, mail from people you've emailed, senders on the allow list (banks, payments, scheduling…), and personal Primary-tab mail. Kept out: newsletters and notifications, login/2FA codes, and anything matching `never_store` (legal mail by default). The first run reads 180 days; after that, only changes.

## Credits

The architecture comes from Nick Saraev's personal knowledge-base prompt. The ranking tunings were added after a head-to-head benchmark: best raw chunk shown as evidence, reference material ranked lower, a boost for short notes, and the low-confidence flag.
