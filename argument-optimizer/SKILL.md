---
name: argument-optimizer
description: Iterative refinement loop for legal documents (autoresearch pattern). Scores a draft on a 7-dimension rubric, rewrites it to fix the weakest dimension, scores again, keeps the winner, verifies every fact and citation, and logs what worked. Use when drafting or refining any substantive document that will be filed, sent or relied on.
---

# Argument Optimizer

## Origin

Adapted from [Karpathy's autoresearch](https://github.com/karpathy/autoresearch):
- **Original:** modify train.py, train 5 min, measure val_bpb, keep or discard, repeat
- **Here:** generate a variant draft, score it on a rubric, verify facts, keep or discard, log the learning, repeat

## Execution model

Runs natively inside Claude Code. No external API calls and no separate key. The agent does the scoring, the rewriting and the verification in the conversation with its normal tools (Read, Grep, Edit). The user sees every step and can stop at any iteration.

## Core loop

```
baseline draft
  -> score baseline on the 7-dimension rubric
  -> find the weakest dimension (weighted gap)
  -> write a challenger that fixes ONLY that dimension
  -> score the challenger
  -> keep the higher composite score
  -> (final iteration) verify every fact and citation
  -> log the learning
  -> present to the user
```

## When to use

- A response to opposing counsel
- A motion, application or factum
- A demand letter (mise en demeure)
- Any document that will be filed, sent or relied on

Suggest it when a draft was just created or substantially edited (see `hooks/suggest-optimizer.sh`), or when the user asks to finalize, send or file.

## Inputs

| Input | Description | Required |
|---|---|---|
| `draft_path` | Path to the baseline draft | Yes |
| `objective` | What the document must achieve (1-2 sentences) | Yes |
| `sources` | Folders holding the evidence and source documents to verify against | Yes |
| `iterations` | Refinement loops (default 3, max 5) | No |

Source documents are read-only. The optimizer never edits evidence.

## Scoring rubric (7 dimensions, each 0-10)

1. **Legal accuracy (x2).** Cited articles correct and applicable? Principles correctly stated? Procedural requirements met?
2. **Factual verification (x2).** Every factual claim traceable to a specific source document? Dates, amounts and quotes exact? **Any unverified claim = automatic REVISE, whatever the other scores.**
3. **Persuasiveness (x1.5).** Logical flow? Strongest point first? Conclusion follows from the premises?
4. **Conciseness (x1).** As short as it can be without losing substance? Judges read hundreds of pages.
5. **Tone and professionalism (x1).** Neutral, measured, no emotional appeals or accusations. Right register for the court.
6. **Abuse resistance (x2).** Could any part be characterized as abusive, vexatious or disproportionate, especially if the file has any prior adverse finding or costs award? Would a reasonable judge see it as proportionate and in good faith?
7. **Strategic alignment (x1).** Does it advance the overall strategy? Does it avoid conceding a point needed elsewhere in the file or in a related proceeding? Does it keep future options open?

**Composite** = weighted sum / 105 x 100

| Dimension | Weight | Max |
|---|---|---|
| Legal accuracy | 2 | 20 |
| Factual verification | 2 | 20 |
| Persuasiveness | 1.5 | 15 |
| Conciseness | 1 | 10 |
| Tone | 1 | 10 |
| Abuse resistance | 2 | 20 |
| Strategic alignment | 1 | 10 |
| **Total** | | **105** |

Tune the weights to your practice. For a plaintiff-side firm with no adverse history, abuse resistance might drop to 1.

## Steps

1. **Score the baseline.** Read the draft, score all 7 dimensions with one line of reasoning each, compute the composite.
2. **Pick the focus.** Weighted gap per dimension = `(10 - score) x weight`. Highest gap wins. Tell the user which one is targeted.
3. **Write the challenger.** Rewrite for that dimension only. Keep every fact, date, amount, quote, legal position and demand exactly as is. Change only framing, structure, order, level of detail, tone, choice of authority, opening and closing.
4. **Score the challenger** on the same rubric.
5. **Pick the winner.** Show both scores side by side. A winning challenger becomes the new baseline. If the baseline wins, mark that dimension "attempted" and move to the next-highest gap.
6. **Verify (final iteration only).**
   - Citations: run a citation checker on the winning draft (for Canadian law, `strategy-arena/tools/verify_citations.py` in this toolkit checks neutral citations against CanLII). NOT FOUND must be fixed or removed.
   - Facts: for each factual claim, find the source with Grep/Read. Mark VERIFIED (with path) or UNVERIFIED. Unverified claims are sourced or removed before the draft moves on.
7. **Log the learning** (append to `learnings.md` next to the draft):
   ```markdown
   ## [Date] - [Document] - Iteration [N]
   **Dimension tested:** ...
   **Baseline score:** ... **Challenger score:** ... **Winner:** ...
   **What worked:** ...
   **What didn't:** ...
   **Insight:** (a generalizable lesson for future drafts)
   ```
8. **Present the result.** Write `{name}-optimized-{date}.md` and an iteration log beside the draft. Ask whether to move on to adversarial review.

## Challenger rules

One dimension per iteration, like single-variable experiments:
1. Iteration 1: highest weighted gap
2. Iteration 2: second-highest
3. Iteration 3: overall coherence after the targeted fixes

**Can change:** framing, structure and order, level of detail, tone, choice of authority, opening and closing.
**Cannot change:** facts, legal position, relief sought, identity of parties, procedural context. The position is set by the lawyer, not the optimizer.

## Where it sits

```
strategy-arena      decides WHAT to do
argument-optimizer  improves HOW it is written   <- this skill
adversarial review  stress-tests the finished draft
human review        before anything is filed or sent
```

## Constraints

- Improves presentation, not strategy.
- Every output stays a DRAFT until reviewed.
- Max 5 iterations per run. Returns diminish fast.
- Not an overnight autonomous loop: the user approves each step.
