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


def _has_yield_in_body(nodes) -> bool:
    """Return True if body contains yield/yield-from, not crossing function boundaries.

    An async def that yields is an async generator — each `yield` suspends the
    generator and gives control back to the caller's `await __anext__()`, so it
    IS a valid event-loop checkpoint and must not be flagged by PYVIBE-018.
    """
    for node in nodes:
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            return True
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue  # inner function's yields are its own scope
        for child in ast.iter_child_nodes(node):
            if _has_yield_in_body([child]):
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

    Exclusion: async generators (async def bodies that contain `yield` or
    `yield from`) are not flagged — each `yield` suspends the generator and the
    caller's `await __anext__()` is a real event-loop checkpoint.
    """

    RULE_ID = "PYVIBE-018"
    SEVERITY = "CRITICAL"

    def __init__(self):
        self.violations: List[Violation] = []
        self._current_async_func: Optional[str] = None
        self._current_func_is_async_gen: bool = False

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        previous = self._current_async_func
        previous_is_gen = self._current_func_is_async_gen
        self._current_async_func = node.name
        self._current_func_is_async_gen = _has_yield_in_body(node.body)
        self.generic_visit(node)
        self._current_async_func = previous
        self._current_func_is_async_gen = previous_is_gen

    def visit_FunctionDef(self, node: ast.FunctionDef):
        previous = self._current_async_func
        previous_is_gen = self._current_func_is_async_gen
        self._current_async_func = None
        self._current_func_is_async_gen = False
        self.generic_visit(node)
        self._current_async_func = previous
        self._current_func_is_async_gen = previous_is_gen

    def visit_Lambda(self, node: ast.Lambda):
        previous = self._current_async_func
        previous_is_gen = self._current_func_is_async_gen
        self._current_async_func = None
        self._current_func_is_async_gen = False
        self.generic_visit(node)
        self._current_async_func = previous
        self._current_func_is_async_gen = previous_is_gen

    def visit_While(self, node: ast.While):
        if (
            self._current_async_func
            and not self._current_func_is_async_gen
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
