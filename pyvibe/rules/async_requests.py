import ast
from typing import List, Set
from pyvibe.rules.base import Violation, AsyncBlockingCallVisitor

REQUESTS_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "request"}


class AsyncRequestsRule(AsyncBlockingCallVisitor):
    """
    PYVIBE-002 — requests.* inside async def

    `requests` is a synchronous HTTP library. Calling it inside an async
    function blocks the OS thread running the event loop. Under concurrent
    load this serialises all I/O and eliminates any benefit of async.

    Fix: use `httpx.AsyncClient` or `aiohttp.ClientSession` with await.
    """

    RULE_ID = "PYVIBE-002"
    SEVERITY = "CRITICAL"

    def __init__(self):
        super().__init__()
        # Names bound to the `requests` module via `import requests [as X]`
        self._requests_aliases: Set[str] = set()

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name == "requests":
                self._requests_aliases.add(alias.asname if alias.asname else alias.name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if self._current_async_func is None:
            self.generic_visit(node)
            return

        method = self._get_requests_method(node)
        if method:
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message=f"requests.{method}() is synchronous — blocks the event loop",
                evidence=f"Use `async with httpx.AsyncClient() as c: await c.{method}(url)`",
            ))

        self.generic_visit(node)

    def _get_requests_method(self, node: ast.Call):
        # requests.get(...), requests.post(...), etc. — qualified form only.
        # Guard against NAME_COLLISION: only flag when the receiver name is
        # known to be bound to the `requests` module via an import statement.
        # Without this, `requests = get_pending_requests(); requests.get(key)`
        # (a dict/object .get() call) would be a false positive.
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in REQUESTS_METHODS
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in self._requests_aliases
        ):
            return node.func.attr

        return None
