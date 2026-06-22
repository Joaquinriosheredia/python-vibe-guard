import ast
from typing import List, Optional
from pyvibe.rules.base import Violation

# Loop variable names that signal retry intent.
# Excluded: i, j, n, count, idx, chunk_start, page_num, dpynum — index/iteration variables.
_RETRY_VAR_NAMES = frozenset({"_"})
_RETRY_VAR_PREFIXES = ("attempt", "retry", "retries")


def _ends_with_retry(body: list) -> bool:
    """True if the except body ends with continue.

    `pass` alone is intentionally NOT counted. CLEANUP_PASS analysis (jun 2026)
    showed 97/186 hits (52.2%) were pass-only handlers in cleanup blocks — all false
    positives. `pass` lets the enclosing loop continue by fall-through rather than
    expressing explicit retry intent.
    """
    if not body:
        return False
    last = body[-1]
    return isinstance(last, ast.Continue)


def _is_retry_loop(node: ast.For) -> bool:
    """True if the for loop is a bounded retry: for _ in range(N) or for attempt in range(N).

    Two conditions required:
    1. Iterable must be range() — bounded count of attempts.
    2. Loop variable must be anonymous (_) or carry retry-intent semantics
       (name contains 'attempt', 'retry', or 'retries').

    Excluded: for i/j/n/count/idx in range(N) — these are index variables used to
    iterate over elements, not retry counters. Analysis of 30 for-range hits showed
    the 'i'-named group was 100% RANGE_FOREACH false positives.
    """
    if not (
        isinstance(node.iter, ast.Call)
        and isinstance(node.iter.func, ast.Name)
        and node.iter.func.id == "range"
    ):
        return False
    target = node.target
    if not isinstance(target, ast.Name):
        return False
    varname = target.id.lower()
    return varname in _RETRY_VAR_NAMES or any(p in varname for p in _RETRY_VAR_PREFIXES)


def _is_sleep_call(func_node) -> bool:
    """True if func_node is asyncio.sleep, time.sleep, or bare sleep() (direct import)."""
    if isinstance(func_node, ast.Attribute):
        return (
            func_node.attr == "sleep"
            and isinstance(func_node.value, ast.Name)
            and func_node.value.id in ("asyncio", "time")
        )
    # Bare name: `from time import sleep; sleep(N)` — no module prefix
    if isinstance(func_node, ast.Name):
        return func_node.id == "sleep"
    return False


def _has_backoff_name(func_node) -> bool:
    """True if the callable signals backoff/sleep delay.

    Detects:
    - Function/method name contains 'backoff' or 'jitter'
    - Method name is 'asleep' (Backoff class async-sleep pattern: await backoff.asleep())
    - Receiver object name contains 'backoff' or 'jitter' (e.g. backoff.sleep())
    """
    if isinstance(func_node, ast.Name):
        name = func_node.id.lower()
        return "backoff" in name or "jitter" in name
    if isinstance(func_node, ast.Attribute):
        attr = func_node.attr.lower()
        if "backoff" in attr or "jitter" in attr or attr == "asleep":
            return True
        # Receiver object named after a backoff helper: backoff.sleep(), jitter.wait()
        if isinstance(func_node.value, ast.Name):
            receiver = func_node.value.id.lower()
            return "backoff" in receiver or "jitter" in receiver
    return False


def _body_has_backoff(stmts: list) -> bool:
    """True if any statement contains a sleep or backoff/jitter call."""
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


def _is_timeout_only_handler(handler: ast.ExceptHandler) -> bool:
    """True if the handler catches ONLY asyncio.TimeoutError or bare TimeoutError.

    Handlers that catch TimeoutError exclusively are very likely polling loops
    (e.g. `await asyncio.wait_for(event.wait(), timeout=N)`) rather than retries.
    Tuple handlers like `except (asyncio.TimeoutError, ConnectionError)` return False
    because the presence of other exception types indicates genuine error handling.
    """
    typ = handler.type
    if typ is None:
        return False
    if isinstance(typ, ast.Name) and typ.id == "TimeoutError":
        return True
    return (
        isinstance(typ, ast.Attribute)
        and typ.attr == "TimeoutError"
        and isinstance(typ.value, ast.Name)
        and typ.value.id == "asyncio"
    )


def _try_body_has_timeout_kwarg(stmts: list) -> bool:
    """True if any call in the try body uses a 'timeout' keyword argument.

    Combined with _is_timeout_only_handler, this identifies the POLL_LOOP pattern:
        try:
            await asyncio.wait_for(event.wait(), timeout=N)  ← timeout= here
        except asyncio.TimeoutError:                          ← TimeoutError only
            continue                                          ← not a retry

    A genuine network retry would either catch Exception (not TimeoutError only)
    or would catch asyncio.TimeoutError without any explicit timeout= in the try body.
    """
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "timeout":
                        return True
    return False


class RetryNoBackoffRule(ast.NodeVisitor):
    """
    PYVIBE-019 — retry loop without backoff inside async def

    Scope (v3, jun 2026): exclusively `for _ in range(N)` or `for attempt in range(N)`
    loops inside async functions. While loops are out of scope (FP rate ~90% due to
    CLEANUP_PASS, MEM_PARSE, and MISSED_BACKOFF patterns; not reducible with AST alone).

    Fires when:
    - Loop iterates over range() with anonymous (_) or retry-intent variable name
    - Handler body ends with `continue` (explicit retry)
    - No sleep or backoff call detected in the handler body

    Not flagged when the except handler contains:
    - asyncio.sleep(N) or time.sleep(N) or bare sleep(N)
    - await backoff.asleep() or any call with 'backoff'/'jitter'/'asleep' in the name
    - An escalation pattern (if-block leading to raise or break)
    - Catches only asyncio.TimeoutError AND try body has timeout= kwarg (POLL_LOOP pattern)

    Fix: add `await asyncio.sleep(2 ** attempt)` before continue, or use
    tenacity / backoff library.
    """

    RULE_ID = "PYVIBE-019"
    SEVERITY = "WARNING"

    def __init__(self):
        self.violations: List[Violation] = []
        self._current_async_func: Optional[str] = None
        # Stack: True = enclosing loop is a qualifying retry loop (for _ in range(N)).
        # Innermost value determines firing — `continue` resumes the innermost loop.
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
        prev_func = self._current_async_func
        prev_stack = self._retry_loop_stack
        self._current_async_func = None
        self._retry_loop_stack = []
        self.generic_visit(node)
        self._current_async_func = prev_func
        self._retry_loop_stack = prev_stack

    def visit_For(self, node: ast.For):
        self._retry_loop_stack.append(_is_retry_loop(node))
        self.generic_visit(node)
        self._retry_loop_stack.pop()

    def visit_While(self, node: ast.While):
        # While loops are explicitly out of scope for PYVIBE-019 v3.
        # Push False so nested for-range retry loops can still be detected.
        self._retry_loop_stack.append(False)
        self.generic_visit(node)
        self._retry_loop_stack.pop()

    def visit_Try(self, node: ast.Try):
        if (self._current_async_func
                and self._retry_loop_stack
                and self._retry_loop_stack[-1]):
            for handler in node.handlers:
                self._check_handler(handler, node.body)
        self.generic_visit(node)

    def _check_handler(self, handler: ast.ExceptHandler, try_body: list):
        body = handler.body
        if not _ends_with_retry(body):
            return
        if _body_has_backoff(body):
            return
        if _body_has_escalation(body):
            return
        # POLL_LOOP exclusion: `except asyncio.TimeoutError` + `timeout=` kwarg in try body
        # is the canonical asyncio.wait_for polling pattern — not a retry.
        if _is_timeout_only_handler(handler) and _try_body_has_timeout_kwarg(try_body):
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
