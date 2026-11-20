#!/usr/bin/env python3
"""
Fact Change Validator — scans written/edited files for stale values
from config/fact-changes.yaml.

Called by dispatch-validator.sh with args: PROJECT_ROOT FILE_PATH
Reads tool input JSON from stdin.
Prints warning message if stale values found, nothing otherwise.
"""

import os
import re
import sys

def main():
    if len(sys.argv) < 3:
        return

    project_root = sys.argv[1]
    file_path = sys.argv[2]

    fact_changes_path = os.path.join(project_root, "config", "fact-changes.yaml")
    if not os.path.exists(fact_changes_path):
        return

    # Simple YAML parsing for our specific format (avoid external deps)
    try:
        content = open(fact_changes_path, "r", encoding="utf-8").read()
    except (OSError, IOError):
        return

    # Extract incomplete fact changes with old values
    stale_values = []
    current_entry = {}
    for line in content.splitlines():
        # drop inline YAML comments ("value"  # note) so status values compare cleanly
        line_stripped = re.sub(r'\s+#.*$', '', line).strip()
        if line_stripped.startswith("- id:"):
            if current_entry:
                stale_values.append(current_entry)
            current_entry = {"id": line_stripped.split(":", 1)[1].strip().strip('"')}
        elif "old_value:" in line_stripped and current_entry:
            current_entry["old_value"] = line_stripped.split(":", 1)[1].strip().strip('"')
        elif "new_value:" in line_stripped and current_entry:
            current_entry["new_value"] = line_stripped.split(":", 1)[1].strip().strip('"')
        elif "propagation_status:" in line_stripped and current_entry:
            status = line_stripped.split(":", 1)[1].strip().strip('"')
            current_entry["status"] = status

    if current_entry:
        stale_values.append(current_entry)

    # Filter to incomplete propagations only
    incomplete = [e for e in stale_values if e.get("status") in ("incomplete", "deferred")]
    if not incomplete:
        return

    # Read the target file
    try:
        target_content = open(file_path, "r", encoding="utf-8").read()
    except (OSError, IOError):
        return

    # Check for stale values
    warnings = []
    for entry in incomplete:
        old_val = entry.get("old_value", "")
        if old_val and old_val in target_content:
            warnings.append(
                f"[FACT-CHANGE] {entry.get('id', '?')}: File contains stale value "
                f"'{old_val}' — should be '{entry.get('new_value', '?')}'"
            )

    if warnings:
        print("\n".join(warnings))


if __name__ == "__main__":
    main()
