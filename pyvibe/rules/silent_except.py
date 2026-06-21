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


class SilentExceptRule(ast.NodeVisitor):
    """
    PYVIBE-017 — except Exception with empty body (silences errors)

    A bare except or except Exception block whose body is only pass/... swallows
    every exception without any record, making bugs invisible in production.
    bare except also catches KeyboardInterrupt and SystemExit, preventing clean
    shutdown.

    Suppression: add `# nosec B110` on the `except` line to mark intentional
    suppression (Bandit convention). Generic `# nosec` without B110 is NOT
    honoured — specificity is required so that the opt-out is deliberate.

    Fix: log the error, re-raise, or handle explicitly.
    """

    RULE_ID = "PYVIBE-017"
    SEVERITY = "CRITICAL"

    def __init__(self, source_lines: Optional[List[str]] = None):
        self.violations: List[Violation] = []
        self._current_func: Optional[str] = None
        self._source_lines: List[str] = source_lines or []

    def _is_suppressed(self, lineno: int) -> bool:
        """Return True if the given 1-based line carries # nosec B110."""
        if not self._source_lines:
            return False
        idx = lineno - 1
        if 0 <= idx < len(self._source_lines):
            return bool(_NOSEC_B110.search(self._source_lines[idx]))
        return False

    def visit_FunctionDef(self, node: ast.FunctionDef):
        previous = self._current_func
        self._current_func = node.name
        self.generic_visit(node)
        self._current_func = previous

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        previous = self._current_func
        self._current_func = node.name
        self.generic_visit(node)
        self._current_func = previous

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if not _is_empty_body(node.body):
            self.generic_visit(node)
            return

        if self._is_suppressed(node.lineno):
            self.generic_visit(node)
            return

        exc_type = node.type
        if exc_type is None:
            severity = "CRITICAL"
            message = (
                "bare except swallows all exceptions including "
                "KeyboardInterrupt and SystemExit"
            )
        elif isinstance(exc_type, ast.Name) and exc_type.id == "Exception":
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
