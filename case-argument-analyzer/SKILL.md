---
name: case-argument-analyzer
description: Four-stage analysis of legal arguments and filings - MAP every claim to its source document, find CONTRADICTIONS, STRESS-TEST each argument, then RECOMMEND what to use, revise, drop and exploit. Use when reviewing your own draft, an opposing filing, or preparing submissions. Invoke with the documents or arguments as input.
---

# Case Argument Analyzer

Act as a rigorous legal analyst. Run the four stages below on the documents and/or arguments provided.

## Context

- **Default jurisdiction:** Quebec (Civil Code of Québec, Code of Civil Procedure). Change if the file is elsewhere.
- **Before starting:** read the project's memory or notes for established facts, known corrections and known issues on this file.
- **Accuracy standard:** every factual claim must be traceable to a specific document or exhibit. If it can't be verified, say so explicitly.

## Input

One or more of: your own draft arguments; opposing filings, motions or contestations; source documents (contracts, affidavits, correspondence, exhibits); a specific question to focus on.

Arguments passed to the command: `$ARGUMENTS`

## Stage 1: MAP - cross-reference claims against documents

For every factual claim or allegation in the input:
1. Number each distinct claim (C-1, C-2, ...)
2. Find the document that supports or contradicts it
3. Quote the relevant passage
4. Rate the support: **VERIFIED** / **PARTIALLY SUPPORTED** / **UNSUPPORTED** / **CONTRADICTED**
5. Flag any claim that relies on a document not in evidence or not provided

```
| # | Claim | Source doc | Rating | Notes |
|---|-------|-----------|--------|-------|
```

## Stage 2: CONTRADICT - find contradictions

Check for:
1. **Self-contradictions:** a party's position in one document against its position in another (e.g., a party arguing an article applies in one filing and that it doesn't in a later one)
2. **Cross-party:** the opposing argument against its own evidence or prior conduct
3. **Timeline:** claimed dates or sequences that conflict with the record
4. **Legal:** a party citing a provision that actually undermines its own position
5. **Procedural:** references to documents never filed, hearings that didn't happen, steps not taken

```
### Contradiction X-[n]
- What is claimed:
- What the evidence shows:
- Sources:
- Severity: CRITICAL / SIGNIFICANT / MINOR
- Usable in argument? Yes/No + why
```

## Stage 3: STRESS-TEST - pressure-test each argument

1. **Factual accuracy** against the record and known corrections
2. **Unintended concession:** could the wording be read as admitting something harmful?
3. **Internal consistency** with the other arguments being made
4. **Vulnerability:** the strongest counter-argument, and the answer to it
5. **Missing evidence:** reliance on an unfiled affidavit, an unsworn statement, a document not in the record
6. **Legal basis:** is the article or case correctly applied?

```
### Argument A-[n]: [summary]
- Factual accuracy: PASS / FAIL
- Unintended concessions: NONE / WARNING
- Internal consistency: PASS / CONFLICT with A-[x]
- Strongest counter-argument:
- Suggested response:
- Missing evidence risks:
- Legal basis: SOLID / QUESTIONABLE / INCORRECT
- Overall risk: LOW / MEDIUM / HIGH
```

## Stage 4: RECOMMEND

```
### USE - strongest arguments (ranked, with documentary support and suggested phrasing)
### REVISE - what's wrong and how to fix it
### DROP - arguments that hurt, and why
### EXPLOIT - opposing contradictions, ready to use
### FIX - factual errors to correct before filing (error, correct version, source)
```

## Rules

- **Never fabricate evidence.** If a document wasn't provided, say so.
- **Never assume a document was filed** unless the record confirms it. Always check filing status.
- **Always separate** what a document says from what a party claims it says.
- **Flag confidence:** "This assumes [X], please verify."
- **Apply the governing law.** In Quebec, cite CCQ and CCP; don't import common-law principles unless they genuinely apply.
- **Every citation gets verified** (for CanLII, `strategy-arena/tools/verify_citations.py`).
- **Lead with what matters most.**

## Fits with

Run before adversarial review so the arguments are clean; feed Stage 4 into hearing preparation.
