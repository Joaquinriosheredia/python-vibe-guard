import ast
from typing import List
from pyvibe.rules.base import Violation


class GatherNoReturnExceptionsRule(ast.NodeVisitor):
    """
    PYVIBE-013 — asyncio.gather() without return_exceptions=True

    Without return_exceptions=True, the first exception raised by any task
    immediately propagates to the gather() caller. The remaining tasks are
    NOT automatically cancelled — they keep running detached, leaking
    resources and producing results nobody reads.

    AI-generated code almost never adds return_exceptions=True because the
    pattern "looks correct" in single-task testing where exceptions don't
    race. The bug surfaces only under concurrent load.

    Fix: add return_exceptions=True and inspect the result list, or use
    asyncio.TaskGroup (Python 3.11+) for explicit structured concurrency.
    """

    RULE_ID = "PYVIBE-013"
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
        if self._current_async_func and self._is_gather(node) and not self._has_return_exceptions_true(node):
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message="asyncio.gather() without return_exceptions=True — first exception leaks remaining tasks",
                evidence=(
                    "Add return_exceptions=True and check results: "
                    "`results = await asyncio.gather(*coros, return_exceptions=True)`, "
                    "or use `async with asyncio.TaskGroup() as tg:` (Python 3.11+)"
                ),
            ))
        self.generic_visit(node)

    def _is_gather(self, node: ast.Call) -> bool:
        return (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "gather"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "asyncio"
        )

    def _has_return_exceptions_true(self, node: ast.Call) -> bool:
        for kw in node.keywords:
            if (
                kw.arg == "return_exceptions"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
            ):
                return True
        return False
