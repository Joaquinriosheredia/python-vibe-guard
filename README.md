# python-vibe-guard

[![tests](https://github.com/Joaquinriosheredia/python-vibe-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/Joaquinriosheredia/python-vibe-guard/actions/workflows/ci.yml)

## The incident

A FastAPI service that handled 50 concurrent requests in staging started timing out in production at 200 rps. The team spent two days adding replicas, tweaking Gunicorn workers, and profiling CPU — nothing helped. The p99 latency was 8 seconds for an endpoint that should take 80ms.

> Scenario based on a common pattern observed in async Python codebases.
> Reproduced in controlled testing with locust against a FastAPI service.

Root cause: one engineer had asked an AI assistant to "add a retry with backoff" to an async handler. The AI generated `time.sleep(2)` inside the `async def`. In staging with a handful of requests it was invisible. In production it froze the entire event loop for 2 seconds per request, serializing all 200 concurrent calls through a single bottleneck.

The code passed every unit test. It passed the integration tests. It shipped to production in a Friday deploy.

**python-vibe-guard catches this in CI before it reaches staging.**

---

## What it detects

Sixteen patterns that AI models generate repeatedly, that pass all static checks, and that silently destroy async performance under real load:

| Rule | Pattern | Gate | Runtime effect |
|------|---------|------|----------------|
| PYVIBE-001 | `time.sleep()` inside `async def` | `async def` | Freezes entire event loop for sleep duration |
| PYVIBE-002 | `requests.*` inside `async def` | `async def` | Blocks OS thread, serializes all concurrent I/O |
| PYVIBE-003 | `asyncio.run()` inside `async def` | `async def` | `RuntimeError: This event loop is already running` |
| PYVIBE-004 | `threading.Lock/RLock/…` inside `async def` | `async def` | Blocks event loop under contention |
| PYVIBE-005 | `@app.task` / `@shared_task` without `soft_time_limit` or `time_limit` | decorator | Worker hangs forever if external call never returns |
| PYVIBE-006 | `ContextVar.set()` inside `async def` without `try/finally reset()` | `async def` | Context leaks into sibling async tasks |
| PYVIBE-007 | `subprocess.run/call/check_output/Popen` inside `async def` | `async def` | Blocks OS thread for entire subprocess duration |
| PYVIBE-008 | `sqlite3.connect()` inside `async def` | `async def` | Synchronous file I/O blocks the event loop |
| PYVIBE-009 | `open()` builtin inside `async def` | `async def` | Synchronous file I/O blocks the event loop |
| PYVIBE-010 | `httpx.get/post/put/…` inside `async def` | `async def` | httpx sync API blocks OS thread for full HTTP round-trip |
| PYVIBE-011 | `os.system/popen/waitpid` inside `async def` | `async def` | Blocking OS calls with no direct async equivalent |
| PYVIBE-012 | `asyncio.create_task()` with discarded return value | `async def` | Task GC'd mid-execution; exceptions silently swallowed |
| PYVIBE-013 | `asyncio.gather()` without `return_exceptions=True` | `async def` | First exception leaks remaining tasks; no per-task error handling |
| PYVIBE-014 | `asyncio.ensure_future()` with discarded return value | `async def` | Same GC hazard as PYVIBE-012; pre-3.7 API still common in older codebases |
| PYVIBE-015 | `loop.run_until_complete()` inside `async def` | `async def` | `RuntimeError: This event loop is already running` |
| PYVIBE-016 | `httpx.Client()` instantiated inside `async def` | `async def` | Sync client blocks OS thread per request; `httpx.AsyncClient()` is excluded |

Rules PYVIBE-001–004, 006–016 fire **only inside `async def`**. PYVIBE-005 fires on the decorator regardless of whether the function body is async.

**PYVIBE-013 in test files:** `asyncio.gather()` without `return_exceptions=True` is intentional in test code — exceptions should propagate for assertions. pyvibe automatically downgrades this violation to `WARNING` (not `CRITICAL`) in files matching `test_*.py`, `*_test.py`, or paths under `tests/`.

---

## Validation

Scanned against 4 production Python repos with pyvibe v0.4.0 (16 rules, shallow clone, `python -m pyvibe <repo> --json`):

| Repo | .py files | Violations |
|------|-----------|-----------|
| [fastapi/fastapi](https://github.com/tiangolo/fastapi) | 1 121 | 0 |
| [celery/celery](https://github.com/celery/celery) | 416 | 352 |
| [aio-libs/aiohttp](https://github.com/aio-libs/aiohttp) | 164 | 27 |
| [encode/httpx](https://github.com/encode/httpx) | 60 | 0 |
| **Total** | **1 761** | **379** |

**By rule (rules with 0 hits omitted):**

| Rule | Hits | Repo |
|------|------|------|
| PYVIBE-001 | 1 | aiohttp |
| PYVIBE-005 | 352 | celery |
| PYVIBE-006 | 2 | aiohttp |
| PYVIBE-009 | 4 | aiohttp |
| PYVIBE-013 | 20 | aiohttp |

Rules PYVIBE-002–004, 007–008, 010–012, 014–016 produced zero hits across these four repos. PYVIBE-014/015/016 target application code patterns (orphaned futures, `run_until_complete` inside async, sync httpx client), not framework internals — these repos are the frameworks themselves.

Raw scan data: [`validation/breakdown.json`](validation/breakdown.json)

**Real findings:**

- **Celery `celery/app/builtins.py`** — 12 internal tasks (`backend_cleanup`, `accumulate`, `unlock_chord`, and others) defined without `soft_time_limit` or `time_limit`. Under certain broker/backend conditions these workers can hang indefinitely. Detected by PYVIBE-005.

- **aiohttp `examples/web_ws.py`** — `open()` called inside an async WebSocket handler in the official aiohttp examples directory. Synchronous file I/O in a production-facing async context. Detected by PYVIBE-009.

- **aiohttp** — 20 `asyncio.gather()` calls without `return_exceptions=True`. In test files these are downgraded to WARNING automatically; in production async handlers they remain CRITICAL. Detected by PYVIBE-013.

---

## Installation

```bash
pip install python-vibe-guard
```

Or run without installing:

```bash
pip install -e .
```

---

## Usage

```bash
# Scan a file
python -m pyvibe path/to/file.py

# Scan a directory recursively
python -m pyvibe src/

# JSON output for CI/CD pipelines
python -m pyvibe src/ --json

# Exclude directories (adds to built-in defaults: venv, .venv, __pycache__, …)
python -m pyvibe src/ --exclude tests

# Exit code: 0 = clean, 1 = violations found, 2 = path error
```

### Example output

```
  python-vibe-guard
  ─────────────────────────────────────────────

  demo/bad_async.py

  [CRITICAL] [PYVIBE-001] — line 14
     Function : process_order()
     Problem  : time.sleep() blocks the entire event loop
     Fix      : Use `await asyncio.sleep(n)` instead

  [CRITICAL] [PYVIBE-002] — line 20
     Function : fetch_user()
     Problem  : requests.get() is synchronous — blocks the event loop
     Fix      : Use `async with httpx.AsyncClient() as c: await c.get(url)`

  [CRITICAL] [PYVIBE-003] — line 26
     Function : orchestrate()
     Problem  : asyncio.run() inside async def raises RuntimeError at runtime
     Fix      : Use `await coroutine()` directly — asyncio.run() is for sync entrypoints only

  [CRITICAL] [PYVIBE-004] — line 32
     Function : update_counter()
     Problem  : threading.Lock() blocks the event loop under contention
     Fix      : Use `asyncio.Lock()` with `async with lock:` instead

  ─────────────────────────────────────────────
  4 violation(s) in 1 file(s)
```

---

## CI/CD integration

Add to your GitHub Actions workflow:

```yaml
- name: python-vibe-guard scan
  run: |
    pip install python-vibe-guard
    python -m pyvibe src/ --json
```

The scanner exits with code `1` when violations are found, failing the CI job.

---

## Pre-commit integration

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/Joaquinriosheredia/python-vibe-guard
    rev: v0.4.0
    hooks:
      - id: python-vibe-guard
```

Then install the hook:

```bash
pre-commit install
```

The hook runs on every `git commit`, scans all Python files in the project, and blocks the commit if any violations are found.

---

## Design

- **Pure AST, zero runtime dependencies** — uses only Python's built-in `ast` module
- **Each rule is an independent `ast.NodeVisitor`** — easy to add, disable, or extend
- **Gate on `async def`** — every rule checks `_current_async_func` before firing; sync context is never flagged
- **No import resolution** — works on any Python file without installing its dependencies
- **Test-aware severity** — PYVIBE-013 is automatically downgraded to WARNING in test files

---

## Run the demo

```bash
python -m pyvibe demo/bad_async.py
```

Expected: 16 CRITICAL findings, one per rule. `demo/bad_async.py` also contains a sync function with the same patterns — those produce zero findings.

---

## Run the tests

```bash
python -m pytest tests/ -v
# or
python tests/test_rules.py
```

76 tests: true positives + false-positive guards for every rule.

---

## Ecosystem

This project is part of the **vibe-guard** family of runtime anti-pattern scanners:

- [java-vibe-guard](https://github.com/jouninno/java-vibe-guard) — Spring Boot / async Java (blocking Kafka, @Transactional + Virtual Threads)
- **python-vibe-guard** — FastAPI / asyncio (this project)

---

## License

MIT
