import ast
from typing import List
from pyvibe.rules.base import Violation


class AsyncSleepRule(ast.NodeVisitor):
    """
    PYVIBE-001 — time.sleep() inside async def

    Blocks the event loop entirely. All concurrent tasks on the same
    loop are frozen for the duration of the sleep. Under load, this
    causes cascading timeouts that look like random failures.

    Fix: use `await asyncio.sleep(n)` instead.
    """

    RULE_ID = "PYVIBE-001"
    SEVERITY = "CRITICAL"

    def __init__(self):
        self.violations: List[Violation] = []
        self._current_async_func: str = None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        previous = self._current_async_func
        self._current_async_func = node.name
        self.generic_visit(node)
        self._current_async_func = previous

    def visit_Call(self, node: ast.Call):
        if self._current_async_func is None:
            self.generic_visit(node)
            return

        if self._is_time_sleep(node):
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message="time.sleep() blocks the entire event loop",
                evidence="Use `await asyncio.sleep(n)` instead",
            ))

        self.generic_visit(node)

    def _is_time_sleep(self, node: ast.Call) -> bool:
        # time.sleep(n)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "sleep"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "time"
        ):
            return True

        # from time import sleep → sleep(n)
        if isinstance(node.func, ast.Name) and node.func.id == "sleep":
            return True

        return False
