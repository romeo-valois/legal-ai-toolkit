---
name: knowledge-base
description: A local search over everything this project knows - every note and doc in the folder plus every past Claude Code session (with a short summary of each), optionally your important email. Use it to look up a fact, a past decision, or "what did we do about X" before grepping files, and to install or maintain the knowledge base. Triggers on "search the knowledge base", "what did we decide about", "did we already", "find where we", "remember this", "set up the knowledge base", "install kb", "refresh the index".
---

# Knowledge base

One local search box (SQLite + full-text search, on this machine) over:
- every `.md` / `.txt` file in this project,
- every Claude Code session for this project: what the user asked, what Claude did, what tools returned, plus a short summary of each finished session,
- (optional add-on) the email that matters, read-only.

All commands below run from the project root. `KB` means `python3 .claude/skills/knowledge-base/scripts/kb.py`.

## Searching (the everyday job)

```bash
KB search "what did we decide about pricing"
KB search "stripe webhook" --source sessions            # only past conversations
KB search "invoice" --source gmail --after 2026-01-01    # only email (if the add-on is on)
KB search "launch plan" --domain docs --limit 10        # domain = top-level folder name
KB recent --hours 48                                     # what changed lately, newest first
KB stats                                                 # what's indexed, last refresh
```

How to read results:
1. **Check the header first.** `match strength` is the share of your distinctive words found in the best result. Below 0.5 it prints `LOW CONFIDENCE`: the answer is probably not here. Say so; don't guess. Try different words once.
2. Each hit shows `[date] source · domain · title`, a snippet with matched words in `[brackets]`, and `->` a pointer (file + line, session file, or Gmail link).
3. **Open the pointer before acting.** A snippet is evidence that something exists, not the full story.
4. When results disagree, the newer one usually wins. Say which you trusted.

Saving a quick fact: `KB note "Title" "the fact"` writes `notes/<date>-<title>.md`. It's searchable after the next refresh (`ingest_all.py --only files`).

## Installing (first time in a project)

Do these in order and tell the user what each step does in plain words.

1. **Check Python.** `python3 --version` must be 3.8+ with SQLite FTS5 (it almost always is). Test: `python3 -c "import sqlite3; sqlite3.connect(':memory:').execute('create virtual table t using fts5(x)')"`.
2. **Set up.** `KB setup` creates `.kb/` (the database + `config.json`), creates `notes/`, and adds `.kb/` to `.gitignore` so the private index is never committed.
3. **First fill.** `python3 .claude/skills/knowledge-base/scripts/ingest_all.py --no-summaries`. This reads every note and past session (usually under a minute).
4. **Try it.** Run `KB stats`, then one real search about something the user worked on recently. Show them the result.
5. **Summaries (ask first).** The summary step sends each finished session's text to Claude (Haiku) through the user's own `claude` login, the same as normal Claude use. On a Pro/Max plan there's no extra bill. If they agree: `python3 .claude/skills/knowledge-base/scripts/summarize.py --limit 3` as a test, then run the full refresh. If they decline, set `"summaries": false` in `.kb/config.json`.
6. **Memory rules (ask first).** Offer to add `templates/CLAUDE-memory-rules.md` to the project's `CLAUDE.md`. That block teaches every future session to search first, respect LOW CONFIDENCE, and keep one fact in one home. Show them the block; append only on a yes.
7. **Auto-refresh (ask first).** `bash .claude/skills/knowledge-base/scripts/schedule.sh install` refreshes every 6 hours (macOS launchd; on Linux it prints a cron line). Undo: `schedule.sh uninstall`.
8. **Session retention (mention it).** Claude Code deletes old session files after `cleanupPeriodDays` (default 30) in `~/.claude/settings.json`. The index keeps their text after the files are gone, but only if a refresh ran first. Suggest raising it (e.g. `60`) if they refresh rarely.

Optional email add-on: see README.md > "Email add-on". Only set it up if the user asks.

## Settings (`.kb/config.json`)

| Key | Default | What it does |
|---|---|---|
| `sessions` | `"this-project"` | `"all"` = index sessions from every project on this machine; `"off"` = none |
| `skip_projects` | `[]` | Session folders to never index (substring match), e.g. `["legal", "personal"]` |
| `skip_paths` | `[]` | Project subfolders to never index, e.g. `["private/", "clients/secret"]` |
| `domains` | `{}` | Rename top-level folders as labels, e.g. `{"docs": "Docs", "src": "Code"}` |
| `reference_paths` | swipes, transcripts, references | Regex: matching files rank lower so your own work comes first |
| `extensions` | `.md`, `.txt` | File types to read |
| `summaries` / `summary_model` | `true` / `"haiku"` | Session summaries on/off, and which model |
| `notes_dir` | `"notes"` | The capture inbox |

Delete a row from the index: remove or exclude the file, then refresh. Start over: delete `.kb/kb.sqlite` and refresh.

## Troubleshooting

- `EMPTY` header: nothing indexed yet. Run `ingest_all.py`.
- Sessions show 0: Claude Code names the session folder after the project path. Run `ls ~/.claude/projects` and check that one matches this project's path, with every `/`, space and `.` turned into `-`.
- Summaries fail: run `claude -p "hi"` by hand. It needs to be logged in. `ANTHROPIC_API_KEY` is removed for the summary call on purpose, so it uses the subscription login.
- Log of every refresh: `.kb/ingest.log`.
