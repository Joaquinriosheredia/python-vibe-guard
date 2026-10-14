"""0.13.0 (vibe-guard Phase 1, decisions of 2026-10-14).

PYVIBE-013, strict: not reported only when every gathered awaitable resolves, in the
same module, to a function whose whole body (at most a docstring before it) is one try
that catches Exception/BaseException/everything, with no else, no finally and no raise in
a handler. In doubt, reported.

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


# ─── PYVIBE-013: strict body → reported ──────────────────────────────────────

@pytest.mark.parametrize("body", [
    # a statement before the try (only a docstring is allowed)
    "    y = x\n    try:\n        return await call(y)\n    except Exception:\n        return None\n",
    # a statement after the try
    "    try:\n        r = await call(x)\n    except Exception:\n        r = None\n    return r\n",
    # else: runs outside the handlers
    "    try:\n        r = await call(x)\n    except Exception:\n        return None\n    else:\n        return r\n",
    # finally: can raise
    "    try:\n        return await call(x)\n    except Exception:\n        return None\n    finally:\n        cleanup()\n",
    # a handler re-raises
    "    try:\n        return await call(x)\n    except Exception:\n        raise\n",
    "    try:\n        return await call(x)\n    except Exception as e:\n        raise RuntimeError() from e\n",
    # no broad handler
    "    try:\n        return await call(x)\n    except (ValueError, KeyError):\n        return None\n",
    # no try at all
    "    return await call(x)\n",
    # async with around the try
    "    async with lock:\n        try:\n            return await call(x)\n        except Exception:\n            return None\n",
])
def test_013_strict_body_reported(body):
    assert len(_013(f"import asyncio\n\nasync def f(x):\n{body}\nasync def handler():\n    await asyncio.gather(f(1), f(2))\n")) == 1


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
