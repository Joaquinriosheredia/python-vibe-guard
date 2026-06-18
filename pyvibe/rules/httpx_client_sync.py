import ast
from typing import List
from pyvibe.rules.base import Violation


class HttpxClientSyncRule(ast.NodeVisitor):
    """
    PYVIBE-016 — httpx.Client() instantiated inside async def

    httpx.Client is the synchronous client. Every request it makes blocks
    the OS thread for the full HTTP round-trip, starving all other coroutines
    on the event loop. AI-generated code frequently picks httpx.Client over
    httpx.AsyncClient because the sync API looks simpler.

    httpx.AsyncClient() has attr='AsyncClient', which is explicitly excluded.

    Fix: use `async with httpx.AsyncClient() as client: response = await client.get(url)`.
    """

    RULE_ID = "PYVIBE-016"
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
        if self._current_async_func and self._is_httpx_client_sync(node):
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message="httpx.Client() is synchronous — blocks the event loop for every HTTP request",
                evidence=(
                    "Use `async with httpx.AsyncClient() as client: response = await client.get(url)` instead"
                ),
            ))
        self.generic_visit(node)

    def _is_httpx_client_sync(self, node: ast.Call) -> bool:
        return (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "Client"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "httpx"
        )
