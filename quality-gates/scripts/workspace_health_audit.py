#!/usr/bin/env python3
"""
Workspace Health Audit — lint check for a Claude Code legal workspace.

Checks:
  1. File freshness (stale files in the scanned folders)
  2. Cross-reference integrity (broken file references in .md files)
  3. MEMORY.md line count (approaching 200-line truncation)
  4. Deadline consistency (past-due and upcoming items in deadlines.json)
  5. Directive validation freshness (last_validated front matter)

Output: .tmp/health-audit-report.md
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# --- Configuration ---

PROJECT_ROOT = Path(os.environ.get("AUDIT_ROOT", os.getcwd())).resolve()
_mem = os.environ.get("AUDIT_MEMORY_FILE", "")
MEMORY_PATH = Path(_mem).expanduser() if _mem else None
DEADLINES_PATH = PROJECT_ROOT / "config/deadlines.json"
OUTPUT_DIR = PROJECT_ROOT / ".tmp"
OUTPUT_PATH = OUTPUT_DIR / "health-audit-report.md"

FRESHNESS_DIRS = [d.strip() for d in os.environ.get("AUDIT_SCAN_DIRS", "directives,matters,strategy").split(",") if d.strip()]
FRESHNESS_THRESHOLD_DAYS = 30
FRESHNESS_EXEMPT = {"_shared", "archive", ".tmp", ".git", "config/credentials", "node_modules"}

MEMORY_WARNING_LINES = 150
MEMORY_CRITICAL_LINES = 180

DIRECTIVE_STALE_DAYS = 30


def count_lines(path: Path) -> int:
    """Count lines in a file."""
    try:
        return sum(1 for _ in open(path, "r", encoding="utf-8", errors="replace"))
    except (OSError, IOError):
        return -1


def get_mtime_days_ago(path: Path) -> int:
    """Return how many days ago a file was last modified."""
    try:
        mtime = os.path.getmtime(path)
        return (time.time() - mtime) / 86400
    except OSError:
        return -1


def is_exempt(path: Path) -> bool:
    """Check if a path is in an exempt directory."""
    rel = str(path.relative_to(PROJECT_ROOT))
    return any(rel.startswith(ex) for ex in FRESHNESS_EXEMPT)


# --- Check 1: File Freshness ---

def check_freshness() -> list:
    """Find files not modified in FRESHNESS_THRESHOLD_DAYS+ days."""
    findings = []
    scan_dirs = []

    for d in FRESHNESS_DIRS:
        dp = PROJECT_ROOT / d
        if dp.is_dir():
            scan_dirs.append(dp)

    for scan_dir in scan_dirs:
        for f in scan_dir.rglob("*"):
            if not f.is_file():
                continue
            if is_exempt(f):
                continue
            days = get_mtime_days_ago(f)
            if days >= FRESHNESS_THRESHOLD_DAYS:
                rel = f.relative_to(PROJECT_ROOT)
                findings.append({
                    "severity": "WARNING",
                    "file": str(rel),
                    "days_stale": int(days),
                    "message": f"Not modified in {int(days)} days"
                })

    findings.sort(key=lambda x: x["days_stale"], reverse=True)
    return findings


# --- Check 2: Cross-Reference Integrity ---

def check_cross_references() -> list:
    """Scan .md files for broken file references."""
    findings = []
    # Patterns: backtick paths (e.g., `directives/foo.md`) and markdown links [text](path)
    backtick_re = re.compile(r'`([a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+)`')
    link_re = re.compile(r'\]\(([^)#]+?)(?:#[^)]+)?\)')

    # Directories with extensions that look like file references
    file_extensions = {'.md', '.py', '.sh', '.json', '.yaml', '.yml', '.txt', '.docx', '.pdf', '.jpg', '.png'}

    for md_file in PROJECT_ROOT.rglob("*.md"):
        if ".git" in md_file.parts or ".tmp" in md_file.parts or "node_modules" in md_file.parts:
            continue

        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except (OSError, IOError):
            continue

        for line_num, line in enumerate(content.splitlines(), 1):
            for match in backtick_re.finditer(line):
                ref = match.group(1)
                # Only check things that look like local file paths (not URLs, not code snippets)
                if ref.startswith(("http", "//", "#")):
                    continue
                ext = Path(ref).suffix.lower()
                if ext not in file_extensions:
                    continue
                # Skip if it looks like code (e.g., module.exports, package.json patterns)
                if "." in Path(ref).stem and not ref.startswith((".", "/")):
                    # Could be module notation, skip
                    pass
                else:
                    # Try relative to project root and relative to the md file's directory
                    ref_path_root = PROJECT_ROOT / ref
                    ref_path_rel = md_file.parent / ref
                    if not ref_path_root.exists() and not ref_path_rel.exists():
                        findings.append({
                            "severity": "WARNING",
                            "file": str(md_file.relative_to(PROJECT_ROOT)),
                            "line": line_num,
                            "reference": ref,
                            "message": f"Broken reference to `{ref}`"
                        })

            for match in link_re.finditer(line):
                ref = match.group(1).strip()
                if ref.startswith(("http", "//", "#", "mailto:")):
                    continue
                ref_path_root = PROJECT_ROOT / ref
                ref_path_rel = md_file.parent / ref
                if not ref_path_root.exists() and not ref_path_rel.exists():
                    findings.append({
                        "severity": "WARNING",
                        "file": str(md_file.relative_to(PROJECT_ROOT)),
                        "line": line_num,
                        "reference": ref,
                        "message": f"Broken link to `{ref}`"
                    })

    return findings


# --- Check 3: MEMORY.md Health ---

def check_memory_health() -> list:
    """Check MEMORY.md line count."""
    findings = []
    if MEMORY_PATH is None:
        return [{"severity": "INFO", "file": "MEMORY.md",
                 "message": "Skipped: set AUDIT_MEMORY_FILE to check your Claude memory index"}]
    lines = count_lines(MEMORY_PATH)
    if lines < 0:
        findings.append({
            "severity": "CRITICAL",
            "file": str(MEMORY_PATH),
            "message": "MEMORY.md not found or unreadable"
        })
    elif lines >= MEMORY_CRITICAL_LINES:
        findings.append({
            "severity": "CRITICAL",
            "file": "MEMORY.md",
            "lines": lines,
            "message": f"MEMORY.md at {lines} lines — approaching 200-line truncation limit"
        })
    elif lines >= MEMORY_WARNING_LINES:
        findings.append({
            "severity": "WARNING",
            "file": "MEMORY.md",
            "lines": lines,
            "message": f"MEMORY.md at {lines} lines — consider archiving stale entries"
        })
    else:
        findings.append({
            "severity": "INFO",
            "file": "MEMORY.md",
            "lines": lines,
            "message": f"MEMORY.md at {lines} lines — healthy"
        })
    return findings


# --- Check 4: Deadline Consistency ---

def check_deadlines() -> list:
    """Check deadlines.json exists and is parseable. Flag past-due items still marked active."""
    findings = []
    if not DEADLINES_PATH.exists():
        findings.append({
            "severity": "CRITICAL",
            "file": "config/deadlines.json",
            "message": "deadlines.json not found"
        })
        return findings

    try:
        data = json.loads(DEADLINES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        findings.append({
            "severity": "CRITICAL",
            "file": "config/deadlines.json",
            "message": f"Failed to parse: {e}"
        })
        return findings

    now = datetime.now()
    for dl in data.get("deadlines", []):
        dl_id = dl.get("id", "UNKNOWN")
        dl_date_str = dl.get("date", "")
        dl_status = dl.get("status", "")

        # Parse date (handle timezone offset)
        try:
            # Strip timezone for simple comparison
            clean = re.sub(r'[+-]\d{2}:\d{2}$', '', dl_date_str)
            dl_date = datetime.fromisoformat(clean)
        except (ValueError, TypeError):
            findings.append({
                "severity": "WARNING",
                "file": "config/deadlines.json",
                "message": f"Deadline {dl_id}: unparseable date '{dl_date_str}'"
            })
            continue

        # Flag past-due deadlines not marked as PASSED or completed
        if dl_date < now and "PASSED" not in dl_status.upper() and "COMPLETE" not in dl_status.upper():
            days_past = (now - dl_date).days
            findings.append({
                "severity": "CRITICAL" if days_past > 7 else "WARNING",
                "file": "config/deadlines.json",
                "deadline_id": dl_id,
                "date": dl_date_str,
                "status": dl_status,
                "message": f"Deadline {dl_id} was {days_past} days ago but status is '{dl_status}'"
            })

        # Flag upcoming deadlines within 14 days
        elif 0 <= (dl_date - now).days <= 14:
            findings.append({
                "severity": "WARNING",
                "file": "config/deadlines.json",
                "deadline_id": dl_id,
                "date": dl_date_str,
                "days_remaining": (dl_date - now).days,
                "message": f"Deadline {dl_id} in {(dl_date - now).days} days"
            })

    return findings


# --- Check 5: Directive Validation Freshness ---

def check_directive_freshness() -> list:
    """Check last_validated in directive YAML front matter."""
    findings = []
    directives_dir = PROJECT_ROOT / "directives"
    if not directives_dir.is_dir():
        return findings

    frontmatter_re = re.compile(r'^---\s*\n(.*?)\n---', re.DOTALL)
    date_re = re.compile(r'last_validated:\s*(\d{4}-\d{2}-\d{2})')

    for f in sorted(directives_dir.glob("*.md")):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except (OSError, IOError):
            continue

        fm_match = frontmatter_re.match(content)
        if not fm_match:
            findings.append({
                "severity": "WARNING",
                "file": str(f.relative_to(PROJECT_ROOT)),
                "message": "Missing YAML front matter (no last_validated field)"
            })
            continue

        date_match = date_re.search(fm_match.group(1))
        if not date_match:
            findings.append({
                "severity": "WARNING",
                "file": str(f.relative_to(PROJECT_ROOT)),
                "message": "Missing last_validated in front matter"
            })
            continue

        try:
            validated_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
            days_ago = (datetime.now() - validated_date).days
            if days_ago > DIRECTIVE_STALE_DAYS:
                findings.append({
                    "severity": "WARNING",
                    "file": str(f.relative_to(PROJECT_ROOT)),
                    "last_validated": date_match.group(1),
                    "message": f"Directive not validated in {days_ago} days"
                })
        except ValueError:
            findings.append({
                "severity": "WARNING",
                "file": str(f.relative_to(PROJECT_ROOT)),
                "message": f"Invalid last_validated date: {date_match.group(1)}"
            })

    return findings


# --- Report Generation ---

def generate_report(all_findings: dict) -> str:
    """Generate markdown report."""
    lines = [
        "# Workspace Health Audit Report",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Project:** {PROJECT_ROOT}",
        "",
    ]

    # Summary counts
    total_critical = sum(1 for cat in all_findings.values() for f in cat if f.get("severity") == "CRITICAL")
    total_warning = sum(1 for cat in all_findings.values() for f in cat if f.get("severity") == "WARNING")
    total_info = sum(1 for cat in all_findings.values() for f in cat if f.get("severity") == "INFO")

    lines.append(f"## Summary: {total_critical} CRITICAL | {total_warning} WARNING | {total_info} INFO")
    lines.append("")

    if total_critical == 0 and total_warning == 0:
        lines.append("Workspace is healthy. No issues found.")
        lines.append("")

    # Detail sections
    section_names = {
        "freshness": "File Freshness",
        "cross_references": "Cross-Reference Integrity",
        "memory": "MEMORY.md Health",
        "deadlines": "Deadline Consistency",
        "directive_freshness": "Directive Validation Freshness",
    }

    for key, title in section_names.items():
        findings = all_findings.get(key, [])
        lines.append(f"## {title}")
        lines.append("")
        if not findings:
            lines.append("No issues found.")
            lines.append("")
            continue

        for f in findings:
            sev = f.get("severity", "INFO")
            msg = f.get("message", "")
            file_ref = f.get("file", "")
            line_num = f.get("line", "")
            loc = f"`{file_ref}`" + (f":{line_num}" if line_num else "")
            lines.append(f"- **{sev}** — {loc}: {msg}")

        lines.append("")

    return "\n".join(lines)


def main():
    print("Running workspace health audit...")

    all_findings = {
        "freshness": check_freshness(),
        "cross_references": check_cross_references(),
        "memory": check_memory_health(),
        "deadlines": check_deadlines(),
        "directive_freshness": check_directive_freshness(),
    }

    report = generate_report(all_findings)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report, encoding="utf-8")

    # Print summary to stdout
    total_critical = sum(1 for cat in all_findings.values() for f in cat if f.get("severity") == "CRITICAL")
    total_warning = sum(1 for cat in all_findings.values() for f in cat if f.get("severity") == "WARNING")
    print(f"Audit complete: {total_critical} CRITICAL | {total_warning} WARNING")
    print(f"Report: {OUTPUT_PATH}")

    return 1 if total_critical > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
