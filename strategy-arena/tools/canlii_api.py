#!/usr/bin/env python3
"""
CanLII REST API client — metadata lookups and citation graph.

Endpoints:
  - case_databases()          → list all courts/tribunals
  - case_list(db, ...)        → list decisions from a court
  - case_metadata(db, case)   → metadata for one decision
  - cited_cases(db, case)     → cases cited by a decision
  - citing_cases(db, case)    → cases that cite a decision
  - cited_legislation(db, case) → legislation cited by a decision
  - legislation_databases()   → list legislation databases
  - legislation_list(db)      → list statutes/regs in a database
  - legislation_metadata(db, leg) → metadata for one statute/reg

Rate limits: 2 req/s, 1 concurrent, 5000/day.
Metadata only — no full text access.

Usage:
  python canlii_api.py case-meta qccs 2026canlii12345
  python canlii_api.py cited-cases csc-scc 2008scc9
  python canlii_api.py citing-cases csc-scc 2008scc9
  python canlii_api.py cited-leg csc-scc 2008scc9
  python canlii_api.py case-list qccs --after 2026-01-01 --count 20
  python canlii_api.py databases
  python canlii_api.py leg-databases
  python canlii_api.py leg-list qcs
  python canlii_api.py leg-meta qcs cqlr-c-ccq-1991
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from typing import Optional

BASE_URL = "https://api.canlii.org/v1"
LANG = "en"

# Rate limiting: 2 req/s max
_last_request_time = 0.0


def _get_api_key() -> str:
    """Load API key from .env file or environment."""
    key = os.environ.get("CANLII_API_KEY", "").strip()
    if key:
        return key

    # Try .env in project root
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("CANLII_API_KEY=") and not line.startswith("#"):
                val = line.split("=", 1)[1].strip().strip("'\"")
                if val:
                    return val

    print("ERROR: CANLII_API_KEY not set. Add it to .env or export it.", file=sys.stderr)
    sys.exit(1)


def _request(path: str, params: Optional[dict] = None) -> dict:
    """Make a rate-limited GET request to the CanLII API."""
    global _last_request_time

    key = _get_api_key()
    params = params or {}
    params["api_key"] = key

    url = f"{BASE_URL}/{path}"
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params)

    # Rate limit: min 0.5s between requests
    elapsed = time.time() - _last_request_time
    if elapsed < 0.5:
        time.sleep(0.5 - elapsed)

    req = Request(url, headers={"Accept": "application/json"})
    try:
        _last_request_time = time.time()
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        print(f"HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr)
        sys.exit(1)


# ── Case law endpoints ──────────────────────────────────────────────

def case_databases(lang: str = LANG) -> dict:
    """List all courts/tribunals and their databaseId."""
    return _request(f"caseBrowse/{lang}/")


def case_list(
    database_id: str,
    lang: str = LANG,
    offset: int = 0,
    count: int = 25,
    published_after: Optional[str] = None,
    published_before: Optional[str] = None,
    decision_after: Optional[str] = None,
    decision_before: Optional[str] = None,
) -> dict:
    """List decisions from a specific court database."""
    params = {"offset": offset, "resultCount": count}
    if published_after:
        params["publishedAfter"] = published_after
    if published_before:
        params["publishedBefore"] = published_before
    if decision_after:
        params["decisionDateAfter"] = decision_after
    if decision_before:
        params["decisionDateBefore"] = decision_before
    return _request(f"caseBrowse/{lang}/{database_id}/", params)


def case_metadata(database_id: str, case_id: str, lang: str = LANG) -> dict:
    """Get metadata for a specific case."""
    return _request(f"caseBrowse/{lang}/{database_id}/{case_id}/")


def cited_cases(database_id: str, case_id: str) -> dict:
    """Get cases cited BY a decision."""
    return _request(f"caseCitator/en/{database_id}/{case_id}/citedCases")


def citing_cases(database_id: str, case_id: str) -> dict:
    """Get cases that CITE a decision."""
    return _request(f"caseCitator/en/{database_id}/{case_id}/citingCases")


def cited_legislation(database_id: str, case_id: str) -> dict:
    """Get legislation cited by a decision."""
    return _request(f"caseCitator/en/{database_id}/{case_id}/citedLegislations")


# ── Legislation endpoints ───────────────────────────────────────────

def legislation_databases(lang: str = LANG) -> dict:
    """List all legislation/regulation databases."""
    return _request(f"legislationBrowse/{lang}/")


def legislation_list(database_id: str, lang: str = LANG) -> dict:
    """List statutes/regulations in a database."""
    return _request(f"legislationBrowse/{lang}/{database_id}/")


def legislation_metadata(database_id: str, legislation_id: str, lang: str = LANG) -> dict:
    """Get metadata for a specific statute or regulation."""
    return _request(f"legislationBrowse/{lang}/{database_id}/{legislation_id}/")


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CanLII API client")
    sub = parser.add_subparsers(dest="command", required=True)

    # databases
    sub.add_parser("databases", help="List all case law databases")

    # case-list
    p = sub.add_parser("case-list", help="List cases from a database")
    p.add_argument("database", help="Database ID (e.g. qccs, onca, csc-scc)")
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--count", type=int, default=25)
    p.add_argument("--after", help="Published after (YYYY-MM-DD)")
    p.add_argument("--before", help="Published before (YYYY-MM-DD)")
    p.add_argument("--decision-after", help="Decision date after (YYYY-MM-DD)")
    p.add_argument("--decision-before", help="Decision date before (YYYY-MM-DD)")

    # case-meta
    p = sub.add_parser("case-meta", help="Get case metadata")
    p.add_argument("database", help="Database ID")
    p.add_argument("case_id", help="Case ID (e.g. 2008scc9)")

    # cited-cases
    p = sub.add_parser("cited-cases", help="Cases cited by a decision")
    p.add_argument("database", help="Database ID")
    p.add_argument("case_id", help="Case ID")

    # citing-cases
    p = sub.add_parser("citing-cases", help="Cases that cite a decision")
    p.add_argument("database", help="Database ID")
    p.add_argument("case_id", help="Case ID")

    # cited-leg
    p = sub.add_parser("cited-leg", help="Legislation cited by a decision")
    p.add_argument("database", help="Database ID")
    p.add_argument("case_id", help="Case ID")

    # leg-databases
    sub.add_parser("leg-databases", help="List legislation databases")

    # leg-list
    p = sub.add_parser("leg-list", help="List legislation in a database")
    p.add_argument("database", help="Database ID (e.g. qcs, qcr)")

    # leg-meta
    p = sub.add_parser("leg-meta", help="Get legislation metadata")
    p.add_argument("database", help="Database ID")
    p.add_argument("legislation_id", help="Legislation ID")

    args = parser.parse_args()

    if args.command == "databases":
        result = case_databases()
    elif args.command == "case-list":
        result = case_list(
            args.database,
            offset=args.offset,
            count=args.count,
            published_after=args.after,
            published_before=args.before,
            decision_after=args.decision_after,
            decision_before=args.decision_before,
        )
    elif args.command == "case-meta":
        result = case_metadata(args.database, args.case_id)
    elif args.command == "cited-cases":
        result = cited_cases(args.database, args.case_id)
    elif args.command == "citing-cases":
        result = citing_cases(args.database, args.case_id)
    elif args.command == "cited-leg":
        result = cited_legislation(args.database, args.case_id)
    elif args.command == "leg-databases":
        result = legislation_databases()
    elif args.command == "leg-list":
        result = legislation_list(args.database)
    elif args.command == "leg-meta":
        result = legislation_metadata(args.database, args.legislation_id)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
