import ast
from pyvibe.rules.base import Violation, AsyncBlockingCallVisitor


class LoopRunUntilCompleteRule(AsyncBlockingCallVisitor):
    """
    PYVIBE-015 — loop.run_until_complete() inside async def

    run_until_complete() blocks the calling OS thread until the coroutine
    finishes. Calling it from inside an already-running async function raises
    RuntimeError at runtime ("This event loop is already running") and defeats
    the entire purpose of async/await. AI-generated code that wraps existing
    sync code often makes this mistake when trying to "bridge" sync and async.

    Fix: replace `loop.run_until_complete(coro())` with `await coro()` directly.
    """

    RULE_ID = "PYVIBE-015"
    SEVERITY = "CRITICAL"

    def visit_Call(self, node: ast.Call):
        if self._current_async_func and self._is_run_until_complete(node):
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message="loop.run_until_complete() inside async def — raises RuntimeError at runtime (event loop already running)",
                evidence="Replace with `await coro()` directly; the enclosing async function is already on the event loop",
            ))
        self.generic_visit(node)

    def _is_run_until_complete(self, node: ast.Call) -> bool:
        return (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "run_until_complete"
        )
