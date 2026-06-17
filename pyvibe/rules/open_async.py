import ast
from typing import List
from pyvibe.rules.base import Violation


class OpenAsyncRule(ast.NodeVisitor):
    """
    PYVIBE-009 — open() builtin inside async def

    The builtin open() performs synchronous file I/O. Each call blocks the
    OS thread until the kernel completes the read/write, preventing the event
    loop from scheduling other coroutines. AI-generated FastAPI code routinely
    mixes open() with async endpoints.

    aiofiles.open() is an ast.Attribute node — structurally different from the
    bare ast.Name 'open', so it is never matched by this rule.

    Fix: use `async with aiofiles.open(path) as f: content = await f.read()`.
    """

    RULE_ID = "PYVIBE-009"
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

        if isinstance(node.func, ast.Name) and node.func.id == "open":
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message="open() performs synchronous file I/O — blocks the event loop",
                evidence="Use `async with aiofiles.open(path) as f: content = await f.read()`",
            ))

        self.generic_visit(node)
