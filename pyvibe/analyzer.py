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

ALL_RULES = [
    AsyncSleepRule,
    AsyncRequestsRule,
    AsyncioRunRule,
    ThreadingLockRule,
    CeleryTaskTimeLimitRule,
    SubprocessAsyncRule,
    SqliteAsyncRule,
    OpenAsyncRule,
    ContextVarCleanupRule,
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


def analyze_directory(root: Path) -> dict:
    """Walk directory and analyze all .py files. Returns {path: [violations]}."""
    results = {}
    for py_file in sorted(root.rglob("*.py")):
        violations = analyze_file(py_file)
        if violations:
            results[py_file] = violations
    return results
