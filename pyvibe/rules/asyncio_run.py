import ast
from typing import List, Optional
from pyvibe.autofix import render_node
from pyvibe.rules.base import Violation, AsyncBlockingCallVisitor


class AsyncioRunRule(AsyncBlockingCallVisitor):
    """
    PYVIBE-003 — asyncio.run() inside async def

    asyncio.run() creates a *new* event loop and blocks until the coroutine
    completes. Calling it from within a running loop raises:
        RuntimeError: This event loop is already running.

    AI-generated code frequently does this when mixing sync entrypoints
    with async handlers — it compiles, passes basic tests, and explodes
    at runtime in FastAPI / async frameworks.

    Fix: use `await coroutine()` directly.
    """

    RULE_ID = "PYVIBE-003"
    SEVERITY = "CRITICAL"

    def __init__(self, source: Optional[str] = None):
        super().__init__()
        self._source = source

    def visit_Call(self, node: ast.Call):
        if self._current_async_func is None:
            self.generic_visit(node)
            return

        if self._is_asyncio_run(node):
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message="asyncio.run() inside async def raises RuntimeError at runtime",
                evidence="Use `await coroutine()` directly — asyncio.run() is for sync entrypoints only",
                suggested_fix=self._suggest_fix(node),
            ))

        self.generic_visit(node)

    def _suggest_fix(self, node: ast.Call) -> Optional[str]:
        if not self._source or not node.args:
            return None
        coro_src = render_node(self._source, node.args[0])
        if not coro_src:
            return None
        return f"await {coro_src}"

    def _is_asyncio_run(self, node: ast.Call) -> bool:
        # asyncio.run(...)
        return (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "asyncio"
        )
