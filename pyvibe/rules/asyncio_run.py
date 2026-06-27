import ast
from typing import List
from pyvibe.rules.base import Violation


class AsyncioRunRule(ast.NodeVisitor):
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

    def __init__(self):
        self.violations: List[Violation] = []
        self._current_async_func: str = None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        previous = self._current_async_func
        self._current_async_func = node.name
        self.generic_visit(node)
        self._current_async_func = previous

    def visit_FunctionDef(self, node: ast.FunctionDef):
        previous = self._current_async_func
        self._current_async_func = None
        self.generic_visit(node)
        self._current_async_func = previous

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
            ))

        self.generic_visit(node)

    def _is_asyncio_run(self, node: ast.Call) -> bool:
        # asyncio.run(...)
        return (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "asyncio"
        )
