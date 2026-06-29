import ast
from typing import List
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
            ))

        self.generic_visit(node)

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
