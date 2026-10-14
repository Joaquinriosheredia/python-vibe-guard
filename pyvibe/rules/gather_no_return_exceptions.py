import ast
from typing import Dict, List, Optional, Union

from pyvibe.rules.base import Violation, AsyncContextVisitor

FuncDef = Union[ast.FunctionDef, ast.AsyncFunctionDef]

_BROAD_EXCEPTIONS = {"Exception", "BaseException"}


class GatherNoReturnExceptionsRule(AsyncContextVisitor):
    """
    PYVIBE-013 — asyncio.gather() without return_exceptions=True

    Without return_exceptions=True, the first exception raised by any of the
    gathered awaitables propagates to the gather() caller. The other awaitables
    are NOT cancelled: they keep running with nobody observing their results or
    their later exceptions ("Task exception was never retrieved"). No memory is
    lost for good; the work and its failures go unobserved.

    Not reported when this file shows that none of the gathered awaitables can
    raise an ordinary exception: each one resolves, in the same module, to a
    function whose whole body (at most a docstring before it) is a single try
    with no else/finally, at least one handler catching Exception, BaseException
    or everything, and no raise in any handler; or to asyncio.sleep(). Resolved
    forms: f(...) for an undecorated async def of the module, a nested one or
    self.f/cls.f of the same class; asyncio.to_thread(f, ...) for a plain def;
    asyncio.ensure_future(x) and asyncio.create_task(x); *[f(a) for ...] and
    *(f(a) for ...); *tasks for a local list only ever built from a list literal
    and tasks.append(x). Anything else (a parameter, an attribute, an imported
    function, a lambda, statements outside the try) is reported: in doubt, the
    finding stays.

    Fix: add return_exceptions=True and inspect the result list, or use
    asyncio.TaskGroup (Python 3.11+) for explicit structured concurrency.
    """

    RULE_ID = "PYVIBE-013"
    SEVERITY = "CRITICAL"

    def __init__(self):
        super().__init__()
        self._module_funcs: Dict[str, List[FuncDef]] = {}
        # Innermost last: the function bodies and classes enclosing the current node.
        self._func_stack: List[FuncDef] = []
        self._class_stack: List[ast.ClassDef] = []

    # ─── scope tracking ──────────────────────────────────────────────────────

    def visit_Module(self, node: ast.Module):
        self._module_funcs = _defs_in(node.body)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self._class_stack.append(node)
        outer_funcs, self._func_stack = self._func_stack, []
        self.generic_visit(node)
        self._func_stack = outer_funcs
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._func_stack.append(node)
        self.generic_visit(node)
        self._func_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._func_stack.append(node)
        super().visit_AsyncFunctionDef(node)
        self._func_stack.pop()

    # ─── the rule ────────────────────────────────────────────────────────────

    def visit_Call(self, node: ast.Call):
        if (
            self._current_async_func
            and self._is_gather(node)
            and not self._has_return_exceptions_true(node)
            and not self._all_awaitables_contained(node)
        ):
            self.violations.append(Violation(
                rule_id=self.RULE_ID,
                severity=self.SEVERITY,
                line=node.lineno,
                function_name=self._current_async_func,
                message=(
                    "asyncio.gather() without return_exceptions=True: if one awaitable raises, "
                    "gather re-raises it and the others keep running with nobody observing "
                    "their results or later exceptions"
                ),
                evidence=(
                    "Add return_exceptions=True and check results: "
                    "`results = await asyncio.gather(*coros, return_exceptions=True)`, "
                    "or use `async with asyncio.TaskGroup() as tg:` (Python 3.11+)"
                ),
            ))
        self.generic_visit(node)

    def _is_gather(self, node: ast.Call) -> bool:
        return _is_asyncio_call(node, "gather")

    def _has_return_exceptions_true(self, node: ast.Call) -> bool:
        for kw in node.keywords:
            if (
                kw.arg == "return_exceptions"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
            ):
                return True
        return False

    def _all_awaitables_contained(self, node: ast.Call) -> bool:
        # Any keyword other than return_exceptions (e.g. **kwargs) is not understood.
        if any(kw.arg != "return_exceptions" for kw in node.keywords):
            return False
        if not node.args:
            return False
        return all(self._arg_contained(arg) for arg in node.args)

    def _arg_contained(self, arg: ast.expr) -> bool:
        if isinstance(arg, ast.Starred):
            value = arg.value
            if isinstance(value, (ast.ListComp, ast.GeneratorExp)) and not _plain_comprehension(value):
                return False
            if isinstance(value, (ast.ListComp, ast.GeneratorExp)):
                return self._awaitable_contained(value.elt)
            if isinstance(value, ast.Name):
                elements = self._local_list_elements(value.id)
                return elements is not None and all(self._awaitable_contained(e) for e in elements)
            return False
        return self._awaitable_contained(arg)

    def _awaitable_contained(self, expr: ast.expr) -> bool:
        if not isinstance(expr, ast.Call):
            return False
        if _is_asyncio_call(expr, "sleep"):
            return True
        if _is_asyncio_call(expr, "ensure_future") or _is_asyncio_call(expr, "create_task"):
            return len(expr.args) >= 1 and self._awaitable_contained(expr.args[0])
        if _is_asyncio_call(expr, "to_thread"):
            if not expr.args:
                return False
            func = self._resolve(expr.args[0])
            return isinstance(func, ast.FunctionDef) and _body_contains_exceptions(func)
        func = self._resolve(expr.func)
        return isinstance(func, ast.AsyncFunctionDef) and _body_contains_exceptions(func)

    def _resolve(self, ref: ast.expr) -> Optional[FuncDef]:
        """The single undecorated def a name or self.f/cls.f refers to, or None."""
        if isinstance(ref, ast.Name):
            for scope in reversed(self._func_stack):
                found = _defs_in(scope.body).get(ref.id)
                if found is not None:
                    return _single_plain(found)
            return _single_plain(self._module_funcs.get(ref.id))
        if (
            isinstance(ref, ast.Attribute)
            and isinstance(ref.value, ast.Name)
            and ref.value.id in ("self", "cls")
            and self._class_stack
        ):
            return _single_plain(_defs_in(self._class_stack[-1].body).get(ref.attr))
        return None

    def _local_list_elements(self, name: str) -> Optional[List[ast.expr]]:
        """Elements of a local list built only from a list literal and name.append(x)."""
        if not self._func_stack:
            return None
        func = self._func_stack[-1]
        elements: List[ast.expr] = []
        allowed = set()  # ids of Name nodes whose use is understood
        literal_seen = False
        for node in ast.walk(func):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Name) and t.id == name for t in targets):
                    if len(targets) != 1 or literal_seen or not isinstance(node.value, ast.List):
                        return None
                    literal_seen = True
                    elements.extend(node.value.elts)
                    allowed.add(id(targets[0]))
            elif (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "append"
                and isinstance(node.value.func.value, ast.Name)
                and node.value.func.value.id == name
                and len(node.value.args) == 1
                and not node.value.keywords
            ):
                elements.append(node.value.args[0])
                allowed.add(id(node.value.func.value))
            elif (
                isinstance(node, ast.Call)
                and _is_asyncio_call(node, "gather")
            ):
                for a in node.args:
                    if isinstance(a, ast.Starred) and isinstance(a.value, ast.Name) and a.value.id == name:
                        allowed.add(id(a.value))
        if not literal_seen:
            return None
        # Any other use of the name (extend, +=, reassignment, passed elsewhere) → unknown.
        for node in ast.walk(func):
            if isinstance(node, ast.Name) and node.id == name and id(node) not in allowed:
                return None
        return elements


def _is_asyncio_call(node: ast.Call, attr: str) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == attr
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "asyncio"
    )


def _defs_in(body: List[ast.stmt]) -> Dict[str, List[FuncDef]]:
    defs: Dict[str, List[FuncDef]] = {}
    for stmt in body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.setdefault(stmt.name, []).append(stmt)
    return defs


def _single_plain(defs: Optional[List[FuncDef]]) -> Optional[FuncDef]:
    # Redefined (ambiguous) or decorated (a wrapper may re-raise): not resolved.
    if not defs or len(defs) != 1 or defs[0].decorator_list:
        return None
    return defs[0]


def _plain_comprehension(comp: Union[ast.ListComp, ast.GeneratorExp]) -> bool:
    # Plain `for` clauses (filters allowed, no `async for`): every item is the element.
    return all(not g.is_async for g in comp.generators)


def _body_contains_exceptions(func: FuncDef) -> bool:
    """The whole body (at most a docstring before it) is one try that catches
    Exception, BaseException or everything, with no else, no finally and no
    raise in any handler (decision of 2026-10-14: strict; in doubt, report)."""
    body = func.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    if len(body) != 1 or not isinstance(body[0], ast.Try):
        return False
    try_node = body[0]
    if try_node.orelse or try_node.finalbody:
        return False
    if not any(_is_broad(h) for h in try_node.handlers):
        return False
    return not any(isinstance(n, ast.Raise) for h in try_node.handlers for n in ast.walk(h))


def _is_broad(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(isinstance(t, ast.Name) and t.id in _BROAD_EXCEPTIONS for t in types)
