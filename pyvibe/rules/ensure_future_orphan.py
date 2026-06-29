import ast
from pyvibe.rules.base import Violation, AsyncContextVisitor


class EnsureFutureOrphanRule(AsyncContextVisitor):
    """
    PYVIBE-014 — asyncio.ensure_future() with discarded return value

    ensure_future() (the pre-3.7 predecessor to create_task()) schedules a
    coroutine and returns a Task/Future. If the return value is not retained,
    the garbage collector can cancel the task mid-execution and any exception
    is silently swallowed. Identical hazard to PYVIBE-012 but with a different
    API that is still widespread in older codebases.

    Fix: assign the result and await it, or migrate to asyncio.create_task()
    (Python 3.7+) / asyncio.TaskGroup (Python 3.11+).
    """

    RULE_ID = "PYVIBE-014"
    SEVERITY = "CRITICAL"

    def visit_Expr(self, node: ast.Expr):
        if self._current_async_func and self._is_ensure_future(node.value):
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message="asyncio.ensure_future() return value discarded — task may be GC'd and silently cancelled",
                evidence=(
                    "Assign and await: `task = asyncio.ensure_future(coro()); await task`, "
                    "or migrate to `asyncio.create_task(coro())` (Python 3.7+)"
                ),
            ))
        self.generic_visit(node)

    def _is_ensure_future(self, node: ast.expr) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "ensure_future"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "asyncio"
        )
