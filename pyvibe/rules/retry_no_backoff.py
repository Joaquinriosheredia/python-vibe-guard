import ast
from typing import List, Optional
from pyvibe.rules.base import Violation


def _ends_with_retry(body: list) -> bool:
    """True if the except body ends with continue, or consists solely of pass."""
    if not body:
        return False
    last = body[-1]
    if isinstance(last, ast.Continue):
        return True
    if isinstance(last, ast.Pass) and len(body) == 1:
        return True
    return False


def _is_sleep_call(func_node) -> bool:
    """True if func_node is asyncio.sleep or time.sleep."""
    if isinstance(func_node, ast.Attribute):
        return (
            func_node.attr == "sleep"
            and isinstance(func_node.value, ast.Name)
            and func_node.value.id in ("asyncio", "time")
        )
    return False


def _has_backoff_name(func_node) -> bool:
    """True if the callable name contains 'backoff' or 'jitter'."""
    name = ""
    if isinstance(func_node, ast.Name):
        name = func_node.id
    elif isinstance(func_node, ast.Attribute):
        name = func_node.attr
    return "backoff" in name.lower() or "jitter" in name.lower()


def _body_has_backoff(stmts: list) -> bool:
    """True if any statement contains asyncio.sleep, time.sleep, or a backoff/jitter call."""
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                if _is_sleep_call(node.func):
                    return True
                if _has_backoff_name(node.func):
                    return True
    return False


def _body_has_escalation(stmts: list) -> bool:
    """True if any if-block in the except body contains raise or break (escalation pattern)."""
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.If):
                for child in ast.walk(node):
                    if isinstance(child, (ast.Raise, ast.Break)):
                        return True
    return False


class RetryNoBackoffRule(ast.NodeVisitor):
    """
    PYVIBE-019 — retry loop without backoff inside async def

    A for/while loop that catches exceptions and retries immediately (except
    body ends with continue, or is solely pass) with no sleep or backoff delay.
    Under error conditions this becomes a tight loop: thousands of failed
    requests per second, cascading failures, and rate-limit bans.

    Not flagged when the except handler contains: asyncio.sleep, time.sleep,
    any call with "backoff" or "jitter" in the name, or an escalation pattern
    (if-block leading to raise or break).

    Fix: add `await asyncio.sleep(2 ** attempt)` before the retry, or use
    a backoff library (tenacity, backoff).
    """

    RULE_ID = "PYVIBE-019"
    SEVERITY = "WARNING"

    def __init__(self):
        self.violations: List[Violation] = []
        self._current_async_func: Optional[str] = None
        self._in_loop_depth: int = 0

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        prev_func = self._current_async_func
        prev_depth = self._in_loop_depth
        self._current_async_func = node.name
        self._in_loop_depth = 0  # reset: loops inside this function are tracked fresh
        self.generic_visit(node)
        self._current_async_func = prev_func
        self._in_loop_depth = prev_depth

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Sync functions are out of scope; reset state so nested sync defs don't fire
        prev_func = self._current_async_func
        prev_depth = self._in_loop_depth
        self._current_async_func = None
        self._in_loop_depth = 0
        self.generic_visit(node)
        self._current_async_func = prev_func
        self._in_loop_depth = prev_depth

    def visit_For(self, node: ast.For):
        self._in_loop_depth += 1
        self.generic_visit(node)
        self._in_loop_depth -= 1

    def visit_While(self, node: ast.While):
        self._in_loop_depth += 1
        self.generic_visit(node)
        self._in_loop_depth -= 1

    def visit_Try(self, node: ast.Try):
        if self._current_async_func and self._in_loop_depth > 0:
            for handler in node.handlers:
                self._check_handler(handler)
        self.generic_visit(node)

    def _check_handler(self, handler: ast.ExceptHandler):
        body = handler.body
        if not _ends_with_retry(body):
            return
        if _body_has_backoff(body):
            return
        if _body_has_escalation(body):
            return
        self.violations.append(Violation(
            rule_id=self.RULE_ID,
            severity=self.SEVERITY,
            line=handler.lineno,
            function_name=self._current_async_func,
            message=(
                "retry loop without backoff — except retries immediately with no delay"
            ),
            evidence=(
                "Add `await asyncio.sleep(2 ** attempt)` before continue, "
                "or use tenacity / backoff library"
            ),
        ))
