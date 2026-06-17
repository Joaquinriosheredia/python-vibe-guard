import ast
from typing import List
from pyvibe.rules.base import Violation


class SqliteAsyncRule(ast.NodeVisitor):
    """
    PYVIBE-008 — sqlite3.connect() inside async def

    sqlite3 is a synchronous library. connect() opens the database file with
    blocking I/O and all subsequent cursor operations block the OS thread.
    AI-generated FastAPI examples routinely use sqlite3 inside async handlers.

    Fix: use `aiosqlite.connect()` with async context manager and await.
    """

    RULE_ID = "PYVIBE-008"
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

        if self._is_sqlite_connect(node):
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message="sqlite3.connect() is synchronous — blocks the event loop during I/O",
                evidence="Use `async with aiosqlite.connect('db.sqlite3') as db:` instead",
            ))

        self.generic_visit(node)

    def _is_sqlite_connect(self, node: ast.Call) -> bool:
        # sqlite3.connect(...)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "connect"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "sqlite3"
        ):
            return True

        # from sqlite3 import connect → connect(...)
        if isinstance(node.func, ast.Name) and node.func.id == "connect":
            return True

        return False
