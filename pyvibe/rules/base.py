import ast
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Violation:
    rule_id: str
    severity: str
    line: int
    function_name: str
    message: str
    evidence: str


class AsyncContextVisitor(ast.NodeVisitor):
    """Base visitor that tracks the name of the enclosing async function.

    ``_current_async_func`` is set to the function name while visiting its body
    and restored on exit, supporting nested async defs correctly.

    Use as the base for rules that detect misuse of asyncio primitives
    (``create_task``, ``ensure_future``, ``gather``) where the bug exists
    regardless of whether the call appears in a nested sync callable.
    """

    def __init__(self):
        self.violations: List[Violation] = []
        self._current_async_func: Optional[str] = None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        previous = self._current_async_func
        self._current_async_func = node.name
        self.generic_visit(node)
        self._current_async_func = previous


class AsyncBlockingCallVisitor(AsyncContextVisitor):
    """AsyncContextVisitor extended with context isolation for nested sync callables.

    A synchronous ``def`` or ``lambda`` nested inside an ``async def`` resets
    ``_current_async_func`` to ``None``.  The rationale: such callables may be
    passed to ``run_in_executor`` / ``async_add_executor_job`` / thread pools
    and therefore do *not* inherently block the event loop.  Without this reset,
    any blocking call (``requests.get``, ``time.sleep``, ``subprocess.run`` …)
    inside the nested callable would be falsely flagged.

    Use as the base for rules that detect synchronous blocking calls inside
    async functions: I/O, HTTP, subprocesses, threading primitives, etc.
    Do NOT use it for asyncio-primitive-misuse rules (``create_task``,
    ``ensure_future``, ``gather``) — those rules must inherit from
    ``AsyncContextVisitor`` directly.
    """

    def visit_FunctionDef(self, node: ast.FunctionDef):
        previous = self._current_async_func
        self._current_async_func = None
        self.generic_visit(node)
        self._current_async_func = previous

    def visit_Lambda(self, node: ast.Lambda):
        previous = self._current_async_func
        self._current_async_func = None
        self.generic_visit(node)
        self._current_async_func = previous
