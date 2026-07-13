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
    python -m pyvibe <path> --verbose         # also list suppressed findings (inline / pyvibe.toml)
    python -m pyvibe audit [path]             # audit inline suppressions: justification + orphan usage

Suppressing findings:
    # pyvibe: ignore PYVIBE-008              (same line, or the next non-comment line if standalone)
    # pyvibe: ignore PYVIBE-008, PYVIBE-003  (multiple rules)
    # pyvibe: ignore-next-line PYVIBE-008    (always the next line)
    # pyvibe: ignore PYVIBE-008 -- reason    (optional justification, shown in `pyvibe audit`)
See pyvibe.toml for project-wide ignore / exclude / severity overrides.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple

from pyvibe import __version__
from pyvibe.analyzer import (
    analyze_file,
    analyze_file_full,
    analyze_directory,
    analyze_directory_full,
    DEFAULT_EXCLUDES,
    ALL_RULE_IDS,
    TEST_FILE_DOWNGRADE,
    _is_test_file,
)
from pyvibe.baseline import DEFAULT_BASELINE_PATH
from pyvibe.config import is_excluded


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

    if len(sys.argv) > 1 and sys.argv[1] == "audit":
        _main_audit(sys.argv[2:])
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
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Also list suppressed findings (inline `# pyvibe: ignore` comments and pyvibe.toml)",
    )
    args = parser.parse_args()

    file_results, suppressed = _resolve_file_results(args)
    file_results = _apply_baseline_filter(args, file_results)
    total_violations = sum(len(v) for v in file_results.values())
    total_files = sum(1 for v in file_results.values() if v)

    _emit_scan_output(args, file_results, total_violations, total_files, suppressed)

    sys.exit(1 if total_violations > 0 else 0)


def _load_config_or_exit(path):
    from pyvibe.config import ConfigError, load_config

    try:
        return load_config(Path(path))
    except ConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


def _resolve_file_results(args) -> Tuple[dict, List[Tuple[Path, object, str]]]:
    """Shared by the bare `pyvibe <path>` command and `pyvibe scan`.

    Returns (file_results, suppressed) — suppressed is a flat list of
    (path, Violation, reason) tuples, reason being "inline" or "config".
    Expects args.path/.exclude/.no_test_files/.downgrade_in_tests.
    """
    target = Path(args.path)
    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        sys.exit(2)

    config = _load_config_or_exit(target)

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
            return {}, []
        if skip_test_files and _is_test_file(str(target)):
            return {}, []
        if config and is_excluded(target, config):
            return {}, []
        reported, suppressed = analyze_file_full(
            target, downgrade_in_tests=downgrade_in_tests, config=config
        )
        file_results = {target: reported} if reported else {}
        return file_results, [(target, v, reason) for v, reason in suppressed]

    return analyze_directory_full(
        target,
        exclude=exclude,
        skip_test_files=skip_test_files,
        downgrade_in_tests=downgrade_in_tests,
        config=config,
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


def _emit_scan_output(args, file_results: dict, total_violations: int, total_files: int, suppressed: list):
    """Shared by the bare `pyvibe <path>` command and `pyvibe scan`.

    Expects args.sarif/.sarif_output/.json/.verbose.
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
        _print_human(file_results, total_violations, total_files, suppressed, verbose=args.verbose)


def _print_human(
    file_results: dict, total_violations: int, total_files: int, suppressed: list, verbose: bool = False
):
    print()
    print("  python-vibe-guard")
    print("  ─────────────────────────────────────────────")
    print()

    if not file_results and not suppressed:
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

    if verbose and suppressed:
        print("  Suppressed:")
        for path, v, reason in suppressed:
            print(f"    {v.rule_id} {path}:{v.line} ({reason})")
        print()

    print("  ─────────────────────────────────────────────")
    print(f"  {total_violations} reported · {len(suppressed)} suppressed")
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

    config = _load_config_or_exit(repo_root)

    file_results = {}
    for rel_path, added_lines in changed.items():
        abs_path = repo_root / rel_path
        if not abs_path.exists():
            continue
        if config and is_excluded(abs_path, config):
            continue
        violations = analyze_file(abs_path, line_filter=added_lines, config=config)
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
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Also list suppressed findings (inline `# pyvibe: ignore` comments and pyvibe.toml)",
    )
    args = parser.parse_args(argv)

    file_results, suppressed = _resolve_file_results(args)
    file_results = _apply_baseline_filter(args, file_results)

    total_violations = sum(len(v) for v in file_results.values())
    total_files = sum(1 for v in file_results.values() if v)

    _emit_scan_output(args, file_results, total_violations, total_files, suppressed)

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

    config = _load_config_or_exit(target)
    exclude = DEFAULT_EXCLUDES | frozenset(args.exclude)

    if target.is_file():
        if target.suffix != ".py":
            file_results = {}
        elif args.no_test_files and _is_test_file(str(target)):
            file_results = {}
        elif config and is_excluded(target, config):
            file_results = {}
        else:
            file_results = {target: analyze_file(target, config=config)}
    else:
        file_results = analyze_directory(
            target, exclude=exclude, skip_test_files=args.no_test_files, config=config
        )

    from pyvibe.baseline import write_baseline

    total_findings = sum(len(v) for v in file_results.values())
    write_baseline(file_results, args.baseline_path)

    verb = "created" if args.action == "create" else "updated"
    print(f"Baseline {verb}: {total_findings} findings saved to {args.baseline_path}")
    sys.exit(0)


def _main_audit(argv):
    parser = argparse.ArgumentParser(
        prog="pyvibe audit",
        description="Audit inline `# pyvibe: ignore` suppressions: justification coverage + orphaned (unused) suppressions",
    )
    parser.add_argument("path", nargs="?", default=".", help="File or directory to audit (default: current directory)")
    parser.add_argument(
        "--exclude",
        metavar="DIR",
        action="append",
        default=[],
        help="Directory name to exclude (can be repeated)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--fail-on-unused",
        action="store_true",
        help="Exit 1 if any orphaned suppression is found (no violation on its target line)",
    )
    parser.add_argument(
        "--fail-on-unjustified",
        action="store_true",
        help="Exit 1 if any suppression is missing a `-- justification`",
    )
    parser.add_argument(
        "--max-unused",
        metavar="N",
        type=int,
        default=None,
        help="Exit 1 if more than N orphaned suppressions are found",
    )
    args = parser.parse_args(argv)

    from pyvibe.audit import audit_path, summarize

    target = Path(args.path)
    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        sys.exit(2)

    config = _load_config_or_exit(target)
    exclude = DEFAULT_EXCLUDES | frozenset(args.exclude)

    records = audit_path(target, exclude=exclude, config=config)
    summary = summarize(records)

    if args.json:
        _print_audit_json(summary)
    else:
        _print_audit_human(summary)

    failed = (
        (args.fail_on_unused and summary.unused > 0)
        or (args.fail_on_unjustified and summary.without_justification > 0)
        or (args.max_unused is not None and summary.unused > args.max_unused)
    )
    sys.exit(1 if failed else 0)


def _format_directive(record) -> str:
    return f"# pyvibe: {record.directive} {record.rule_id}"


def _print_audit_human(summary):
    print()
    title = "Suppressions audit"
    print(title)
    print("─" * len(title))

    if summary.total == 0:
        print("No suppressions found.")
        print()
        return

    pct = round(summary.with_justification / summary.total * 100)
    print(f"Total suppressions: {summary.total}")
    print(f"With justification: {summary.with_justification} ({pct}%)")
    print(f"Without justification: {summary.without_justification}")
    print(f"Unused (no violation found): {summary.unused}")
    print()

    print("By rule:")
    for rule_id, count in summary.by_rule.items():
        print(f"{rule_id:<12} {count}")
    print()

    if summary.unused_records:
        print("Unused suppressions:")
        for r in summary.unused_records:
            print(f"{r.filepath}:{r.comment_line}  {_format_directive(r)}")
        print()

    if summary.unjustified_records:
        print("Without justification:")
        for r in summary.unjustified_records:
            print(f"{r.filepath}:{r.comment_line}  {_format_directive(r)}")
        print()


def _print_audit_json(summary):
    output = {
        "total": summary.total,
        "with_justification": summary.with_justification,
        "without_justification": summary.without_justification,
        "unused": summary.unused,
        "by_rule": summary.by_rule,
        "unused_suppressions": [
            {
                "file": r.filepath,
                "line": r.comment_line,
                "rule_id": r.rule_id,
                "justification": r.justification,
            }
            for r in summary.unused_records
        ],
        "without_justification_suppressions": [
            {
                "file": r.filepath,
                "line": r.comment_line,
                "rule_id": r.rule_id,
                "justification": r.justification,
            }
            for r in summary.unjustified_records
        ],
    }
    print(json.dumps(output, indent=2))


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
