import ast
from typing import List, Optional, Set
from pyvibe.autofix import render_call_args, render_node
from pyvibe.rules.base import Violation, AsyncBlockingCallVisitor

# run / call / check_output block inherently: they launch the child and wait for
# it to finish in the same call.  Popen is different: on its own it only starts
# the child and returns a handle, so it does NOT block the event loop; it blocks
# only when the handle is later waited on with a synchronous .wait()/.communicate().
ALWAYS_BLOCKING = {"run", "call", "check_output"}
POPEN = "Popen"
WAITING_METHODS = {"wait", "communicate"}


def _is_subprocess_popen(call: ast.AST) -> bool:
    return (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == POPEN
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "subprocess"
    )


class _PopenUsage(ast.NodeVisitor):
    """Collect, within a single function scope (not descending into nested
    functions/lambdas), which ``subprocess.Popen(...)`` calls are later waited on
    synchronously via ``.wait()`` / ``.communicate()``.

    Two forms count as waiting:
      * assigned then waited:  ``p = subprocess.Popen(...)`` ... ``p.communicate()``
      * inline chained:        ``subprocess.Popen(...).wait()``
    """

    def __init__(self):
        self.waited_vars: Set[str] = set()
        self.inline_blocking: Set[int] = set()
        self.assigned = {}  # var name -> list of Popen call nodes

    # Do not descend into nested callables: a different scope.
    def visit_FunctionDef(self, node):  # noqa: D401
        return

    def visit_AsyncFunctionDef(self, node):
        return

    def visit_Lambda(self, node):
        return

    def _record_assign(self, target, value):
        if isinstance(target, ast.Name) and _is_subprocess_popen(value):
            self.assigned.setdefault(target.id, []).append(value)

    def visit_Assign(self, node):
        for t in node.targets:
            self._record_assign(t, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        if node.value is not None:
            self._record_assign(node.target, node.value)
        self.generic_visit(node)

    def visit_withitem(self, node):
        if node.optional_vars is not None:
            self._record_assign(node.optional_vars, node.context_expr)
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and node.func.attr in WAITING_METHODS:
            recv = node.func.value
            if isinstance(recv, ast.Name):
                self.waited_vars.add(recv.id)
            elif _is_subprocess_popen(recv):
                self.inline_blocking.add(id(recv))
        self.generic_visit(node)

    def blocking_popen_ids(self) -> Set[int]:
        blocking = set(self.inline_blocking)
        for var, popens in self.assigned.items():
            if var in self.waited_vars:
                for p in popens:
                    blocking.add(id(p))
        return blocking


class SubprocessAsyncRule(AsyncBlockingCallVisitor):
    """
    PYVIBE-007 — subprocess blocking calls inside async def

    subprocess.run / call / check_output block the OS thread running the event
    loop for the entire duration of the subprocess.  subprocess.Popen only blocks
    when its handle is later waited on synchronously (``.wait()`` /
    ``.communicate()``) in the same function; a Popen that merely starts a child
    and returns does not block, so it is not reported.  Under concurrent load a
    blocking call serialises execution and eliminates the benefit of async.

    Fix: use asyncio.create_subprocess_exec() or
         asyncio.create_subprocess_shell() with await proc.communicate().
    """

    RULE_ID = "PYVIBE-007"
    SEVERITY = "CRITICAL"

    def __init__(self, source: Optional[str] = None):
        super().__init__()
        self._source = source
        # ids of subprocess.Popen(...) calls that are waited on in the current
        # async function scope (recomputed on entering each async function).
        self._blocking_popen_ids: Set[int] = set()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        previous_ids = self._blocking_popen_ids
        usage = _PopenUsage()
        for stmt in node.body:
            usage.visit(stmt)
        self._blocking_popen_ids = usage.blocking_popen_ids()
        super().visit_AsyncFunctionDef(node)
        self._blocking_popen_ids = previous_ids

    def visit_Call(self, node: ast.Call):
        if self._current_async_func is None:
            self.generic_visit(node)
            return

        method = self._get_subprocess_method(node)
        if method == POPEN and id(node) not in self._blocking_popen_ids:
            # Popen without a synchronous wait()/communicate() in the same
            # function only starts the child and returns: it does not block.
            method = None

        if method:
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message=f"subprocess.{method}() blocks the event loop for the entire subprocess duration",
                evidence="Use `proc = await asyncio.create_subprocess_exec(*cmd)` then `await proc.communicate()`",
                suggested_fix=self._suggest_fix(node, method),
            ))

        self.generic_visit(node)

    def _cmd_source(self, node: ast.Call) -> str:
        """Render the command portion of the call, unpacking list literals."""
        if not node.args:
            return "*cmd"
        first = node.args[0]
        if isinstance(first, ast.List):
            elts_src = ", ".join(render_node(self._source, e) or "..." for e in first.elts)
            return elts_src
        seg = render_node(self._source, first)
        return f"*{seg}" if seg else "*cmd"

    def _suggest_fix(self, node: ast.Call, method: str) -> Optional[str]:
        if not self._source:
            return None

        cmd_src = self._cmd_source(node)

        if method == "run":
            return (
                f"proc = await asyncio.create_subprocess_exec({cmd_src})\n"
                "stdout, stderr = await proc.communicate()"
            )
        if method == "call":
            return (
                f"proc = await asyncio.create_subprocess_exec({cmd_src})\n"
                "returncode = await proc.wait()"
            )
        if method == "check_output":
            return (
                f"proc = await asyncio.create_subprocess_exec({cmd_src}, stdout=asyncio.subprocess.PIPE)\n"
                "stdout, _ = await proc.communicate()"
            )
        if method == POPEN:
            return (
                f"proc = await asyncio.create_subprocess_exec({cmd_src})\n"
                "stdout, stderr = await proc.communicate()"
            )
        return None

    def _get_subprocess_method(self, node: ast.Call):
        # subprocess.run(...), subprocess.Popen(...), etc. — qualified form only
        # Bare names (run, call…) excluded: 'call' is too generic and caused a
        # false positive in FastAPI where 'call' is a local dependency variable.
        if (
            isinstance(node.func, ast.Attribute)
            and (node.func.attr in ALWAYS_BLOCKING or node.func.attr == POPEN)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        ):
            return node.func.attr

        return None
