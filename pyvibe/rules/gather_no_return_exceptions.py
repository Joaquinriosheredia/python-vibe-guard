import ast
from typing import Dict, List, Optional, Set, Union

from pyvibe.rules.base import Violation, AsyncContextVisitor

FuncDef = Union[ast.FunctionDef, ast.AsyncFunctionDef]

_BROAD_EXCEPTIONS = {"Exception", "BaseException"}
# Re-raising these is correct practice (cancellation / interpreter exit), not a
# leak of an ordinary exception, so it does not break containment.
_CANCELLATION = {"CancelledError", "KeyboardInterrupt", "SystemExit"}

# A synchronous call on the task's path, outside any swallowing try, can itself
# raise and escape — so it breaks containment. The only exceptions are this short
# whitelist of calls that do not raise for in-range inputs in normal use. Each
# entry is justified; project/HTTP/DB/validation calls are deliberately absent, so
# a synchronous validation that raises before the try (e.g. assert_in_scope) keeps
# the finding.
# Builtins that do not raise for ordinary inputs:
_SAFE_CALL_NAMES = {
    "isinstance", "issubclass",   # type checks, never raise for normal args
    "len", "bool", "str", "repr", "ascii",  # total on normal objects
    "hasattr",                    # returns False instead of raising
    "id", "type", "callable",     # introspection, never raise
    "list", "dict", "tuple", "set", "frozenset",  # constructors over iterables
    "enumerate", "range", "sorted", "reversed", "zip",  # iteration helpers
    "any", "all",                 # boolean folds
}
# Methods that do not raise on their normal receiver:
_SAFE_CALL_METHODS = {
    "get", "keys", "values", "items", "copy", "setdefault",  # dict reads/merges
    "append", "add", "extend", "update",                      # collection growth
    "strip", "lstrip", "rstrip", "lower", "upper", "title",   # str transforms
    "split", "rsplit", "splitlines", "join",                  # str split/join
    "startswith", "endswith", "format",                       # str predicates/format
    "isoformat",                                              # datetime -> str
    "debug", "info", "warning", "error", "exception", "critical", "log",  # logging
}


def _call_is_safe(call: ast.Call) -> bool:
    f = call.func
    if isinstance(f, ast.Name):
        if f.id == "getattr":
            return len(call.args) >= 3  # getattr with a default never raises
        return f.id in _SAFE_CALL_NAMES
    if isinstance(f, ast.Attribute):
        return f.attr in _SAFE_CALL_METHODS
    return False


class GatherNoReturnExceptionsRule(AsyncContextVisitor):
    """
    PYVIBE-013 — asyncio.gather() without return_exceptions=True

    Without return_exceptions=True, the first exception raised by any of the
    gathered awaitables propagates to the gather() caller. The other awaitables
    are NOT cancelled: they keep running with nobody observing their results or
    their later exceptions ("Task exception was never retrieved").

    Not reported when this file shows that none of the gathered awaitables can
    raise an ordinary exception: each resolves (same module/class/nested scope)
    to a function that *contains* its exceptions. A function contains its
    exceptions when every ``await`` in its body is either (a) lexically inside a
    ``try`` whose handlers include a broad one (Exception / BaseException /
    bare) and none of which re-raise an ordinary exception — re-raising
    CancelledError / KeyboardInterrupt / SystemExit is allowed — or (b) an await
    of an expression that itself cannot raise an ordinary exception
    (``asyncio.sleep``; ``asyncio.gather`` whose awaitables are all contained;
    ``asyncio.ensure_future`` / ``create_task`` of a contained awaitable;
    ``asyncio.to_thread`` of a plain def that contains its exceptions; a call to
    another contained function); and the function raises no ordinary exception
    outside a cancellation handler. A *synchronous* call outside a swallowing try
    (on the task's path) can itself raise and escape, so it breaks containment
    unless it is on a short whitelist of calls that do not raise in normal use
    (safe builtins, str/dict/collection/logging methods, ``getattr`` with a
    default); a validation that raises before the try therefore keeps the finding.
    Resolution follows nested
    defs, ``self.f`` / ``cls.f`` methods and module functions; recursion is
    assumed contained. Awaitable forms understood: ``f(...)``, ``*[...]``,
    ``*(...)``, ``*a, *b``, a local name bound once to a list literal (+append)
    or to a plain comprehension. Anything not resolved or not understood is
    reported: in doubt, the finding stays.

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

    # ─── containment analysis ─────────────────────────────────────────────────

    def _scope(self) -> "_Containment":
        return _Containment(self._module_funcs, self._func_stack, self._class_stack)

    def _all_awaitables_contained(self, node: ast.Call) -> bool:
        # Any keyword other than return_exceptions (e.g. **kwargs) is not understood.
        if any(kw.arg != "return_exceptions" for kw in node.keywords):
            return False
        if not node.args:
            return False
        scope = self._scope()
        host = self._func_stack[-1] if self._func_stack else None
        return all(scope.arg_contained(arg, host) for arg in node.args)


class _Containment:
    """Resolves awaitables and decides whether each cannot raise an ordinary
    exception, following nested/method/module scope, with memoisation and cycle
    handling.  Unknown → not contained (the finding stays)."""

    def __init__(self, module_funcs, func_stack, class_stack):
        # Flat lexical scope seen from the gather site: module funcs, overridden
        # by each enclosing function's defs (outer→inner so inner wins), which
        # also exposes sibling nested defs (e.g. a recursive _build_tree).
        self._flat: Dict[str, List[FuncDef]] = dict(module_funcs)
        for f in func_stack:
            self._flat.update(_defs_in(f.body))
        self._class = class_stack[-1] if class_stack else None
        self._memo: Dict[int, bool] = {}
        self._inprogress: Set[int] = set()

    # -- resolution ---------------------------------------------------------
    def _resolve(self, ref: ast.expr, host: Optional[FuncDef]) -> Optional[FuncDef]:
        if isinstance(ref, ast.Name):
            if host is not None:
                own = _defs_in(host.body)
                if ref.id in own:
                    return _single_plain(own[ref.id])
            return _single_plain(self._flat.get(ref.id))
        if (
            isinstance(ref, ast.Attribute)
            and isinstance(ref.value, ast.Name)
            and ref.value.id in ("self", "cls")
            and self._class is not None
        ):
            return _single_plain(_defs_in(self._class.body).get(ref.attr))
        return None

    # -- gather argument forms ----------------------------------------------
    def arg_contained(self, arg: ast.expr, host: Optional[FuncDef]) -> bool:
        if isinstance(arg, ast.Starred):
            value = arg.value
            if isinstance(value, (ast.ListComp, ast.GeneratorExp)):
                return _plain_comprehension(value) and self.awaitable_contained(value.elt, host)
            if isinstance(value, ast.Name):
                elements = self._local_list_elements(value.id, host)
                if elements is None:
                    comp = self._local_comprehension(value.id, host)
                    if comp is None:
                        return False
                    return self.awaitable_contained(comp.elt, host)
                return all(self.awaitable_contained(e, host) for e in elements)
            return False
        return self.awaitable_contained(arg, host)

    # -- an awaitable expression cannot raise an ordinary exception ----------
    def awaitable_contained(self, expr: ast.expr, host: Optional[FuncDef]) -> bool:
        if not isinstance(expr, ast.Call):
            return False
        if _is_asyncio_call(expr, "sleep"):
            return True
        if _is_asyncio_call(expr, "ensure_future") or _is_asyncio_call(expr, "create_task"):
            return len(expr.args) >= 1 and self.awaitable_contained(expr.args[0], host)
        if _is_asyncio_call(expr, "gather"):
            if any(kw.arg != "return_exceptions" for kw in expr.keywords) or not expr.args:
                return False
            return all(self.arg_contained(a, host) for a in expr.args)
        if _is_asyncio_call(expr, "to_thread"):
            if not expr.args:
                return False
            func = self._resolve(expr.args[0], host)
            return isinstance(func, ast.FunctionDef) and _sync_contains_exceptions(func)
        func = self._resolve(expr.func, host)
        return func is not None and self.func_contained(func)

    # -- a function contains its exceptions ---------------------------------
    def func_contained(self, func: FuncDef) -> bool:
        key = id(func)
        if key in self._memo:
            return self._memo[key]
        if key in self._inprogress:
            return True  # recursion: assume contained (the awaits are checked elsewhere)
        self._inprogress.add(key)
        result = self._analyze(func)
        self._inprogress.discard(key)
        self._memo[key] = result
        return result

    def _analyze(self, func: FuncDef) -> bool:
        ok = [True]

        def walk(node: ast.AST, protect: int, in_cancel: bool, in_handler: bool):
            if not ok[0]:
                return
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                return  # a different scope; analysed when called
            if isinstance(node, ast.Raise):
                if not in_cancel:
                    ok[0] = False
                return
            if isinstance(node, ast.Await):
                if protect == 0 and not self.awaitable_contained(node.value, func):
                    ok[0] = False
                return
            if isinstance(node, ast.Call):
                # A synchronous call on the task's *normal* path, outside a
                # swallowing try, can raise and escape (an awaited call is handled
                # above). Calls inside an except handler run only after an
                # exception was already caught, so they are not on that path.
                if protect == 0 and not in_handler and not _call_is_safe(node):
                    ok[0] = False
                    return
                for child in ast.iter_child_nodes(node):
                    walk(child, protect, in_cancel, in_handler)
                return
            if isinstance(node, ast.Try):
                # A non-trivial `finally` runs on every path and can raise and
                # escape, so it breaks containment (conservative: protects TPs).
                if any(
                    isinstance(n, (ast.Call, ast.Await, ast.Raise))
                    for s in node.finalbody
                    for n in ast.walk(s)
                ):
                    ok[0] = False
                    return
                swallow = _try_is_swallowing(node)
                for s in node.body:
                    walk(s, protect + (1 if swallow else 0), in_cancel, in_handler)
                for h in node.handlers:
                    cancel = _handler_is_cancellation_only(h)
                    for s in h.body:
                        walk(s, protect, cancel, True)
                for s in node.orelse:
                    walk(s, protect, in_cancel, in_handler)
                return
            for child in ast.iter_child_nodes(node):
                walk(child, protect, in_cancel, in_handler)

        for stmt in func.body:
            walk(stmt, 0, False, False)
        return ok[0]

    # -- local name bound to a list literal (+ append) ----------------------
    def _local_list_elements(self, name: str, func: Optional[FuncDef]) -> Optional[List[ast.expr]]:
        if func is None:
            return None
        elements: List[ast.expr] = []
        allowed = set()
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
            elif isinstance(node, ast.Call) and _is_asyncio_call(node, "gather"):
                for a in node.args:
                    if isinstance(a, ast.Starred) and isinstance(a.value, ast.Name) and a.value.id == name:
                        allowed.add(id(a.value))
        if not literal_seen:
            return None
        for node in ast.walk(func):
            if isinstance(node, ast.Name) and node.id == name and id(node) not in allowed:
                return None
        return elements

    # -- local name bound exactly once to a plain comprehension -------------
    def _local_comprehension(self, name: str, func: Optional[FuncDef]):
        if func is None:
            return None
        found = None
        for node in ast.walk(func):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Name) and t.id == name for t in targets):
                    value = node.value
                    if (
                        len(targets) == 1
                        and found is None
                        and isinstance(value, (ast.ListComp, ast.GeneratorExp))
                        and _plain_comprehension(value)
                    ):
                        found = value
                    else:
                        return None  # reassigned / not a plain comprehension
            elif (
                isinstance(node, ast.AugAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == name
            ):
                return None
        return found


def _is_asyncio_call(node: ast.Call, attr: str) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == attr
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "asyncio"
    )


def _defs_in(body: List[ast.stmt]) -> Dict[str, List[FuncDef]]:
    """All functions defined lexically in this body, including those nested in
    compound statements (``with`` / ``try`` / ``if`` / ``for`` …), but not those
    inside a nested function or class (a different scope)."""
    defs: Dict[str, List[FuncDef]] = {}

    def rec(stmts: List[ast.stmt]):
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.setdefault(stmt.name, []).append(stmt)
            elif isinstance(stmt, ast.ClassDef):
                continue
            else:
                for sub in _stmt_bodies(stmt):
                    rec(sub)

    rec(body)
    return defs


def _stmt_bodies(stmt: ast.stmt) -> List[List[ast.stmt]]:
    """The statement-list bodies a compound statement owns directly."""
    bodies: List[List[ast.stmt]] = []
    for field, value in ast.iter_fields(stmt):
        if isinstance(value, list):
            if value and all(isinstance(v, ast.stmt) for v in value):
                bodies.append(value)
            else:
                for v in value:
                    inner = getattr(v, "body", None)  # ExceptHandler, match_case
                    if isinstance(inner, list) and inner and all(isinstance(s, ast.stmt) for s in inner):
                        bodies.append(inner)
    return bodies


def _single_plain(defs: Optional[List[FuncDef]]) -> Optional[FuncDef]:
    # Redefined (ambiguous) or decorated (a wrapper may re-raise): not resolved.
    if not defs or len(defs) != 1 or defs[0].decorator_list:
        return None
    return defs[0]


def _plain_comprehension(comp: Union[ast.ListComp, ast.GeneratorExp]) -> bool:
    # Plain `for` clauses (filters allowed, no `async for`): every item is the element.
    return all(not g.is_async for g in comp.generators)


def _handler_is_cancellation_only(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return False
    types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    names = []
    for t in types:
        if isinstance(t, ast.Name):
            names.append(t.id)
        elif isinstance(t, ast.Attribute):
            names.append(t.attr)
        else:
            return False
    return bool(names) and all(n in _CANCELLATION for n in names)


def _is_broad(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(isinstance(t, ast.Name) and t.id in _BROAD_EXCEPTIONS for t in types)


def _try_is_swallowing(try_node: ast.Try) -> bool:
    """The try has a broad handler and no handler re-raises an ordinary
    exception (a bare/typed re-raise in a cancellation-only handler is fine)."""
    if not any(_is_broad(h) for h in try_node.handlers):
        return False
    for h in try_node.handlers:
        if _handler_is_cancellation_only(h):
            continue
        if any(isinstance(n, ast.Raise) for n in ast.walk(h)):
            return False
    return True


def _sync_contains_exceptions(func: FuncDef) -> bool:
    """A plain def whose whole body (at most a docstring first) is one try that
    swallows broadly with no else/finally and no ordinary re-raise."""
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
    return _try_is_swallowing(try_node)
