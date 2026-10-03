# PYVIBE-008 — sqlite3 en async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/sqlite_async.py`  
**Patrón:** `sqlite3.connect(...)` / operaciones de cursor sqlite3 dentro de `async def`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 10/100 (10.0%) | 22/250 (8.8%) |
| Total hits | 121 | 436 |
| Estabilidad 100→250 | Alta (−1.2 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `nats-io/nats.py` — 128 hits (nuevo en sweep 250)
- `aio-libs/aiopg` — 122 hits (nuevo en sweep 250)
- `Kludex/uvicorn` — 45 hits
- `aiortc/aioquic` — 26 hits
- `IBM/mcp-context-forge` — 25 hits

## Evidence Level: B

- ✅ Validada en repos reales: 22 repos, 436 hits — los hits se triplican en sweep 250 por `nats-io/nats.py` y `aio-libs/aiopg`
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

## Nota

El salto de 121 a 436 hits (3.6×) con solo 2.2× más repos indica alta concentración en los nuevos repos `nats-io/nats.py` (128 hits) y `aio-libs/aiopg` (122 hits). Pueden ser wrappers de bajo nivel donde sqlite3 se usa intencionalmente en contexto de pruebas o compatibility layer. Candidato a revisión manual de FP.

---

## Auditoría de Precisión (Sweep 250)

**Muestra analizada:** 20 hits de 436 totales (22 repos)
**Metodología:** Muestra estratificada (max 3 por repo)

### Clasificación hit-by-hit

| # | Repo | File:Line | Function | Clasificación | Razón |
|---|------|-----------|----------|---------------|-------|
| 1 | Amm1rr__WebAI-to-API | sqlite_repository.py:128 | list_snapshots | TP | `sqlite3.connect(...)` dentro de función `def _list()` síncrona pero llamada con `await asyncio.to_thread(_list)` — el detector flagueó la línea de `sqlite3.connect` dentro del `def _list()` interno, que se ejecuta en thread. FP contextual: el sqlite3 está correctamente en thread. |
| 2 | Amm1rr__WebAI-to-API | sqlite_repository.py:156 | prune_stale_snapshots | TP | Mismo patrón — `sqlite3.connect` en función `def _prune()` interna que se ejecuta con `asyncio.to_thread()`. FP: correcto. |
| 3 | Amm1rr__WebAI-to-API | tests/test_sqlite_repository.py:86 | test_repository_raises_state_integrity_error_for_corrupted_json | FP | `with sqlite3.connect(str(db_file)) as conn:` dentro de `async def test_...` — se usa sqlite3 **directamente** para insertar datos corruptos en la DB de test. Técnicamente bloquea el event loop en el test pero es un acceso único a una DB de test, no un servidor de producción. FP por contexto de test. |
| 4 | IBM__mcp-context-forge | results_store.py:114 | store_evaluation_result | TP | `with sqlite3.connect(self.db_path) as conn:` directo en `async def store_evaluation_result()` sin executor. Bug real — el servidor MCP bloquea el event loop durante escrituras a SQLite. |
| 5 | IBM__mcp-context-forge | results_store.py:186 | get_evaluation_result | TP | Mismo archivo — `sqlite3.connect()` en `async def get_evaluation_result()`. Bug real. |
| 6 | IBM__mcp-context-forge | results_store.py:219 | list_evaluation_results | TP | Mismo archivo — `sqlite3.connect()` en `async def list_evaluation_results()`. Bug real. |
| 7 | JoeanAmier__XHS-Downloader | source/module/recorder.py:23 | _connect_database | FP | `self.database = await connect(self.file)` — este `connect` es de `aiosqlite.connect` (async wrapper), no `sqlite3.connect`. El detector flagueó un `connect()` async de aiosqlite como si fuera `sqlite3.connect`. Colisión de nombre de función. |
| 8 | JoeanAmier__XHS-Downloader | source/module/recorder.py:111 | _connect_database | FP | Mismo repo — otra referencia a `aiosqlite.connect()` confundida con `sqlite3.connect`. |
| 9 | JoeanAmier__XHS-Downloader | source/module/recorder.py:154 | _connect_database | FP | Mismo repo — tercer hit de `aiosqlite.connect()`. |
| 10 | Kludex__uvicorn | tests/middleware/test_logging.py:104 | open_connection | FP | `async with connect(url) as websocket:` — `connect` es `websockets.asyncio.client.connect`, NO `sqlite3.connect`. El detector confundió cualquier llamada a una función llamada `connect()` con `sqlite3.connect`. Colisión de nombre grave. |
| 11 | Kludex__uvicorn | tests/middleware/test_proxy_headers.py:543 | test_proxy_headers_websocket_x_forwarded_proto | FP | Mismo repo — `connect(url)` es `websockets.asyncio.client.connect`. |
| 12 | Kludex__uvicorn | tests/protocols/test_websocket.py:120 | open_connection | FP | Mismo repo y mismo patrón — `websockets.asyncio.client.connect`, no sqlite3. |
| 13 | MagicStack__asyncpg | tests/test_connect.py:2299 | _run_connection_test | FP | `await connect(target_session_attrs=target_attribute)` — `connect` es `asyncpg.connect`, no `sqlite3.connect`. Colisión de nombre: el detector flagueó cualquier `connect()` dentro de `async def`. |
| 14 | MagicStack__asyncpg | tests/test_connect.py:2335 | test_target_attribute_not_matched | FP | Mismo repo — `asyncpg.connect()` confundido con `sqlite3.connect`. |
| 15 | MagicStack__asyncpg | tests/test_connect.py:2346 | test_target_attribute_not_matched | FP | Mismo. |
| 16 | aio-libs__aiomysql | aiomysql/pool.py:182 | _fill_free_pool | FP | `conn = await connect(echo=..., **self._conn_kwargs)` — `connect` es la función interna de aiomysql para crear conexiones MySQL (async). No es `sqlite3.connect`. |
| 17 | aio-libs__aiomysql | aiomysql/pool.py:195 | _fill_free_pool | FP | Mismo — `await connect(...)` es aiomysql async. |
| 18 | aio-libs__aiopg | aiopg/pool.py:336 | _fill_free_pool | FP | `conn = await connect(...)` — `connect` es `aiopg.connection.connect` (async PostgreSQL). No es sqlite3. |
| 19 | aio-libs__aiopg | aiopg/pool.py:358 | _fill_free_pool | FP | Mismo — aiopg async connect. |
| 20 | aio-libs__aiopg | tests/test_connection.py:25 | test_connect | FP | `await connect(...)` es `aiopg.connect()` async. En test de la librería de conexión. |

### Resultado

| Métrica | Valor |
|---------|-------|
| TP | 5 |
| FP | 15 |
| EDGE | 0 |
| Precisión (TP/total) | 5/20 = 25% |

### Patrones de FP identificados

1. **ASYNC_CONNECT_NAME_COLLISION** — cualquier función llamada `connect()` dentro de `async def` es confundida con `sqlite3.connect()`. Esto afecta a: `aiosqlite.connect()`, `asyncpg.connect()`, `aiopg.connect()`, `aiomysql.connect()`, `websockets.asyncio.client.connect()`.
   - **Este es el FP más grave y sistemático** — afecta a múltiples repos con drivers async correctos
   - Repos afectados: 5 (XHS-Downloader, asyncpg, aiomysql, aiopg, uvicorn)

2. **TO_THREAD_WRAPPER** — `sqlite3.connect()` dentro de función `def` síncrona interna que se pasa a `asyncio.to_thread()`. El acceso a SQLite está correctamente delegado a un thread.
   - Repos afectados: 1 (Amm1rr/WebAI-to-API, 2 instancias)

3. **TEST_ONE_SHOT_ACCESS** — `sqlite3.connect()` directo en test para insertar datos de test. Técnicamente bloquea el loop pero en test de uso único no es un riesgo de producción.
   - Repos afectados: 1 (Amm1rr/WebAI-to-API test)

### Recomendación de Evidence Level

**ALERTA CRÍTICA: Precisión 25% — el detector tiene un bug fundamental.** La causa dominante de FPs es que el detector flagueó cualquier llamada a una función llamada `connect()` dentro de `async def`, no solo `sqlite3.connect()`. Con 122 hits de `aio-libs/aiopg` (que usa `await connect()` async en todas sus funciones de pool) y 128 hits de `nats-io/nats.py` (probablemente el mismo patrón), la mayoría de los 436 hits son probablemente FPs del mismo tipo.

**Acción urgente:** El detector debe verificar que `connect` sea específicamente `sqlite3.connect` verificando el módulo de origen del símbolo (igual que el problema de PYVIBE-004 con `threading.Lock`). **Degradar a 🔵 Limited Scope hasta que el detector se corrija.** Los TPs reales (IBM mcp-context-forge results_store) son genuinos pero representan ~5-15% del total de hits.
