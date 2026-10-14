"""0.13.0 (vibe-guard Phase 1, decisions of 2026-10-14), with the containment
relaxation of FASE1-DISENO.md point 2 (fix/pyvibe-013-containment).

PYVIBE-013: not reported when every gathered awaitable resolves to a function that
*contains* its exceptions — every ``await`` is inside a ``try`` that swallows broadly
without re-raising an ordinary exception (re-raising CancelledError is allowed), or is an
await of an expression that cannot raise an ordinary exception (asyncio.sleep; a gather of
contained awaitables; to_thread of a contained plain def; a call to a contained function).
Synchronous statements outside the try are allowed; a non-trivial ``finally`` and any
ordinary re-raise break containment. In doubt, reported.

PYVIBE-009: WARNING (not CRITICAL) when the opened file's I/O is delegated to a thread.
"""
import textwrap

import pytest

from pyvibe.analyzer import analyze_source
from pyvibe.rules.gather_no_return_exceptions import GatherNoReturnExceptionsRule


def _013(src):
    return [v for v in analyze_source(textwrap.dedent(src)) if v.rule_id == "PYVIBE-013"]


SAFE = '''
import asyncio

async def safe(x):
    """Docstring allowed before the try."""
    try:
        return await call(x)
    except Exception:
        return None
'''


# ─── PYVIBE-013: forms that resolve to contained coroutines → not reported ────

@pytest.mark.parametrize("gather", [
    "await asyncio.gather(safe(1), safe(2))",
    "await asyncio.gather(*[safe(x) for x in xs])",
    "await asyncio.gather(*(safe(x) for x in xs if x))",
    "await asyncio.gather(*[safe(x) for x in xs for y in ys])",
    "await asyncio.gather(asyncio.ensure_future(safe(1)), asyncio.create_task(safe(2)))",
    "await asyncio.gather(asyncio.sleep(1), safe(1))",
])
def test_013_module_function_forms_not_reported(gather):
    assert _013(SAFE + f"\nasync def handler(xs, ys):\n    {gather}\n") == []


def test_013_local_list_built_with_append_not_reported():
    assert _013(SAFE + '''
async def handler(xs):
    tasks = []
    for x in xs:
        tasks.append(safe(x))
    tasks.append(asyncio.ensure_future(asyncio.sleep(1)))
    await asyncio.gather(*tasks)
''') == []


def test_013_nested_function_not_reported():
    assert _013('''
import asyncio

async def handler(xs):
    async def fetch(x):
        try:
            return await call(x)
        except BaseException:
            return None
    await asyncio.gather(*[fetch(x) for x in xs])
''') == []


def test_013_to_thread_of_a_plain_def_not_reported():
    assert _013('''
import asyncio

def work(x):
    try:
        return do(x)
    except:
        return None

async def handler(xs):
    await asyncio.gather(*[asyncio.to_thread(work, x) for x in xs])
''') == []


def test_013_self_method_not_reported():
    assert _013('''
import asyncio

class Client:
    async def one(self, x):
        try:
            return await call(x)
        except (ValueError, Exception) as e:
            return e

    async def all(self, xs):
        await asyncio.gather(*[self.one(x) for x in xs])
''') == []


# ─── PYVIBE-013: leaky body → reported ───────────────────────────────────────

@pytest.mark.parametrize("body", [
    # finally: a non-trivial finally runs on every path and can raise and escape
    "    try:\n        return await call(x)\n    except Exception:\n        return None\n    finally:\n        cleanup()\n",
    # a handler re-raises an ordinary exception
    "    try:\n        return await call(x)\n    except Exception:\n        raise\n",
    "    try:\n        return await call(x)\n    except Exception as e:\n        raise RuntimeError() from e\n",
    # no broad handler: a non-matching exception propagates
    "    try:\n        return await call(x)\n    except (ValueError, KeyError):\n        return None\n",
    # no try at all
    "    return await call(x)\n",
    # the await is in the else, outside the handlers' protection
    "    try:\n        pass\n    except Exception:\n        return None\n    else:\n        return await call(x)\n",
])
def test_013_leaky_body_reported(body):
    assert len(_013(f"import asyncio\n\nasync def f(x):\n{body}\nasync def handler():\n    await asyncio.gather(f(1), f(2))\n")) == 1


# ─── PYVIBE-013: contained body (relaxation of FASE1-DISENO.md §2) → not reported ─

@pytest.mark.parametrize("body", [
    # a synchronous statement before the try (the awaited I/O is still guarded) — C203 shape
    "    y = x\n    try:\n        return await call(y)\n    except Exception:\n        return None\n",
    # a synchronous statement after the try
    "    try:\n        r = await call(x)\n    except Exception:\n        r = None\n    return r\n",
    # an else with no await and no raise
    "    try:\n        r = await call(x)\n    except Exception:\n        return None\n    else:\n        return r\n",
    # async with around the try, and a re-raise of CancelledError — C124 shape
    "    async with lock:\n        try:\n            return await call(x)\n        except asyncio.CancelledError:\n            raise\n        except BaseException:\n            return None\n",
])
def test_013_contained_body_not_reported(body):
    assert _013(f"import asyncio\n\nasync def f(x):\n{body}\nasync def handler():\n    await asyncio.gather(f(1), f(2))\n") == []


@pytest.mark.parametrize("src", [
    # a parameter
    "import asyncio\nasync def handler(fn):\n    await asyncio.gather(fn(1), fn(2))\n",
    # an attribute
    "import asyncio\nasync def handler(request):\n    await asyncio.gather(request.app.state.F(1))\n",
    # an imported function
    "import asyncio\nfrom m import safe\nasync def handler():\n    await asyncio.gather(safe(1))\n",
    # a lambda
    "import asyncio\nasync def handler():\n    await asyncio.gather((lambda: call())())\n",
    # one awaitable not contained
    SAFE + "\nasync def handler():\n    await asyncio.gather(safe(1), other(2))\n",
    # decorated: a wrapper may re-raise
    "import asyncio\n@retry\nasync def f(x):\n    try:\n        return await call(x)\n    except Exception:\n        return None\nasync def handler():\n    await asyncio.gather(f(1))\n",
    # defined twice: ambiguous
    SAFE + SAFE + "\nasync def handler():\n    await asyncio.gather(safe(1))\n",
    # to_thread of an async def
    SAFE + "\nasync def handler():\n    await asyncio.gather(asyncio.to_thread(safe, 1))\n",
    # list mutated other than by append, or passed elsewhere
    SAFE + "\nasync def handler(xs):\n    tasks = []\n    tasks.extend([safe(x) for x in xs])\n    await asyncio.gather(*tasks)\n",
    SAFE + "\nasync def handler(xs):\n    tasks = [safe(1)]\n    tasks += [other()]\n    await asyncio.gather(*tasks)\n",
    SAFE + "\nasync def handler(xs):\n    tasks = [safe(1)]\n    log(tasks)\n    await asyncio.gather(*tasks)\n",
    SAFE + "\nasync def handler(xs):\n    tasks = [safe(1)]\n    tasks = [other()]\n    await asyncio.gather(*tasks)\n",
    # an async comprehension
    SAFE + "\nasync def handler(xs):\n    await asyncio.gather(*[safe(x) async for x in xs])\n",
    # **kwargs and no arguments at all
    SAFE + "\nasync def handler(kw):\n    await asyncio.gather(safe(1), **kw)\n",
    "import asyncio\nasync def handler():\n    await asyncio.gather()\n",
])
def test_013_unresolved_reported(src):
    assert len(_013(src)) == 1


def test_013_message_does_not_say_leak_and_says_keep_running():
    [v] = _013("import asyncio\nasync def handler():\n    await asyncio.gather(a(), b())\n")
    assert "leak" not in v.message.lower()
    assert "keep running" in v.message
    assert "leak" not in (GatherNoReturnExceptionsRule.__doc__ or "").lower()  # `pyvibe explain` text


def test_013_demo_still_reported():
    from pathlib import Path
    src = (Path(__file__).parent.parent / "demo" / "bad_async.py").read_text()
    assert any(v.rule_id == "PYVIBE-013" for v in analyze_source(src))


# ─── PYVIBE-009: I/O delegated to a thread → WARNING ─────────────────────────

def _009(src):
    return [(v.severity, v.line) for v in analyze_source(textwrap.dedent(src)) if v.rule_id == "PYVIBE-009"]


def test_009_read_delegated_to_to_thread_is_warning():
    assert _009('''
import asyncio

async def handler(path):
    with open(path, "rb") as image:
        data = await asyncio.to_thread(image.read, 1024)
''') == [("WARNING", 5)]


def test_009_write_delegated_to_run_in_executor_is_warning():
    assert _009('''
async def handler(path, loop):
    with open(path, "w") as f:
        await loop.run_in_executor(None, f.write, "x")
''') == [("WARNING", 3)]


@pytest.mark.parametrize("body", [
    "        data = f.read()\n",                                         # read on the loop
    "        await asyncio.to_thread(f.read)\n        f.seek(0)\n",       # one call on the loop
    "        await asyncio.to_thread(lambda: f.read())\n",                # handle inside a lambda
    "        await asyncio.to_thread(process, f)\n",                      # handle passed whole
    "        pass\n",                                                     # handle never used
])
def test_009_other_uses_stay_critical(body):
    assert _009(f"import asyncio\n\nasync def handler(p):\n    with open(p) as f:\n{body}") == [("CRITICAL", 4)]


def test_009_open_without_with_stays_critical():
    assert _009("import asyncio\nasync def handler(p):\n    f = open(p)\n    await asyncio.to_thread(f.read)\n") == [("CRITICAL", 3)]


# ─── PYVIBE-013: regression against Joaquín's verdicts on test-corpus-1 ────────
# Each fixture reproduces the mechanism of a reviewed finding (rewritten, not
# copied) and cites the verdict in vibe-guard-evaluation audit-joaquin.json.

def test_013_C124_fp_async_with_wrapper_cancelled_reraise():
    # C124 (FP): gather(*(run(item) ...)) where run wraps its await in async with
    # + try, re-raising only CancelledError and returning None otherwise.
    assert _013('''
import asyncio

async def map_bounded(worker, items):
    semaphore = asyncio.Semaphore(4)
    async def run(item):
        async with semaphore:
            try:
                return await worker(item)
            except asyncio.CancelledError:
                raise
            except BaseException:
                return None
    return list(await asyncio.gather(*(run(item) for item in items)))
''') == []


def test_013_C011_fp_recursive_tree_over_contained_fetch():
    # C011 (FP): _build_tree awaits gathers of a contained fetch and of itself
    # (recursion); nothing can raise an ordinary exception.
    assert _013('''
import asyncio

async def handler(root):
    async def _fetch(iid):
        try:
            return await call(iid)
        except Exception:
            return None
    async def _build_tree(item, depth):
        raw = await asyncio.gather(*[_fetch(c) for c in item])
        return await asyncio.gather(*[_build_tree(c, depth - 1) for c in raw if c])
    await asyncio.gather(*[_build_tree(c, 2) for c in root])
''') == []


def test_013_C203_fp_sync_stmt_outside_try_and_to_thread_guarded():
    # C203 (FP): a synchronous get_settings() outside the try; the only awaited
    # I/O (to_thread) is inside a try that swallows broadly. Two *a, *b lists.
    assert _013('''
import asyncio

async def _retrieve(call):
    settings = get_settings()
    try:
        return await asyncio.to_thread(retrieve, settings)
    except Exception:
        return ""

async def route_parallel(calls):
    knowledge = [_retrieve(c) for c in calls]
    failures = [_retrieve(c) for c in calls]
    await asyncio.gather(*knowledge, *failures)
''') == []


def test_013_C220_fp_wait_for_guarded_by_timeout_and_broad():
    # C220 (FP): await asyncio.wait_for(...) inside a try catching TimeoutError
    # and Exception, both returning a status dict.
    assert _013('''
import asyncio

async def _probe(timeout):
    name = cfg()
    try:
        return await asyncio.wait_for(asyncio.to_thread(work), timeout=timeout)
    except asyncio.TimeoutError:
        return {"status": "failed"}
    except Exception:
        return {"status": "failed"}

async def warmup(t):
    await asyncio.gather(_probe(t), _probe(t))
''') == []


def test_013_C240_fp_nested_merge_delegates_to_contained_method():
    # C240 (FP): merge_group (async with) awaits self._integrate, which bottoms
    # out in a method whose await is inside a swallowing try.
    assert _013('''
import asyncio

class Summarizer:
    async def _leaf(self, group):
        try:
            return await self._llm(group)
        except Exception:
            return group

    async def _integrate(self, group):
        return await self._leaf(group)

    async def merge(self, groups):
        semaphore = asyncio.Semaphore(4)
        async def merge_group(group):
            async with semaphore:
                return await self._integrate(group)
        await asyncio.gather(*(merge_group(g) for g in groups))
''') == []


def test_013_C180_tp_callee_awaits_unguarded_io():
    # C180 (TP): make_url awaits prepare() with no try → can raise.
    assert len(_013('''
import asyncio

async def make_url(img):
    data = await prepare(img)
    return data

async def build(imgs):
    await asyncio.gather(*(make_url(i) for i in imgs))
''')) == 1


def test_013_C208_tp_callee_reraises_ordinary_exception():
    # C208 (TP): run_query re-raises a non-cancellation exception.
    assert len(_013('''
import asyncio

async def run_query(q):
    try:
        return await search(q)
    except TimeoutError:
        raise

async def stream(qs):
    await asyncio.gather(*(run_query(q) for q in qs))
''')) == 1


def test_013_C231_tp_callee_awaits_db_outside_try():
    # C231 (TP): rank awaits a fallback DB call outside the try.
    assert len(_013('''
import asyncio

async def rank(db, company):
    try:
        ids = await vector_ids(company)
    except Exception:
        ids = []
    return await fallback_similar_companies(db, company)

async def page(db, companies):
    await asyncio.gather(*(rank(db, c) for c in companies))
''')) == 1


@pytest.mark.xfail(
    strict=True,
    reason="known false negative (dev-labels DL-046, ARES scan_hosts, #3): a "
    "synchronous validation that raises BEFORE the try (e.g. scope_guard."
    "assert_in_scope) escapes the task, but PYVIBE-013 requires a concrete I/O "
    "failure escaping the awaited call, so it is not detected. Decision 2026-10-14.",
)
def test_013_B2_sync_validation_before_try_known_false_negative():
    # Pattern of #3 (ARES scan_hosts -> scan_one -> scan_host): scan_host runs a
    # synchronous scope-guard validation that raises for out-of-scope hosts BEFORE
    # the try; gather would propagate it. The lax rule does NOT flag this (xfail).
    assert len(_013('''
import asyncio

async def scan_hosts(hosts, scope_guard):
    async def scan_one(host):
        return await scan_host(host, scope_guard)
    async def scan_host(host, scope_guard):
        if scope_guard is not None:
            scope_guard.assert_in_scope(host, action="scan")
        try:
            return await connect(host)
        except Exception:
            return None
    await asyncio.gather(*(scan_one(h) for h in hosts))
''')) >= 1
