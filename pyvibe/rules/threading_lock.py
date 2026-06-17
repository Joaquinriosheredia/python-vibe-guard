import ast
from typing import List
from pyvibe.rules.base import Violation

THREADING_PRIMITIVES = {"Lock", "RLock", "Semaphore", "BoundedSemaphore", "Event", "Condition"}


class ThreadingLockRule(ast.NodeVisitor):
    """
    PYVIBE-004 — threading.Lock (and other threading primitives) inside async def

    threading.Lock.acquire() is a blocking call. When used inside an async
    function it blocks the OS thread, preventing the event loop from
    scheduling other coroutines. This is the async equivalent of
    synchronized + Virtual Threads pinning in Java.

    AI models mix threading and asyncio when they copy sync patterns into
    async code — the bug only surfaces under concurrent load.

    Fix: use `asyncio.Lock()` with `async with lock:`.
    """

    RULE_ID = "PYVIBE-004"
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

        primitive = self._get_threading_primitive(node)
        if primitive:
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message=f"threading.{primitive}() blocks the event loop under contention",
                evidence="Use `asyncio.Lock()` with `async with lock:` instead",
            ))

        self.generic_visit(node)

    def _get_threading_primitive(self, node: ast.Call):
        # threading.Lock(), threading.RLock(), etc.
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in THREADING_PRIMITIVES
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "threading"
        ):
            return node.func.attr

        # from threading import Lock → Lock()
        if isinstance(node.func, ast.Name) and node.func.id in THREADING_PRIMITIVES:
            return node.func.id

        return None
