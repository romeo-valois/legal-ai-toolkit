#!/usr/bin/env python3
"""
Deadline validator: warns when Claude edits a file belonging to a matter that
has an open deadline within WARN_DAYS.

Called by dispatch-validator.sh with args: PROJECT_ROOT FILE_PATH
Reads config/deadlines.json. Each deadline has a "matter" key; a deadline applies
when that key appears in the edited file's path (e.g. matter "smith-v-jones"
matches matters/smith-v-jones/drafts/reply.md). Optional "keywords" list adds
more path fragments to match.
"""

import json
import os
import re
import sys
from datetime import datetime

WARN_DAYS = 14
CLOSED_WORDS = ("PASSED", "COMPLETE", "DONE", "CLOSED")


def main():
    if len(sys.argv) < 3:
        return
    project_root, file_path = sys.argv[1], sys.argv[2]
    rel_path = os.path.relpath(file_path, project_root).lower()

    deadlines_path = os.path.join(project_root, "config", "deadlines.json")
    try:
        with open(deadlines_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return

    now = datetime.now()
    warnings = []
    for dl in data.get("deadlines", []):
        status = dl.get("status", "")
        if any(w in status.upper() for w in CLOSED_WORDS):
            continue
        fragments = [dl.get("matter", "")] + dl.get("keywords", [])
        if not any(f and f.lower() in rel_path for f in fragments):
            continue
        try:
            when = datetime.fromisoformat(re.sub(r"[+-]\d{2}:\d{2}$", "", dl.get("date", "")))
        except (ValueError, TypeError):
            continue
        days = (when - now).days
        if 0 <= days <= WARN_DAYS:
            warnings.append(
                f"[DEADLINE] {dl.get('id', '?')}: {days} days left ({when:%Y-%m-%d}). Status: {status}"
            )

    if warnings:
        print("\n".join(warnings))


if __name__ == "__main__":
    main()
