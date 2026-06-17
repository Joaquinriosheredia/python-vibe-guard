#!/usr/bin/env python3
"""
python-vibe-guard — runtime anti-pattern scanner for async Python

Usage:
    python -m pyvibe <path>          # file or directory
    python -m pyvibe <path> --json   # machine-readable output
"""
import argparse
import json
import sys
from pathlib import Path

from pyvibe.analyzer import analyze_file, analyze_directory


def main():
    parser = argparse.ArgumentParser(
        prog="pyvibe",
        description="Detect runtime anti-patterns in async Python code",
    )
    parser.add_argument("path", help="File or directory to scan")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    target = Path(args.path)
    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        sys.exit(2)

    if target.is_file():
        file_results = {target: analyze_file(target)} if target.suffix == ".py" else {}
    else:
        file_results = analyze_directory(target)

    total_violations = sum(len(v) for v in file_results.values())
    total_files = sum(1 for v in file_results.values() if v)

    if args.json:
        output = []
        for path, violations in file_results.items():
            for v in violations:
                output.append({
                    "file": str(path),
                    "rule": v.rule_id,
                    "severity": v.severity,
                    "line": v.line,
                    "function": v.function_name,
                    "message": v.message,
                    "evidence": v.evidence,
                })
        print(json.dumps(output, indent=2))
    else:
        _print_human(file_results, total_violations, total_files)

    sys.exit(1 if total_violations > 0 else 0)


def _print_human(file_results: dict, total_violations: int, total_files: int):
    print()
    print("  python-vibe-guard")
    print("  ─────────────────────────────────────────────")
    print()

    if not file_results:
        print("  No violations found\n")
        return

    for path, violations in file_results.items():
        if not violations:
            continue
        print(f"  {path}")
        print()
        for v in violations:
            print(f"  [CRITICAL] [{v.rule_id}] — line {v.line}")
            print(f"     Function : {v.function_name}()")
            print(f"     Problem  : {v.message}")
            print(f"     Fix      : {v.evidence}")
            print()

    print("  ─────────────────────────────────────────────")
    print(f"  {total_violations} violation(s) in {total_files} file(s)")
    print()


if __name__ == "__main__":
    main()
