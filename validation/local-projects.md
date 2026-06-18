# python-vibe-guard — Local Projects Scan

**Date:** 2026-06-18  
**Scanner version:** 0.2.0 (11 rules, 41 tests)  
**Command:** `python -m pyvibe <path> --json`

---

## Jarvis Runtime

**Path:** `/home/usuariojoaquin/AuthorityEngine/jarvis-runtime`

### 1. Files analyzed

| Scope | .py files |
|-------|-----------|
| Project source (excl. venv) | **10** |
| venv/site-packages | ~300+ |

Project files:
```
jarvis/__init__.py
jarvis/cli.py
jarvis/config.py
jarvis/cost.py
jarvis/llm_cloud.py
jarvis/llm_local.py
jarvis/memory.py
jarvis/router.py
tests/__init__.py
tests/test_router.py
```

### 2. Violations by rule

| Rule | Count |
|------|-------|
| (all rules) | **0** |

**Result: CLEAN** — zero violations in project source.

### 3. Top findings

None. The project contains no `async def` in its source code — it is a
**fully synchronous** LLM routing layer. The patterns present (`time` imports,
file reads in `memory.py`, HTTP calls via SDK) are all in sync function bodies
where they are correct and expected.

```python
# jarvis/router.py — sync routing, no async gate, no violations
def route(prompt: str) -> RouteResult:
    score, reason = _score_prompt(prompt)
    if score >= LOCAL_THRESHOLD:
        result = ask_local(prompt)
        ...
```

### 4. False positives

**7 hits from `venv/anyio/`** — all PYVIBE-004 (`threading.Event/Lock` in async def).

These are **not project code**. anyio deliberately uses `threading.Event` and
`threading.Lock` inside async functions as bridge primitives for its
sync-to-async adapters (`from_thread.py`, `_synchronization.py`). This is the
correct and intentional pattern for a library that bridges sync and async
execution — not a bug.

| File | Line | Function | Pattern |
|------|------|----------|---------|
| anyio/_sockets.py | 237 | connect_tcp() | threading.Event() |
| anyio/_synchronization.py | 330 | wait() | threading.Event() |
| anyio/from_thread.py | 139 | run_async_cm() | threading.Event() |
| anyio/functools.py | 178 | \_\_call\_\_() | threading.Lock() |
| anyio/functools.py | 188 | \_\_call\_\_() | threading.Lock() |
| anyio/memory.py | 120 | receive() | threading.Event() |
| anyio/memory.py | 252 | send() | threading.Event() |

**Root cause:** The scanner has no `--exclude` flag and recurses into `venv/`.
See [Action Item](#action-item-add---exclude-flag) below.

---

## Authority Engine

**Path:** `/home/usuariojoaquin/AuthorityEngine`

### 1. Files analyzed

| Scope | .py files |
|-------|-----------|
| Project source (excl. venv, jarvis-runtime counted once) | **19** |
| venv/site-packages | ~300+ |

Project files (root):
```
engine.py              (693 lines — main orchestrator)
openclaw_v9.py         (276 lines — OpenClaw automation)
racha.py               (143 lines — streak tracker)
generar_inventario.py
generar_inventario_v3.4_backup.py
cure.py
_archive/config.py
resto_web/traductor_inma.py
traductor_inma.py
+ jarvis-runtime/ (counted separately above)
```

### 2. Violations by rule

| Rule | Count |
|------|-------|
| (all rules) | **0** |

**Result: CLEAN** — zero violations in project source.

### 3. Top 5 most interesting patterns (clean — provided for context)

The scanner found no violations, but these patterns in `engine.py` are worth
noting: they would be **CRITICAL findings** if this code were ever migrated
into async handlers.

---

**Pattern 1 — `requests.get` in sync function** *(PYVIBE-002 would fire if async)*

```python
# engine.py:259-265  _buscar_hn()
def _buscar_hn(query: str) -> str:
    """Hacker News Algolia API — fallback si Tavily falla."""
    url = "http://hn.algolia.com/api/v1/search"
    r = requests.get(url, params={"query": query, ...}, timeout=10)  # ← sync, correct here
    r.raise_for_status()
    hits = r.json().get("hits", [])
```

Safe because `_buscar_hn` is a sync `def`. If wrapped in a FastAPI `async def`
without `await run_in_threadpool(...)`, this would block the event loop.

---

**Pattern 2 — `requests.post` to local Ollama** *(PYVIBE-002 would fire if async)*

```python
# engine.py:358-366  call_ollama()
def call_ollama(prompt):
    r = requests.post(
        CONFIG["OLLAMA_URL"],                          # ← http://localhost:11434
        json={"model": CONFIG["MODEL"], "prompt": prompt, "stream": False},
        timeout=300                                    # ← 5-minute blocking timeout
    )
    text = r.json().get("response", "")
```

The `timeout=300` is particularly noteworthy: a 5-minute blocking call to
a local Ollama server. In an async context this would freeze the event loop
for up to 300 seconds per request.

---

**Pattern 3 — `subprocess.run` chain for git** *(PYVIBE-007 would fire if async)*

```python
# engine.py:410-423  git_push_review()
def git_push_review(path, tema, score):
    result = subprocess.run(["git", "pull", "--rebase"], capture_output=True, text=True)
    if result.returncode != 0:
        subprocess.run(["git", "rebase", "--abort"], check=False)
        return
    subprocess.run(["git", "add", path], check=True)
    subprocess.run(["git", "commit", "-m", f"draft: {tema}..."], check=True)
    subprocess.run(["git", "push"], check=True)
```

Five sequential blocking subprocess calls. Correct in a sync CLI tool;
catastrophic in an async handler.

---

**Pattern 4 — `time.sleep` retry loop** *(PYVIBE-001 would fire if async)*

```python
# openclaw_v9.py:191  (retry logic)
for intento in range(1, max_retry + 1):
    if intento > 1:
        time.sleep(15)          # ← 15s blocking pause between retries
    exito = ejecutar_tema(tema, modo, timeout, dry_run)
    if exito:
        break

# engine.py (cooldown between topics)
    time.sleep(cooldown)        # ← configurable cooldown, blocks until done
```

Retry with `time.sleep(15)` and topic cooldowns are standard in sync CLIs.
In async context these would freeze the event loop.

---

**Pattern 5 — `open()` for log/lock files** *(PYVIBE-009 would fire if async)*

```python
# engine.py:194,202,214
with open(LOCK_FILE, "r") as f: ...   # lock read
with open(LOCK_FILE, "w") as f: ...   # lock write
with open(LOG_FILE, "a") as f: ...    # append log
```

Sync file I/O for lock and log management. Correct here; would need
`aiofiles` if the engine were converted to async.

---

### 4. False positives

**25 hits from `venv/`** — same root cause as Jarvis Runtime:

| Package | Hits | Rule | Pattern |
|---------|------|------|---------|
| anyio | 14 | PYVIBE-004 | threading.Event/Lock (intentional bridge) |
| google-generativeai | 10 | PYVIBE-004 | threading.Lock in async adapter |
| websockets | 1 | PYVIBE-004 | threading primitive |

All are from third-party packages using threading primitives as intentional
sync-to-async bridge mechanisms — not bugs.

---

## Action Item: Add `--exclude` flag

Both scans show the same problem: the scanner recurses into `venv/` and
`site-packages/`, generating noise from third-party libraries.

**Proposed fix:** add `--exclude` to the CLI.

```bash
# Desired usage:
python -m pyvibe src/ --exclude venv --exclude .venv --exclude site-packages

# Or smart default: auto-skip directories named venv/.venv/__pycache__
```

Until this is implemented, users can work around it by pointing the scanner
at a specific source directory rather than the project root:

```bash
# Jarvis Runtime — scan only project source
python -m pyvibe jarvis-runtime/jarvis --json

# Authority Engine — scan individual files
python -m pyvibe engine.py openclaw_v9.py racha.py --json
```

---

## Summary

| Project | Source .py | Violations | Async def in source | Assessment |
|---------|-----------|-----------|---------------------|------------|
| Jarvis Runtime | 10 | **0** | 0 | Clean — sync-only codebase |
| Authority Engine | 19 | **0** | 0 | Clean — sync-only codebase |

Both projects are fully synchronous. The patterns they use (`requests`, `subprocess`,
`time.sleep`, `open()`) are correct in sync context. **The scanner works correctly:
zero false positives in project source, zero missed real violations.**

The 32 total "violations" are exclusively from `venv/site-packages/` and represent
an **exclusion UX gap**, not scanner errors.
