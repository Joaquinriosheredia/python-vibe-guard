# python-vibe-guard — Gap Analysis

**Última actualización:** 2026-07-17 (902-repo sweep)
**Muestra activa:** 902 repos · 178,557 .py files · 13,510 violations (pyvibe v0.12.1)
**Muestra anterior:** 250 repos · 95,678 .py files
**Purpose:** identify async anti-patterns that appear across the corpus but are NOT detected by any current rule

---

## Methodology change at this update

The 250-repo version of this document used a **looser co-occurrence heuristic** for
Finding 1 and Finding 2: "repos containing both pattern A and pattern B anywhere in the
same file." At 902 repos this was replaced with an **AST-precise detector** (built on
top of pyvibe's own `AsyncBlockingCallVisitor`/`AsyncContextVisitor` base classes from
`pyvibe/rules/base.py`, used read-only — no rule files were modified) that requires the
exact structural relationship described in each finding (e.g. the `create_task()` call
must be literally inside the `lambda` body passed to `add_signal_handler`, not just
present somewhere in the same file). It also separates **production hits** from
**test-file hits** using the same `_is_test_file()` heuristic pyvibe itself uses for
`TEST_FILE_DOWNGRADE` (`test_*.py`, `*_test.py`, `tests/`/`test/` dirs).

This means the repo counts below are **not directly comparable** to the 250-repo numbers
for Findings 1 and 2 — they are more precise, not a sign the pattern became rarer. Where
useful, both the old (loose, any-cooccurrence) and new (strict, production-only) figures
are shown side by side.

Two new gap patterns (Findings 4 and 5) were added for this update after specifically
searching for common sync-client-in-async-def anti-patterns not covered by any of the
20 rules (`psycopg2`, `redis` sync clients — parallel to PYVIBE-008's coverage of
`sqlite3`, but for Postgres and Redis).

---

## Finding 1 — `asyncio.create_task()` inside signal handler lambda (fire-and-forget)

**Pattern:** `loop.add_signal_handler(sig, lambda: asyncio.create_task(coro()))` (or `ensure_future`)

**Not caught by:** PYVIBE-012 only flags `create_task()`/`ensure_future()` whose return
value is discarded as a **statement**. A `lambda` body is an expression, not a
statement — the AST shape doesn't match what PYVIBE-012 looks for, so this specific
fire-and-forget path is invisible to it.

**Why it matters:** the task runs to completion (or raises) with no handle to cancel it,
no exception surfaced, and no way to know if the signal handler fired correctly.

**Repos confirmed (902-repo sample, strict AST match, production files only): 7 repos, 0.8%**

- `IBM/mcp-context-forge` — `mcpgateway/translate.py` (3 call sites)
- `crossbario/autobahn-python` — `src/autobahn/asyncio/component.py:407,410`
- `opsdroid/opsdroid` — `opsdroid/core.py:68,71` (SIGINT/SIGTERM + SIGHUP handlers)
- `plastic-labs/honcho`
- `rabbitmq-community/rstream`
- `soma-smart/framefox`
- `weaiw/trove-ai`

**Code example — `opsdroid/opsdroid` (`opsdroid/core.py`):**
```python
for sig in (signal.SIGINT, signal.SIGTERM):
    self.eventloop.add_signal_handler(
        sig, lambda: asyncio.ensure_future(self.handle_stop_signal())
        #            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        #  Task created when signal fires — reference immediately lost.
    )
self.eventloop.add_signal_handler(
    signal.SIGHUP, lambda: asyncio.ensure_future(self.reload())
)
```
This is the textbook version of the pattern: a widely-used chatops framework
(`opsdroid`) registers its own shutdown *and* config-reload handlers this way — if
`reload()` raises mid-signal, the failure is invisible.

**Correct pattern:** see the 250-repo version of this document (unchanged).

**Prioridad de implementación:** Media (WARNING) — bajo en volumen (0.8% con detección
estricta) pero el mecanismo de daño es real y afecta rutas de shutdown/reload, que ya son
difíciles de testear.

---

## Finding 2 — `aiohttp.ClientSession()` instantiated outside `async with`

**Pattern:** `self.session = aiohttp.ClientSession()` inside `async def`, never closed with `await session.close()` or `async with`.

**Not caught by:** PYVIBE-016 targets `httpx.Client()` only. There is no rule for
`aiohttp.ClientSession()` lifetime management.

**Why it matters:** `ClientSession` holds a connection pool and an internal connector.
If not explicitly closed, it leaks open TCP connections for the process lifetime.

**Repos confirmed (902-repo sample, strict AST match, production files only): 36 repos, 4.0%**
(previously 21/250 = 8.4% under the looser 250-repo methodology; not directly comparable — see Methodology note)

Selected repos: `home-assistant/core`, `aiortc/aiortc`, `bmoscon/cryptofeed`,
`aio-libs/aiobotocore`, `aio-libs/aiozipkin`, `hikari-py/hikari`,
`slackapi/python-slack-sdk`, `mautrix/python`, `nonebot/nonebot2`, `opsdroid/opsdroid`,
`itamarst/eliot`, `faust-streaming/faust`, `IBM/mcp-context-forge`, `Gobot1234/steam.py`,
`vastsa/FileCodeBox`, `zhinianboke/xianyu-auto-reply`, and 20 more (full list in
`gap_scan_902_summary.json`, not committed — regenerate via the methodology note above).

**Code example — `opsdroid/opsdroid` (`opsdroid/connector/gitter/connector.py`):**
```python
async def connect(self):
    """Create the connection to Gitter."""
    self.session = aiohttp.ClientSession()   # ← no async with, no explicit close
    ...
```

**Correct pattern:** unchanged from the 250-repo version.

**Escala:** el patrón se mantiene entre las 4 reglas más frecuentes de "gap" a esta
escala — sigue siendo el candidato más fuerte para una nueva regla PYVIBE-021 o similar,
detrás solo de put_nowait (ya implementado como PYVIBE-020).

**Prioridad de implementación:** Alta (resource leak + `ResourceWarning` en prod, mismo
razonamiento que en el reporte de 250 repos).

---

## Finding 3 — `asyncio.Queue.put_nowait()` in async def on bounded queue

**Status: IMPLEMENTED as PYVIBE-020 (v0.7.0).** At 902 repos this rule now sits at
**12.3% (111/902)** — see `research/top-hazards.md`. No longer a gap; kept here as
historical record of the original discovery.

---

## Finding 4 (NEW) — `psycopg2.connect()` inside `async def`

**Pattern:** `psycopg2.connect(...)` called directly inside an `async def`, mirroring
PYVIBE-008's coverage of `sqlite3.connect()` but for the far more common synchronous
Postgres driver.

**Not caught by:** no current rule inspects `psycopg2`. PYVIBE-008 only tracks the
`sqlite3` module.

**Why it matters:** `psycopg2` is a blocking C-extension driver — `connect()` and every
subsequent cursor operation perform blocking network I/O. Unlike `sqlite3` (mostly a
dev/test convenience), `psycopg2` is extremely common in real FastAPI/Postgres
production stacks, frequently reached for directly inside async handlers by AI-assisted
code generation that doesn't know about `asyncpg`/`psycopg3` async mode.

**Repos confirmed (902-repo sample, production files only): 2 repos, 0.2%**

- `aaronsb/knowledge-graph-system` — `api/app/services/admin_service.py` (2 sites) +
  `api/app/workers/source_embedding_worker.py` (5 sites)
- `pmh1314520/WebRPA` — `backend/app/executors/database_advanced.py:224`

**Code example — `aaronsb/knowledge-graph-system` (`api/app/services/admin_service.py`):**
```python
async def _check_database_connection(self) -> tuple[bool, Optional[str]]:
    """Check if database is connectable using direct connection"""
    import psycopg2
    try:
        conn = psycopg2.connect(          # ← blocking connect + blocking I/O on every call
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "knowledge_graph"),
            user=os.getenv("POSTGRES_USER", "admin"),
            password=os.environ["POSTGRES_PASSWORD"],
            connect_timeout=5,
        )
```
This is a database health-check helper — exactly the kind of code that runs on every
`/health` or `/ready` probe hit, i.e. frequently and on the hot path.

**Correct pattern:**
```python
import asyncpg
conn = await asyncpg.connect(host=..., port=..., database=..., user=..., password=..., timeout=5)
```

**Detection idea (candidate PYVIBE-023):** mirror `SqliteAsyncRule` (`pyvibe/rules/sqlite_async.py`)
exactly — track `import psycopg2 [as X]` / `from psycopg2 import connect`, flag
`X.connect(...)` or bare `connect(...)` inside `async def`, with the same NAME_COLLISION
guard psycopg2_aliases as sqlite3 uses.

**Prioridad de implementación:** Media. Muy bajo volumen a esta escala (0.2%), pero la
mecánica de daño es idéntica a PYVIBE-008 (ya CRITICAL) y psycopg2 es un driver mucho más
común en producción real que sqlite3 — vale la pena vigilar en el próximo sweep (1500+
repos) antes de decidir prioridad final.

---

## Finding 5 (NEW) — `redis.Redis()` / `redis.StrictRedis()` sync client inside `async def`

**Pattern:** the synchronous `redis-py` client instantiated or used inside `async def`,
instead of `redis.asyncio.Redis`.

**Not caught by:** no current rule inspects `redis`.

**Why it matters:** `redis-py`'s classic `Redis`/`StrictRedis` client blocks the event
loop on every command (`.ping()`, `.get()`, `.set()`, …) via a synchronous socket. Since
`redis-py` 4.2+ ships `redis.asyncio` with an (almost) drop-in async API, this is a case
where the fix is usually a one-line import change — making it a good "quick win" rule
candidate once volume justifies it.

**Repos confirmed (902-repo sample, production files only): 4 repos, 0.4%**

- `apocas/restai` — `restai/app_setup.py:122` (inside a FastAPI `/health/ready` endpoint)
- `pmh1314520/WebRPA` — `backend/app/executors/database_advanced.py:1094,1102`
- `NoneGG/aredis`, `Tishka17/aiogram_dialog` — hits land in `examples/` (excluded from the
  production count above; these libraries' own async Redis client examples occasionally
  demo the sync client for comparison, which is expected and not a bug)

**Code example — `apocas/restai` (`restai/app_setup.py`):**
```python
@fs_app.get("/health/ready")
async def health_ready():
    ...
    if config.REDIS_HOST:
        try:
            import redis
            r = redis.Redis(                 # ← sync client
                host=config.REDIS_HOST,
                port=int(config.REDIS_PORT or 6379),
                socket_connect_timeout=2,
            )
            r.ping()                          # ← blocking network round-trip
            r.close()
            health["redis"] = "ok"
        except Exception:
            ...
```
A Kubernetes readiness probe hitting `/health/ready` every few seconds blocks the event
loop on every single check.

**Correct pattern:**
```python
import redis.asyncio as redis
r = redis.Redis(host=config.REDIS_HOST, port=int(config.REDIS_PORT or 6379), socket_connect_timeout=2)
await r.ping()
await r.aclose()
```

**Detection idea (candidate PYVIBE-024):** track `import redis [as X]` (excluding
`import redis.asyncio as X` / `from redis.asyncio import ...`), flag
`X.Redis(...)`/`X.StrictRedis(...)` calls inside `async def`.

**Prioridad de implementación:** Baja–Media a esta escala (0.4%, muestra pequeña), pero
el patrón de "health check bloqueante" repetido en 2 de los 4 hits sugiere que el impacto
por ocurrencia es alto (probes periódicos) aunque el volumen sea bajo.

---

## Summary

| Gap | Pattern | Repos (250, loose) | Repos (902, strict/prod-only) | Severity | Status |
|-----|---------|--------------------|-------------------------------|----------|--------|
| Signal-handler fire-and-forget | `add_signal_handler(sig, lambda: create_task(...))` | 20 (8.0%) | 7 (0.8%) ¹ | WARNING | open — candidate PYVIBE-021 |
| `aiohttp.ClientSession()` not in `async with` | `self.session = aiohttp.ClientSession()` | 21 (8.4%) | 36 (4.0%) ¹ | WARNING | open — candidate PYVIBE-022 |
| `Queue.put_nowait()` without QueueFull handler | `queue.put_nowait(x)` in async def | 41 (16.4%) | 111 (12.3%) | WARNING | **IMPLEMENTED** as PYVIBE-020 (v0.7.0) |
| `psycopg2.connect()` in async def (NEW) | blocking Postgres driver | — | 2 (0.2%) | CRITICAL | open — candidate PYVIBE-023 |
| `redis.Redis()` sync client in async def (NEW) | blocking Redis driver | — | 4 (0.4%) | CRITICAL | open — candidate PYVIBE-024 |

¹ Not directly comparable to the 250-repo figure — see "Methodology change at this
update" above. The 902-repo figures use a stricter AST match and exclude test files;
they are more trustworthy but not a like-for-like trend line.

### Priorización recomendada para el próximo ciclo de reglas

1. **PYVIBE-022 (aiohttp.ClientSession leak)** — mayor volumen de los 4 gaps abiertos
   (4.0% prod-only, sigue siendo estructural y no ruido de muestra pequeña).
2. **PYVIBE-023 (psycopg2 sync connect)** — bajo volumen pero mecanismo de daño idéntico
   a PYVIBE-008 (ya CRITICAL) y psycopg2 es un driver de producción mucho más frecuente
   que sqlite3; vigilar en el próximo sweep.
3. **PYVIBE-021 (signal-handler fire-and-forget)** — bajo volumen con detección estricta,
   pero afecta rutas de shutdown/reload difíciles de testear manualmente.
4. **PYVIBE-024 (redis sync client)** — volumen más bajo, pero fix de una línea; buen
   candidato "quick win" si se implementa junto con PYVIBE-023 (misma estructura de
   detector, solo cambia el módulo rastreado).

**Note on `list.append(create_task(...))` — still NOT a gap:** confirmado de nuevo en el
sweep de 902; el patrón sigue correctamente no flagged por PYVIBE-012 en todos los casos
revisados (el valor de retorno se captura y se usa en `gather`/`wait` posteriormente).
