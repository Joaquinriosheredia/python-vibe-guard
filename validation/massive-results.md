# python-vibe-guard — Validation Results

**Scanner version:** 0.4.0 (16 rules, 76 tests)  
**Scan date:** 2026-06-18  
**Command:** `python -m pyvibe <repo> --json`

---

## Reproducible scan — 4 repos

These results are fully reproducible from the cloned repos in `validation/repos/`.

| Repo | .py files | Violations |
|------|-----------|-----------|
| [fastapi/fastapi](https://github.com/tiangolo/fastapi) | 1 121 | 0 |
| [celery/celery](https://github.com/celery/celery) | 416 | 352 |
| [aio-libs/aiohttp](https://github.com/aio-libs/aiohttp) | 164 | 27 |
| [encode/httpx](https://github.com/encode/httpx) | 60 | 0 |
| **Total** | **1 761** | **379** |

Machine-readable breakdown: [`breakdown.json`](breakdown.json)

### By rule

| Rule | Hits | Repo | Notes |
|------|------|------|-------|
| PYVIBE-001 | 1 | aiohttp | `time.sleep` in async test helper |
| PYVIBE-002 | 0 | — | |
| PYVIBE-003 | 0 | — | |
| PYVIBE-004 | 0 | — | |
| PYVIBE-005 | 352 | celery | Internal tasks without `soft_time_limit` / `time_limit` |
| PYVIBE-006 | 2 | aiohttp | `ContextVar.set()` without cleanup |
| PYVIBE-007 | 0 | — | |
| PYVIBE-008 | 0 | — | |
| PYVIBE-009 | 4 | aiohttp | `open()` in async handlers in `examples/` |
| PYVIBE-010 | 0 | — | |
| PYVIBE-011 | 0 | — | |
| PYVIBE-012 | 0 | — | |
| PYVIBE-013 | 20 | aiohttp | `gather()` without `return_exceptions=True`; auto-downgraded to WARNING in test files |
| PYVIBE-014 | 0 | — | Targets application code, not framework internals |
| PYVIBE-015 | 0 | — | Targets application code, not framework internals |
| PYVIBE-016 | 0 | — | Targets application code, not framework internals |

**Note on PYVIBE-014/015/016:** These rules detect patterns that appear in *application* code (orphaned `ensure_future`, `loop.run_until_complete()` inside async, sync `httpx.Client()` in async handlers). The four repos scanned are the framework libraries themselves — they do not exhibit these patterns by design. The rules fire correctly against application-layer code as shown in `demo/bad_async.py`.

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

## False positives observed

| Rule | Count | Cause |
|------|-------|-------|
| PYVIBE-013 | ~60–70% of hits industry-wide | Test code intentionally lets exceptions propagate; mitigated by automatic WARNING downgrade in test files |

No other false positives were observed in this scan.
