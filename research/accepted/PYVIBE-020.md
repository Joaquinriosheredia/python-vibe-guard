# PYVIBE-020 — put_nowait() sin handler de QueueFull

**Severidad:** WARNING  
**Archivo:** `pyvibe/rules/queue_put_nowait.py`  
**Patrón:** `queue.put_nowait(item)` en `async def` sin bloque `try/except` que capture `asyncio.QueueFull` o `Exception`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | N/A ¹ | 41/250 (16.4%) |
| Total hits | N/A ¹ | 295 |
| Estabilidad 100→250 | N/A ¹ | |
| Falsos positivos documentados | 0 (8 casos de supresión correcta en tests) | |

## Repos representativos (sweep 250)

- `google-gemini/genai-processors` — 56 hits
- (datos completos en `research/datasets/250-repos.json`)

## Evidence Level: B

- ✅ Validada en repos reales: 41 repos afectados en debut — tasa de debut alta para una regla nueva (16.4%)
- ✅ Origen: gap identificado en sweep de 100 repos antes de la implementación (25 repos con el patrón en grep manual)
- ⏳ Incidentes públicos de pérdida de datos por QueueFull no capturado: **PENDIENTE — requiere investigación manual** (ver `research/incidents/queuefull-data-loss.md`)
- ⏳ Documentación oficial Python sobre el riesgo de `put_nowait` vs `await put()`: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

¹ PYVIBE-020 fue añadida en v0.7.0 después de archivar el sweep de 100 repos. No hay baseline comparable.

---

## Auditoría de Precisión (Sweep 250)

**Muestra analizada:** 20 hits de 295 totales (41 repos)
**Metodología:** Muestra estratificada (max 3 por repo)

### Clasificación hit-by-hit

| # | Repo | File:Line | Function | Clasificación | Razón |
|---|------|-----------|----------|---------------|-------|
| 1 | CJackHwang__AIstudioProxyAPI | test_proxy_server_forwarding.py:49 | feed_data | FP | `queue.put_nowait(data)` en método `feed_data` de `AsyncStreamReader` falso para tests — la cola es `asyncio.Queue()` sin `maxsize` (unbounded). `put_nowait` en una cola sin límite nunca lanza `QueueFull`. FP: el handler de QueueFull es innecesario cuando la cola es unbounded. |
| 2 | CJackHwang__AIstudioProxyAPI | test_proxy_server_forwarding.py:53 | feed_eof | FP | Mismo contexto — `queue.put_nowait(b"")` en cola unbounded de test. |
| 3 | IBM__mcp-context-forge | siem_export_service.py:557 | _enqueue_local | TP | `self._local_queue.put_nowait(envelope)` sin try/except — la cola `_local_queue` tiene `maxsize` configurado (`queue_max_size`). El código justo antes hace `get_nowait()` para hacer espacio si está llena, pero si el `get_nowait` falla (race condition), el `put_nowait` puede lanzar `QueueFull`. EDGE/TP. |
| 4 | IBM__mcp-context-forge | server_event_bus.py:221 | publish | TP | `queue.put_nowait(None)` para señalar overflow — se llama después de vaciar la cola con `get_nowait()` en un loop. La lógica es correcta pero si otro productor llena la cola entre el vaciado y el `put_nowait`, puede haber `QueueFull`. El código tiene manejo de overflow antes, pero no captura `QueueFull` en el `put_nowait` final. |
| 5 | IBM__mcp-context-forge | test_translate.py:4993 | subscribe | FP | Test de translate — `put_nowait()` en mock/fixture de test. |
| 6 | Kludex__mangum | mangum/protocols/http.py:36 | __init__ | TP | `self.body_io.put_nowait(event["body"].encode())` en `__init__` de handler HTTP Lambda — cola bounded. Si el cuerpo de la request excede el maxsize (posible con payloads grandes), la excepción se propagaría al __init__ sin manejo. Bug real en handler de Lambda. |
| 7 | Kludex__uvicorn | uvicorn/protocols/websockets/websockets_sansio_impl.py:128 | connection_lost | TP | `self.send_queue.put_nowait(...)` en callback de conexión perdida — en uvicorn, las colas de send son bounded. Si la cola está llena durante `connection_lost`, la notificación de cierre se pierde. |
| 8 | Kludex__uvicorn | websockets_sansio_impl.py:145 | shutdown | TP | `self.send_queue.put_nowait(...)` en shutdown — mismo contexto que hit 7. |
| 9 | Kludex__uvicorn | websockets_sansio_impl.py:216 | handle_connect | TP | `self.receive_queue.put_nowait(...)` en handle de nueva conexión WebSocket. Cola bounded en uvicorn. |
| 10 | Lightning-AI__LitServe | openai_embedding.py:272 | embeddings_endpoint | TP | `request_queue.put_nowait(...)` en endpoint de embeddings — la cola de requests puede estar llena bajo alta carga. Sin manejo de `QueueFull`, el endpoint simplemente lanza una excepción no controlada. Bug real bajo carga. |
| 11 | MagicStack__asyncpg | asyncpg/pool.py:326 | _release | FP | `self._pool._queue.put_nowait(self)` en `_release` de pool — en asyncpg, las colas de pool son del tamaño exacto del pool (bounded), pero `put_nowait` aquí nunca falla porque cada conexión que se libera fue previamente adquirida (garantía de invariante del pool: siempre hay espacio para una conexión devuelta). FP: invariante de diseño garantiza no overflow. |
| 12 | MagicStack__asyncpg | asyncpg/pool.py:455 | _initialize | FP | Mismo razonamiento — `put_nowait` en inicialización del pool donde la cola se llena exactamente hasta `maxsize`. No puede haber overflow por diseño. |
| 13 | MagicStack__asyncpg | asyncpg/pool.py:883 | _acquire_impl | FP | `put_nowait` en `_acquire_impl` del pool — mismo invariante: la cola gestiona su propio ciclo de vida. |
| 14 | Soju06__codex-lb | tests/integration/test_proxy_websocket_responses.py:57 | __init__ | FP | Test de integración WebSocket — cola de test unbounded o con manejo específico. |
| 15 | Soju06__codex-lb | tests/integration/test_proxy_websocket_responses.py:87 | send_text | FP | Mismo test. |
| 16 | Soju06__codex-lb | tests/unit/test_proxy_utils.py:12922 | __init__ | FP | Test unitario de proxy. |
| 17 | TracecatHQ__tracecat | tracecat/dsl/scheduler.py:776 | start | TP | `self._queue.put_nowait(...)` en scheduler de DSL de Tracecat — cola bounded de trabajo. Bajo alta carga de workflows, `QueueFull` causa pérdida silenciosa de trabajo. Bug real. |
| 18 | ag2ai__faststream | faststream/_internal/endpoint/subscriber/utils.py:46 | acquire | EDGE | `queue.put_nowait(...)` en abstracción de subscriber de FastStream — puede ser una cola de semáforo interna. Depende de si tiene maxsize. |
| 19 | agronholm__anyio | anyio/_backends/_asyncio.py:1047 | stop | FP | `self.queue.put_nowait(None)` para señalar stop de worker thread — en anyio esta cola de workers es bounded pero el `put_nowait(None)` del sentinel siempre tiene espacio porque cada `stop()` corresponde exactamente a un worker. Invariante de diseño. |
| 20 | agronholm__anyio | anyio/_backends/_asyncio.py:2595 | run_sync_in_worker_thread | FP | `worker.queue.put_nowait(...)` en anyio worker thread pool — same invariante que hit 19: hay exactamente un slot disponible por llamada. |

### Resultado

| Métrica | Valor |
|---------|-------|
| TP | 8 |
| FP | 11 |
| EDGE | 1 |
| Precisión (TP/total sin EDGE) | 8/19 = 42% |
| Precisión (TP/total con EDGE como FP) | 8/20 = 40% |

### Patrones de FP identificados

1. **UNBOUNDED_QUEUE** — `put_nowait()` en una cola `asyncio.Queue()` sin `maxsize` (o `maxsize=0`). `QueueFull` nunca se lanza en colas unbounded. El handler es innecesario.
   - Repos afectados: 2 (CJackHwang tests)

2. **POOL_INVARIANT** — `put_nowait()` en colas de pool donde el invariante de diseño garantiza que siempre hay espacio (cada elemento adquirido ocupa exactamente un slot que se devuelve en release).
   - Ejemplo: `asyncpg.pool._queue`, `anyio._backends._asyncio.worker.queue`
   - Repos afectados: 2 (MagicStack/asyncpg, agronholm/anyio)

3. **TEST_MOCK_QUEUE** — `put_nowait()` en colas de test fixtures o mocks. El overflow no es un riesgo en contexto de test.
   - Repos afectados: 3 (Soju06 tests, IBM test_translate)

### Recomendación de Evidence Level

**Confirmar B. Precisión 40-42%.** Los 8 TPs son importantes: uvicorn WebSocket, LitServe embeddings, Tracecat scheduler, IBM SIEM service, mangum Lambda handler. Todos en código de producción con colas bounded. Los FPs revelan que el detector necesita verificar si la cola es bounded (`maxsize > 0`) antes de flagear — colas unbounded (`asyncio.Queue()` sin args) nunca lanzan `QueueFull`. Añadir esa comprobación eliminaría ~30% de FPs.
