# python-vibe-guard — Validation Results

**Scanner version:** 0.5.0 (18 rules, 104 tests)  
**Scan date:** 2026-06-19  
**Command:** `python -m pyvibe <repo> --json`

---

## Reproducible scan — 4 repos

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
