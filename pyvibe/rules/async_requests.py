import ast
from typing import List
from pyvibe.rules.base import Violation

REQUESTS_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "request"}


class AsyncRequestsRule(ast.NodeVisitor):
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
        # requests.get(...), requests.post(...), etc.
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in REQUESTS_METHODS
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "requests"
        ):
            return node.func.attr

        # from requests import get → get(...)
        if isinstance(node.func, ast.Name) and node.func.id in REQUESTS_METHODS:
            return node.func.id

        return None
