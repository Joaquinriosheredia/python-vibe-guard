#!/usr/bin/env python3
"""
python-vibe-guard — runtime anti-pattern scanner for async Python

Usage:
    python -m pyvibe <path>                   # file or directory
    python -m pyvibe <path> --json            # machine-readable output
    python -m pyvibe <path> --sarif           # SARIF 2.1.0 -> results.sarif
    python -m pyvibe <path> --no-test-files   # skip test files entirely
    python -m pyvibe <path> --downgrade-in-tests  # WARNING instead of CRITICAL in all test files
    python -m pyvibe explain PYVIBE-002       # show research evidence for a rule
    python -m pyvibe review                   # PR review: only diff-touched lines (git diff HEAD~1)
    python -m pyvibe review --base main       # diff against another ref
    python -m pyvibe baseline create [path]   # snapshot existing findings to .pyvibe-baseline.json
    python -m pyvibe baseline update [path]   # overwrite the existing baseline
    python -m pyvibe <path> --baseline        # scan, suppressing findings already in the baseline
    python -m pyvibe scan <path> --baseline   # equivalent, explicit subcommand form
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
from pyvibe.baseline import DEFAULT_BASELINE_PATH


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "explain":
        _main_explain(sys.argv[2:])
        return

    if len(sys.argv) > 1 and sys.argv[1] == "review":
        _main_review(sys.argv[2:])
        return

    if len(sys.argv) > 1 and sys.argv[1] == "baseline":
        _main_baseline(sys.argv[2:])
        return

    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        _main_scan(sys.argv[2:])
        return

    parser = argparse.ArgumentParser(
        prog="pyvibe",
        description="Detect runtime anti-patterns in async Python code",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("path", help="File or directory to scan")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--sarif",
        action="store_true",
        help="Also write SARIF 2.1.0 output (for GitHub Code Scanning)",
    )
    parser.add_argument(
        "--sarif-output",
        metavar="PATH",
        default="results.sarif",
        help="Path to write SARIF output to (default: results.sarif)",
    )
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
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Only report findings not already present in the baseline (see `pyvibe baseline create`)",
    )
    parser.add_argument(
        "--baseline-path",
        metavar="PATH",
        default=DEFAULT_BASELINE_PATH,
        help=f"Path to the baseline file (default: {DEFAULT_BASELINE_PATH})",
    )
    args = parser.parse_args()

    file_results = _resolve_file_results(args)
    file_results = _apply_baseline_filter(args, file_results)
    total_violations = sum(len(v) for v in file_results.values())
    total_files = sum(1 for v in file_results.values() if v)

    _emit_scan_output(args, file_results, total_violations, total_files)

    sys.exit(1 if total_violations > 0 else 0)


def _resolve_file_results(args) -> dict:
    """Shared by the bare `pyvibe <path>` command and `pyvibe scan`.

    Expects args.path/.exclude/.no_test_files/.downgrade_in_tests.
    """
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
            return {}
        if skip_test_files and _is_test_file(str(target)):
            return {}
        return {target: analyze_file(target, downgrade_in_tests=downgrade_in_tests)}

    return analyze_directory(
        target,
        exclude=exclude,
        skip_test_files=skip_test_files,
        downgrade_in_tests=downgrade_in_tests,
    )


def _apply_baseline_filter(args, file_results: dict) -> dict:
    """Shared by the bare `pyvibe <path>` command and `pyvibe scan`.

    Expects args.baseline/.baseline_path. No-op when --baseline wasn't passed.
    """
    if not args.baseline:
        return file_results

    from pyvibe.baseline import BaselineNotFoundError, filter_new_violations, load_baseline

    try:
        baseline = load_baseline(args.baseline_path)
    except BaselineNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    return filter_new_violations(file_results, baseline)


def _emit_scan_output(args, file_results: dict, total_violations: int, total_files: int):
    """Shared by the bare `pyvibe <path>` command and `pyvibe scan`.

    Expects args.sarif/.sarif_output/.json.
    """
    if args.sarif:
        from pyvibe.sarif import write_sarif

        write_sarif(file_results, args.sarif_output)
        print(f"SARIF results written to {args.sarif_output}")

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
                    "suggested_fix": v.suggested_fix,
                })
        print(json.dumps(output, indent=2))
    else:
        _print_human(file_results, total_violations, total_files)


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
            if v.suggested_fix:
                print("     Suggested fix:")
                for line in v.suggested_fix.splitlines():
                    print(f"         {line}")
            print()

    print("  ─────────────────────────────────────────────")
    print(f"  {total_violations} violation(s) in {total_files} file(s)")
    print()


_SEVERITY_ICON = {"CRITICAL": "❌", "WARNING": "⚠️"}


def _main_review(argv):
    parser = argparse.ArgumentParser(
        prog="pyvibe review",
        description="PR review mode: analyze only lines added/modified in a git diff",
    )
    parser.add_argument(
        "--base",
        default="HEAD~1",
        help="Git ref to diff against (default: HEAD~1)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--sarif",
        action="store_true",
        help="Also write SARIF 2.1.0 output (for GitHub Code Scanning)",
    )
    parser.add_argument(
        "--sarif-output",
        metavar="PATH",
        default="results.sarif",
        help="Path to write SARIF output to (default: results.sarif)",
    )
    args = parser.parse_args(argv)

    from pyvibe.diff import GitDiffError, get_changed_python_files, get_repo_root

    try:
        repo_root = get_repo_root()
        changed = get_changed_python_files(args.base, cwd=repo_root)
    except GitDiffError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    file_results = {}
    for rel_path, added_lines in changed.items():
        abs_path = repo_root / rel_path
        if not abs_path.exists():
            continue
        violations = analyze_file(abs_path, line_filter=added_lines)
        if violations:
            file_results[rel_path] = violations

    total_violations = sum(len(v) for v in file_results.values())

    if args.sarif:
        from pyvibe.sarif import write_sarif

        write_sarif(file_results, args.sarif_output)
        print(f"SARIF results written to {args.sarif_output}")

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
                    "suggested_fix": v.suggested_fix,
                })
        print(json.dumps(output, indent=2))
    else:
        _print_review(file_results, changed, total_violations)

    sys.exit(1 if total_violations > 0 else 0)


def _print_review(file_results: dict, changed: dict, total_violations: int):
    print()
    print("  🐍 python-vibe-guard — PR Review")
    print("  ─────────────────────────────────")
    print(f"  Analyzing {len(changed)} changed file(s)...")
    print()

    if not file_results:
        print("  No violations found in new/modified code")
        print()
        return

    for path, violations in file_results.items():
        lines_reviewed = len(changed.get(path, frozenset()))
        print(f"  📄 {path} (+{lines_reviewed} lines reviewed)")
        print()
        for v in violations:
            icon = _SEVERITY_ICON.get(v.severity, "•")
            print(f"  {icon} {v.severity} [{v.rule_id}] — line {v.line} (NEW)")
            print(f"     Function : {v.function_name}()")
            print(f"     Problem  : {v.message}")
            print(f"     Fix      : {v.evidence}")
            if v.suggested_fix:
                print("     Suggested fix:")
                for line in v.suggested_fix.splitlines():
                    print(f"         {line}")
            print()

    print("  ─────────────────────────────────")
    print(f"  {total_violations} violation(s) in new/modified code")
    print()


def _main_scan(argv):
    parser = argparse.ArgumentParser(
        prog="pyvibe scan",
        description="Scan for anti-patterns (same as bare `pyvibe <path>`), with optional baseline filtering",
    )
    parser.add_argument("path", help="File or directory to scan")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--sarif",
        action="store_true",
        help="Also write SARIF 2.1.0 output (for GitHub Code Scanning)",
    )
    parser.add_argument(
        "--sarif-output",
        metavar="PATH",
        default="results.sarif",
        help="Path to write SARIF output to (default: results.sarif)",
    )
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
    parser.add_argument("--no-test-files", action="store_true", help="Exclude test files from the scan entirely")
    parser.add_argument(
        "--downgrade-in-tests",
        action="store_true",
        help="Downgrade ALL violations in test files from CRITICAL to WARNING",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Only report findings not already present in the baseline (see `pyvibe baseline create`)",
    )
    parser.add_argument(
        "--baseline-path",
        metavar="PATH",
        default=DEFAULT_BASELINE_PATH,
        help=f"Path to the baseline file (default: {DEFAULT_BASELINE_PATH})",
    )
    args = parser.parse_args(argv)

    file_results = _resolve_file_results(args)
    file_results = _apply_baseline_filter(args, file_results)

    total_violations = sum(len(v) for v in file_results.values())
    total_files = sum(1 for v in file_results.values() if v)

    _emit_scan_output(args, file_results, total_violations, total_files)

    sys.exit(1 if total_violations > 0 else 0)


def _main_baseline(argv):
    parser = argparse.ArgumentParser(
        prog="pyvibe baseline",
        description="Snapshot existing findings so future scans only report new ones",
    )
    parser.add_argument("action", choices=["create", "update"], help="create: refuses to overwrite an existing baseline; update: always overwrites")
    parser.add_argument("path", nargs="?", default=".", help="File or directory to scan (default: current directory)")
    parser.add_argument(
        "--baseline-path",
        metavar="PATH",
        default=DEFAULT_BASELINE_PATH,
        help=f"Path to write the baseline to (default: {DEFAULT_BASELINE_PATH})",
    )
    parser.add_argument(
        "--exclude",
        metavar="DIR",
        action="append",
        default=[],
        help="Directory name to exclude (can be repeated)",
    )
    parser.add_argument("--no-test-files", action="store_true", help="Exclude test files from the baseline entirely")
    args = parser.parse_args(argv)

    if args.action == "create" and Path(args.baseline_path).exists():
        print(
            f"Error: {args.baseline_path} already exists. "
            "Use `pyvibe baseline update` to overwrite it.",
            file=sys.stderr,
        )
        sys.exit(2)

    target = Path(args.path)
    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        sys.exit(2)

    exclude = DEFAULT_EXCLUDES | frozenset(args.exclude)

    if target.is_file():
        if target.suffix != ".py":
            file_results = {}
        elif args.no_test_files and _is_test_file(str(target)):
            file_results = {}
        else:
            file_results = {target: analyze_file(target)}
    else:
        file_results = analyze_directory(target, exclude=exclude, skip_test_files=args.no_test_files)

    from pyvibe.baseline import write_baseline

    total_findings = sum(len(v) for v in file_results.values())
    write_baseline(file_results, args.baseline_path)

    verb = "created" if args.action == "create" else "updated"
    print(f"Baseline {verb}: {total_findings} findings saved to {args.baseline_path}")
    sys.exit(0)


def _main_explain(argv):
    parser = argparse.ArgumentParser(
        prog="pyvibe explain",
        description="Show the research evidence behind a python-vibe-guard rule",
    )
    parser.add_argument("rule_id", help="Rule ID, e.g. PYVIBE-002")
    args = parser.parse_args(argv)

    from pyvibe.explain import EvidenceNotFoundError, explain_rule

    try:
        text = explain_rule(args.rule_id)
    except EvidenceNotFoundError as e:
        print(str(e))
        sys.exit(1)

    print()
    print(text)
    print()
    sys.exit(0)


if __name__ == "__main__":
    main()
