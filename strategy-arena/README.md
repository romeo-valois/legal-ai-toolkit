# Strategy Arena

A moot court for litigation strategy, run by AI agents.

When you face a major decision (file or hold, settle or litigate, which claim goes first), the Arena has four strategists with different philosophies each propose a plan. A simulated opposing counsel attacks every plan. The strategists revise. A fact-check gate rejects any plan built on a wrong fact or a non-existent case. A simulated judge then scores the survivors on predicted real-world outcome.

The result is not one AI opinion. It is the plan that survived an adversarial process, plus a clear list of the points where good strategies disagree, which are the real decisions for the client.

## How it works

```
Brief  ->  4 strategists draft independently
       ->  coherence screen (right party, right court, still-valid facts)
       ->  red team attacks each plan
       ->  strategists revise (each sees only its own attack report)
       ->  citation check against CanLII (tools/verify_citations.py)
       ->  fact-check gate (any failure = rejected)
       ->  judicial evaluator scores and ranks
       ->  Synthesis strategist joins from Round 2
       ->  stop at 3 rounds or < 3% improvement
```

## The cast

| Role | File | Philosophy |
|---|---|---|
| The Litigator | `strategists/the-litigator.md` | File early, create procedural pressure |
| The Negotiator | `strategists/the-negotiator.md` | Litigation is a cost; build leverage for resolution |
| The Methodical | `strategists/the-methodical.md` | Sequence correctly, close gaps, then move |
| The Opportunist | `strategists/the-opportunist.md` | Read the board, exploit asymmetries and timing |
| Synthesis | `strategists/synthesis.md` | Joins in Round 2; combines what survived, with attribution |
| Red Team | `red-team.md` | Simulates the actual opposing counsel described in the brief |
| Judicial Evaluator | `judicial-evaluator.md` | Scores on predicted outcome, not cleverness |

## Safeguards

- **Fact-check gate is binary.** A strategy with one wrong fact, misread deadline or bad citation scores zero.
- **Citations are verified by code, not by the AI.** `tools/verify_citations.py` checks each neutral citation against the CanLII API.
- **Role separation.** Strategists cannot see each other's attack reports; the judge reads blind first.
- **No free passes.** Conclusions carried over from earlier matches are re-verified, never assumed.
- **The Arena does not replace a lawyer.** It produces a recommended strategy for human review.

## Running it

The Arena runs inside an AI coding agent (built for Claude Code). The agent plays each role in turn, following `ARENA.md`.

1. Copy `templates/brief.md`, fill it in, and approve it.
2. Tell the agent: "Run this brief through the arena, following ARENA.md."
3. Results go in `matches/`; update `templates/win-records.md` and `templates/arena-log.md` after each match.

Citation checking needs a free CanLII API key in a `.env` file at the repo root:

```
CANLII_API_KEY=your-key-here
```

`.env` is gitignored. Never commit it.

## Default jurisdiction

The judge and red team are calibrated for Quebec civil procedure (CCQ / CCP). To use another jurisdiction, edit the "Jurisdiction" line in the brief and the bench description in `judicial-evaluator.md`.
