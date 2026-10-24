# python-vibe-guard

[![tests](https://github.com/Joaquinriosheredia/python-vibe-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/Joaquinriosheredia/python-vibe-guard/actions/workflows/ci.yml)

## An illustrative scenario

> Illustrative only: not a real incident. None of the figures in this section are measurements.

A FastAPI service that handled 50 concurrent requests in staging started timing out in production at 200 rps. The team spent two days adding replicas, tweaking Gunicorn workers, and profiling CPU — nothing helped. The p99 latency was 8 seconds for an endpoint that should take 80ms.

Root cause: one engineer had asked an AI assistant to "add a retry with backoff" to an async handler. The AI generated `time.sleep(2)` inside the `async def`. In staging with a handful of requests it was invisible. In production it froze the entire event loop for 2 seconds per request, serializing all 200 concurrent calls through a single bottleneck.

The code passed every unit test. It passed the integration tests. It shipped to production in a Friday deploy.

**python-vibe-guard catches this in CI before it reaches staging.**

---

## What it detects

Twenty code patterns that pass static checks and unit tests but can block or break async code under real load. The rules look for code patterns, not authorship: they do not tell AI-generated code from human-written code.

### A. Event Loop Blocking

Synchronous calls inside `async def` — each stalls the event loop for its entire duration, serializing all concurrent requests.

| Rule | Pattern | Gate | Runtime effect |
|------|---------|------|----------------|
| PYVIBE-001 | `time.sleep()` inside `async def` | `async def` | Freezes entire event loop for sleep duration |
| PYVIBE-002 | `requests.*` inside `async def` | `async def` | Blocks OS thread, serializes all concurrent I/O |
| PYVIBE-007 | `subprocess.run/call/check_output` inside `async def`; `Popen` only when waited (`.wait()`/`.communicate()`) | `async def` | Blocks OS thread for entire subprocess duration |
| PYVIBE-008 | `sqlite3.connect()` inside `async def` | `async def` | Synchronous file I/O blocks the event loop |
| PYVIBE-009 | `open()` builtin inside `async def` | `async def` | Synchronous file I/O blocks the event loop |
| PYVIBE-010 | `httpx.get/post/put/…` inside `async def` | `async def` | httpx sync API blocks OS thread for full HTTP round-trip |
| PYVIBE-011 | `os.system/popen/waitpid` inside `async def` (`waitpid` with `WNOHANG` excluded) | `async def` | Blocks the event loop until the child process finishes |
| PYVIBE-016 | `httpx.Client()` instantiated inside `async def` | `async def` | Sync client blocks OS thread per request; `httpx.AsyncClient()` is excluded |

### B. Async Lifecycle Misuse

Incorrect use of asyncio primitives that raise `RuntimeError` at runtime or silently discard tasks mid-execution.

| Rule | Pattern | Gate | Runtime effect |
|------|---------|------|----------------|
| PYVIBE-003 | `asyncio.run()` inside `async def` | `async def` | `RuntimeError: This event loop is already running` |
| PYVIBE-012 | `asyncio.create_task()` with discarded return value | `async def` | The loop keeps only a weak reference: the task can be garbage-collected before it finishes, and its exception is never retrieved |
| PYVIBE-013 | `asyncio.gather()` without `return_exceptions=True` (WARNING) | `async def` | The first exception is re-raised; the other awaitables keep running, and their results and later exceptions are not observed by that call |
| PYVIBE-014 | `asyncio.ensure_future()` with discarded return value | `async def` | Same GC hazard as PYVIBE-012; pre-3.7 API still common in older codebases |
| PYVIBE-015 | `loop.run_until_complete()` inside `async def` | `async def` | `RuntimeError: This event loop is already running` |

### C. Concurrency & State Hazards

Patterns that introduce data races, swallowed errors, or runaway loops under concurrent async load.

| Rule | Pattern | Gate | Runtime effect |
|------|---------|------|----------------|
| PYVIBE-004 | `threading.Lock/RLock/…` inside `async def` | `async def` | Blocks event loop under contention |
| PYVIBE-005 | `@app.task` / `@shared_task` without `soft_time_limit` or `time_limit` (WARNING) | decorator | If the wrapped work never returns, it holds a worker until a global limit (if any) stops it |
| PYVIBE-006 | `ContextVar.set()` inside `async def` without `try/finally reset()` | `async def` | Context leaks into sibling async tasks |
| PYVIBE-017 | bare `except: pass` / `except BaseException: pass` around an `await` (empty body) | async | Swallows `CancelledError`/`KeyboardInterrupt`/`SystemExit`, breaking cancellation and clean shutdown. `except Exception: pass` is opt-in (`--report-broad-except`) |
| PYVIBE-018 | `while True:` inside `async def` with no `await` in body | `async def` | Holds the event loop until the loop exits; no other coroutine runs meanwhile |
| PYVIBE-019 | retry `for`/`while` loop in `async def` with no backoff in `except` | `async def` | Tight retry loop on failure: thousands of failed requests/sec, cascading failures |
| PYVIBE-020 | `put_nowait()` without `asyncio.QueueFull` handler | any | `QueueFull` propagates unhandled; item is silently lost on bounded queues |

**Severity notes:**
- PYVIBE-005: `WARNING` since test-corpus-2 (0 TP of 13; vibe-guard-evaluation `test-corpus-2/FP-ANALYSIS.md`). A receiver imported from a module counts as Celery's only if that module's path contains `celery` or the file imports `celery`; a file that imports Procrastinate, Huey, Dramatiq, taskiq, arq, RQ, SAQ or Faust (and not `celery`) is not reported. Checks per-task decorator arguments only. **If your project sets a global `task_time_limit` via `app.conf.task_time_limit`, `app.conf.update(...)`, or in `celeryconfig.py` / `settings.py`, tasks already covered by that global limit will still be flagged.** Add per-task limits (self-documenting, immune to config drift) or suppress with `# pyvibe: ignore PYVIBE-005` on the task's `def` line.
- PYVIBE-009: `CRITICAL` in production files; automatically downgraded to `WARNING` in test and non-production files (see *Path-based severity* below). **Context matters:** `open()` in a hot-path request handler blocks all concurrent coroutines (CRITICAL); `open()` in a startup/lifespan function runs before requests are served and has zero practical impact. The rule cannot distinguish these contexts via AST — if you use `open()` in an `async def` lifespan or one-time initializer, the idiomatic fix is to use plain `def` instead (FastAPI's own docs do this), which avoids the flag entirely.
- PYVIBE-017: bare `except` / `except BaseException` with an empty body → `CRITICAL`, only in an async function and only when the `try` body contains an `await` (or `async for`/`async with`), where a cancellation can arrive. `except Exception` with an empty body → `WARNING`, only with `report_broad_except = true` / `--report-broad-except`. Specific exceptions (`except ValueError: pass`) are not flagged.
- PYVIBE-013: `WARNING` since test-corpus-2 (2 TP of 10: most gathered awaitables contained their exceptions in another module). (0.14.0) Not reported when every gathered awaitable resolves, in the same module, to a function that contains its exceptions — the awaited I/O is guarded by a `try`/`except` that returns (following nested defs, `self`/`cls` methods and module functions; recursion is assumed contained), or `asyncio.sleep()`. Parameters, attributes, imported or decorated functions and anything not understood are still reported. **Known false negative:** a synchronous statement that raises *before* the `try` (e.g. a validation) is not detected.
- PYVIBE-009 (0.13.0): `WARNING` instead of `CRITICAL` when the file's I/O is delegated to a thread — `with open(...) as f:` whose handle is only passed, uncalled, to `asyncio.to_thread()` / `run_in_executor()` (`await asyncio.to_thread(f.read, n)`): only `open()`/close run on the loop.
- **Start-up (blocking rules):** a `CRITICAL` of PYVIBE-001/002/004/007/008/009/010/011/016/018 directly inside the module-level `async def` that the module passes to `asyncio.run(...)` (outside any `async def`) is downgraded to `WARNING`, never silenced, with the reason in the message: it is the program's top-level coroutine, typically start-up.
- PYVIBE-018: a bounded "first free name" search (a counter incremented until `candidate not in <container>` returns or breaks, every exit being such a branch) is not reported.
- PYVIBE-017: an empty handler nested in a handler of the same function that ends with a bare `raise` is not reported: the exception being handled is re-raised anyway.
- **Path-based severity (0.14.0, all rules):** a `CRITICAL` is downgraded to `WARNING` (never silenced) in a test filename (`test_*.py`, `*_test.py`, `conftest.py`) or under a `tests/`, `test/`, `scripts/`, `wip/`, `spike/` or `examples/` directory. Only the scanned root's own name and the segments inside it count (for a single file, its immediate directory as passed), never the directories above it.
- PYVIBE-007 (0.14.0): **known false negative** — a `Popen` whose pipe is read synchronously (`p.stdout.read()`) without `.wait()`/`.communicate()` blocks but is not reported.
- PYVIBE-019: `WARNING` — flags `except` that ends with `continue` or is solely `pass` with no sleep/backoff call. Suppressed when an escalation pattern (`if … : raise/break`) is present.
- PYVIBE-020: `WARNING` — fires in any function context (sync and async). Suppressed when the `put_nowait()` is inside a `try` whose handlers include `asyncio.QueueFull`, `QueueFull`, bare `except`, or `Exception`.

---

## Validation

### Pre-registered precision measurement

The only pre-registered measurement so far is **test-corpus-1** (2026-10-14, scanned with python-vibe-guard 0.13.0): precision of CRITICAL findings **0.7067** (Wilson 95 % 0.6294–0.7736, n = 150 reviewed, 149 of them Python), below its 90 % target. Its own report says the figure is probably optimistic: 129 of the 150 verdicts come from an AI first review that was not independently checked. The 0.14.0 changes (PYVIBE-007, PYVIBE-013, PYVIBE-017, path-based severity) were designed after looking at that corpus, so it is now a development set and does not measure 0.14.0. Source: [vibe-guard-evaluation `test-corpus-1/RESULTS.md`](https://github.com/Joaquinriosheredia/vibe-guard-evaluation/blob/a80d9ab/test-corpus-1/RESULTS.md).

### 100-repo sweep (June 2026, historical raw hits)

Automated scan of 100 GitHub repos (`stars:>100`, `pushed:>2025-06-20`, async-Python topics and keywords). These are **raw hit counts, not audited findings**, from the June 2026 scanner (0.6.0 according to `aggregate.json`; `massive-results.md` says 0.7.0). Rules have changed since, so 0.14.0 would give different numbers: for example, the PYVIBE-017 row counts `except Exception: pass`, which 0.14.0 no longer reports by default.

| Metric | Value |
|--------|-------|
| Repos scanned | 100 |
| .py files | 64,335 |
| Total hits | 3,639 |

**Rule prevalence (top 10, raw hits):**

| Rule | Hits | Repos affected | % of repos |
|------|------|----------------|-----------|
| PYVIBE-017 `except Exception: pass` (opt-in since 0.14.0) | 999 | 57 | 57% |
| PYVIBE-013 `gather()` no return_exceptions | 766 | 47 | 47% |
| PYVIBE-019 retry loop no backoff | 408 | 43 | 43% |
| PYVIBE-009 `open()` in async def | 178 | 33 | 33% |
| PYVIBE-005 `@task` no time_limit | 882 | 15 | 15% |
| PYVIBE-001 `time.sleep` in async | 55 | 16 | 16% |
| PYVIBE-012 orphaned `create_task()` | 58 | 13 | 13% |
| PYVIBE-008 `sqlite3` in async def | 121 | 10 | 10% |
| PYVIBE-018 `while True` no await | 36 | 10 | 10% |
| PYVIBE-006 ContextVar no reset | 19 | 10 | 10% |

Data, pinned to the commit that produced it: [`validation/aggregate.json` @ 552a57a](https://github.com/Joaquinriosheredia/python-vibe-guard/blob/552a57a/validation/aggregate.json) · [`validation/massive-results.md` @ 552a57a](https://github.com/Joaquinriosheredia/python-vibe-guard/blob/552a57a/validation/massive-results.md). The current `validation/aggregate.json` holds a later sweep and does not back this table.

Per-rule precision self-audits by the author (small samples, not pre-registered) are in [`research/precision-audit.md`](research/precision-audit.md). Example of context changing the count: of Celery's PYVIBE-005 hits in an early scan, about 9 were in production code (`celery/app/builtins.py`) and the rest in test fixtures and examples ([`validation/results.md`](validation/results.md)).

---

## Installation

```bash
pip install python-vibe-guard
```

Or install from a clone (editable install):

```bash
git clone https://github.com/Joaquinriosheredia/python-vibe-guard.git
cd python-vibe-guard
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

# Audit inline suppressions: justification coverage + orphaned (unused) suppressions
python -m pyvibe audit src/
python -m pyvibe audit src/ --json
python -m pyvibe audit src/ --fail-on-unused --fail-on-unjustified

# Exit code: 0 = clean, 1 = violations found, 2 = path error
```

### Example output (excerpt: the first 4 of the demo's 20 findings)

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

  […16 more findings…]

  ─────────────────────────────────────────────
  20 reported · 0 suppressed
```

`Suggested fix:` blocks are generated from the real code on the flagged line — they are
printed to the terminal / JSON output only and are never written back to your files.
Currently available for PYVIBE-001, 002, 003, 007, and 008.

### `pyvibe explain`

`pyvibe explain` prints a rule's evidence: prevalence and evidence level from
`research/accepted/PYVIBE-XXX.md`, and the audited precision and known false positives from
`research/precision-audit.md`. These precision figures are the author's self-audits on small
samples (for PYVIBE-002, ~83% = 5 TP of 6 hits, after a fix), not pre-registered
measurements; the two files can disagree (`accepted/PYVIBE-002.md` reports 36–38% before
that fix). The pre-registered measurement is under *Validation* above.

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
  Falsos positivos conocidos: EXECUTOR_WRAPPER; INNER_SYNC_FUNCTION_EXECUTOR; VARIABLE_NAME_COLLISION; TEST_SUBJECT

  Fix sugerido:
    use `httpx.AsyncClient` or `aiohttp.ClientSession` with await.

  Full report: https://github.com/Joaquinriosheredia/python-vibe-guard/blob/master/research/accepted/PYVIBE-002.md
```

If a rule has no evidence file, it prints a clear `No evidence file found for PYVIBE-XXX`
and exits non-zero — it never invents data.

### Baseline mode

Adopting python-vibe-guard on an existing codebase usually means hundreds of pre-existing
findings you can't fix before CI needs to go green. Baseline mode snapshots the current
findings once, then only fails on genuinely **new** ones:

```bash
# Snapshot every current finding into .pyvibe-baseline.json
# (refuses to run if a baseline already exists — use `update` to overwrite it)
python -m pyvibe baseline create src/

# Overwrite the existing baseline with the current findings
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

Add an optional justification after `--` — it's free text, stored and shown in `pyvibe audit`:

```python
conn = sqlite3.connect(...)  # pyvibe: ignore PYVIBE-008 -- legacy sqlite wrapper
# pyvibe: ignore-next-line PYVIBE-008 -- startup only
conn = sqlite3.connect(...)
```

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
- `report_broad_except = true`: PYVIBE-017 opt-in, also report `except Exception` with an
  empty body (`WARNING`); same as `--report-broad-except`.
- `exclude`: glob patterns (relative to the `pyvibe.toml` directory) for files/directories
  to skip entirely.
- `[tool.pyvibe.severity]`: per-rule severity override (`"critical"` or `"warning"`),
  applied after the built-in path-based downgrade (see *Path-based severity* above).

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

### `pyvibe audit`

Audits every inline `# pyvibe: ignore` comment in a codebase: how many carry a justification,
and how many are **orphaned** — the rule they name never actually fires on the target line,
usually because the underlying code changed since the suppression was added.

```
$ pyvibe audit src/

Suppressions audit
──────────────────
Total suppressions: 12
With justification: 9 (75%)
Without justification: 3
Unused (no violation found): 2

By rule:
PYVIBE-008   5
PYVIBE-019   4
PYVIBE-003   3

Unused suppressions:
app/legacy.py:41  # pyvibe: ignore PYVIBE-008

Without justification:
models/db.py:88  # pyvibe: ignore PYVIBE-019
```

- `--json` — machine-readable output (`total`, `with_justification`, `without_justification`,
  `unused`, `by_rule`, `unused_suppressions`, `without_justification_suppressions`).
- `--fail-on-unused` — exit `1` if any orphaned suppression is found.
- `--fail-on-unjustified` — exit `1` if any suppression is missing a justification.
- `--max-unused N` — exit `1` if more than `N` orphaned suppressions are found.
- `--exclude DIR` — same directory-exclusion convention as `pyvibe scan`.

With no flags, `pyvibe audit` is purely informational (exit `0`) — the flags above are what
you wire into CI to enforce a justification/cleanup policy over time.

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

```yaml
- name: python-vibe-guard
  uses: joaquinriosheredia/python-vibe-guard-action@v1
  with:
    path: src/
```

Violations appear directly in GitHub Security tab (SARIF).
Link: https://github.com/Joaquinriosheredia/python-vibe-guard-action

---

## Pre-commit integration

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/Joaquinriosheredia/python-vibe-guard
    rev: v0.14.0
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

- **Pure AST** — uses Python's built-in `ast` module; the only runtime dependency is `tomli` on Python < 3.11 (to read `pyvibe.toml`)
- **Each rule is an independent `ast.NodeVisitor`** — easy to add, disable, or extend
- **Gate on `async def`** — most rules check `_current_async_func` before firing; PYVIBE-017 (silent except) fires only in async functions, around an `await`
- **No import resolution** — works on any Python file without installing its dependencies
- **Test-aware severity** — every rule's CRITICAL is downgraded to WARNING in test and non-production paths

---

## Run the demo

```bash
python -m pyvibe demo/bad_async.py
```

Expected: 20 findings (16 CRITICAL + 4 WARNING for PYVIBE-005 Celery without time limit, PYVIBE-013 `gather()` without `return_exceptions`, PYVIBE-019 retry without backoff and PYVIBE-020 `put_nowait` without handler), one per rule. `demo/bad_async.py` also contains a sync function that mirrors the async-specific patterns — those produce zero findings.

---

## Run the tests

```bash
python -m pytest tests/ -v
```

Tests cover true positives + false-positive guards for every rule, plus SARIF output, `pyvibe explain`, `pyvibe review`, baseline mode, suppressions (inline comments + pyvibe.toml), and `pyvibe audit` (justifications + orphan detection) coverage.

---

## Documentation

- [research/public-findings.md](research/public-findings.md) — real findings reported to public open source projects, including confirmed cases and cases where context changed the outcome.

---

## Ecosystem

This project is part of the **vibe-guard** family of runtime anti-pattern scanners:

- [java-vibe-guard](https://github.com/Joaquinriosheredia/java-vibe-guard) — Spring Boot / async Java (blocking Kafka, @Transactional + Virtual Threads)
- **python-vibe-guard** — FastAPI / asyncio (this project)

---

## License

MIT
