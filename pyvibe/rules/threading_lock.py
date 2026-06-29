import ast
from typing import List, Set
from pyvibe.rules.base import Violation, AsyncBlockingCallVisitor

# threading.Event is a signalling primitive (set/wait), not a lock — it does not
# block the event loop in the same way and is legitimately used as a sync↔async
# bridge (e.g. signalling a Playwright or subprocess thread). Excluded deliberately.
THREADING_PRIMITIVES = {"Lock", "RLock", "Semaphore", "BoundedSemaphore", "Condition"}


class ThreadingLockRule(AsyncBlockingCallVisitor):
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
        super().__init__()
        # Names bound to the `threading` module via `import threading [as X]`
        self._threading_aliases: Set[str] = set()
        # Names imported directly from threading: `from threading import Lock`
        self._from_threading: Set[str] = set()

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name == "threading":
                self._threading_aliases.add(alias.asname if alias.asname else alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module == "threading":
            for alias in node.names:
                if alias.name in THREADING_PRIMITIVES:
                    self._from_threading.add(alias.asname if alias.asname else alias.name)
        self.generic_visit(node)

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
        # Guard against NAME_COLLISION: only flag when the receiver is known to
        # be bound to the `threading` module via an import statement.
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in THREADING_PRIMITIVES
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in self._threading_aliases
        ):
            return node.func.attr

        # from threading import Lock → Lock()
        # Guard against NAME_COLLISION: bare names only fire when the name was
        # explicitly imported from threading (e.g. anyio.Lock or a custom Lock
        # class would not be in _from_threading and are correctly skipped).
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in self._from_threading
        ):
            return node.func.id

        return None
