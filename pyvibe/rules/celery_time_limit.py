import ast
from typing import Dict, List
from pyvibe.rules.base import Violation

_LIMIT_KEYS = {"soft_time_limit", "time_limit"}

# Task frameworks whose apps also expose a `.task` decorator. A file importing one of
# them (and not celery) is not a Celery file (test-corpus-2: Procrastinate's
# `@task_app.task`, 13 FPs, FP-ANALYSIS.md §1).
_OTHER_TASK_FRAMEWORKS = {"procrastinate", "huey", "dramatiq", "taskiq", "arq", "rq", "saq", "faust"}


class CeleryTaskTimeLimitRule(ast.NodeVisitor):
    """
    PYVIBE-005 — Celery task defined without soft_time_limit or time_limit

    A Celery task with no time limit can hang indefinitely if the external
    call it wraps never returns — blocking a worker process permanently.
    Under load, all workers fill with hung tasks and the queue stalls.

    Detected decorators: @app.task, @shared_task (bare or with kwargs).

    WARNING, not CRITICAL (test-corpus-2, 0 TP of 13): a missing per-task limit only
    hurts if the wrapped work never returns, and the rule cannot see a global limit.

    A receiver imported by the file counts as Celery's only when it is imported from a
    module whose dotted path contains "celery", or the file imports celery; a file that
    imports another task framework (Procrastinate, Huey, Dramatiq, taskiq, arq, RQ, SAQ,
    Faust) and not celery is never reported.
    Fix: @app.task(soft_time_limit=30, time_limit=60)

    Known limitation — global configuration blind spot:
    Celery allows setting task_time_limit and task_soft_time_limit globally
    via app.conf.task_time_limit, app.conf.update(...), or in celeryconfig.py /
    settings.py.  When a project uses global limits every task inherits them
    and per-task decorator arguments are redundant.  This rule does NOT detect
    global configuration: it only inspects the decorator arguments of the
    current file.  Projects with a project-wide task_time_limit will see
    PYVIBE-005 warnings on tasks that are already covered by that global limit.
    If that applies to your project, either add per-task limits (preferred —
    self-documenting, immune to config drift) or suppress with
    `# pyvibe: ignore PYVIBE-005` on the task's `def` line.
    """

    RULE_ID = "PYVIBE-005"
    SEVERITY = "WARNING"

    def __init__(self):
        self.violations: List[Violation] = []
        self._has_celery_import: bool = False
        self._has_other_framework_import: bool = False
        self._imported_from: Dict[str, str] = {}  # local name -> module it was imported from
        self._defs: List[ast.AST] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "celery" or alias.name.startswith("celery."):
                self._has_celery_import = True
            if alias.name.split(".")[0] in _OTHER_TASK_FRAMEWORKS:
                self._has_other_framework_import = True
            self._imported_from[(alias.asname or alias.name).split(".")[0]] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if module == "celery" or module.startswith("celery."):
            self._has_celery_import = True
        if module.split(".")[0] in _OTHER_TASK_FRAMEWORKS:
            self._has_other_framework_import = True
        for alias in node.names:
            self._imported_from[alias.asname or alias.name] = module
        self.generic_visit(node)

    # Decorators are checked after the whole module is visited, so an import below a
    # task (or inside a function) still counts.
    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._defs.append(node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Module(self, node: ast.Module):
        self.generic_visit(node)
        for d in self._defs:
            self._check(d)

    # ── private ──────────────────────────────────────────────────────────────

    def _check(self, node):
        for decorator in node.decorator_list:
            if self._is_task_decorator(decorator) and not self._has_time_limit(decorator):
                self.violations.append(Violation(
                    rule_id=self.RULE_ID,
                    severity=self.SEVERITY,
                    line=node.lineno,
                    function_name=node.name,
                    message=(
                        "Celery task without soft_time_limit or time_limit — if the work it wraps never returns, "
                        "it holds a worker until a global task_time_limit (if one is set) stops it"
                    ),
                    evidence="Use @app.task(soft_time_limit=30, time_limit=60) to bound execution time",
                ))
                break  # one violation per function, even if decorated twice

    def _is_task_decorator(self, decorator: ast.expr) -> bool:
        if self._has_other_framework_import and not self._has_celery_import:
            return False
        # Unwrap @app.task(...) or @shared_task(...) to their func node
        node = decorator.func if isinstance(decorator, ast.Call) else decorator
        # @shared_task — Celery-specific; taskiq/huey/dramatiq don't use this name
        if isinstance(node, ast.Name) and node.id == "shared_task":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "task":
            receiver = node.value
            # @self.huey.task(), @self.app.task — chained attrs seen only in
            # test infrastructure (Celery own tests, Huey tests). Skip.
            if not isinstance(receiver, ast.Name):
                return False
            if receiver.id in self._imported_from:
                # `from proj.celery import app` / `from .celery_app import app` count;
                # `from app.tasks import task_app` (Procrastinate, test-corpus-2) does not.
                return "celery" in self._imported_from[receiver.id].lower() or self._has_celery_import
            name = receiver.id.lower()
            # @app.task / @importer_app.task — "app" strongly signals a Celery
            # application object; no other common async task framework uses it
            if "app" in name:
                return True
            # @celery.task / @celery_app.task / @my_celery.task
            if "celery" in name:
                return True
            # @broker.task (taskiq), @huey.task, @dramatiq_broker.task etc. —
            # only flag when the file explicitly imports from the celery package,
            # confirming this isn't a different task framework
            return self._has_celery_import
        return False

    def _has_time_limit(self, decorator: ast.expr) -> bool:
        # Bare decorator (@app.task with no call) → no kwargs possible
        if not isinstance(decorator, ast.Call):
            return False
        return any(kw.arg in _LIMIT_KEYS for kw in decorator.keywords)
