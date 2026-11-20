#!/usr/bin/env python3
"""
Citation Verification Script — verifies case law citations against CanLII API.

Extracts neutral citations from markdown research memos, checks each against
the CanLII API for existence, title match, date consistency, and potential
reversals. Outputs a markdown verification report.

Usage:
  python3 tools/verify_citations.py research/my-memo.md
  python3 tools/verify_citations.py --all-tracks
  python3 tools/verify_citations.py --citation "2015 QCCA 513"
  python3 tools/verify_citations.py --all-tracks -o output/citation-verification-report.md
"""

import argparse
import glob
import os
import re
import sys
import time
import json
from datetime import date
from pathlib import Path
from typing import Optional, List, Dict
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

# ── API setup (reuse canlii_api.py's key loader) ─────────────────────

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canlii_api import _get_api_key, BASE_URL, LANG

# Rate limiting: 2 req/s max
_last_request_time = 0.0


def _api_request(path: str, params: dict = None) -> dict:
    """Rate-limited GET request that returns dict or raises on error."""
    global _last_request_time

    key = _get_api_key()
    params = params or {}
    params["api_key"] = key

    url = f"{BASE_URL}/{path}"
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params)

    elapsed = time.time() - _last_request_time
    if elapsed < 0.6:
        time.sleep(0.6 - elapsed)

    req = Request(url, headers={"Accept": "application/json"})
    _last_request_time = time.time()
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 429:
            # Rate limited — back off and retry once
            print("  Rate limited (429), waiting 2s...", file=sys.stderr)
            time.sleep(2)
            _last_request_time = time.time()
            with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        raise


def safe_case_metadata(database_id: str, case_id: str) -> Optional[dict]:
    """Get case metadata, returning None on 404/error."""
    try:
        return _api_request(f"caseBrowse/{LANG}/{database_id}/{case_id}/")
    except HTTPError as e:
        if e.code == 404:
            return None
        print(f"  API error ({e.code}) for {database_id}/{case_id}", file=sys.stderr)
        return None
    except (URLError, OSError) as e:
        print(f"  Network error for {database_id}/{case_id}: {e}", file=sys.stderr)
        return None


def safe_citing_cases(database_id: str, case_id: str) -> list:
    """Get cases citing this decision, returning empty list on error."""
    try:
        result = _api_request(f"caseCitator/en/{database_id}/{case_id}/citingCases")
        cases = result.get("citingCases", result if isinstance(result, list) else [])
        # API returns list-of-lists; flatten if needed
        if cases and isinstance(cases[0], list):
            cases = [item for sublist in cases for item in sublist]
        return cases
    except (HTTPError, URLError, OSError):
        return []


# ── Court code mapping ────────────────────────────────────────────────

COURT_MAP = {
    "QCCA": "qcca",       # Quebec Court of Appeal
    "QCCS": "qccs",       # Quebec Superior Court
    "QCCQ": "qccq",       # Court of Quebec
    "QCTDP": "qctdp",     # Quebec Human Rights Tribunal
    "QCTP": "qctp",       # Professions Tribunal
    "QCCDOOOQ": "qccdoooq",  # Barreau discipline
    "SCC": "csc-scc",     # Supreme Court of Canada
    "CSC": "csc-scc",     # Supreme Court (French)
    "FCA": "fca",          # Federal Court of Appeal
    "CAF": "fca",          # Federal Court of Appeal (French)
    "FC": "fct",           # Federal Court
    "CF": "fct",           # Federal Court (French)
    "ONCA": "onca",       # Ontario Court of Appeal
    "ONSC": "onsc",       # Ontario Superior Court
    "BCCA": "bcca",       # BC Court of Appeal
    "BCSC": "bcsc",       # BC Supreme Court
    "ABCA": "abca",       # Alberta Court of Appeal
    "ABQB": "abqb",       # Alberta Queen's Bench
}

# Appellate courts for reversal detection
APPELLATE_DBS = {"csc-scc", "qcca", "onca", "bcca", "fca", "abca"}


# ── Citation extraction ───────────────────────────────────────────────

# Pattern: optional party names, then neutral citation (year court number)
CITATION_RE = re.compile(
    r'(?:([A-ZÀ-Ÿa-zà-ÿ][A-ZÀ-Ÿa-zà-ÿ\s,.\-\'&]+?)\s*,\s*)?'
    r'(\d{4})\s+'
    r'([A-Z]{2,10})\s+'
    r'(\d+)'
)


def extract_citations(text: str) -> List[Dict]:
    """Extract unique case law citations from text."""
    seen = set()
    citations = []

    for match in CITATION_RE.finditer(text):
        party_names = (match.group(1) or "").strip().rstrip(",")
        year = match.group(2)
        court_code = match.group(3)
        number = match.group(4)

        # Skip non-court codes (article references, etc.)
        if court_code not in COURT_MAP:
            continue

        neutral = f"{year} {court_code} {number}"
        if neutral in seen:
            continue
        seen.add(neutral)

        citations.append({
            "party_names": party_names,
            "year": year,
            "court_code": court_code,
            "number": number,
            "neutral": neutral,
            "case_id": f"{year}{court_code.lower()}{number}",
            "database_id": COURT_MAP[court_code],
        })

    return citations


# ── Verification logic ────────────────────────────────────────────────

def fuzzy_title_match(expected: str, actual: str) -> bool:
    """Check if the expected party names appear in the actual title."""
    if not expected:
        return True  # No party names to check

    # Normalize both strings
    def normalize(s):
        s = s.lower()
        s = re.sub(r'[.,\-\'\"&]', ' ', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    actual_norm = normalize(actual)

    # Split expected into individual party name fragments
    # "Smith Holdings c. Jones Investments" → check main words
    parts = re.split(r'\s+c\.\s+|\s+v\.\s+|\s+vs?\.\s+', expected, flags=re.IGNORECASE)
    for part in parts:
        # Check if the significant words appear in the actual title
        words = [w for w in normalize(part).split() if len(w) > 2]
        if words:
            match_count = sum(1 for w in words if w in actual_norm)
            if match_count >= max(1, len(words) // 2):
                continue
            return False
    return True


def verify_citation(cit: dict) -> dict:
    """Verify a single citation against CanLII. Returns result dict."""
    result = {
        "citation": cit["neutral"],
        "party_names": cit["party_names"],
        "status": "NOT FOUND",
        "canlii_title": "—",
        "date": "—",
        "notes": "",
        "citing_count": 0,
        "potential_reversals": [],
    }

    # Step 1: Look up case metadata
    meta = safe_case_metadata(cit["database_id"], cit["case_id"])
    if meta is None:
        result["notes"] = "No match in CanLII. Verify manually."
        return result

    # Case exists — extract metadata
    title = meta.get("title", "")
    decision_date = meta.get("decisionDate", "")
    result["canlii_title"] = title
    result["date"] = decision_date
    result["status"] = "✓ VERIFIED"

    # Step 2: Check title match
    if cit["party_names"] and not fuzzy_title_match(cit["party_names"], title):
        result["status"] = "⚠ WARNING"
        result["notes"] = f'Title mismatch: expected "{cit["party_names"]}", found "{title}"'

    # Step 3: Check year consistency
    if decision_date and not decision_date.startswith(cit["year"]):
        if result["status"] == "✓ VERIFIED":
            result["status"] = "⚠ WARNING"
        year_note = f"Year mismatch: citation says {cit['year']}, decision date is {decision_date}"
        result["notes"] = f"{result['notes']}; {year_note}" if result["notes"] else year_note

    # Step 4: Check citing cases for reversal signals
    citing = safe_citing_cases(cit["database_id"], cit["case_id"])
    result["citing_count"] = len(citing)

    if citing:
        notes_parts = []
        if result["notes"]:
            notes_parts.append(result["notes"])
        notes_parts.append(f"{len(citing)} citing cases.")

        # Check for potential reversals: only flag cases where a higher
        # court decided the SAME case (party names overlap). A QCCA case
        # merely citing an SCC precedent is normal application, not reversal.
        #
        # Hierarchy: SCC > provincial CA > superior/provincial courts
        HIERARCHY = {
            "csc-scc": 3,
            "qcca": 2, "onca": 2, "bcca": 2, "abca": 2, "fca": 2,
            "qccs": 1, "onsc": 1, "bcsc": 1, "abqb": 1, "fct": 1,
            "qccq": 0, "qctdp": 0,
        }
        source_level = HIERARCHY.get(cit["database_id"], 0)
        source_title_norm = title.lower()
        # Extract key party words from the verified title for matching
        party_words = [w for w in re.sub(r'[^a-zà-ÿ\s]', '', source_title_norm).split() if len(w) > 3]

        for c in citing:
            citing_db = c.get("databaseId", "")
            citing_title = c.get("title", "")
            citing_citation = c.get("citation", "")
            citing_level = HIERARCHY.get(citing_db, 0)

            # Only flag if: (a) higher court, AND (b) same parties
            if citing_level > source_level and party_words:
                citing_title_norm = citing_title.lower()
                # Require at least 2 party words to match, or 1 if few words
                threshold = min(2, len(party_words))
                matches = sum(1 for w in party_words if w in citing_title_norm)
                if matches >= threshold:
                    result["potential_reversals"].append({
                        "citation": citing_citation,
                        "title": citing_title,
                        "database": citing_db,
                    })

        if not result["notes"]:
            result["notes"] = f"{len(citing)} citing cases. Active precedent."
        else:
            result["notes"] = "; ".join(notes_parts)

    return result


# ── Report generation ─────────────────────────────────────────────────

def generate_report(source_label: str, results: List[Dict]) -> str:
    """Generate markdown verification report."""
    verified = sum(1 for r in results if r["status"] == "✓ VERIFIED")
    not_found = sum(1 for r in results if r["status"] == "NOT FOUND")
    warnings = sum(1 for r in results if r["status"] == "⚠ WARNING")

    lines = [
        f"# Citation Verification Report — {source_label}",
        f"Date: {date.today().isoformat()}",
        "",
        "## Summary",
        f"- Total citations found: {len(results)}",
        f"- Verified: {verified}",
        f"- Not found: {not_found}",
        f"- Warnings: {warnings}",
        "",
        "## Results",
        "",
        "| Citation | Status | CanLII Title | Date | Notes |",
        "|----------|--------|-------------|------|-------|",
    ]

    for r in results:
        citation = r["citation"]
        if r["party_names"]:
            citation = f"{r['party_names']}, {r['citation']}"
        # Escape pipes in table cells
        title = r["canlii_title"].replace("|", "\\|")
        notes = r["notes"].replace("|", "\\|")
        lines.append(f"| {citation} | {r['status']} | {title} | {r['date']} | {notes} |")

    # Reversal check section
    lines.extend(["", "## Reversal Check", ""])
    reversals_found = False
    for r in results:
        if r["potential_reversals"]:
            reversals_found = True
            lines.append(f"### {r['citation']}")
            lines.append(f"The following appellate decisions cite this case and may warrant review:")
            lines.append("")
            for rev in r["potential_reversals"]:
                lines.append(f"- **{rev['citation']}** — {rev['title']}")
            lines.append("")

    if not reversals_found:
        lines.append("No potential reversals detected among citing cases. This is a heuristic check — lawyer review is still required for authoritative analysis.")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by verify_citations.py — metadata verification only. Full text analysis requires lawyer review.*")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────

def find_research_memos() -> List[str]:
    """Find all research memos across track directories."""
    pattern = os.path.join(
        Path(__file__).resolve().parent.parent, "track-*/research/*.md"
    )
    return sorted(glob.glob(pattern))


def main():
    parser = argparse.ArgumentParser(
        description="Verify case law citations against CanLII API"
    )
    parser.add_argument(
        "files", nargs="*",
        help="Markdown files to scan for citations"
    )
    parser.add_argument(
        "--all-tracks", action="store_true",
        help="Scan all research memos in track-*/research/"
    )
    parser.add_argument(
        "--citation",
        help='Verify a single citation, e.g. "2015 QCCA 513"'
    )
    parser.add_argument(
        "-o", "--output",
        help="Write report to file instead of stdout"
    )

    args = parser.parse_args()

    # Mode 1: Single citation
    if args.citation:
        citations = extract_citations(args.citation)
        if not citations:
            print(f"Could not parse citation: {args.citation}", file=sys.stderr)
            sys.exit(1)
        source_label = f"Single citation: {args.citation}"
        results = []
        for cit in citations:
            print(f"  Verifying {cit['neutral']}...", file=sys.stderr)
            results.append(verify_citation(cit))

    # Mode 2: All tracks
    elif args.all_tracks:
        files = find_research_memos()
        if not files:
            print("No research memos found in track-*/research/", file=sys.stderr)
            sys.exit(1)
        print(f"Found {len(files)} research memos", file=sys.stderr)

        all_citations = []
        seen_neutrals = set()
        for f in files:
            text = Path(f).read_text(encoding="utf-8", errors="replace")
            for cit in extract_citations(text):
                if cit["neutral"] not in seen_neutrals:
                    seen_neutrals.add(cit["neutral"])
                    cit["source_file"] = os.path.relpath(f)
                    all_citations.append(cit)

        print(f"Found {len(all_citations)} unique citations", file=sys.stderr)
        source_label = f"All tracks ({len(files)} memos)"
        results = []
        for cit in all_citations:
            print(f"  Verifying {cit['neutral']}...", file=sys.stderr)
            results.append(verify_citation(cit))

    # Mode 3: Specific files
    elif args.files:
        all_citations = []
        seen_neutrals = set()
        for f in args.files:
            if not os.path.isfile(f):
                print(f"File not found: {f}", file=sys.stderr)
                sys.exit(1)
            text = Path(f).read_text(encoding="utf-8", errors="replace")
            for cit in extract_citations(text):
                if cit["neutral"] not in seen_neutrals:
                    seen_neutrals.add(cit["neutral"])
                    all_citations.append(cit)

        if not all_citations:
            print("No citations found in the specified files.", file=sys.stderr)
            sys.exit(0)

        file_label = ", ".join(os.path.basename(f) for f in args.files)
        source_label = file_label
        results = []
        for cit in all_citations:
            print(f"  Verifying {cit['neutral']}...", file=sys.stderr)
            results.append(verify_citation(cit))

    else:
        parser.print_help()
        sys.exit(1)

    # Generate and output report
    report = generate_report(source_label, results)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"\nReport written to {args.output}", file=sys.stderr)
    else:
        print(report)

    # Summary to stderr
    verified = sum(1 for r in results if r["status"] == "✓ VERIFIED")
    not_found = sum(1 for r in results if r["status"] == "NOT FOUND")
    warnings = sum(1 for r in results if r["status"] == "⚠ WARNING")
    print(f"\nDone: {verified} verified, {not_found} not found, {warnings} warnings", file=sys.stderr)


if __name__ == "__main__":
    main()
