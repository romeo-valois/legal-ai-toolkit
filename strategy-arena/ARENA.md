---
name: strategy-arena
description: Multi-agent competitive strategy simulation. Multiple legal strategists independently propose approaches to a decision, get red-teamed by simulated opposing counsel, revise, pass fact-check gate, then get scored by a judicial evaluator. Produces an evolved best-of-breed strategy. Use when facing any significant strategic decision in a litigation matter.
scripts:
  - tools/verify_citations.py
---

# Directive: Strategy Arena

## Origin

Adapted from two systems:
- **[Karpathy's autoresearch](https://github.com/karpathy/autoresearch):** Hypothesis → execute → evaluate → keep/discard → loop. Single-metric iterative refinement.
- **Competitive multi-agent copywriting arenas:** Multiple independent AI agents with distinct methodologies compete in rounds. A judge evaluates. Losers learn from winners. System evolves.

**Our adaptation:** Multiple legal strategists with distinct philosophies propose approaches to a litigation decision. Simulated opposing counsel attacks each one. Strategists revise. Fact-check gate filters. Judicial evaluator scores. Best elements synthesized. System learns.

## Execution Model

**This directive runs natively inside Claude Code.** No external API calls. The agent plays each role sequentially within a single session, maintaining strict separation between roles.

**Critical constraint:** When playing a role (strategist, red team, judge), the agent commits fully to that role's perspective and does NOT bleed insights from other roles. The Litigator does not know what The Methodical will say. The Red Team does not soften attacks because it also played a strategist. The Judge does not favor the strategy it found most intellectually interesting.

## When to Use

- **Major strategic decisions:** Which tracks to pursue, in what order, with what timing
- **Filing decisions:** Whether to file, what to file, when to file
- **Settlement vs. litigation:** Whether to negotiate or litigate a specific track
- **Resource allocation:** Where to invest limited time and lawyer access
- **Any decision that is hard to reverse** (filing, withdrawing, settling, waiving a right)

**Do NOT use for:**
- Individual document refinement
- Stress-testing a single draft
- Pure research questions
- Evidence gathering

## Inputs

The arena requires a **Brief** — a structured description of the decision to be made.

### Brief Template

```markdown
## Arena Brief — [Decision Name]

### Decision
[What specific decision needs to be made? One sentence.]

### Context
[What's the current situation? What has happened? What's the state of the relevant tracks?]

### Constraints
- Prescription deadlines: [list any approaching deadlines]
- Budget/resources: [what's available]
- Lawyer status: [retained or not, availability]
- Court posture: [any existing orders, condemnations, judicial signals]
- Self-represented context: [relevant limitations]

### Objectives
[What does the client actually want? Not just "win": what outcome serves their interests?]
1. [Primary objective]
2. [Secondary objective]
3. [Tertiary objective]

### Tracks in Play
[Which tracks are relevant to this decision? Current status of each.]

### Known Dependencies
[Any sequencing constraints, e.g., suing former counsel before disavowing their procedural act = ratification risk]

### Opposing Counsel Profile (Required — feeds the Red Team)
- Name / firm: [opposing counsel]
- Represents: [party or parties]
- Prior wins or adverse findings against the client: [e.g., abuse-of-process condemnation, costs award]
- Known constraints: [conflicts, fiduciary roles of their clients, standing gaps, budget]
- Judicial signals they must answer: [e.g., a paragraph in a prior judgment]

### Jurisdiction
[Court and governing law, e.g., Quebec Superior Court, CCQ / CCP]

### Party Map (Required)
| Party | Represents | Tracks Involving This Party | Correct Recipient For |
|-------|-----------|---------------------------|---------------------|
| [name] | [who they are] | [T#, T#] | [what demands/filings go to this party] |
| [name] | [who] | [T#] | [what] |

### Brief Self-Validation (Required)
- [ ] **Temporal validity:** For each document described as "ready" or "complete," is it still valid and appropriate to use TODAY (not just at some prior date)? If any document was drafted for a specific deadline or context that has since passed, flag it as STALE with the reason.
- [ ] **Delta integrity (sequential matches only):** For each item listed under "What Changed Since Last Match," verify it was NOT already true during the prior match. If it was, recategorize as "Previously Omitted" (not "Changed").
- [ ] **Party-action mapping:** Every proposed action in the brief that involves sending something to a party specifies the recipient and confirms they are the correct party.

### Fact-Check Gate (Decision-Specific)
[Binary checks that MUST pass before any strategy is scored]
- [ ] [Check 1: e.g., "Prescription for claim X correctly calculated from date Y"]
- [ ] [Check 2: e.g., "Former counsel's mandate date verified against the signed mandate"]
- [ ] [Check 3: ...]
- [ ] [Check 4: ...]
```

## Phase Flow

```
PHASE 0: BRIEF
    User provides or agent drafts the brief for user approval.
    Brief must include Party Map and Brief Self-Validation.
    Brief must be approved before proceeding.
    |
    v
PHASE 0.5: BRIEF VALIDATION
    Run Brief Self-Validation checklist.
    Verify temporal validity, delta integrity, party-action mapping.
    Any failure = revise brief before proceeding.
    |
    v
PHASE 1: INDEPENDENT DRAFTING (4 strategists, parallel)
    Each strategist reads: brief + their own philosophy file + relevant track data.
    Each produces a strategy proposal with Action-Recipient Map.
    Synthesis does NOT compete in Round 1.
    |
    v
PHASE 1.5: COHERENCE SCREEN
    For each strategy, verify party-action match, internal consistency,
    and temporal validity against the Brief's Party Map.
    Failures flagged for correction BEFORE Red Team review.
    |
    v
PHASE 2: RED TEAM (parallel)
    Red Team reads all 4 strategies.
    Produces a Vulnerability Report for each.
    Identifies systemic blind spots (shared across all strategies).
    |
    v
PHASE 3: REVISION (4 strategists, parallel)
    Each strategist receives ONLY their own Vulnerability Report.
    Revises their strategy to address vulnerabilities.
    Cannot see other strategists' reports or revisions.
    |
    v
PHASE 3.25: CITATION VERIFICATION
    Run verify_citations.py on each revised strategy.
    Any NOT FOUND citation = flagged for correction before fact-check gate.
    |
    v
PHASE 3.5: FACT-CHECK GATE
    Each revised strategy checked against the Brief's fact-check items.
    FAIL = REJECTED. Does not proceed to judgment.
    |
    v
PHASE 4: JUDGMENT
    Judicial Evaluator scores all passing strategies.
    Produces ranking, scoring matrix, differential analysis.
    Provides individual feedback to each strategist.
    |
    v
PHASE 5: LEARNING & SYNTHESIS
    If Round 1: Synthesis enters for Round 2 using all strategies + feedback.
    All strategists receive winner feedback + their own feedback.
    System learnings logged.
    |
    v
[ROUND 2+: Repeat from Phase 1 with learnings integrated]
    Synthesis competes from Round 2 onward.
    Continue until: user stops, or diminishing returns (< 3% improvement between rounds).
```

## Agent Execution Steps

### Phase 0: Brief

1. If the user provides a decision, draft a brief using the template above
2. Present brief to user for review and approval
3. User may add, modify, or remove fact-check gate items
4. **Do not proceed until the user approves the brief**

### Phase 0.5: Brief Validation

After drafting the brief and before user approval:

1. Run the **Brief Self-Validation** checklist embedded in the brief:
   - **Temporal validity:** For each document described as "ready" or "complete," verify it is still valid and appropriate to use as of today's date. If a document was drafted for a specific deadline or context that has since passed, mark it STALE in the brief with the reason.
   - **Delta integrity (sequential matches only):** For each item in "What Changed Since Last Match," verify it was NOT already true during the prior match. If it was an omission, recategorize honestly as "CORRECTION — previously omitted" (not "CHANGE").
   - **Party-action mapping:** Cross-reference the Party Map. Every action mentioned in the brief must target the correct party.

2. If any validation fails, revise the brief before presenting to the user.

3. **Sequential Match Protocol:** When a match carries forward results from a prior match:
   - **No free passes.** Prior consensus is a HYPOTHESIS, not a FACT. Every carried-forward item must be re-verified against the Party Map and current state of facts.
   - **Carry-forward validation table (required in brief):**
     | # | Prior Consensus Item | Still Valid? | Verification |
     |---|---------------------|-------------|--------------|
     | 1 | [item] | YES/NO/MODIFIED | [how verified — not "per Match 001" but actual verification] |
   - **Delta claims must be substantiated.** Every item in "What Changed" must include: when it became true (specific date/event), why it wasn't in the prior match (new event vs. omission), and if it was an omission, flag it honestly as "CORRECTION."

### Phase 1: Independent Drafting

For each strategist (Litigator, Negotiator, Methodical, Opportunist):

1. Read the strategist's philosophy file from `strategists/`
2. Read the brief
3. Read relevant track data (track directories, evidence dossiers, research memos)
4. **Adopt the strategist's perspective fully** — think as they would think
5. Produce a strategy proposal following this structure:

```markdown
## [Strategist Name] — Strategy Proposal — Round [N]

### Theory of the Case
[2-3 sentences: what is this case really about, from this strategist's perspective?]

### Recommended Actions (Sequenced)
1. [Action] — [Timeline] — [Why this order]
2. [Action] — [Timeline] — [Why]
3. ...

### Tracks: Pursue / Defer / Abandon
| Track | Recommendation | Reasoning |
|-------|---------------|-----------|
| T1 | Pursue/Defer/Abandon | [why] |
| T2 | ... | ... |
| ... | ... | ... |

### Key Dependencies
[What must happen before what? What breaks if the order changes?]

### Risk Assessment
[Top 3 risks of this strategy and how they're mitigated]

### Expected Outcome (12 months)
[What does the client's position look like if this strategy is executed well?]

### Action-Recipient Map (Required)
| Action | Recipient | Why This Recipient | Track |
|--------|-----------|-------------------|-------|
| [demand/filing/notice] | [specific person or counsel] | [legal basis for targeting this party] | [T#] |

### What I'm Sacrificing
[What am I giving up by choosing this approach? Every strategy has tradeoffs — name them.]
```

**Present each strategy to the user as it's produced.** The user can see the competition developing.

### Phase 1.5: Coherence Screen

Before Red Team attacks, run this checklist against each strategy:

1. **Party-action match:** For every proposed action (demand, filing, notice), verify:
   - Is the recipient the correct party? (Cross-reference the Brief's Party Map)
   - Does the recipient have standing/relevance to the claim?
   - If sending to counsel, does that counsel represent the relevant party?

2. **Internal consistency:** Does the strategy contradict information in the brief?
   - Brief says X, strategy proposes Y that assumes not-X

3. **Temporal validity:** Does the strategy assume a deadline, document state, or fact that was true at some point but is no longer true as of the brief date?

Any failure = flagged for the strategist to correct BEFORE Red Team review. This is not a rejection gate — it's a correction gate. The strategist revises the flagged element, then the corrected strategy proceeds to Phase 2.

### Phase 2: Red Team

1. Read `red-team.md` and the brief's Opposing Counsel Profile
2. Read ALL four strategy proposals
3. **Adopt opposing counsel's perspective fully**
4. Produce a Vulnerability Report for each strategy (per the Red Team output format)
5. After all four reports, produce a **Systemic Blind Spot Analysis:**

```markdown
## Systemic Blind Spots — Round [N]

### Vulnerabilities Shared by ALL Strategies
[These are the most important findings — if everyone missed it, the arena hasn't solved it]

### Vulnerabilities Shared by 3 of 4
[Almost-universal gaps]

### Unique Vulnerabilities (Strategy-Specific)
[Only one strategy has this problem — and only one strategy solved it]
```

### Phase 3: Revision

For each strategist:
1. Re-read their philosophy file
2. Read their original strategy
3. Read ONLY their own Vulnerability Report (not other strategies' reports)
4. Revise the strategy to address the vulnerabilities
5. Mark what changed and why

### Phase 3.25: Citation Verification

For each revised strategy that cites case law:

1. Write the strategy text to a temp file (`.tmp/arena-strategy-[name].md`)
2. Run: `python3 tools/verify_citations.py .tmp/arena-strategy-[name].md`
3. Review the verification report:
   - **All VERIFIED:** Proceed to Phase 3.5
   - **Any NOT FOUND:** Flag the citation. The strategist must either correct it or remove it. A strategy citing a non-existent case cannot proceed.
   - **Any WARNING (title mismatch, year mismatch):** Note for the fact-check gate but do not block.
4. Record verification results — the Judicial Evaluator receives these as part of the scoring package.

**Rate limit note:** The CanLII API allows 2 req/s and 5000/day. The script handles rate limiting internally. For 4 strategies with ~5 citations each, expect ~1-2 minutes total.

### Phase 3.5: Fact-Check Gate

For each revised strategy, run through every item in the Brief's fact-check gate:
- Check against actual source documents (use Read, Grep, Glob)
- **PASS:** All checks verified against sources
- **FAIL:** Any check fails → strategy is REJECTED with explanation of which check failed and why
- Record gate results for the Judicial Evaluator

### Phase 4: Judgment

1. Read `judicial-evaluator.md`
2. Read all passing strategies (not the rejected ones)
3. **Blind read first** — form impressions without attribution
4. Score each strategy on the 6 criteria (weighted)
5. Produce the full judgment output (scoring matrix, ranking, differentials, feedback)
6. Present to user

### Phase 5: Learning & Synthesis

1. Log the round results to `templates/arena-log.md`:

```markdown
## Arena Match [N] — [Decision Name] — [Date]

### Round [N] Results
| Rank | Strategist | Score | Key Strength | Key Weakness |
|------|-----------|-------|-------------|-------------|
| 1 | [name] | X% | [strength] | [weakness] |
| ... | ... | ... | ... | ... |

### Systemic Blind Spots
[what the Red Team found that all strategies missed]

### Key Learning
[the single most important insight from this round]
```

2. If proceeding to Round 2+:
   - Synthesis reads all strategies + all feedback + all red team reports
   - Synthesis produces its strategy (per its philosophy file)
   - All four original strategists receive their feedback and revise
   - Repeat Phases 1-4

3. **Stopping conditions:**
   - User says stop
   - Less than 3% improvement in top score between rounds
   - Maximum 3 rounds (diminishing returns beyond this)

### Final Output

After the final round:

```markdown
## Arena Result — [Decision Name] — [Date]

### Winning Strategy: [Strategist Name]
[Full strategy proposal — the version that won]

### Runner-Up: [Strategist Name] (+/- X%)
[The key element from this strategy that the winner should incorporate]

### Consensus Moves
[Actions that ALL strategies agreed on — highest confidence]

### Contested Decisions
[Points where strategies diverged — these are the real decisions the client needs to make]

### Systemic Risks
[Risks that survived all rounds — the arena couldn't solve these; they need human judgment]

### Recommendation to Client
[3-5 sentences integrating the arena results into a clear recommendation]
```

## Relationship to Other Directives

```
/strategy-arena (this directive — competitive strategy simulation)
    |
    v
Lead strategist integrates arena result into recommendation
    |
    v
Client decides
    |
    v
Draft and refine the documents the chosen strategy requires
    |
    v
Stress-test each filing from both sides and the bench
    |
    v
Human lawyer review (required before filing)
    |
    v
File / Send
```

The arena operates at **strategic altitude** — it decides WHAT to do. Drafting and document review operate at **document altitude** — they improve HOW it's written.

## Constraints

- The arena does not replace lawyer review. It produces a recommended strategy for the lawyer to evaluate.
- Original source documents are READ-ONLY. The arena never edits evidence.
- If the client is self-represented, that context must be factored into every strategy (judges apply different standards).
- Any prior adverse finding recorded in the brief must be addressed by every strategy (not ignored).
- Maximum 3 rounds per arena match. Diminishing returns are real.
- The user can stop the arena at any phase. Partial results are still valuable.
- **Fact-check failures are non-negotiable.** A strategy that fails the gate is rejected regardless of how compelling it is.

## Evolution

### Win Records

After each arena match, update `templates/win-records.md`:

```markdown
| Match | Date | Decision | Winner | Runner-Up | Rounds | Key Learning |
|-------|------|----------|--------|-----------|--------|-------------|
| 1 | [date] | [decision] | [name] | [name] | [N] | [learning] |
```

Over time, this reveals which strategist wins in which context. "The Methodical wins when sequencing dependencies are present." "The Opportunist wins when timing windows are short."

### Strategist Evolution

After every 3 arena matches, review win records and identify:
- Strategists that consistently lose in certain contexts → update their philosophy to address the gap
- Strategists that consistently win → identify what makes them win and test whether that element helps others
- New patterns that no existing strategist captures → candidate for a new strategist file

### Synthesis Spawning

If Synthesis wins all rounds of a match, log the combination ratios. If Synthesis wins all rounds of 2+ matches with a similar combination, propose codifying it as a new permanent strategist.
