---
name: quality-gates
description: Strict PASS/FAIL checklists a document must clear before it leaves the workspace (court filings, demand letters, research memos, strategy documents, evidence dossiers), plus a workspace health audit that finds stale files, broken references, an overgrown memory file and deadline inconsistencies. Use before anything is filed or sent, and at the start of a work session.
---

# Quality gates and health audit

## Core principle

**Every gate is PASS or FAIL. Nothing in between.** No conditional pass, no partial pass, no "pass with caveats." If a condition is unmet, it's a FAIL. (The `gate_validator.py` hook in `fact-and-deadline-checks/` flags these soft statuses automatically.)

| Forbidden | Why |
|---|---|
| CONDITIONAL_PASS | Conditions remain, so FAIL |
| PARTIAL_PASS | Incomplete, so FAIL |
| PASS_WITH_CAVEATS | Unresolved, so FAIL |
| SOFT_PASS | No such thing |
| PROVISIONAL_PASS | Unverified, so FAIL |
| PASS_PENDING_REVIEW | The review hasn't happened, so FAIL |
| WAIVED | Only the lawyer or client can waive a gate, in writing, logged |

## Gates by document type

### 1. Court filings - FILING_READY
| # | Criterion | How to verify |
|---|---|---|
| 1 | Every citation verified | Citation checker: 100% hit rate (`strategy-arena/tools/verify_citations.py` for CanLII) |
| 2 | Language requirements met | Required language versions exist and match |
| 3 | Adversarial review passed | Stress test returns GO |
| 4 | Human review done | Lawyer sign-off recorded |
| 5 | Related proceedings checked | No sequencing conflict with another file or claim |
| 6 | Prescription and delays verified | Filing doesn't trigger, reset or miss a clock |
| 7 | Facts verified | Every factual claim traceable to a document in the evidence folder |

### 2. Demand letters (mises en demeure) - DEMAND_READY
| # | Criterion | How to verify |
|---|---|---|
| 1 | Facts verified | Every assertion traced to a source, cited inline |
| 2 | Recipient address confirmed | Cross-checked against the contact record |
| 3 | Tone reviewed | Firm, professional, nothing inflammatory |
| 4 | Adversarial review passed | GO |
| 5 | Human review done | Sign-off recorded |
| 6 | Sender details confirmed | Correct return address and signature block |
| 7 | Response deadline stated | Clear date |
| 8 | Related proceedings checked | No sequencing conflict |

### 3. Research memos - RESEARCH_COMPLETE
| # | Criterion | How to verify |
|---|---|---|
| 1 | Every citation verified | Checker or manual CanLII/SOQUIJ check |
| 2 | Counter-arguments addressed | At least one opposing argument analysed |
| 3 | Conclusion supported | Follows from the analysis |
| 4 | Jurisdiction confirmed | Governing law stated |
| 5 | No uncited factual claims | Cited or flagged "needs verification" |

### 4. Strategy documents - STRATEGY_VALIDATED
| # | Criterion | How to verify |
|---|---|---|
| 1 | Adversarial review passed | GO |
| 2 | Related proceedings checked | No conflicts |
| 3 | Delays verified | No deadline missed or triggered |
| 4 | Risk assessment included | At least one risk with a mitigation |
| 5 | Arena run for major decisions | `strategy-arena/` for anything hard to reverse |

### 5. Evidence dossiers - DOSSIER_COMPLETE
| # | Criterion | How to verify |
|---|---|---|
| 1 | Every item sourced | Traced to a file or a described source |
| 2 | Chain of custody | Who created it, how obtained, where stored |
| 3 | No unverified claims | Every statement backed by a reference |
| 4 | Gaps listed | Missing evidence named explicitly |

## Enforcement

Gate status lives in the document's front matter or the matter's state file:
```yaml
gates:
  FILING_READY:
    status: FAIL
    last_checked: 2026-01-15
    failures:
      - "Criterion 4: human review not done"
```

Workflow: a new draft starts at FAIL; the author runs the check; any FAIL keeps it in `drafts/`; all PASS moves it to `output/`; any later edit resets it to FAIL.

---

## Workspace health audit

`scripts/workspace_health_audit.py` is a lint check for the whole workspace. Run it at the start of a session, after a big restructure, and at least weekly.

```bash
python3 quality-gates/scripts/workspace_health_audit.py
# options via environment variables:
#   AUDIT_ROOT=/path/to/project      (default: current folder)
#   AUDIT_MEMORY_FILE=/path/MEMORY.md  (default: none, check skipped)
#   AUDIT_SCAN_DIRS="directives,matters,strategy"
```

Report: `.tmp/health-audit-report.md`

| Check | What it finds |
|---|---|
| File freshness | Files in the scanned folders untouched for 30+ days |
| Cross-references | Backtick paths and markdown links in `.md` files that point to files that don't exist |
| Memory file size | Claude Code's `MEMORY.md` index is truncated after 200 lines: WARNING at 150, CRITICAL at 180 |
| Deadlines | In `config/deadlines.json`: past-due items still marked active, and items due within 14 days |
| Directive freshness | Directives whose `last_validated` front-matter date is 30+ days old |

Severity: **CRITICAL** (fix now), **WARNING** (fix this session if possible), **INFO** (awareness).
