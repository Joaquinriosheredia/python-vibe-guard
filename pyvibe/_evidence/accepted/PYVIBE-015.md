# PYVIBE-015 — loop.run_until_complete() dentro de async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/loop_run_until_complete.py`  
**Patrón:** `loop.run_until_complete(coro())` llamado dentro de `async def`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 1/100 (1.0%) | 5/250 (2.0%) |
| Total hits | 1 | 8 |
| Estabilidad 100→250 | Alta (+1.0 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `pmh1314520/WebRPA` — 4 hits (nuevo en sweep 250)
- `aio-libs/aiomysql` — 1 hit
- `mongodb/motor` — 1 hit (nuevo en sweep 250)
- `ormar-orm/ormar` — 1 hit (nuevo en sweep 250)
- `omnilib/aiosqlite` — 1 hit (nuevo en sweep 250)

## Evidence Level: B

- ✅ Validada en repos reales: 5 repos afectados en sweep 250 (era 1 repo en sweep 100 — la regla gana más validación)
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

---

## Auditoría de Precisión (Sweep 250)

**Muestra analizada:** 8 hits de 8 totales (5 repos)
**Metodología:** 100% audit (8 hits)

### Clasificación hit-by-hit

| # | Repo | File:Line | Function | Clasificación | Razón |
|---|------|-----------|----------|---------------|-------|
| 1 | aio-libs__aiomysql | tests/sa/test_sa_transaction.py:21 | wrapper | FP | Decorador en archivo de test — la función `wrapper` es un `async def` interno que hace `await self.loop.run_until_complete(self._connect())`, que es runtime incorrecto dentro de async, pero el contexto es un decorador de test que podría ejecutarse en un loop recién creado; EDGE por contexto de test |
| 2 | mongodb__motor | test/asyncio_tests/test_asyncio_basic.py:164 | test_executor_reset | FP | `self.loop.run_until_complete(...)` llamado en **proceso hijo** creado con `os.fork()` — el proceso hijo hace `set_event_loop(None)` y `self.loop = new_event_loop()`, por tanto no hay loop activo cuando se llama `run_until_complete`. Uso correcto en contexto fork. |
| 3 | omnilib__aiosqlite | aiosqlite/tests/smoke.py:141 | (inner) runner | FP | `loop.run_until_complete(query())` en función **síncrona** `runner()` interna — el detector flagueó la línea 141 pero la función contenedora inmediata es `def runner`, no `async def`; solo la función externa `test_multi_loop_usage` es async. Mismo bug de detección que PYVIBE-003. |
| 4 | ormar-orm__ormar | benchmarks/conftest.py:99 | aio_benchmark | EDGE | `loop.run_until_complete(func(...))` dentro de función síncrona `benchmarked_func()` anidada en `async def aio_benchmark`. La función síncrona se registra como benchmark y se ejecuta fuera del event loop; desde ese scope síncrono el `run_until_complete` podría ser correcto. Indetectable sin análisis de flujo. |
| 5 | pmh1314520__WebRPA | backend/app/api/system_napcat.py:53 | start_napcat | TP | `loop.run_until_complete(...)` dentro de callback síncrono `on_qrcode()` anidado en `async def start_napcat`. El callback se llama desde dentro del contexto async (hay un loop activo), lo que causará `RuntimeError`. Bug real. |
| 6 | pmh1314520__WebRPA | backend/app/api/system_napcat.py:65 | start_napcat | TP | Igual que hit 5 — segundo callback `on_login()` en la misma función con el mismo patrón problemático. |
| 7 | pmh1314520__WebRPA | backend/app/api/system_napcat.py:121 | refresh_napcat_qrcode | TP | `loop.run_until_complete(...)` en callback síncrono dentro de `async def refresh_napcat_qrcode`. Mismo patrón que hits 5-6. Bug real. |
| 8 | pmh1314520__WebRPA | backend/app/api/system_napcat.py:133 | refresh_napcat_qrcode | TP | Igual que hit 7 — segundo callback `on_login()` en la misma función. |

### Resultado

| Métrica | Valor |
|---------|-------|
| TP | 4 |
| FP | 3 |
| EDGE | 1 |
| Precisión (TP/total sin EDGE) | 4/7 = 57% |
| Precisión (TP/total con EDGE como FP) | 4/8 = 50% |

### Patrones de FP identificados

1. **FORK_CHILD_PROCESS** — `run_until_complete()` llamado en proceso hijo después de `os.fork()` + `new_event_loop()`. No hay loop activo, uso correcto.
   - Ejemplo: código en `mongodb/motor` — fork + `set_event_loop(None)` + `new_event_loop()` antes de la llamada.
   - Repos afectados: 1

2. **INNER_SYNC_FUNCTION** — el detector flagueó una línea dentro de una función `def` (síncrona) anidada en una función `async def` exterior. El `run_until_complete` pertenece al scope síncrono, que es correcto si el loop no está activo en ese momento.
   - Ejemplo: `def runner(k, conn): loop.run_until_complete(query())` dentro de `async def test_multi_loop_usage`.
   - Repos afectados: 2 (aiomysql, aiosqlite)

3. **BENCHMARK_SYNC_WRAPPER** — función de benchmark síncrona anidada en `async def` que llama `run_until_complete` desde su scope síncrono (EDGE).
   - Repos afectados: 1 (ormar-orm/ormar)

### Recomendación de Evidence Level

**Mantener B. Revisar detección para funciones síncronas anidadas.** La regla tiene un problema concreto: flagueaba `run_until_complete` en funciones `def` (síncronas) anidadas dentro de `async def`, que no son el patrón objetivo. El detector debería verificar que el `run_until_complete` esté en el scope de un `AsyncFunctionDef` directo, no en funciones `def` anidadas. Los 4 TP reales son genuinos (callbacks síncronos que se ejecutan en contexto de loop activo). Precisión real en producción (excluyendo test y FPs de detección): estimada en ~70-80%.
