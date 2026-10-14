import ast
from typing import Set
from pyvibe.rules.base import Violation, AsyncBlockingCallVisitor


class OpenAsyncRule(AsyncBlockingCallVisitor):
    """
    PYVIBE-009 — open() builtin inside async def

    The builtin open() performs synchronous file I/O. Each call blocks the
    OS thread until the kernel completes the read/write, preventing the event
    loop from scheduling other coroutines. AI-generated FastAPI code routinely
    mixes open() with async endpoints.

    aiofiles.open() is an ast.Attribute node — structurally different from the
    bare ast.Name 'open', so it is never matched by this rule.

    WARNING instead of CRITICAL when the file I/O is already delegated to a
    thread: `with open(...) as f:` whose handle is only ever passed, uncalled,
    to asyncio.to_thread() or run_in_executor() (`await asyncio.to_thread(f.read, n)`).
    Only the open() and close() calls run on the event loop then. Any other use
    of the handle keeps the finding CRITICAL.

    Fix: use `async with aiofiles.open(path) as f: content = await f.read()`.
    """

    RULE_ID = "PYVIBE-009"
    SEVERITY = "CRITICAL"

    def __init__(self):
        super().__init__()
        self._delegated: Set[int] = set()  # id() of open() calls whose I/O runs in a thread

    def visit_With(self, node: ast.With):
        if self._current_async_func is not None:
            for item in node.items:
                if (
                    _is_open(item.context_expr)
                    and isinstance(item.optional_vars, ast.Name)
                    and _handle_only_delegated(item.optional_vars.id, node.body)
                ):
                    self._delegated.add(id(item.context_expr))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if self._current_async_func is None:
            self.generic_visit(node)
            return

        if _is_open(node):
            if id(node) in self._delegated:
                self.violations.append(Violation(
                    rule_id=self.RULE_ID,
                    severity="WARNING",
                    line=node.lineno,
                    function_name=self._current_async_func,
                    message=(
                        "open() on the event loop; the file's reads/writes are delegated to a thread "
                        "(asyncio.to_thread / run_in_executor), so only open() and close() block the loop"
                    ),
                    evidence="Move the open() into the thread too: `await asyncio.to_thread(read_file, path)`, or use aiofiles",
                ))
            else:
                self.violations.append(Violation(
                    rule_id=self.RULE_ID,
                    severity=self.SEVERITY,
                    line=node.lineno,
                    function_name=self._current_async_func,
                    message="open() performs synchronous file I/O — blocks the event loop",
                    evidence="Use `async with aiofiles.open(path) as f: content = await f.read()`",
                ))

        self.generic_visit(node)


def _is_open(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open"


def _is_thread_offload(call: ast.Call) -> bool:
    func = call.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr == "to_thread":
        return isinstance(func.value, ast.Name) and func.value.id == "asyncio"
    return func.attr == "run_in_executor"


def _handle_only_delegated(name: str, body) -> bool:
    """Every use of `name` in the with-body is `name.<method>` passed, uncalled, as an
    argument of asyncio.to_thread(...) or <loop>.run_in_executor(...); at least one."""
    delegated = set()
    uses = []
    for stmt in body:
        for n in ast.walk(stmt):
            if isinstance(n, ast.Call) and _is_thread_offload(n):
                for a in n.args:
                    if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and a.value.id == name:
                        delegated.add(id(a.value))
            elif isinstance(n, ast.Name) and n.id == name:
                uses.append(id(n))
    return bool(uses) and all(u in delegated for u in uses)
