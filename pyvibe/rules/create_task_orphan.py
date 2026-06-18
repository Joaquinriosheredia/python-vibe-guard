import ast
from typing import List
from pyvibe.rules.base import Violation


class CreateTaskOrphanRule(ast.NodeVisitor):
    """
    PYVIBE-012 — asyncio.create_task() with discarded return value

    create_task() returns a Task. If the Task object is not retained by any
    reference, the garbage collector can cancel it mid-execution. Any exception
    raised inside the task is also silently lost — no traceback, no crash,
    just missing work. AI-generated "fire-and-forget" code hits this constantly.

    Fix: assign the task and await it, or use asyncio.TaskGroup (Python 3.11+).
    """

    RULE_ID = "PYVIBE-012"
    SEVERITY = "CRITICAL"

    def __init__(self):
        self.violations: List[Violation] = []
        self._current_async_func: str = None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        previous = self._current_async_func
        self._current_async_func = node.name
        self.generic_visit(node)
        self._current_async_func = previous

    def visit_Expr(self, node: ast.Expr):
        # ast.Expr (capital-E) is the *statement* wrapper for a discarded expression.
        # If its direct value is create_task(), the Task reference is lost.
        if self._current_async_func and self._is_create_task(node.value):
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message="asyncio.create_task() return value discarded — task may be GC'd and silently cancelled",
                evidence=(
                    "Assign and await: `task = asyncio.create_task(coro()); await task`, "
                    "or use `async with asyncio.TaskGroup() as tg: tg.create_task(coro())` (Python 3.11+)"
                ),
            ))
        self.generic_visit(node)

    def _is_create_task(self, node: ast.expr) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "create_task"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "asyncio"
        )
