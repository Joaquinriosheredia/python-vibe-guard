import ast
from pathlib import Path
from typing import FrozenSet, List

from pyvibe.rules.base import Violation
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

# Rules downgraded CRITICAL → WARNING when the violation is inside a test file.
# time.sleep in fixtures and subprocess in service-startup helpers are valid patterns.
TEST_FILE_DOWNGRADE: FrozenSet[str] = frozenset({"PYVIBE-001", "PYVIBE-007", "PYVIBE-013"})


def _is_test_file(filepath: str) -> bool:
    p = Path(filepath)
    name = p.name
    parts = p.parts
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or "tests" in parts
        or "test" in parts
    )


def analyze_source(
    source: str,
    filepath: str = "<string>",
    *,
    downgrade_in_tests: FrozenSet[str] = TEST_FILE_DOWNGRADE,
) -> List[Violation]:
    """Parse source and run all rules. Returns list of violations.

    downgrade_in_tests: rule IDs whose severity is lowered to WARNING when
    the file is detected as a test file. Pass frozenset() to disable all
    downgrading, or ALL_RULE_IDS to downgrade every rule.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    violations = []
    for RuleClass in ALL_RULES:
        visitor = RuleClass()
        visitor.visit(tree)
        violations.extend(visitor.violations)

    if downgrade_in_tests and _is_test_file(filepath):
        for v in violations:
            if v.rule_id in downgrade_in_tests:
                v.severity = "WARNING"

    violations.sort(key=lambda v: v.line)
    return violations


def analyze_file(
    path: Path,
    *,
    downgrade_in_tests: FrozenSet[str] = TEST_FILE_DOWNGRADE,
) -> List[Violation]:
    source = path.read_text(encoding="utf-8", errors="ignore")
    return analyze_source(source, filepath=str(path), downgrade_in_tests=downgrade_in_tests)


DEFAULT_EXCLUDES = frozenset({
    "venv", ".venv", "env", "__pycache__", ".git",
    "node_modules", ".tox", "dist", "build", ".eggs",
})


def analyze_directory(
    root: Path,
    exclude: frozenset = DEFAULT_EXCLUDES,
    *,
    skip_test_files: bool = False,
    downgrade_in_tests: FrozenSet[str] = TEST_FILE_DOWNGRADE,
) -> dict:
    """Walk directory and analyze all .py files. Returns {path: [violations]}.

    Directories whose *name* appears in `exclude` are skipped entirely.
    skip_test_files: if True, files matching test_*.py / *_test.py / tests/* are
    omitted from results entirely rather than downgraded.
    """
    results = {}
    for py_file in _walk(root, exclude):
        if skip_test_files and _is_test_file(str(py_file)):
            continue
        violations = analyze_file(py_file, downgrade_in_tests=downgrade_in_tests)
        if violations:
            results[py_file] = violations
    return results


def _walk(root: Path, exclude: frozenset):
    """Yield .py files under root, skipping any directory in exclude."""
    for entry in sorted(root.iterdir()):
        if entry.is_dir():
            if entry.name not in exclude:
                yield from _walk(entry, exclude)
        elif entry.suffix == ".py":
            yield entry
