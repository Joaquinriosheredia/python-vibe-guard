import ast
from typing import List, Optional
from pyvibe.rules.base import Violation


def _catches_queuefull(handlers: list) -> bool:
    """True if any handler catches asyncio.QueueFull, QueueFull, bare except, or Exception."""
    for h in handlers:
        t = h.type
        if t is None:  # bare except — catches everything
            return True
        if isinstance(t, ast.Name) and t.id in ("QueueFull", "Exception"):
            return True
        if isinstance(t, ast.Attribute) and t.attr in ("QueueFull", "Exception"):
            return True
        if isinstance(t, ast.Tuple):  # except (QueueFull, ...) — tuple of types
            for elt in t.elts:
                if isinstance(elt, ast.Name) and elt.id in ("QueueFull", "Exception"):
                    return True
                if isinstance(elt, ast.Attribute) and elt.attr in ("QueueFull", "Exception"):
                    return True
    return False


class QueuePutNowaitRule(ast.NodeVisitor):
    """
    PYVIBE-020 — put_nowait() without asyncio.QueueFull handler

    asyncio.Queue.put_nowait() raises asyncio.QueueFull immediately when the
    queue is at maxsize. Unless caught, the exception propagates and the item
    is silently lost — no log, no retry, no metric. This affects any queue
    with maxsize > 0 (unbounded queues never raise, but maxsize is often set
    later or injected).

    Fix: wrap in try/except asyncio.QueueFull and decide explicitly what to
    do — log and drop, or switch to `await queue.put()` to block instead.

    Fires in any function context (sync and async). The guard is the absence
    of an enclosing try/except that catches asyncio.QueueFull or Exception.
    """

    RULE_ID = "PYVIBE-020"
    SEVERITY = "WARNING"

    def __init__(self):
        self.violations: List[Violation] = []
        self._current_func: Optional[str] = None
        self._protected_depth: int = 0  # try/except with QueueFull handler nesting depth

    def visit_FunctionDef(self, node: ast.FunctionDef):
        prev = self._current_func
        self._current_func = node.name
        self.generic_visit(node)
        self._current_func = prev

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        prev = self._current_func
        self._current_func = node.name
        self.generic_visit(node)
        self._current_func = prev

    def visit_Try(self, node: ast.Try):
        protected = _catches_queuefull(node.handlers)
        if protected:
            self._protected_depth += 1
        for stmt in node.body:
            self.visit(stmt)
        if protected:
            self._protected_depth -= 1
        # handlers, orelse, finalbody are NOT covered by this try's own handlers
        for handler in node.handlers:
            self.visit(handler)
        for stmt in node.orelse:
            self.visit(stmt)
        for stmt in node.finalbody:
            self.visit(stmt)

    def visit_Call(self, node: ast.Call):
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "put_nowait"
            and self._protected_depth == 0
        ):
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_func or "<module>",
                message=(
                    "put_nowait() without asyncio.QueueFull handler — "
                    "raises silently if queue is full, item is lost"
                ),
                evidence=(
                    "Wrap in `try/except asyncio.QueueFull:` and log or handle explicitly, "
                    "or use `await queue.put()` to block until space is available"
                ),
            ))
        self.generic_visit(node)
