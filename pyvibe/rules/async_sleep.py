import ast
from typing import List
from pyvibe.rules.base import Violation, AsyncBlockingCallVisitor


class AsyncSleepRule(AsyncBlockingCallVisitor):
    """
    PYVIBE-001 — time.sleep() inside async def

    Blocks the event loop entirely. All concurrent tasks on the same
    loop are frozen for the duration of the sleep. Under load, this
    causes cascading timeouts that look like random failures.

    Fix: use `await asyncio.sleep(n)` instead.
    """

    RULE_ID = "PYVIBE-001"
    SEVERITY = "CRITICAL"

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
        # time.sleep(n) — qualified form only; bare sleep() excluded (false positives)
        return (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "sleep"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "time"
        )
