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


def _is_retry_loop(node: ast.For) -> bool:
    """True if the for loop iterates over range() — likely a retry, not a for-each.

    A `for item in collection` loop that catches exceptions and uses continue is
    "skip this item", not "retry the same operation". Only `for x in range(N)` has
    retry semantics because range() produces a bounded count of attempts.
    While loops are handled separately (always retry-like by construction).
    """
    return (
        isinstance(node.iter, ast.Call)
        and isinstance(node.iter.func, ast.Name)
        and node.iter.func.id == "range"
    )


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
        # Stack of booleans: True = enclosing loop is a retry loop (while or for range()).
        # The innermost value determines whether a try/except fires — because `continue`
        # in the except resumes the *innermost* loop, not any outer loop.
        self._retry_loop_stack: List[bool] = []

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        prev_func = self._current_async_func
        prev_stack = self._retry_loop_stack
        self._current_async_func = node.name
        self._retry_loop_stack = []
        self.generic_visit(node)
        self._current_async_func = prev_func
        self._retry_loop_stack = prev_stack

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Sync functions are out of scope; reset state so nested sync defs don't fire
        prev_func = self._current_async_func
        prev_stack = self._retry_loop_stack
        self._current_async_func = None
        self._retry_loop_stack = []
        self.generic_visit(node)
        self._current_async_func = prev_func
        self._retry_loop_stack = prev_stack

    def visit_For(self, node: ast.For):
        # Only fire when iterating over range() — for-each over collections is not retry.
        self._retry_loop_stack.append(_is_retry_loop(node))
        self.generic_visit(node)
        self._retry_loop_stack.pop()

    def visit_While(self, node: ast.While):
        # while loops are inherently retry-like (no per-item semantics).
        self._retry_loop_stack.append(True)
        self.generic_visit(node)
        self._retry_loop_stack.pop()

    def visit_Try(self, node: ast.Try):
        if (self._current_async_func
                and self._retry_loop_stack
                and self._retry_loop_stack[-1]):
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
