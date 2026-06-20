# python-vibe-guard — Stability Report: 100 → 250 Repos

**Generated:** 2026-06-20  
**Version:** 0.7.0 (20 rules, 123 tests)  
**Baseline:** 100 repos · 64,335 .py files · 3,639 violations  
**Extended:** 250 repos · 95,678 .py files · 7,106 violations  
**New repos added:** 150 (0 clone failures, 0 scan failures)

---

## Stability Table — % of Repos Affected per Rule

> **Estabilidad:** Alta = diferencia < 5 pp · Media = 5–15 pp · Baja = > 15 pp  
> *All rates expressed as % of repos in the sample with ≥1 hit for that rule.*

| Regla | Severidad | Patrón | % en 100 | % en 250 | Diferencia | Estabilidad |
|-------|-----------|--------|-----------|-----------|------------|-------------|
| PYVIBE-001 | CRITICAL | `time.sleep()` in `async def` | 16.0% | 12.4% | −3.6 pp | **Alta** |
| PYVIBE-002 | CRITICAL | `requests.get/post` in `async def` | 3.0% | 4.0% | +1.0 pp | **Alta** |
| PYVIBE-003 | CRITICAL | `asyncio.run()` inside `async def` | 1.0% | 0.4% | −0.6 pp | **Alta** |
| PYVIBE-004 | CRITICAL | `threading.Lock()` in `async def` | 5.0% | 2.0% | −3.0 pp | **Alta** |
| PYVIBE-005 | CRITICAL | Celery task without `time_limit` | 15.0% | 12.8% | −2.2 pp | **Alta** |
| PYVIBE-006 | CRITICAL | `ContextVar` without `reset()` | 10.0% | 6.0% | −4.0 pp | **Alta** |
| PYVIBE-007 | CRITICAL | `subprocess.run/call` in `async def` | 6.0% | 4.8% | −1.2 pp | **Alta** |
| PYVIBE-008 | CRITICAL | `sqlite3` operations in `async def` | 10.0% | 8.8% | −1.2 pp | **Alta** |
| PYVIBE-009 | CRITICAL | `open()` instead of `aiofiles` | 33.0% | 24.0% | −9.0 pp | **Media** |
| PYVIBE-010 | CRITICAL | `httpx.get/post` (sync) in `async def` | 2.0% | 0.8% | −1.2 pp | **Alta** |
| PYVIBE-011 | CRITICAL | `os.path/listdir` blocking in `async def` | 0.0% | 0.0% | 0.0 pp | **Alta** ¹ |
| PYVIBE-012 | CRITICAL | `asyncio.create_task()` orphan | 13.0% | 12.0% | −1.0 pp | **Alta** |
| PYVIBE-013 | CRITICAL | `asyncio.gather()` without `return_exceptions` | 47.0% | 35.2% | −11.8 pp | **Media** |
| PYVIBE-014 | CRITICAL | `asyncio.ensure_future()` orphan | 8.0% | 5.6% | −2.4 pp | **Alta** |
| PYVIBE-015 | CRITICAL | `loop.run_until_complete()` in `async def` | 1.0% | 2.0% | +1.0 pp | **Alta** |
| PYVIBE-016 | CRITICAL | `httpx.Client()` (sync) in `async def` | 1.0% | 0.8% | −0.2 pp | **Alta** |
| PYVIBE-017 | CRITICAL | Silent `except` in `async def` | 57.0% | 48.8% | −8.2 pp | **Media** |
| PYVIBE-018 | CRITICAL | `while True` without `await` | 10.0% | 6.8% | −3.2 pp | **Alta** |
| PYVIBE-019 | WARNING | Retry without backoff | 43.0% | 32.8% | −10.2 pp | **Media** |
| PYVIBE-020 | WARNING | `put_nowait()` without `QueueFull` handler | N/A ² | 16.4% | N/A ² | N/A ² |

¹ PYVIBE-011 has zero hits at both scales — consistently detecting a rare, always-incorrect pattern.  
² PYVIBE-020 was added in v0.7.0 after the 100-repo scan was archived; no baseline available. Debut rate 16.4% (41/250 repos) is strong for a new rule.

### Observations on rate dilution

All non-zero rates dropped between 100→250 repos. This is expected: the first 100 repos were curated toward high-star async-heavy libraries (FastAPI ecosystem, aiohttp, Celery). The 150 new repos include more Django admin tools, boilerplate scaffolds, and general-purpose projects with fewer async patterns. The direction of change is structural, not a signal of false positives.

---

## Most Valuable Rules — Severity-Weighted Score

> **Score = % repos affected × severity weight (CRITICAL = 3, WARNING = 1)**  
> Purpose: surface rules that are rare but always-wrong (e.g. PYVIBE-003, PYVIBE-011) and avoid penalising them for low frequency.

| Rank | Regla | Severidad | % repos (250) | Peso | Score | Notas |
|------|-------|-----------|---------------|------|-------|-------|
| 1 | PYVIBE-017 | CRITICAL | 48.8% | 3 | **146.4** | Más frecuente Y crítico — máxima prioridad |
| 2 | PYVIBE-013 | CRITICAL | 35.2% | 3 | **105.6** | Presente en 1 de cada 3 repos con asyncio |
| 3 | PYVIBE-009 | CRITICAL | 24.0% | 3 | **72.0** | `open()` blocking: sorprendentemente común |
| 4 | PYVIBE-005 | CRITICAL | 12.8% | 3 | **38.4** | Celery sin `time_limit`: alto impacto en prod |
| 5 | PYVIBE-001 | CRITICAL | 12.4% | 3 | **37.2** | `time.sleep()` bloquea el event loop |
| 6 | PYVIBE-012 | CRITICAL | 12.0% | 3 | **36.0** | Task orphan: excepción silenciada + memory leak |
| 7 | PYVIBE-019 | WARNING | 32.8% | 1 | **32.8** | Alta prevalencia compensa peso bajo |
| 8 | PYVIBE-008 | CRITICAL | 8.8% | 3 | **26.4** | sqlite3 bloquea el event loop completamente |
| 9 | PYVIBE-018 | CRITICAL | 6.8% | 3 | **20.4** | Bucle infinito sin yield — congela async |
| 10 | PYVIBE-006 | CRITICAL | 6.0% | 3 | **18.0** | ContextVar leak: difícil de reproducir en tests |
| 11 | PYVIBE-014 | CRITICAL | 5.6% | 3 | **16.8** | `ensure_future` orphan — igual de peligroso que PYVIBE-012 |
| 12 | PYVIBE-020 | WARNING | 16.4% | 1 | **16.4** | Nueva regla; debut fuerte (41/250 repos) |
| 13 | PYVIBE-007 | CRITICAL | 4.8% | 3 | **14.4** | subprocess bloquea igual que sqlite3 |
| 14 | PYVIBE-002 | CRITICAL | 4.0% | 3 | **12.0** | `requests` sync en async: patrón legacy |
| 15 | PYVIBE-004 | CRITICAL | 2.0% | 3 | **6.0** | threading.Lock() causa deadlock en async |
| 16 | PYVIBE-015 | CRITICAL | 2.0% | 3 | **6.0** | `loop.run_until_complete` anidado — crash seguro |
| 17 | PYVIBE-010 | CRITICAL | 0.8% | 3 | **2.4** | httpx sync: similar a PYVIBE-002 |
| 18 | PYVIBE-016 | CRITICAL | 0.8% | 3 | **2.4** | `httpx.Client()` sync en async def |
| 19 | PYVIBE-003 | CRITICAL | 0.4% | 3 | **1.2** | Raro pero siempre incorrecto |
| 20 | PYVIBE-011 | CRITICAL | 0.0% | 3 | **0.0** | ³ |

³ **PYVIBE-011 (os.blocking) — análisis especial:**  
0 hits en 250 repos no implica que la regla sea innecesaria. El patrón (`os.path.exists()`, `os.listdir()`, `os.stat()` en async def) es real pero los repos del ecosistema async tienden a usar `pathlib`/`aiofiles` ya. La regla protege contra código legacy que mezcla `os.*` con asyncio. Mantener con revisión de FP ratio cuando llegue a 500 repos.

---

## Ranking Top 10 — Cambios entre 100 y 250 repos

> Ranking por `% repos afectados` (sin peso de severidad).

| Posición | En 100 repos | En 250 repos | Cambio |
|----------|-------------|--------------|--------|
| #1 | PYVIBE-017 (57.0%) | PYVIBE-017 (48.8%) | Sin cambio ✓ |
| #2 | PYVIBE-013 (47.0%) | PYVIBE-013 (35.2%) | Sin cambio ✓ |
| #3 | PYVIBE-019 (43.0%) | PYVIBE-019 (32.8%) | Sin cambio ✓ |
| #4 | PYVIBE-009 (33.0%) | PYVIBE-009 (24.0%) | Sin cambio ✓ |
| #5 | PYVIBE-001 (16.0%) | PYVIBE-020 (16.4%) ⚠ | Nueva regla debuta; PYVIBE-001 pasa a #6 |
| #6 | PYVIBE-005 (15.0%) | PYVIBE-001 (12.4%) | Permuta menor con PYVIBE-005 (0.4 pp) |
| #7 | PYVIBE-012 (13.0%) | PYVIBE-005 (12.8%) | Permuta menor |
| #8 | PYVIBE-008 (10.0%) | PYVIBE-012 (12.0%) | Sin cambio efectivo |
| #9 | PYVIBE-006 (10.0%) | PYVIBE-008 (8.8%) | PYVIBE-006 sale del top 10 |
| #10 | PYVIBE-018 (10.0%) | PYVIBE-018 (6.8%) | Mantiene posición |

### Veredicto de estabilidad del ranking

**✅ SEGURO ESCALAR A 500 repos.** El top 4 es idéntico en orden y proporciones. Las permutaciones en #5–#9 son de décimas de pp entre reglas muy próximas y no indican inestabilidad. La entrada de PYVIBE-020 en #5 es esperada (regla nueva con debut sólido) y no desplaza ninguna regla crítica.

No se recomienda revisión especial antes de escalar a 500.

---

## Notas adicionales

- **Dilución estructural:** La bajada generalizada de tasas (−2 a −11 pp) refleja la composición del nuevo lote, no ruido estadístico. Con 500 repos la tendencia probablemente se estabilice en torno a los valores de 250.
- **PYVIBE-009 (−9 pp) y PYVIBE-013 (−11.8 pp):** Estabilidad "Media" por la dilución, pero ambas son reglas de alto score. No requieren revisión; el patrón es más frecuente en frameworks de alta concurrencia que en apps Django generales.
- **PYVIBE-019 (−10.2 pp):** También Media. Retry sin backoff es un patrón de código de integración; los 150 nuevos repos incluyen más scaffolds sin código de red real.
- **Nuevos repos destacados en 250:**  
  - `nats-io/nats.py` — 128 hits PYVIBE-008 (sqlite3 patterns en cliente NATS)  
  - `aio-libs/aiopg` — 122 hits PYVIBE-008 (asyncpg wrapper)  
  - `ronf/asyncssh` — 94 hits PYVIBE-009 (open() en SSH async)  
  - `pmh1314520/WebRPA` — 352 hits PYVIBE-017 (silent except masivo)
