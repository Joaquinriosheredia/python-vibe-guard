import ast
from typing import List, Optional
from pyvibe.autofix import render_call_args
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

    def __init__(self, source: Optional[str] = None):
        super().__init__()
        self._source = source

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
                suggested_fix=self._suggest_fix(node),
            ))

        self.generic_visit(node)

    def _suggest_fix(self, node: ast.Call) -> Optional[str]:
        if not self._source:
            return None
        args_src = render_call_args(self._source, node)
        return f"await asyncio.sleep({args_src})"

    def _is_time_sleep(self, node: ast.Call) -> bool:
        # time.sleep(n) — qualified form only; bare sleep() excluded (false positives)
        return (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "sleep"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "time"
        )
