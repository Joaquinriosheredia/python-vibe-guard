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

Twenty patterns that AI models generate repeatedly, that pass all static checks, and that silently destroy async performance under real load:

### A. Event Loop Blocking

Synchronous calls inside `async def` — each stalls the event loop for its entire duration, serializing all concurrent requests.

| Rule | Pattern | Gate | Runtime effect |
|------|---------|------|----------------|
| PYVIBE-001 | `time.sleep()` inside `async def` | `async def` | Freezes entire event loop for sleep duration |
| PYVIBE-002 | `requests.*` inside `async def` | `async def` | Blocks OS thread, serializes all concurrent I/O |
| PYVIBE-007 | `subprocess.run/call/check_output/Popen` inside `async def` | `async def` | Blocks OS thread for entire subprocess duration |
| PYVIBE-008 | `sqlite3.connect()` inside `async def` | `async def` | Synchronous file I/O blocks the event loop |
| PYVIBE-009 | `open()` builtin inside `async def` | `async def` | Synchronous file I/O blocks the event loop |
| PYVIBE-010 | `httpx.get/post/put/…` inside `async def` | `async def` | httpx sync API blocks OS thread for full HTTP round-trip |
| PYVIBE-011 | `os.system/popen/waitpid` inside `async def` | `async def` | Blocking OS calls with no direct async equivalent |
| PYVIBE-016 | `httpx.Client()` instantiated inside `async def` | `async def` | Sync client blocks OS thread per request; `httpx.AsyncClient()` is excluded |

### B. Async Lifecycle Misuse

Incorrect use of asyncio primitives that raise `RuntimeError` at runtime or silently discard tasks mid-execution.

| Rule | Pattern | Gate | Runtime effect |
|------|---------|------|----------------|
| PYVIBE-003 | `asyncio.run()` inside `async def` | `async def` | `RuntimeError: This event loop is already running` |
| PYVIBE-012 | `asyncio.create_task()` with discarded return value | `async def` | Task GC'd mid-execution; exceptions silently swallowed |
| PYVIBE-013 | `asyncio.gather()` without `return_exceptions=True` | `async def` | First exception leaks remaining tasks; no per-task error handling |
| PYVIBE-014 | `asyncio.ensure_future()` with discarded return value | `async def` | Same GC hazard as PYVIBE-012; pre-3.7 API still common in older codebases |
| PYVIBE-015 | `loop.run_until_complete()` inside `async def` | `async def` | `RuntimeError: This event loop is already running` |

### C. Concurrency & State Hazards

Patterns that introduce data races, swallowed errors, or runaway loops under concurrent async load.

| Rule | Pattern | Gate | Runtime effect |
|------|---------|------|----------------|
| PYVIBE-004 | `threading.Lock/RLock/…` inside `async def` | `async def` | Blocks event loop under contention |
| PYVIBE-005 | `@app.task` / `@shared_task` without `soft_time_limit` or `time_limit` | decorator | Worker hangs forever if external call never returns |
| PYVIBE-006 | `ContextVar.set()` inside `async def` without `try/finally reset()` | `async def` | Context leaks into sibling async tasks |
| PYVIBE-017 | `except Exception: pass` / bare `except: pass` (empty body) | any | Swallows all errors silently; bare except also catches `KeyboardInterrupt`/`SystemExit` |
| PYVIBE-018 | `while True:` inside `async def` with no `await` in body | `async def` | Event loop blocked indefinitely; CPU hits 100% |
| PYVIBE-019 | retry `for`/`while` loop in `async def` with no backoff in `except` | `async def` | Tight retry loop on failure: thousands of failed requests/sec, cascading failures |
| PYVIBE-020 | `put_nowait()` without `asyncio.QueueFull` handler | any | `QueueFull` propagates unhandled; item is silently lost on bounded queues |

**Severity notes:**
- PYVIBE-005: `CRITICAL` — checks per-task decorator arguments only. **If your project sets a global `task_time_limit` via `app.conf.task_time_limit`, `app.conf.update(...)`, or in `celeryconfig.py` / `settings.py`, tasks already covered by that global limit will still be flagged.** Add per-task limits (self-documenting, immune to config drift) or suppress with `# noqa: PYVIBE-005`.
- PYVIBE-009: `CRITICAL` in production files; automatically downgraded to `WARNING` in test files (`test_*.py`, `*_test.py`, `tests/`). **Context matters:** `open()` in a hot-path request handler blocks all concurrent coroutines (CRITICAL); `open()` in a startup/lifespan function runs before requests are served and has zero practical impact. The rule cannot distinguish these contexts via AST — if you use `open()` in an `async def` lifespan or one-time initializer, the idiomatic fix is to use plain `def` instead (FastAPI's own docs do this), which avoids the flag entirely.
- PYVIBE-017: bare `except` → `CRITICAL` (catches `KeyboardInterrupt`/`SystemExit`); `except Exception` with empty body → `WARNING`. Specific exceptions (`except ValueError: pass`) are not flagged.
- PYVIBE-013 in test files: automatically downgraded to `WARNING` in files matching `test_*.py`, `*_test.py`, or paths under `tests/` — exceptions should propagate for assertions in test code.
- PYVIBE-019: `WARNING` — flags `except` that ends with `continue` or is solely `pass` with no sleep/backoff call. Suppressed when an escalation pattern (`if … : raise/break`) is present.
- PYVIBE-020: `WARNING` — fires in any function context (sync and async). Suppressed when the `put_nowait()` is inside a `try` whose handlers include `asyncio.QueueFull`, `QueueFull`, bare `except`, or `Exception`.

---

## Validation

### 100-repo sweep (automated, v0.7.0)

Automated scan of 100 GitHub repos (`stars:>100`, updated last year, async Python keywords). Script: [`validation/run_massive_scan.py`](validation/run_massive_scan.py).

| Metric | Value |
|--------|-------|
| Repos scanned | 100 |
| .py files | 64,335 |
| Total violations | 3,639 |

**Rule prevalence (top 10):**

| Rule | Hits | Repos affected | % of repos |
|------|------|----------------|-----------|
| PYVIBE-017 `except Exception: pass` | 999 | 57 | **57%** |
| PYVIBE-013 `gather()` no return_exceptions | 766 | 47 | **47%** |
| PYVIBE-019 retry loop no backoff | 408 | 43 | **43%** |
| PYVIBE-009 `open()` in async def | 178 | 33 | **33%** |
| PYVIBE-005 `@task` no time_limit | 882 | 15 | 15% |
| PYVIBE-001 `time.sleep` in async | 55 | 16 | 16% |
| PYVIBE-012 orphaned `create_task()` | 58 | 13 | 13% |
| PYVIBE-008 `sqlite3` in async def | 121 | 10 | 10% |
| PYVIBE-018 `while True` no await | 36 | 10 | 10% |
| PYVIBE-006 ContextVar no reset | 19 | 10 | 10% |

Full data: [`validation/aggregate.json`](validation/aggregate.json) · [`validation/massive-results.md`](validation/massive-results.md)

### Reference scan — 4 repos (reproducible)

| Repo | .py files | Violations |
|------|-----------|-----------|
| [fastapi/fastapi](https://github.com/tiangolo/fastapi) | 1 121 | 5 |
| [celery/celery](https://github.com/celery/celery) | 416 | 363 |
| [aio-libs/aiohttp](https://github.com/aio-libs/aiohttp) | 164 | 29 |
| [encode/httpx](https://github.com/encode/httpx) | 60 | 0 |
| **Total** | **1 761** | **397** |

Raw data: [`validation/breakdown.json`](validation/breakdown.json)

**Notable findings:**

- **home-assistant/core** — 418 violations across 17,702 files; 331 PYVIBE-013, 21 PYVIBE-018.
- **Celery** — 352 tasks without `time_limit`; workers can hang indefinitely on broker timeouts.
- **aiortc, anyio, uvicorn** — `while True` loops without `await` in production async I/O code (PYVIBE-018, 29 confirmed real hits after async-generator FP fix).
- **aiohttp examples** — `open()` in async WebSocket handlers; synchronous I/O in production-facing code.

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

# SARIF 2.1.0 output for GitHub Code Scanning (writes results.sarif)
python -m pyvibe src/ --sarif
python -m pyvibe src/ --sarif --sarif-output custom-path.sarif

# Exclude directories (adds to built-in defaults: venv, .venv, __pycache__, …)
python -m pyvibe src/ --exclude tests

# Show the research evidence behind a rule (accuracy, false positives, sources)
python -m pyvibe explain PYVIBE-002

# Baseline mode: suppress pre-existing findings, only fail on new ones
python -m pyvibe baseline create src/     # snapshot current findings
python -m pyvibe src/ --baseline          # only reports findings NOT in the baseline

# Show suppressed findings (inline comments + pyvibe.toml) alongside the report
python -m pyvibe src/ --verbose

# Exit code: 0 = clean, 1 = violations found, 2 = path error
```

### Example output

```
  python-vibe-guard
  ─────────────────────────────────────────────

  demo/bad_async.py

  [CRITICAL] [PYVIBE-001] — line 27
     Function : process_order()
     Problem  : time.sleep() blocks the entire event loop
     Fix      : Use `await asyncio.sleep(n)` instead
     Suggested fix:
         await asyncio.sleep(2)

  [CRITICAL] [PYVIBE-002] — line 33
     Function : fetch_user()
     Problem  : requests.get() is synchronous — blocks the event loop
     Fix      : Use `async with httpx.AsyncClient() as c: await c.get(url)`
     Suggested fix:
         async with httpx.AsyncClient() as client:
             response = await client.get(f"https://api.example.com/users/{user_id}")

  [CRITICAL] [PYVIBE-003] — line 39
     Function : orchestrate()
     Problem  : asyncio.run() inside async def raises RuntimeError at runtime
     Fix      : Use `await coroutine()` directly — asyncio.run() is for sync entrypoints only
     Suggested fix:
         await process_order(42)

  [CRITICAL] [PYVIBE-004] — line 45
     Function : update_counter()
     Problem  : threading.Lock() blocks the event loop under contention
     Fix      : Use `asyncio.Lock()` with `async with lock:` instead

  ─────────────────────────────────────────────
  4 reported · 0 suppressed
```

`Suggested fix:` blocks are generated from the real code on the flagged line — they are
printed to the terminal / JSON output only and are never written back to your files.
Currently available for PYVIBE-001, 002, 003, 007, and 008.

### `pyvibe explain`

Every rule's accuracy claims come from `research/accepted/PYVIBE-XXX.md` — a per-rule
evidence file with repo-sweep data, an evidence-level grade, and a hit-by-hit precision
audit. `pyvibe explain` surfaces that in the terminal instead of making you go dig for it:

```bash
python -m pyvibe explain PYVIBE-002
```

```
  PYVIBE-002 — requests.* inside async def
  ───────────────────────────────────────────────

  Problema:
    requests.* inside async def

  Por qué ocurre:
    `requests` is a synchronous HTTP library. Calling it inside an async function
    blocks the OS thread running the event loop. Under concurrent load this
    serialises all I/O and eliminates any benefit of async.

  Visto en: 4.0% (10/250 repos, sweep-250 dataset)
  Nivel de evidencia: B
  Precisión auditada: ~83%
  Falsos positivos conocidos: EXECUTOR_WRAPPER; INNER_SYNC_FUNCTION_EXECUTOR; ...

  Fix sugerido:
    use `httpx.AsyncClient` or `aiohttp.ClientSession` with await.

  Full report: research/accepted/PYVIBE-002.md
```

If a rule has no evidence file, it prints a clear `No evidence file found for PYVIBE-XXX`
and exits non-zero — it never invents data.

### Baseline mode

Adopting python-vibe-guard on an existing codebase usually means hundreds of pre-existing
findings you can't fix before CI needs to go green. Baseline mode snapshots the current
findings once, then only fails on genuinely **new** ones:

```bash
# Snapshot every current finding into .pyvibe-baseline.json
python -m pyvibe baseline create src/

# Refuses to run if a baseline already exists — use `update` to overwrite it
python -m pyvibe baseline update src/

# Full scan, but only reports findings NOT already in the baseline
python -m pyvibe src/ --baseline
python -m pyvibe src/ --baseline --json
python -m pyvibe src/ --baseline --sarif

# `pyvibe scan` is an equivalent, explicit subcommand form of the same flags
python -m pyvibe scan src/ --baseline
```

A finding is considered "already known" on an exact match of `(file path, rule ID, line
number)`. Anything that doesn't match — a new violation, or an existing one that moved to
a different line — is reported and fails the scan (exit code `1`); an unchanged baseline
produces exit code `0`.

`.pyvibe-baseline.json` is a plain JSON file — whether to commit it or add it to
`.gitignore` is up to your team. Commit it if you want the accepted-debt snapshot shared
and reviewed like any other file; gitignore it if each contributor/CI run should
regenerate its own baseline instead.

### Suppressing findings

For one-off exceptions, use an inline comment right in the source:

```python
# pyvibe: ignore PYVIBE-008
conn = sqlite3.connect(...)              # suppressed — standalone comment targets the next line

conn = sqlite3.connect(...)  # pyvibe: ignore PYVIBE-008   # suppressed — trailing comment targets its own line

time.sleep(n)  # pyvibe: ignore PYVIBE-001, PYVIBE-003     # multiple rules, comma-separated

# pyvibe: ignore-next-line PYVIBE-008
conn = sqlite3.connect(...)              # suppressed — always targets the next line
```

`pyvibe:` is case-insensitive. A directive with no recognizable `PYVIBE-XXX` id is ignored
(treated as a regular comment).

For project-wide rules, add a `pyvibe.toml` next to your code (python-vibe-guard walks up
from the scan target to find it, same convention as `pyproject.toml`):

```toml
[tool.pyvibe]
ignore = ["PYVIBE-019"]
exclude = ["tests/**", "examples/**", "docs/**"]

[tool.pyvibe.severity]
PYVIBE-008 = "warning"
```

- `ignore`: rule IDs suppressed everywhere, project-wide.
- `exclude`: glob patterns (relative to the `pyvibe.toml` directory) for files/directories
  to skip entirely.
- `[tool.pyvibe.severity]`: per-rule severity override (`"critical"` or `"warning"`),
  applied after the built-in test-file downgrade.

Both mechanisms feed into the same summary line:

```
  4 reported · 2 suppressed
```

Add `--verbose` to see exactly what was suppressed and why:

```
  Suppressed:
    PYVIBE-008 app/db.py:42 (inline)
    PYVIBE-019 legacy.py:81 (config)
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

### GitHub Code Scanning (SARIF)

```yaml
- name: python-vibe-guard scan
  run: |
    pip install python-vibe-guard
    python -m pyvibe src/ --sarif
  continue-on-error: true  # let the upload step surface results in the PR instead

- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: results.sarif
```

Findings then show up as annotations on the PR diff and in the repo's Security tab,
each linking back to its `research/accepted/PYVIBE-XXX.md` evidence file via `helpUri`.

---

## GitHub Action

- name: python-vibe-guard
  uses: joaquinriosheredia/python-vibe-guard-action@v1
  with:
    path: src/

Violations appear directly in GitHub Security tab (SARIF).
Link: https://github.com/Joaquinriosheredia/python-vibe-guard-action

---

## Pre-commit integration

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/Joaquinriosheredia/python-vibe-guard
    rev: v0.7.0
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
- **Gate on `async def`** — most rules check `_current_async_func` before firing; PYVIBE-017 (silent except) fires in any function context
- **No import resolution** — works on any Python file without installing its dependencies
- **Test-aware severity** — PYVIBE-013 is automatically downgraded to WARNING in test files

---

## Run the demo

```bash
python -m pyvibe demo/bad_async.py
```

Expected: 20 findings (17 CRITICAL + 3 WARNING for PYVIBE-017 `except Exception`, PYVIBE-019 retry without backoff, and PYVIBE-020 `put_nowait` without handler), one per rule. `demo/bad_async.py` also contains a sync function that mirrors the async-specific patterns — those produce zero findings.

---

## Run the tests

```bash
python -m pytest tests/ -v
# or
python tests/test_rules.py
```

309 tests: true positives + false-positive guards for every rule, plus SARIF output, `pyvibe explain`, `pyvibe review`, baseline mode, and suppressions (inline comments + pyvibe.toml) coverage.

---

## Ecosystem

This project is part of the **vibe-guard** family of runtime anti-pattern scanners:

- [java-vibe-guard](https://github.com/jouninno/java-vibe-guard) — Spring Boot / async Java (blocking Kafka, @Transactional + Virtual Threads)
- **python-vibe-guard** — FastAPI / asyncio (this project)

---

## License

MIT
