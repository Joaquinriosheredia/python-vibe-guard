import ast
from typing import List
from pyvibe.rules.base import Violation

HTTPX_BLOCKING = {"get", "post", "put", "patch", "delete", "request", "stream"}


class HttpxSyncRule(ast.NodeVisitor):
    """
    PYVIBE-010 — httpx top-level sync methods inside async def

    httpx exposes both a synchronous API (httpx.get, httpx.post, …) and an
    async API (httpx.AsyncClient). AI-generated code frequently uses the sync
    top-level functions inside async handlers, blocking the OS thread for the
    full HTTP round-trip.

    httpx.AsyncClient() has attr='AsyncClient' — outside HTTPX_BLOCKING —
    so it is never matched by this rule.

    Fix: async with httpx.AsyncClient() as client: response = await client.get(url)
    """

    RULE_ID = "PYVIBE-010"
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

        method = self._get_httpx_method(node)
        if method:
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message=f"httpx.{method}() is synchronous — blocks the event loop for the full HTTP round-trip",
                evidence=f"Use `async with httpx.AsyncClient() as client: await client.{method}(url)`",
            ))

        self.generic_visit(node)

    def _get_httpx_method(self, node: ast.Call):
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in HTTPX_BLOCKING
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "httpx"
        ):
            return node.func.attr
        return None
