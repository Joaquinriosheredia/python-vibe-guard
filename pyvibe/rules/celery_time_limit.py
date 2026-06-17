import ast
from typing import List
from pyvibe.rules.base import Violation

_LIMIT_KEYS = {"soft_time_limit", "time_limit"}


class CeleryTaskTimeLimitRule(ast.NodeVisitor):
    """
    PYVIBE-005 — Celery task defined without soft_time_limit or time_limit

    A Celery task with no time limit can hang indefinitely if the external
    call it wraps never returns — blocking a worker process permanently.
    Under load, all workers fill with hung tasks and the queue stalls.

    Detected decorators: @app.task, @shared_task (bare or with kwargs).
    Fix: @app.task(soft_time_limit=30, time_limit=60)
    """

    RULE_ID = "PYVIBE-005"
    SEVERITY = "CRITICAL"

    def __init__(self):
        self.violations: List[Violation] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check(node)
        self.generic_visit(node)

    # ── private ──────────────────────────────────────────────────────────────

    def _check(self, node):
        for decorator in node.decorator_list:
            if self._is_task_decorator(decorator) and not self._has_time_limit(decorator):
                self.violations.append(Violation(
                    rule_id=self.RULE_ID,
                    severity=self.SEVERITY,
                    line=node.lineno,
                    function_name=node.name,
                    message="Celery task defined without soft_time_limit or time_limit — can hang forever",
                    evidence="Use @app.task(soft_time_limit=30, time_limit=60) to bound execution time",
                ))
                break  # one violation per function, even if decorated twice

    def _is_task_decorator(self, decorator: ast.expr) -> bool:
        # Unwrap @app.task(...) or @shared_task(...) to their func node
        node = decorator.func if isinstance(decorator, ast.Call) else decorator
        # @shared_task
        if isinstance(node, ast.Name) and node.id == "shared_task":
            return True
        # @app.task  /  @celery.task  /  @<any>.task
        if isinstance(node, ast.Attribute) and node.attr == "task":
            return True
        return False

    def _has_time_limit(self, decorator: ast.expr) -> bool:
        # Bare decorator (@app.task with no call) → no kwargs possible
        if not isinstance(decorator, ast.Call):
            return False
        return any(kw.arg in _LIMIT_KEYS for kw in decorator.keywords)
