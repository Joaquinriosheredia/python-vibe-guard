# python-vibe-guard — Validation Results

**Scanner version:** 0.6.0 (19 rules, 115 tests)  
**Scan date:** 2026-06-20  
**Command:** `python -m pyvibe <repo> --json`

---

## Massive scan — 100 repos

Automated scan via `validation/run_massive_scan.py --target 100`. GitHub search queries: `topic:fastapi`, `topic:aiohttp`, `topic:asyncio`, `topic:celery`, `topic:django`, + in:description keywords, all `stars:>100 pushed:>2025-06-20`. Repos sorted by stars, deduplicated, reference set excluded.

| Metric | Value |
|--------|-------|
| Repos scanned | 100 |
| .py files | 64,335 |
| Total violations | 3,639 |
| Failed clones | 0 |
| Failed scans | 0 |

Machine-readable data: [`aggregate.json`](aggregate.json)

### Rule prevalence across 100 repos — all 19 rules

| Rule | Total hits | Repos affected | % of repos |
|------|-----------|----------------|-----------|
| PYVIBE-017 `except Exception: pass` | 999 | 57 | **57%** |
| PYVIBE-013 `gather()` no return_exceptions | 766 | 47 | **47%** |
| PYVIBE-019 retry loop no backoff | 408 | 43 | **43%** |
| PYVIBE-009 `open()` in async def | 178 | 33 | **33%** |
| PYVIBE-005 `@task` no time_limit | 882 | 15 | 15% |
| PYVIBE-001 `time.sleep` in async | 55 | 16 | 16% |
| PYVIBE-012 orphaned `create_task()` | 58 | 13 | 13% |
| PYVIBE-008 `sqlite3` in async def | 121 | 10 | 10% |
| PYVIBE-006 ContextVar no reset | 19 | 10 | 10% |
| PYVIBE-018 `while True` no await | 36 | 10 | 10% |
| PYVIBE-004 `threading.Lock` in async | 60 | 5 | 5% |
| PYVIBE-014 orphaned `ensure_future()` | 16 | 8 | 8% |
| PYVIBE-007 `subprocess` in async | 16 | 6 | 6% |
| PYVIBE-002 `requests.*` in async | 5 | 3 | 3% |
| PYVIBE-010 `httpx` sync in async | 17 | 2 | 2% |
| PYVIBE-003 `asyncio.run()` in async | 1 | 1 | 1% |
| PYVIBE-015 `loop.run_until_complete()` | 1 | 1 | 1% |
| PYVIBE-016 `httpx.Client()` in async | 1 | 1 | 1% |
| PYVIBE-011 `os.system` in async | **0** | **0** | **0%** |

### PYVIBE-011 and PYVIBE-016 after 100-repo sweep

**PYVIBE-011 (`os.system/popen/waitpid` in async def): 0 hits across 100 repos.**  
This confirms the 50-repo result. The pattern does not appear in any of the 100 scanned codebases. Possible explanations: `os.system` is considered too low-level even for synchronous code, and `subprocess` (PYVIBE-007, 6% of repos) is the preferred API. PYVIBE-011 remains in the ruleset as a safety net — the pattern would be extremely dangerous if it did appear — but it is empirically rare.

**PYVIBE-016 (`httpx.Client()` instantiated in async def): 1 hit in 1 repo (1%).**  
`plastic-labs/honcho` has 1 instance. At 100 repos, the rule has fired — it is not dead code. But its prevalence is low (1%) compared to PYVIBE-010 (`httpx.get/post` sync API, 2%) and PYVIBE-002 (`requests.*`, 3%). The rule targets a subtle pattern (sync client instantiated, not just called) that developers appear to mostly avoid, perhaps because httpx documentation prominently recommends `AsyncClient`.

### Top repos by violation count (100-repo sweep)

| Repo | Stars | .py files | Violations |
|------|-------|-----------|-----------|
| home-assistant/core | 87k | 17,702 | 491 |
| IBM/mcp-context-forge | 3.9k | 1,436 | 390 |
| zhinianboke/xianyu-auto-reply | 5.1k | 442 | 189 |
| chopratejas/headroom | 39k | 895 | 110 |
| coleifer/huey | 6k | 65 | 174 |
| WeblateOrg/weblate | 5.9k | 932 | 81 |
| jumpserver/jumpserver | 30.6k | 1,318 | 100 |
| taskiq-python/taskiq | 2.2k | 165 | 63 |
| inventree/InvenTree | 7.2k | 1,013 | 61 |
| learning-at-home/hivemind | 2.5k | 145 | 67 |

### Key findings from the 100-repo sweep

**PYVIBE-017 is now the most prevalent rule by repos affected (57%).** `except Exception: pass` and bare `except: pass` appear in 57 of 100 codebases. IBM/mcp-context-forge has 238 instances alone. This is a codebase-health indicator more than a performance issue, but bare `except:` (CRITICAL) also catches `KeyboardInterrupt`/`SystemExit` and prevents clean shutdown.

**PYVIBE-019 (retry without backoff) appears in 43% of repos on first scan.** 408 hits across 43 repos makes it immediately the third most prevalent rule by repos affected and second by total hits (408 is more than PYVIBE-009's 178). Top offenders: zhinianboke/xianyu-auto-reply (75 hits), home-assistant/core (73 hits), MODSetter/SurfSense (60 hits). This validates that the pattern is endemic in production async Python.

**PYVIBE-013 (`gather()` no return_exceptions) confirmed at 47% of repos.** 766 hits, same rank as in the 50-repo scan. home-assistant/core has 331 instances; aiortc/aiortc has 54. Pattern is stable and widely distributed.

**PYVIBE-005 (`@task` no time_limit) has the highest raw hit count (882).** Concentrated in celery (352), coleifer/huey (172), WeblateOrg/weblate (79). Each hit is a task that can hang indefinitely on a broker timeout.

**PYVIBE-018 (`while True` no await) reaches 10% of repos.** 36 confirmed blocking loops across 10 repos. home-assistant/core leads with 21; agronholm/anyio has 3 in compatibility shim code.

---

## Reproducible scan — 4 repos (reference set)

These results are fully reproducible from the cloned repos in `validation/repos/`.

| Repo | .py files | Violations |
|------|-----------|-----------|
| [fastapi/fastapi](https://github.com/tiangolo/fastapi) | 1 121 | 5 |
| [celery/celery](https://github.com/celery/celery) | 416 | 363 |
| [aio-libs/aiohttp](https://github.com/aio-libs/aiohttp) | 164 | 29 |
| [encode/httpx](https://github.com/encode/httpx) | 60 | 0 |
| **Total** | **1 761** | **397** |

Machine-readable breakdown: [`breakdown.json`](breakdown.json)

### By rule

| Rule | Total | fastapi | celery | aiohttp | httpx | Notes |
|------|-------|---------|--------|---------|-------|-------|
| PYVIBE-001 | 1 | 0 | 0 | 1 | 0 | `time.sleep` in async test helper |
| PYVIBE-002 | 0 | — | — | — | — | |
| PYVIBE-003 | 0 | — | — | — | — | |
| PYVIBE-004 | 0 | — | — | — | — | |
| PYVIBE-005 | 352 | 0 | 352 | 0 | 0 | Internal tasks without `soft_time_limit` / `time_limit` |
| PYVIBE-006 | 2 | 0 | 0 | 2 | 0 | `ContextVar.set()` without cleanup |
| PYVIBE-007 | 0 | — | — | — | — | |
| PYVIBE-008 | 0 | — | — | — | — | |
| PYVIBE-009 | 4 | 0 | 0 | 4 | 0 | `open()` in async handlers in `examples/` |
| PYVIBE-010 | 0 | — | — | — | — | |
| PYVIBE-011 | 0 | — | — | — | — | |
| PYVIBE-012 | 0 | — | — | — | — | |
| PYVIBE-013 | 20 | 0 | 0 | 20 | 0 | `gather()` without `return_exceptions`; WARNING in test files |
| PYVIBE-014 | 0 | — | — | — | — | Targets application code, not framework internals |
| PYVIBE-015 | 0 | — | — | — | — | Targets application code, not framework internals |
| PYVIBE-016 | 0 | — | — | — | — | Targets application code, not framework internals |
| PYVIBE-017 | 18 | 5 | 11 | 2 | 0 | `except Exception: pass`; see FP analysis below |
| PYVIBE-018 | 0 | 0 | 0 | 0 | 0 | FP fixed: async generators now excluded |

---

## Key findings

### PYVIBE-005 — Celery tasks without time limits (352 hits)

`celery/celery` contains 352 task definitions across its internal modules without `soft_time_limit` or `time_limit`. This is the highest-signal finding: every task that makes an external call is vulnerable to hanging indefinitely if the remote system stops responding.

```python
# celery/app/builtins.py
@app.task
def backend_cleanup():       # ← no time_limit — hangs if backend is unreachable
    ...

@app.task
def accumulate(it, fun):     # ← same
    ...
```

### PYVIBE-009 — open() in aiohttp examples (4 hits)

The official aiohttp examples include `open()` calls inside async WebSocket handlers. These block the event loop on every file read and would serialize all concurrent connections in production.

```python
# aiohttp/examples/web_ws.py
async def websocket_handler(request):
    with open("log.txt", "a") as f:   # ← blocks event loop
        f.write(...)
```

### PYVIBE-013 — gather() without return_exceptions (20 hits, aiohttp)

20 `asyncio.gather()` calls without `return_exceptions=True`. pyvibe automatically downgrades this to WARNING in test files (files matching `test_*.py`, `*_test.py`, or under `tests/`). In production async handlers it remains CRITICAL.

---

## False positives observed (v0.5.0)

### PYVIBE-018 — async generator false positive (FIXED)

**Previously a false positive; fixed in this release.** PYVIBE-018 was firing on `while True: yield` inside async generator functions. These are NOT blocked loops: each `yield` suspends the generator and the caller's `await __anext__()` is a real event loop checkpoint.

```python
# fastapi/tests/test_stream_cancellation.py:28  ← was a FP, now correctly excluded
@app.get("/stream-raw", response_class=StreamingResponse)
async def stream_raw() -> AsyncIterable[str]:
    i = 0
    while True:
        yield f"item {i}\n"   # yield IS a suspension point in async generators
        i += 1
```

**Fix applied:** `_has_yield_in_body()` helper detects `ast.Yield`/`ast.YieldFrom` in the function body (not crossing nested function scopes). If the enclosing `async def` contains a `yield`, it is treated as an async generator and excluded from PYVIBE-018. FastAPI now shows 0 PYVIBE-018 hits.

### PYVIBE-017 — except Exception: pass in test code (FastAPI: 5 hits, mixed)

**Partial false positive.** FastAPI's test suite uses `except Exception: pass` deliberately — it captures exceptions via middleware and ignores the client-side raise:

```python
# fastapi/tests/test_validation_error_context.py:91
def test_request_validation_error_includes_endpoint_context():
    captured_exception.exception = None
    try:
        client.get("/users/invalid")
    except Exception:
        pass    # ← intentional; exception captured in middleware, not here
    assert captured_exception.exception is not None
```

The other PYVIBE-017 hits in celery and aiohttp are genuine anti-patterns (e.g., swallowing `os.sysconf` errors silently). Severity is WARNING (not CRITICAL) for `except Exception` vs CRITICAL for bare `except:`.

**Mitigation available:** Extend `_is_test_file()` logic to downgrade PYVIBE-017 from WARNING to INFO in test files, consistent with PYVIBE-013 treatment. Not yet implemented.

---

## Rules with zero hits across all 4 repos

PYVIBE-002–004, 007–008, 010–012, 014–016 produced zero hits. PYVIBE-014/015/016 target application code patterns (orphaned futures, `run_until_complete` inside async, sync httpx client) — these repos are the frameworks themselves and don't exhibit these patterns. PYVIBE-002–004, 007–008, 010–012 fire on patterns that these mature libraries have already eliminated from their codebases.
