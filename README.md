# python-vibe-guard

## The incident

A FastAPI service that handled 50 concurrent requests in staging started timing out in production at 200 rps. The team spent two days adding replicas, tweaking Gunicorn workers, and profiling CPU — nothing helped. The p99 latency was 8 seconds for an endpoint that should take 80ms.

Root cause: one engineer had asked an AI assistant to "add a retry with backoff" to an async handler. The AI generated `time.sleep(2)` inside the `async def`. In staging with a handful of requests it was invisible. In production it froze the entire event loop for 2 seconds per request, serializing all 200 concurrent calls through a single bottleneck.

The code passed every unit test. It passed the integration tests. It shipped to production in a Friday deploy.

**python-vibe-guard catches this in CI before it reaches staging.**

---

## What it detects

Four patterns that AI models generate repeatedly, that pass all static checks, and that silently destroy async performance under real load:

| Rule | Pattern | Runtime effect |
|------|---------|----------------|
| PYVIBE-001 | `time.sleep()` inside `async def` | Freezes entire event loop for sleep duration |
| PYVIBE-002 | `requests.*` inside `async def` | Blocks OS thread, serializes all concurrent I/O |
| PYVIBE-003 | `asyncio.run()` inside `async def` | `RuntimeError: This event loop is already running` |
| PYVIBE-004 | `threading.Lock()` inside `async def` | Blocks event loop under contention |

All rules fire **only inside `async def`**. The same patterns in sync code are valid and produce zero findings.

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

## Design

- **Pure AST, zero runtime dependencies** — uses only Python's built-in `ast` module
- **Each rule is an independent `ast.NodeVisitor`** — easy to add, disable, or extend
- **Gate on `async def`** — every rule checks `_current_async_func` before firing; sync context is never flagged
- **No import resolution** — works on any Python file without installing its dependencies

---

## Run the demo

```bash
python -m pyvibe demo/bad_async.py
```

Expected: 4 CRITICAL findings. `demo/bad_async.py` also contains a sync function with the same patterns — those produce zero findings.

---

## Run the tests

```bash
python -m pytest tests/ -v
# or
python tests/test_rules.py
```

13 tests: true positives + false-positive guards for every rule.

---

## Ecosystem

This project is part of the **vibe-guard** family of runtime anti-pattern scanners:

- [java-vibe-guard](https://github.com/jouninno/java-vibe-guard) — Spring Boot / async Java (blocking Kafka, @Transactional + Virtual Threads)
- **python-vibe-guard** — FastAPI / asyncio (this project)

---

## License

MIT
