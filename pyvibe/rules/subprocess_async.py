import ast
from typing import List, Optional
from pyvibe.autofix import render_call_args, render_node
from pyvibe.rules.base import Violation, AsyncBlockingCallVisitor

SUBPROCESS_BLOCKING = {"run", "call", "check_output", "Popen"}


class SubprocessAsyncRule(AsyncBlockingCallVisitor):
    """
    PYVIBE-007 — subprocess blocking calls inside async def

    subprocess.run / call / check_output / Popen all block the OS thread
    running the event loop for the entire duration of the subprocess.
    Under concurrent load this serialises execution and eliminates the
    benefit of async.

    Fix: use asyncio.create_subprocess_exec() or
         asyncio.create_subprocess_shell() with await proc.communicate().
    """

    RULE_ID = "PYVIBE-007"
    SEVERITY = "CRITICAL"

    def __init__(self, source: Optional[str] = None):
        super().__init__()
        self._source = source

    def visit_Call(self, node: ast.Call):
        if self._current_async_func is None:
            self.generic_visit(node)
            return

        method = self._get_subprocess_method(node)
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
        if method == "Popen":
            return f"proc = await asyncio.create_subprocess_exec({cmd_src})"
        return None

    def _get_subprocess_method(self, node: ast.Call):
        # subprocess.run(...), subprocess.Popen(...), etc. — qualified form only
        # Bare names (run, call…) excluded: 'call' is too generic and caused a
        # false positive in FastAPI where 'call' is a local dependency variable.
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in SUBPROCESS_BLOCKING
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        ):
            return node.func.attr

        return None
