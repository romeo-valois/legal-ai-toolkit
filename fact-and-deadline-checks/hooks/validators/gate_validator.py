#!/usr/bin/env python3
"""
Gate Validator — scans written/edited files for forbidden gate statuses.

Forbidden: CONDITIONAL_PASS, PARTIAL_PASS, PASS_WITH_CAVEATS, SOFT_PASS,
           PROVISIONAL_PASS, PASS_PENDING_REVIEW, NEAR_PASS, WAIVED

Called by dispatch-validator.sh with args: PROJECT_ROOT FILE_PATH
Reads tool input JSON from stdin.
Prints warning if forbidden status found, nothing otherwise.
"""

import sys
import os
import re

FORBIDDEN_STATUSES = [
    "CONDITIONAL_PASS",
    "PARTIAL_PASS",
    "PASS_WITH_CAVEATS",
    "SOFT_PASS",
    "PROVISIONAL_PASS",
    "PASS_PENDING_REVIEW",
    "NEAR_PASS",
    "WAIVED",
]

# Build regex: match these as standalone terms (case-insensitive)
PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(s) for s in FORBIDDEN_STATUSES) + r')\b',
    re.IGNORECASE
)


def main():
    if len(sys.argv) < 3:
        return

    file_path = sys.argv[2]

    try:
        content = open(file_path, "r", encoding="utf-8").read()
    except (OSError, IOError):
        return

    # Skip if the file IS the quality-gates directive (it lists them as examples)
    if "quality-gates.md" in file_path or "gate_validator.py" in file_path:
        return

    warnings = []
    for i, line in enumerate(content.splitlines(), 1):
        matches = PATTERN.findall(line)
        for m in matches:
            # Skip if in a "forbidden" context (i.e., documenting what NOT to do)
            line_lower = line.lower()
            if "forbidden" in line_lower or "do not" in line_lower or "does not exist" in line_lower:
                continue
            warnings.append(f"[GATE] Line {i}: Forbidden status '{m}' detected")

    if warnings:
        print("\n".join(warnings))


if __name__ == "__main__":
    main()
