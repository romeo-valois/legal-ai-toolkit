---
name: fact-change-propagation
description: Automatic checks on every draft edit (stale facts, soft gate statuses, deadlines within 14 days) plus the 6-step protocol for when a fact changes, so a corrected date or amount never survives in some other memo or draft. Use when any factual value (date, amount, party role, article, file number) is corrected.
---

# Fact and deadline checks

Two parts:
1. **Hooks** that run by themselves every time Claude writes or edits a file (warnings, never blocks).
2. **A 6-step protocol** Claude follows when a fact changes.

## Why

A corrected date gets fixed in the file you're working on, and stays wrong in the three memos and the draft that quoted it. In a file that runs for months, that drift compounds. The hooks catch it at write time; the protocol fixes it everywhere.

## Install the hooks

1. Copy `hooks/` into your project at `.claude/hooks/`.
2. Copy `config/` samples into your project's `config/` and fill them in.
3. Add to `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/dispatch-validator.sh\"" }
        ]
      }
    ]
  }
}
```

By default only paths matching `(matters/|drafts/|output/)` are checked. Change `WATCH_PATTERN` in `dispatch-validator.sh` to fit your layout.

| Validator | What it flags |
|---|---|
| `fact_change_validator.py` | The file still contains an `old_value` from `config/fact-changes.yaml` whose propagation is `incomplete` or `deferred` |
| `gate_validator.py` | "Soft" statuses like CONDITIONAL_PASS or PASS_WITH_CAVEATS (a gate is PASS or FAIL, nothing in between) |
| `deadline_validator.py` | An open deadline within 14 days on the matter whose folder is being edited (from `config/deadlines.json`) |

## The 6-step protocol

**Triggers:** a source document shows a different value than the workspace files; the client corrects a fact; research shows the current value is wrong; a new document (email, judgment, transcript) changes a known fact.

**Counts as a fact:** dates, amounts, party roles, article numbers, addresses, contact details, file numbers, prescription and procedural deadlines, witness statements, who wrote which document.

### 1. Identify the change
```
FACT CHANGE DETECTED:
  Field:      [what changed]
  Old value:  [exact]
  New value:  [exact]
  Source:     [document / client correction / research]
  Authority:  [which source is canonical]
```

### 2. Search everything
Search the whole workspace (every matter folder, outputs, config, timelines, Claude's memory files) for the old value. Show the full list before touching anything:
```
PROPAGATION REQUIRED: [N] files contain "[old value]"
  1. path:line - "context"
  2. ...
```

### 3. Update, mark or defer each file
| Action | When |
|---|---|
| **Update** | Active file that downstream work reads |
| **Mark superseded** | Historical or archived file: add `[SUPERSEDED - see FC-XXX]` |
| **Defer** | File will be regenerated soon. Logged; the validator re-checks on the next write |

### 4. Log it in `config/fact-changes.yaml`
See `config/fact-changes.example.yaml`.

### 5. Update any shared-facts map
If you keep a map of facts shared between matters or proceedings, update the canonical source there too.

### 6. Gate
**Blocking.** No downstream work until every file is updated, marked or explicitly deferred with a reason, and the log entry has a `propagation_status`. If it can't be completed (too many files, ambiguous context), stop and ask the lawyer.

## Anti-patterns

1. Silently updating files. Always show the list first.
2. Skipping propagation because "the file will be regenerated." Log it as deferred.
3. Updating only nearby files. Drift travels through chains: search everything.
4. Treating it as optional. A stale fact in a legal document is a liability.
