# PYVIBE-004 — threading.Lock() en async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/threading_lock.py`  
**Patrón:** `threading.Lock()` / `threading.RLock()` instanciado o usado dentro de `async def`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 5/100 (5.0%) | 5/250 (2.0%) |
| Total hits | 60 | 60 |
| Estabilidad 100→250 | Alta (−3.0 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `agronholm/anyio` — 36 hits
- `BeanieODM/beanie` — 11 hits
- `home-assistant/core` — 8 hits
- `IBM/mcp-context-forge` — 3 hits
- `polarsource/polar` — 2 hits

## Evidence Level: B

- ✅ Validada en repos reales: 5 repos afectados; el total de hits (60) se mantiene igual en ambos sweeps, concentrado en los mismos repos
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

## Nota

El total de hits es idéntico entre 100 y 250 repos (60), lo que indica que los 5 repos afectados ya estaban en el sweep de 100. Los 150 repos nuevos no añaden ningún hit.

---

## Auditoría de Precisión (Sweep 250)

**Muestra analizada:** 14 hits de 60 totales (5 repos) — todos los repos tienen < 3 hits salvo anyio (36 hits, toma 3)
**Metodología:** Muestra estratificada (max 3 por repo) — total 14 de 60 hits; anyio concentra 36/60

### Clasificación hit-by-hit

| # | Repo | File:Line | Function | Clasificación | Razón |
|---|------|-----------|----------|---------------|-------|
| 1 | BeanieODM__beanie | test_validation_on_save.py:70 | test_validate_on_save_dbref | FP | `lock = Lock(k=1)` — `Lock` aquí es un modelo de Beanie/MongoDB (clase ORM de la aplicación, no `threading.Lock`). Colisión de nombre de clase: el detector flagueó la instanciación de un documento ORM llamado `Lock`. |
| 2 | BeanieODM__beanie | test_find.py:435 | test_fetch_links_with_chained_delete | FP | Mismo repo — `Lock` es un documento ORM de Beanie en los tests. Colisión de nombre. |
| 3 | BeanieODM__beanie | test_find.py:511 | test_distinct_with_fetch_links | FP | Mismo repo — mismo patrón, `Lock` es modelo ORM. |
| 4 | IBM__mcp-context-forge | test_cache_invalidation_subscriber.py:125 | test_process_tool_lookup_name_invalidation | FP | `mock_tool_lookup._lock = threading.Lock()` — se asigna un `threading.Lock` a un objeto mock en un test. En el test no hay `async def` que lo use como mutex — se está configurando un atributo del mock para que el SUT pueda acceder a él. El `threading.Lock()` aquí es un setup de datos de test, no un mutex que bloquee el event loop. FP contextual. |
| 5 | IBM__mcp-context-forge | test_cache_invalidation_subscriber.py:143 | test_process_tool_lookup_gateway_invalidation | FP | Mismo repo y mismo patrón — `threading.Lock()` en atributo de mock. |
| 6 | IBM__mcp-context-forge | test_cache_invalidation_subscriber.py:161 | test_process_admin_invalidation | FP | Mismo repo — `threading.Lock()` en atributo de mock de admin cache. |
| 7 | agronholm__anyio | src/anyio/functools.py:173 | __call__ | EDGE | `Lock(fast_acquire=not self._always_checkpoint)` — este es `anyio.Lock`, no `threading.Lock`. Si el detector flagueó esto por el nombre `Lock`, es una colisión de nombre. anyio.Lock es el mutex async correcto. |
| 8 | agronholm__anyio | src/anyio/functools.py:183 | __call__ | EDGE | Mismo contexto — `Lock(fast_acquire=...)` es `anyio.Lock` en el memoize cache de anyio. Uso correcto de Lock async. |
| 9 | agronholm__anyio | tests/test_synchronization.py:38 | test_contextmanager | FP | Test de anyio — verificación de comportamiento del Lock async de anyio. En test de la librería de sync. |
| 10 | home-assistant__core | homeassistant/util/async_.py:105 | gather_with_limited_concurrency | FP | `semaphore = Semaphore(limit)` — `Semaphore` es `asyncio.Semaphore`, no `threading.Semaphore`. Incluso si fuera `threading.Lock`, la función no usa la primitiva directamente como mutex bloqueante sino para limitar concurrencia a través de `async with semaphore:`. FP si el detector flagueó el Semaphore como Lock threading. |
| 11 | home-assistant__core | tests/components/backblaze_b2/test_backup.py:911 | test_metadata_downloads_are_sequential | FP | Test de HA — probablemente `threading.Lock()` en mock o fixture de test. |
| 12 | home-assistant__core | tests/components/homekit/test_type_locks.py:44 | test_lock_unlock | FP | El nombre del archivo ya indica que se testea la integración "locks" de HomeKit — `Lock` en este contexto es un dispositivo HomeKit, no `threading.Lock`. Colisión de dominio. |
| 13 | polarsource__polar | server/polar/locker.py:63 | lock | FP | `Lock(self.redis, self._get_key(name), ...)` — este `Lock` es `redis.asyncio.lock.Lock` (importado en la línea 7 del archivo). Es un distributed lock async sobre Redis, no `threading.Lock`. |
| 14 | polarsource__polar | server/polar/locker.py:122 | is_locked | FP | Mismo repo — `Lock(self.redis, ...)` es `redis.asyncio.lock.Lock`. Correcto. |

### Resultado

| Métrica | Valor |
|---------|-------|
| TP | 0 |
| FP | 12 |
| EDGE | 2 |
| Precisión (TP/total sin EDGE) | 0/12 = 0% |
| Precisión (TP+EDGE/total) | 2/14 = 14% |

### Patrones de FP identificados

1. **DOMAIN_CLASS_NAME_COLLISION** — clase de dominio llamada `Lock` (ORM model, HomeKit device) que el detector confundió con `threading.Lock`.
   - Ejemplo: `lock = Lock(k=1)` donde `Lock` es un documento de Beanie MongoDB
   - Repos afectados: 1 (BeanieODM/beanie, 3 instancias)

2. **ASYNC_LOCK_SAME_NAME** — `anyio.Lock`, `redis.asyncio.lock.Lock` importados y usados correctamente dentro de `async def` — son primitivas async válidas, no `threading.Lock`.
   - Ejemplo: `from redis.asyncio.lock import Lock; ... Lock(self.redis, ...)`
   - Repos afectados: 2 (polarsource/polar, agronholm/anyio)

3. **MOCK_ATTRIBUTE_SETUP** — `threading.Lock()` asignado como atributo de un objeto mock en test (`mock._lock = threading.Lock()`). El lock no se adquiere en la función async bajo prueba — se pasa como dato al SUT que lo usa internamente.
   - Repos afectados: 1 (IBM/mcp-context-forge, 3 instancias)

4. **TEST_INTEGRATION_DOMAIN** — tests de integraciones HomeKit donde `Lock` es un tipo de dispositivo de automatización del hogar.
   - Repos afectados: 1 (home-assistant/core)

### Recomendación de Evidence Level

**ALERTA: Precisión 0-14% — regla requiere revisión profunda del detector.** Todos los hits en la muestra son falsos positivos. El problema es sistemático:
- El detector no verifica que `Lock` sea específicamente `threading.Lock` (verificando el módulo de origen del símbolo)
- Flagueó `anyio.Lock`, `redis.asyncio.Lock`, clases ORM llamadas `Lock`, y mocks
- Para reparar: el detector debe verificar que el import de `Lock` sea `from threading import Lock` o `import threading; threading.Lock()`, no cualquier clase con nombre `Lock`
- Los 36 hits de anyio probablemente son todos FPs del mismo tipo (anyio.Lock siendo confundido con threading.Lock)
- **Recomendación: degradar a 🔵 Limited Scope hasta que el detector se corrija.** Con 0% de precisión en la muestra, la regla genera más ruido que valor.
