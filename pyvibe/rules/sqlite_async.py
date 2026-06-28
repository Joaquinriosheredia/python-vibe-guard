import ast
from typing import List, Set
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
        # Names bound to the `sqlite3` module via `import sqlite3 [as X]`
        self._sqlite3_aliases: Set[str] = set()
        # Names imported directly from sqlite3: `from sqlite3 import connect`
        self._from_sqlite3: Set[str] = set()

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name == "sqlite3":
                self._sqlite3_aliases.add(alias.asname if alias.asname else alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module == "sqlite3":
            for alias in node.names:
                if alias.name == "connect":
                    self._from_sqlite3.add(alias.asname if alias.asname else alias.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        previous = self._current_async_func
        self._current_async_func = node.name
        self.generic_visit(node)
        self._current_async_func = previous

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # A sync `def` nested inside an `async def` creates its own synchronous
        # scope. sqlite3.connect() inside that scope is NOT blocking the event
        # loop — if the caller passes the sync function to asyncio.to_thread()
        # or run_in_executor(), the blocking happens in a thread pool as intended.
        # Reset async context so inner sync bodies don't inherit it.
        previous = self._current_async_func
        self._current_async_func = None
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
        # Guard against NAME_COLLISION: only flag when the receiver name is
        # known to be bound to the sqlite3 module via an import statement.
        # Without this, any `obj.connect(...)` where the variable happens to
        # be named `sqlite3` would be a false positive.
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "connect"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in self._sqlite3_aliases
        ):
            return True

        # from sqlite3 import connect → connect(...)
        # Guard against NAME_COLLISION: bare `connect()` is an extremely common
        # name used by asyncpg, aiomysql, aiopg, websockets, aio-pika, asyncssh,
        # and many other async libraries. Only flag when `connect` was explicitly
        # imported from sqlite3 (a rare but real pattern: `from sqlite3 import connect`).
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in self._from_sqlite3
        ):
            return True

        return False
