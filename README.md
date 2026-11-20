# Legal AI Toolkit

Six Claude Code skills pulled out of the system I use to run a civil litigation file. Take whatever is useful, change anything, ignore the rest.

They all follow the same idea: the AI does the thinking, plain code does the checking, and nothing built on an unverified fact or citation gets through.

| Folder | What it does | Install effort |
|---|---|---|
| [`strategy-arena/`](strategy-arena/) | Four AI strategists with different philosophies each build a plan for a big decision. An AI opposing counsel attacks every plan, the strategists revise, a fact-check gate rejects anything built on a wrong fact or a non-existent case, and an AI judge scores what survives. | Copy the folder |
| [`second-brain/`](second-brain/) | A local search over every note in the project and every past Claude Code session, with a short summary of each. Claude finds past decisions in about half a second, and says `LOW CONFIDENCE` instead of guessing. Works for any kind of work. | Copy, then 2 commands |
| [`argument-optimizer/`](argument-optimizer/) | Scores a draft on a 7-point rubric, rewrites it to fix the weakest point, keeps whichever version scores higher, then verifies every fact and citation. Optional hook suggests it whenever a draft changes. | Copy the folder |
| [`fact-and-deadline-checks/`](fact-and-deadline-checks/) | Hooks that run on every file Claude writes: they flag a stale fact you already corrected somewhere else, a "soft" PASS status, and any deadline within 14 days on that matter. Plus the 6-step protocol for propagating a corrected fact everywhere. | Copy + add to settings.json |
| [`case-argument-analyzer/`](case-argument-analyzer/) | Four stages: map every claim to its source document, find contradictions, stress-test each argument, then recommend what to use, revise, drop and exploit. | Copy the folder |
| [`quality-gates/`](quality-gates/) | Strict PASS/FAIL checklists before a filing, demand letter, memo or dossier leaves the workspace, and a health audit that finds stale files, broken references and deadline problems. | Copy the folder |

## Install

Each folder has a `SKILL.md` (or `ARENA.md` for the arena). The simplest route: copy a folder into your project at `.claude/skills/<name>/` and tell Claude "read this skill and set it up." The arena's citation checker needs your own `CANLII_API_KEY` (see `strategy-arena/README.md`).

Everything defaults to Quebec civil procedure (CCQ / CCP) where jurisdiction matters, and everything is easy to retarget.

## Notes

- None of these replace a lawyer's judgment. They're built to catch the errors an AI (or a tired human) makes before they reach a document.
- No client data is in here: all examples are invented.
