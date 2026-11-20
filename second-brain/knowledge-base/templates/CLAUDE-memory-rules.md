## Knowledge base and memory (search first, files second)

Before hunting through files with grep/glob for a fact that probably exists in this project or in a past session, search the knowledge base:

```bash
python3 .claude/skills/knowledge-base/scripts/kb.py search "<question>"                     # notes + every past Claude session + summaries
python3 .claude/skills/knowledge-base/scripts/kb.py search "<q>" --source sessions          # only past conversations ("what did we decide…")
python3 .claude/skills/knowledge-base/scripts/kb.py note "Title" "text"                     # quick capture into the notes inbox
```

Rules:
- **Search first, open the pointed-to file second.** A result is a pointer, not proof. Read the file or session it points to before acting.
- **`LOW CONFIDENCE` in the header means the answer is probably not here.** Say so plainly; never guess. Try other words once, then ask.
- **Newer beats older.** When two results disagree, trust the more recent one and mention the conflict.

**Where facts live: one fact, one home.** The index points to homes; it is never a home itself.
- Durable facts about a topic, client or product → that topic's own folder (its canonical file). Update it in place; don't create a second copy.
- Goals, priorities, principles → one goals file only. Everything else reads it, never copies it.
- Session state (what's in progress, open loops, what's next) → one session log.
- Claude's own working memory (who the user is, how they like to work) → Claude Code's memory files.
- Quick captures with no obvious home yet → `notes/` (the **capture inbox**). At the weekly review, move each note to its real home, then delete it from the inbox.

The index refreshes by itself every 6 hours. After a big change, refresh now: `python3 .claude/skills/knowledge-base/scripts/ingest_all.py`.
