import ast
from typing import List, Set
from pyvibe.rules.base import Violation


def _shallow_walk(node: ast.AST):
    """Walk AST without recursing into nested function or class definitions."""
    yield node
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield from _shallow_walk(child)


class ContextVarCleanupRule(ast.NodeVisitor):
    """
    PYVIBE-006 — ContextVar.set() inside async def without guaranteed cleanup

    ContextVar.set() returns a Token. Without reset(token) in a finally block,
    the context value leaks into sibling async tasks that share the same context
    — a common bug in FastAPI request handlers and async workers.

    Fix: token = var.set(value) then var.reset(token) inside a finally block.
    """

    RULE_ID = "PYVIBE-006"
    SEVERITY = "CRITICAL"

    def __init__(self):
        self.violations: List[Violation] = []
        self._contextvar_names: Set[str] = set()
        self._current_async_func: str = None

    def visit_Module(self, node: ast.Module):
        self._contextvar_names = self._collect_contextvar_names(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        previous = self._current_async_func
        self._current_async_func = node.name

        set_calls = self._find_set_calls(node)
        if set_calls and not self._has_finally_reset(node):
            first = set_calls[0]
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=first.lineno,
                function_name=node.name,
                message="ContextVar.set() without guaranteed cleanup leaks state between async tasks",
                evidence="Capture the token: `token = var.set(v)` then call `var.reset(token)` in a finally block",
            ))

        self.generic_visit(node)
        self._current_async_func = previous

    # ── private ──────────────────────────────────────────────────────────────

    def _collect_contextvar_names(self, module: ast.Module) -> Set[str]:
        """Return variable names assigned from ContextVar(...) anywhere in the module."""
        names: Set[str] = set()
        for node in ast.walk(module):
            if isinstance(node, ast.Assign) and self._is_contextvar_call(node.value):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
            elif (
                isinstance(node, ast.AnnAssign)
                and node.value
                and self._is_contextvar_call(node.value)
                and isinstance(node.target, ast.Name)
            ):
                names.add(node.target.id)
        return names

    def _is_contextvar_call(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        # ContextVar('name')
        if isinstance(func, ast.Name) and func.id == "ContextVar":
            return True
        # contextvars.ContextVar('name')
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "ContextVar"
            and isinstance(func.value, ast.Name)
            and func.value.id == "contextvars"
        ):
            return True
        return False

    def _find_set_calls(self, func_node: ast.AsyncFunctionDef) -> list:
        """Find .set() calls on known ContextVar names, not crossing nested function boundaries."""
        calls = []
        for node in _shallow_walk(func_node):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "set"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in self._contextvar_names
            ):
                calls.append(node)
        return calls

    def _has_finally_reset(self, func_node: ast.AsyncFunctionDef) -> bool:
        """Return True if the function body contains a try/finally with a .reset() call."""
        for node in _shallow_walk(func_node):
            if isinstance(node, ast.Try) and node.finalbody:
                for stmt in node.finalbody:
                    for child in ast.walk(stmt):
                        if (
                            isinstance(child, ast.Call)
                            and isinstance(child.func, ast.Attribute)
                            and child.func.attr == "reset"
                        ):
                            return True
        return False
