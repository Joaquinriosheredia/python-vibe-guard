# Top Hazards

Ranking de las 20 reglas de python-vibe-guard por **porcentaje de repos afectados**,
sobre el sweep más reciente (902 repos, v0.12.1). Sin ponderar por severidad — para el
ranking severity-weighted ver `research/datasets/stability-report.md` (sección "Most
Valuable Rules").

**Fuente:** `research/datasets/1000-repos.json` · 902 repos · 178,557 archivos .py · 13,510 violaciones
**Fecha:** 2026-07-17

| # | Regla | Severidad | Patrón | % repos | Repos con hit | Hits totales |
|---|-------|-----------|--------|--------:|---------------:|-------------:|
| 1 | PYVIBE-017 | CRITICAL | Silent `except` in `async def` | **43.9%** | 396/902 | 6,731 |
| 2 | PYVIBE-013 | CRITICAL | `asyncio.gather()` without `return_exceptions` | **32.4%** | 292/902 | 2,299 |
| 3 | PYVIBE-009 | CRITICAL | `open()` instead of `aiofiles` | **22.8%** | 206/902 | 1,132 |
| 4 | PYVIBE-012 | CRITICAL | `asyncio.create_task()` orphan | 12.6% | 114/902 | 496 |
| 5 | PYVIBE-020 | WARNING | `put_nowait()` without `QueueFull` handler | 12.3% | 111/902 | 590 |
| 6 | PYVIBE-005 | CRITICAL | Celery task without `time_limit` | 9.1% | 82/902 | 1,316 |
| 7 | PYVIBE-001 | CRITICAL | `time.sleep()` in `async def` | 6.5% | 59/902 | 178 |
| 8 | PYVIBE-007 | CRITICAL | `subprocess.run/call` in `async def` | 4.5% | 41/902 | 205 |
| 9 | PYVIBE-006 | CRITICAL | `ContextVar` without `reset()` | 4.5% | 41/902 | 72 |
| 10 | PYVIBE-014 | CRITICAL | `asyncio.ensure_future()` orphan | 4.4% | 40/902 | 138 |
| 11 | PYVIBE-018 | CRITICAL | `while True` without `await` | 3.9% | 35/902 | 67 |
| 12 | PYVIBE-002 | CRITICAL | `requests.get/post` in `async def` | 2.2% | 20/902 | 130 |
| 13 | PYVIBE-008 | CRITICAL | `sqlite3` operations in `async def` | 2.0% | 18/902 | 67 |
| 14 | PYVIBE-019 | WARNING | Retry without backoff | 1.9% | 17/902 | 35 |
| 15 | PYVIBE-010 | CRITICAL | `httpx.get/post` (sync) in `async def` | 1.0% | 9/902 | 33 |
| 16 | PYVIBE-004 | CRITICAL | `threading.Lock()` in `async def` | 0.8% | 7/902 | 10 |
| 17 | PYVIBE-015 | CRITICAL | `loop.run_until_complete()` in `async def` | 0.4% | 4/902 | 5 |
| 18 | PYVIBE-016 | CRITICAL | `httpx.Client()` (sync) in `async def` | 0.3% | 3/902 | 4 |
| 19 | PYVIBE-003 | CRITICAL | `asyncio.run()` inside `async def` | 0.1% | 1/902 | 1 |
| 19 | PYVIBE-011 | CRITICAL | `os.path/listdir` blocking in `async def` | 0.1% | 1/902 | 1 |

---

## Top 5 — detail with worst offenders

### #1 PYVIBE-017 — Silent `except` in `async def` (43.9%)
Top repos by hit count: `braedonsaunders/homerun` (440), `pmh1314520/WebRPA` (352),
`DemonDamon/AgenticX` (215), `IBM/mcp-context-forge` (209), `BetaStreetOmnis/xhs_ai_publisher` (193).

### #2 PYVIBE-013 — `asyncio.gather()` without `return_exceptions` (32.4%)
Top repos: `home-assistant/core` (331), `PyPlanet/PyPlanet` (61), `aiortc/aiortc` (54),
`TracecatHQ/tracecat` (51), `braedonsaunders/homerun` (46).

### #3 PYVIBE-009 — `open()` instead of `aiofiles` (22.8%)
Top repos: `ronf/asyncssh` (94), `tubecreate/tubecli` (61), `pmh1314520/WebRPA` (49),
`xr843/fojin` (45), `dymmond/edgy` (37).

### #4 PYVIBE-012 — `asyncio.create_task()` orphan (12.6%)
Top repos: `peterhinch/micropython-async` (66), `learning-at-home/hivemind` (17),
`Amm1rr/WebAI-to-API` (16), `chenyme/grok2api` (16), `judahpaul16/gpt-home` (16).

### #5 PYVIBE-020 — `put_nowait()` without `QueueFull` handler (12.3%)
Top repos: `google-gemini/genai-processors` (56), `home-assistant/core` (55),
`aio-libs/janus` (33), `gevent/gevent` (23), `nggit/tremolo` (22).

---

## Changes vs the 250-repo baseline

The ranking order for the top 3 positions is unchanged from the 250-repo sample
(PYVIBE-017 → PYVIBE-013 → PYVIBE-009). PYVIBE-012 overtakes PYVIBE-020 for the #4 spot
by a narrow 0.3 pp margin. Full comparison and stability classification per rule is in
`research/datasets/stability-report.md`.
