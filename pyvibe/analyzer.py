import ast
from pathlib import Path
from typing import FrozenSet, List, Optional, Tuple

from pyvibe.config import PyvibeConfig, is_excluded
from pyvibe.rules.base import Violation
from pyvibe.suppressions import parse_inline_suppressions
from pyvibe.rules.async_sleep import AsyncSleepRule
from pyvibe.rules.async_requests import AsyncRequestsRule
from pyvibe.rules.asyncio_run import AsyncioRunRule
from pyvibe.rules.threading_lock import ThreadingLockRule
from pyvibe.rules.contextvar_cleanup import ContextVarCleanupRule
from pyvibe.rules.celery_time_limit import CeleryTaskTimeLimitRule
from pyvibe.rules.subprocess_async import SubprocessAsyncRule
from pyvibe.rules.sqlite_async import SqliteAsyncRule
from pyvibe.rules.open_async import OpenAsyncRule
from pyvibe.rules.httpx_sync import HttpxSyncRule
from pyvibe.rules.os_blocking import OsBlockingRule
from pyvibe.rules.create_task_orphan import CreateTaskOrphanRule
from pyvibe.rules.gather_no_return_exceptions import GatherNoReturnExceptionsRule
from pyvibe.rules.ensure_future_orphan import EnsureFutureOrphanRule
from pyvibe.rules.loop_run_until_complete import LoopRunUntilCompleteRule
from pyvibe.rules.httpx_client_sync import HttpxClientSyncRule
from pyvibe.rules.silent_except import SilentExceptRule
from pyvibe.rules.while_true_no_await import WhileTrueNoAwaitRule
from pyvibe.rules.retry_no_backoff import RetryNoBackoffRule
from pyvibe.rules.queue_put_nowait import QueuePutNowaitRule

ALL_RULES = [
    AsyncSleepRule,
    AsyncRequestsRule,
    AsyncioRunRule,
    ThreadingLockRule,
    CeleryTaskTimeLimitRule,
    SubprocessAsyncRule,
    SqliteAsyncRule,
    OpenAsyncRule,
    HttpxSyncRule,
    OsBlockingRule,
    ContextVarCleanupRule,
    CreateTaskOrphanRule,
    GatherNoReturnExceptionsRule,
    EnsureFutureOrphanRule,
    LoopRunUntilCompleteRule,
    HttpxClientSyncRule,
    SilentExceptRule,
    WhileTrueNoAwaitRule,
    RetryNoBackoffRule,
    QueuePutNowaitRule,
]

ALL_RULE_IDS: FrozenSet[str] = frozenset(r.RULE_ID for r in ALL_RULES)

# Rules that build a concrete "Suggested fix" snippet from the real source
# text (see pyvibe/autofix.py) and therefore need the full source passed
# into their constructor.
_NEEDS_SOURCE: FrozenSet[type] = frozenset({
    AsyncSleepRule,
    AsyncRequestsRule,
    AsyncioRunRule,
    SubprocessAsyncRule,
    SqliteAsyncRule,
})

# Rules downgraded CRITICAL → WARNING when the violation is inside a test file.
# time.sleep in fixtures, subprocess in service-startup helpers, open() in
# async test helpers (e.g. asyncssh, aiofiles own test suites), and Celery task
# fixtures in test suites (e.g. celery/t/) that intentionally omit time_limit.
TEST_FILE_DOWNGRADE: FrozenSet[str] = frozenset({
    "PYVIBE-001",  # time.sleep — valid in timing tests
    "PYVIBE-005",  # celery task — fixtures intentionally omit time_limit
    "PYVIBE-006",  # ContextVar.set — test subjects verifying propagation
    "PYVIBE-007",  # subprocess.run — launching test servers/processes
    "PYVIBE-008",  # sqlite3.connect — smoke tests using real sqlite
    "PYVIBE-009",  # open() — test helpers, aiofiles own test suite
    "PYVIBE-012",  # create_task orphan — concurrent setup in tests
    "PYVIBE-013",  # gather no return_exceptions — test stubs
    "PYVIBE-014",  # ensure_future orphan — concurrent setup in tests
    "PYVIBE-016",  # httpx.Client sync — test transport fixtures
})


# Non-production directory segments: a CRITICAL finding whose path has any of
# these as a FULL directory segment is downgraded to WARNING (never silenced).
# Full-segment match only, so `com/example/` (segment "example", not "examples")
# and `app/my_tests_utils.py` (filename contains "tests", no such segment) are
# NOT downgraded. (FASE1-DISENO.md point 1 / decision 2026-10-14.)
_NONPROD_SEGMENTS: FrozenSet[str] = frozenset({
    "tests", "test", "scripts", "wip", "spike", "examples",
})


def _is_test_file(filepath: str) -> bool:
    p = Path(filepath)
    name = p.name
    dir_segments = p.parts[:-1]  # directory segments only, never the filename
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name == "conftest.py"
        or any(seg in _NONPROD_SEGMENTS for seg in dir_segments)
    )


def analyze_source_full(
    source: str,
    filepath: str = "<string>",
    *,
    downgrade_in_tests: FrozenSet[str] = ALL_RULE_IDS,
    config: Optional[PyvibeConfig] = None,
    report_broad_except: bool = False,
) -> Tuple[List[Violation], List[Tuple[Violation, str]]]:
    """Parse source and run all rules. Returns (reported, suppressed) where
    suppressed is a list of (Violation, reason) with reason "inline" (a
    `# pyvibe: ignore ...` comment) or "config" (pyvibe.toml's [tool.pyvibe]
    ignore list).

    downgrade_in_tests: rule IDs whose severity is lowered to WARNING when
    the file is detected as a test file. Pass frozenset() to disable all
    downgrading, or ALL_RULE_IDS to downgrade every rule.

    config: optional PyvibeConfig (see pyvibe/config.py) applying a global
    ignore list and per-rule severity overrides on top of the above.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], []

    source_lines = source.splitlines()
    broad_except = report_broad_except or bool(config.report_broad_except if config else False)
    violations = []
    for RuleClass in ALL_RULES:
        if RuleClass is SilentExceptRule:
            visitor = RuleClass(source_lines, report_broad_except=broad_except)
        elif RuleClass in _NEEDS_SOURCE:
            visitor = RuleClass(source)
        else:
            visitor = RuleClass()
        visitor.visit(tree)
        violations.extend(visitor.violations)

    if downgrade_in_tests and _is_test_file(filepath):
        for v in violations:
            # Rebaja, never silence: only CRITICAL is lowered to WARNING.
            if v.rule_id in downgrade_in_tests and v.severity == "CRITICAL":
                v.severity = "WARNING"

    if config and config.severity:
        for v in violations:
            if v.rule_id in config.severity:
                v.severity = config.severity[v.rule_id]

    violations.sort(key=lambda v: v.line)

    inline_suppressions = parse_inline_suppressions(source)
    reported: List[Violation] = []
    suppressed: List[Tuple[Violation, str]] = []
    for v in violations:
        if v.rule_id in inline_suppressions.get(v.line, frozenset()):
            suppressed.append((v, "inline"))
        elif config and v.rule_id in config.ignore:
            suppressed.append((v, "config"))
        else:
            reported.append(v)

    return reported, suppressed


def analyze_source(
    source: str,
    filepath: str = "<string>",
    *,
    downgrade_in_tests: FrozenSet[str] = ALL_RULE_IDS,
    config: Optional[PyvibeConfig] = None,
) -> List[Violation]:
    """Parse source and run all rules. Returns the reported (non-suppressed)
    violations — see analyze_source_full() for the suppressed ones too.
    """
    reported, _ = analyze_source_full(
        source, filepath, downgrade_in_tests=downgrade_in_tests, config=config
    )
    return reported


def analyze_file_full(
    path: Path,
    *,
    downgrade_in_tests: FrozenSet[str] = ALL_RULE_IDS,
    config: Optional[PyvibeConfig] = None,
) -> Tuple[List[Violation], List[Tuple[Violation, str]]]:
    source = path.read_text(encoding="utf-8", errors="ignore")
    return analyze_source_full(
        source, filepath=str(path), downgrade_in_tests=downgrade_in_tests, config=config
    )


def analyze_file(
    path: Path,
    *,
    downgrade_in_tests: FrozenSet[str] = ALL_RULE_IDS,
    line_filter: Optional[FrozenSet[int]] = None,
    config: Optional[PyvibeConfig] = None,
) -> List[Violation]:
    """line_filter: if given, only violations whose `line` is in this set
    are returned (used by `pyvibe review` to report only diff-touched lines).
    """
    source = path.read_text(encoding="utf-8", errors="ignore")
    violations = analyze_source(
        source, filepath=str(path), downgrade_in_tests=downgrade_in_tests, config=config
    )
    if line_filter is not None:
        violations = [v for v in violations if v.line in line_filter]
    return violations


DEFAULT_EXCLUDES = frozenset({
    "venv", ".venv", "env", "__pycache__", ".git",
    "node_modules", ".tox", "dist", "build", ".eggs",
})


def analyze_directory(
    root: Path,
    exclude: frozenset = DEFAULT_EXCLUDES,
    *,
    skip_test_files: bool = False,
    downgrade_in_tests: FrozenSet[str] = ALL_RULE_IDS,
    config: Optional[PyvibeConfig] = None,
) -> dict:
    """Walk directory and analyze all .py files. Returns {path: [violations]}.

    Directories whose *name* appears in `exclude` are skipped entirely.
    skip_test_files: if True, files matching test_*.py / *_test.py / tests/* are
    omitted from results entirely rather than downgraded.
    config: optional PyvibeConfig — files matching its exclude glob patterns
    are also skipped entirely.
    """
    results = {}
    for py_file in _walk(root, exclude):
        if skip_test_files and _is_test_file(str(py_file)):
            continue
        if config and is_excluded(py_file, config):
            continue
        violations = analyze_file(py_file, downgrade_in_tests=downgrade_in_tests, config=config)
        if violations:
            results[py_file] = violations
    return results


def analyze_directory_full(
    root: Path,
    exclude: frozenset = DEFAULT_EXCLUDES,
    *,
    skip_test_files: bool = False,
    downgrade_in_tests: FrozenSet[str] = ALL_RULE_IDS,
    config: Optional[PyvibeConfig] = None,
) -> Tuple[dict, List[Tuple[Path, Violation, str]]]:
    """Like analyze_directory(), but also returns the suppressed findings
    (across every scanned file) as a flat list of (path, Violation, reason).
    """
    results = {}
    all_suppressed: List[Tuple[Path, Violation, str]] = []
    for py_file in _walk(root, exclude):
        if skip_test_files and _is_test_file(str(py_file)):
            continue
        if config and is_excluded(py_file, config):
            continue
        reported, suppressed = analyze_file_full(
            py_file, downgrade_in_tests=downgrade_in_tests, config=config
        )
        if reported:
            results[py_file] = reported
        all_suppressed.extend((py_file, v, reason) for v, reason in suppressed)
    return results, all_suppressed


def _walk(root: Path, exclude: frozenset):
    """Yield .py files under root, skipping any directory in exclude."""
    for entry in sorted(root.iterdir()):
        if entry.is_dir():
            if entry.name not in exclude:
                yield from _walk(entry, exclude)
        elif entry.suffix == ".py":
            yield entry
