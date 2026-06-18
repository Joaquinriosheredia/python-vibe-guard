#!/usr/bin/env python3
"""
python-vibe-guard — runtime anti-pattern scanner for async Python

Usage:
    python -m pyvibe <path>                   # file or directory
    python -m pyvibe <path> --json            # machine-readable output
    python -m pyvibe <path> --no-test-files   # skip test files entirely
    python -m pyvibe <path> --downgrade-in-tests  # WARNING instead of CRITICAL in all test files
"""
import argparse
import json
import sys
from pathlib import Path

from pyvibe import __version__
from pyvibe.analyzer import (
    analyze_file,
    analyze_directory,
    DEFAULT_EXCLUDES,
    ALL_RULE_IDS,
    TEST_FILE_DOWNGRADE,
    _is_test_file,
)


def main():
    parser = argparse.ArgumentParser(
        prog="pyvibe",
        description="Detect runtime anti-patterns in async Python code",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("path", help="File or directory to scan")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--exclude",
        metavar="DIR",
        action="append",
        default=[],
        help=(
            "Directory name to exclude (can be repeated). "
            "Added on top of the built-in defaults: "
            + ", ".join(sorted(DEFAULT_EXCLUDES))
        ),
    )
    parser.add_argument(
        "--no-test-files",
        action="store_true",
        help=(
            "Exclude test files from the scan entirely "
            "(files matching test_*.py, *_test.py, or under tests/ / test/)"
        ),
    )
    parser.add_argument(
        "--downgrade-in-tests",
        action="store_true",
        help=(
            "Downgrade ALL violations in test files from CRITICAL to WARNING. "
            "Default: only PYVIBE-001, PYVIBE-007, and PYVIBE-013 are downgraded."
        ),
    )
    args = parser.parse_args()

    target = Path(args.path)
    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        sys.exit(2)

    exclude = DEFAULT_EXCLUDES | frozenset(args.exclude)

    # Resolve test-file handling flags (mutually exclusive in effect)
    if args.no_test_files:
        skip_test_files = True
        downgrade_in_tests = frozenset()
    elif args.downgrade_in_tests:
        skip_test_files = False
        downgrade_in_tests = ALL_RULE_IDS
    else:
        skip_test_files = False
        downgrade_in_tests = TEST_FILE_DOWNGRADE

    if target.is_file():
        if target.suffix != ".py":
            file_results = {}
        elif skip_test_files and _is_test_file(str(target)):
            file_results = {}
        else:
            file_results = {target: analyze_file(target, downgrade_in_tests=downgrade_in_tests)}
    else:
        file_results = analyze_directory(
            target,
            exclude=exclude,
            skip_test_files=skip_test_files,
            downgrade_in_tests=downgrade_in_tests,
        )

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
            print(f"  [{v.severity}] [{v.rule_id}] — line {v.line}")
            print(f"     Function : {v.function_name}()")
            print(f"     Problem  : {v.message}")
            print(f"     Fix      : {v.evidence}")
            print()

    print("  ─────────────────────────────────────────────")
    print(f"  {total_violations} violation(s) in {total_files} file(s)")
    print()


if __name__ == "__main__":
    main()
