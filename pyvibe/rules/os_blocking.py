import ast
from typing import List
from pyvibe.rules.base import Violation, AsyncBlockingCallVisitor

OS_BLOCKING = {"system", "popen", "waitpid"}


class OsBlockingRule(AsyncBlockingCallVisitor):
    """
    PYVIBE-011 — os.system / os.popen / os.waitpid inside async def

    These OS calls block the thread until the child process or I/O completes.
    Unlike subprocess, they have no direct async equivalent and are commonly
    generated when AI migrates sync scripts to async without replacing the
    OS interaction layer.

    Not reported: os.waitpid(pid, os.WNOHANG) (WNOHANG anywhere in its options),
    which returns at once instead of waiting (test-corpus-2 P119/P122, polled with
    await asyncio.sleep).

    Fix: use asyncio.create_subprocess_shell() with await proc.communicate().
    """

    RULE_ID = "PYVIBE-011"
    SEVERITY = "CRITICAL"

    def visit_Call(self, node: ast.Call):
        if self._current_async_func is None:
            self.generic_visit(node)
            return

        method = self._get_os_blocking_method(node)
        if method == "waitpid" and _has_wnohang(node):
            method = None
        if method:
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message=f"os.{method}() inside async def blocks the event loop until the child process finishes",
                evidence="Use `proc = await asyncio.create_subprocess_shell(cmd)` then `await proc.communicate()`",
            ))

        self.generic_visit(node)

    def _get_os_blocking_method(self, node: ast.Call):
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in OS_BLOCKING
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "os"
        ):
            return node.func.attr
        return None


def _has_wnohang(node: ast.Call) -> bool:
    """os.waitpid(pid, options) whose options mention WNOHANG (os.WNOHANG, a bare WNOHANG,
    or either OR-ed with other flags)."""
    options = node.args[1] if len(node.args) > 1 else next(
        (kw.value for kw in node.keywords if kw.arg == "options"), None)
    if options is None:
        return False
    return any(
        (isinstance(n, ast.Attribute) and n.attr == "WNOHANG") or (isinstance(n, ast.Name) and n.id == "WNOHANG")
        for n in ast.walk(options)
    )
