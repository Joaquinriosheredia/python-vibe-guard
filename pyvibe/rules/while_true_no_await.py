import ast
from typing import List, Optional
from pyvibe.rules.base import Violation


def _has_await_in_scope(nodes) -> bool:
    """Return True if any await exists in the given nodes, not crossing function boundaries."""
    for node in nodes:
        if isinstance(node, ast.Await):
            return True
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            # new scope — awaits inside don't help the outer loop
            continue
        for child in ast.iter_child_nodes(node):
            if _has_await_in_scope([child]):
                return True
    return False


class WhileTrueNoAwaitRule(ast.NodeVisitor):
    """
    PYVIBE-018 — while True without await inside async def

    An infinite loop in an async function with no await point monopolises the
    event loop indefinitely — no other coroutine can run, and CPU usage hits
    100%. AI-generated worker loops frequently omit the await.

    Fix: add `await asyncio.sleep(0)` (yield control) or any real await inside
    the loop body.
    """

    RULE_ID = "PYVIBE-018"
    SEVERITY = "CRITICAL"

    def __init__(self):
        self.violations: List[Violation] = []
        self._current_async_func: Optional[str] = None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        previous = self._current_async_func
        self._current_async_func = node.name
        self.generic_visit(node)
        self._current_async_func = previous

    def visit_While(self, node: ast.While):
        if (
            self._current_async_func
            and isinstance(node.test, ast.Constant)
            and node.test.value is True
            and not _has_await_in_scope(node.body)
        ):
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message=(
                    "while True loop inside async def has no await — "
                    "event loop blocked indefinitely"
                ),
                evidence=(
                    "Add `await asyncio.sleep(0)` to yield control, "
                    "or `await asyncio.sleep(N)` for a real polling interval"
                ),
            ))
        self.generic_visit(node)
