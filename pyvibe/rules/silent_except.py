import ast
import re
from typing import List, Optional
from pyvibe.rules.base import Violation

_NOSEC_B110 = re.compile(r'#\s*nosec\b[^#\n]*\bB110\b')


def _is_empty_body(body: list) -> bool:
    """Return True if every statement is pass or ... (Ellipsis)."""
    if not body:
        return True
    for stmt in body:
        if isinstance(stmt, ast.Pass):
            continue
        if (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and stmt.value.value is ...
        ):
            continue
        return False
    return True


def _handler_names(exc_type) -> List[str]:
    if exc_type is None:
        return []  # bare except
    types = exc_type.elts if isinstance(exc_type, ast.Tuple) else [exc_type]
    return [t.id for t in types if isinstance(t, ast.Name)]


_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
_SUSPENSION = (ast.Await, ast.AsyncFor, ast.AsyncWith)


def _has_suspension_point(stmts: list) -> bool:
    """True if `stmts` contain an await (or async for/with) in the same scope.

    Nested functions, lambdas and classes are not entered: an await there does
    not suspend the enclosing coroutine.
    """
    stack = list(stmts)
    while stack:
        node = stack.pop()
        if isinstance(node, _SUSPENSION):
            return True
        if isinstance(node, _SCOPES):
            continue
        stack.extend(ast.iter_child_nodes(node))
    return False


class SilentExceptRule(ast.NodeVisitor):
    """
    PYVIBE-017 — a handler that silently swallows system-exiting exceptions

    By default (decision 2026-10-14) this reports only, and only inside an async
    function: a **bare `except:`** and an **`except BaseException`** whose body is
    just pass/... (and does not re-raise). Both swallow CancelledError /
    KeyboardInterrupt / SystemExit, breaking cancellation and clean shutdown of an
    event loop. Only when the **`try` body contains a suspension point** (an
    `await`, `async for` or `async with` in that coroutine) can a cancellation
    be delivered inside it; without one (e.g. only `future.result()` or string
    operations) these handlers are not reported (decision 2026-10-14, dev-labels
    DL-055..DL-057). A plain **`except Exception: pass`** is extremely common and is
    *opt-in* (set `report_broad_except = true` under `[tool.pyvibe]`, or pass
    `--report-broad-except`); it is not reported by default. A bare except in
    synchronous code, a specific exception type, a non-empty handler, and a
    handler that re-raises are not reported.

    Suppression: add `# nosec B110` on the `except` line to mark intentional
    suppression (Bandit convention). Generic `# nosec` without B110 is NOT
    honoured — specificity is required so that the opt-out is deliberate.

    Fix: log the error, re-raise, or handle explicitly.
    """

    RULE_ID = "PYVIBE-017"
    SEVERITY = "CRITICAL"

    def __init__(self, source_lines: Optional[List[str]] = None, report_broad_except: bool = False):
        self.violations: List[Violation] = []
        self._current_func: Optional[str] = None
        self._source_lines: List[str] = source_lines or []
        self._report_broad_except = report_broad_except
        self._in_async = False
        self._handler_suspends: dict = {}  # id(handler) -> try body has a suspension point

    def _is_suppressed(self, lineno: int) -> bool:
        """Return True if the given 1-based line carries # nosec B110."""
        if not self._source_lines:
            return False
        idx = lineno - 1
        if 0 <= idx < len(self._source_lines):
            return bool(_NOSEC_B110.search(self._source_lines[idx]))
        return False

    def visit_FunctionDef(self, node: ast.FunctionDef):
        prev_func, prev_async = self._current_func, self._in_async
        self._current_func, self._in_async = node.name, False  # a sync def is not async context
        self.generic_visit(node)
        self._current_func, self._in_async = prev_func, prev_async

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        prev_func, prev_async = self._current_func, self._in_async
        self._current_func, self._in_async = node.name, True
        self.generic_visit(node)
        self._current_func, self._in_async = prev_func, prev_async

    def visit_Lambda(self, node: ast.Lambda):
        prev_async = self._in_async
        self._in_async = False
        self.generic_visit(node)
        self._in_async = prev_async

    def visit_Try(self, node: ast.Try):
        suspends = _has_suspension_point(node.body)
        for handler in node.handlers:
            self._handler_suspends[id(handler)] = suspends
        self.generic_visit(node)

    visit_TryStar = visit_Try  # Python 3.11+ (except*)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if not _is_empty_body(node.body):
            self.generic_visit(node)
            return

        if self._is_suppressed(node.lineno):
            self.generic_visit(node)
            return

        names = _handler_names(node.type)
        suspends = self._handler_suspends.get(id(node), False)
        if node.type is None:
            # bare except: only in async context (swallows CancelledError etc.),
            # and only if the try body can be suspended (where cancellation arrives)
            if not self._in_async or not suspends:
                self.generic_visit(node)
                return
            severity = "CRITICAL"
            message = (
                "bare except around an await swallows every exception, including "
                "CancelledError, KeyboardInterrupt and SystemExit — breaking cancellation "
                "and clean shutdown"
            )
        elif "BaseException" in names:
            # except BaseException with an empty body: only in async context,
            # and only if the try body can be suspended (where cancellation arrives)
            if not self._in_async or not suspends:
                self.generic_visit(node)
                return
            severity = "CRITICAL"
            message = (
                "except BaseException with an empty body around an await swallows CancelledError, "
                "KeyboardInterrupt and SystemExit — breaking cancellation and clean shutdown"
            )
        elif "Exception" in names:
            # except Exception: pass — common; opt-in only.
            if not self._report_broad_except:
                self.generic_visit(node)
                return
            severity = "WARNING"
            message = "except Exception with empty body silences all errors silently"
        else:
            # specific exception type — acceptable pattern
            self.generic_visit(node)
            return

        self.violations.append(Violation(
            rule_id=self.RULE_ID,
            severity=severity,
            line=node.lineno,
            function_name=self._current_func or "<module>",
            message=message,
            evidence=(
                "Log the error: `except Exception as e: logger.error(e)`, "
                "or re-raise: `except Exception: raise`, "
                "or handle explicitly"
            ),
        ))
        self.generic_visit(node)
