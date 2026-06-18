import ast
from pathlib import Path
from typing import List

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
]


def analyze_source(source: str, filepath: str = "<string>") -> List[Violation]:
    """Parse source and run all rules. Returns list of violations."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    violations = []
    for RuleClass in ALL_RULES:
        visitor = RuleClass()
        visitor.visit(tree)
        violations.extend(visitor.violations)

    violations.sort(key=lambda v: v.line)
    return violations


def analyze_file(path: Path) -> List[Violation]:
    source = path.read_text(encoding="utf-8", errors="ignore")
    return analyze_source(source, filepath=str(path))


DEFAULT_EXCLUDES = frozenset({
    "venv", ".venv", "env", "__pycache__", ".git",
    "node_modules", ".tox", "dist", "build", ".eggs",
})


def analyze_directory(root: Path, exclude: frozenset = DEFAULT_EXCLUDES) -> dict:
    """Walk directory and analyze all .py files. Returns {path: [violations]}.

    Directories whose *name* appears in `exclude` are skipped entirely.
    """
    results = {}
    for py_file in _walk(root, exclude):
        violations = analyze_file(py_file)
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
