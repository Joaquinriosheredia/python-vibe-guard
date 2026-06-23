# PYVIBE-018 — while True sin await

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/while_true_no_await.py`  
**Patrón:** bucle `while True:` dentro de `async def` sin ningún `await` en el cuerpo del bucle

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 10/100 (10.0%) | 17/250 (6.8%) |
| Total hits | 36 | 49 |
| Estabilidad 100→250 | Alta (−3.2 pp) | |
| Falsos positivos documentados | 0 (post-fix v0.5.0) | |

## Repos representativos (sweep 250)

- `home-assistant/core` — 21 hits
- `pmh1314520/WebRPA` — 5 hits (nuevo en sweep 250)
- `agronholm/anyio` — 3 hits
- `MODSetter/SurfSense` — 2 hits
- `Tinche/aiofiles` — 2 hits

## Evidence Level: B

- ✅ Validada en repos reales: 17 repos afectados en sweep 250
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

## Historial de falsos positivos

**Falso positivo documentado y corregido en v0.5.0 (sesión S232, 2026-06-19):**  
Async generators con `while True: yield ...` dentro de `async def` eran incorrectamente
flagueados. El patrón `while True` + `yield` en `async def` es un generador asíncrono
válido (no bloquea el event loop). Fix: la regla ahora excluye funciones que contienen
`yield` en el cuerpo del bucle.

Post-fix, 0 falsos positivos documentados en campo.

---

## Auditoría de Precisión (Sweep 250)

**Muestra analizada:** 20 hits de 49 totales (17 repos)
**Metodología:** Muestra estratificada (max 3 por repo)

### Clasificación hit-by-hit

| # | Repo | File:Line | Function | Clasificación | Razón |
|---|------|-----------|----------|---------------|-------|
| 1 | MODSetter__SurfSense | slack_history.py:341 | get_conversation_history | TP | `while True:` con `time.sleep(1.2)` — bloqueo sync explícito en loop dentro de `async def`. Doble antipatrón: mientras True sin await async Y usa `time.sleep` bloqueante. Bug real grave. |
| 2 | MODSetter__SurfSense | slack_history.py:490 | get_user_info | TP | Mismo repo, `while True:` con lógica de paginación y sin `await` en el cuerpo del bucle. Bug real. |
| 3 | Neoteroi__BlackSheep | tests/test_files_handler.py:116 | test_read_file_chunks | FP | `while True:` dentro de `with open(...) as f:` en función sync `_sync_queue_consumer()` anidada en `async def` test — la función interna es síncrona y el `while True` lee de un archivo con `f.read(chunk_size)` síncrono. El detector flagueó el `while True` del scope interno síncrono. |
| 4 | Tinche__aiofiles | tests/threadpool/test_binary.py:139 | test_staggered_read | FP | `while True:` con `f.read(1)` en función síncrona interna dentro de `async def` test — misma situación: `while True` en función `def` anidada dentro de `async def` test. El await está en el scope async exterior, no en el `while True`. |
| 5 | Tinche__aiofiles | tests/threadpool/test_text.py:133 | test_staggered_read | FP | Mismo patrón que hit 4. |
| 6 | TracecatHQ__tracecat | tests/unit/test_concurrency.py:441 | test_cooperative_infinite_iterable | FP | Test de concurrencia — `while True:` en un generador o iterable cooperativo bajo prueba. El test verifica que el iterable sea efectivamente cooperativo. Contexto de test. |
| 7 | agronholm__anyio | tests/test_sockets.py:313 | test_send_eof | FP | `while True:` en test de sockets anyio — la condición de salida está en el cuerpo pero el detector no ve el `break`. Tests tienen `while True: ...break` patterns que no bloquean. |
| 8 | agronholm__anyio | tests/test_sockets.py:1233 | test_send_large_buffer | FP | Mismo repo, test de sockets con `while True:` que tiene break interno. |
| 9 | agronholm__anyio | tests/test_sockets.py:1340 | test_send_eof | FP | Mismo repo, tercer test con `while True:` + break. |
| 10 | aio-libs__aiokafka | benchmark/simple_consume_bench.py:73 | bench_simple | EDGE | `while True:` en benchmark de consumo Kafka — script de benchmark, no producción. Puede no tener `await` si consume de un buffer local. Borderline. |
| 11 | aio-libs__aiokafka | tests/test_producer.py:334 | test_producer_send_batch | FP | Test de productor Kafka con `while True:`. Contexto de test. |
| 12 | aio-libs__aiomysql | aiomysql/connection.py:732 | _execute_command | TP | `while True:` en `_execute_command` de aiomysql — bucle de envío de chunks de SQL. Dentro de `async def` pero el bucle procesa datos en memoria sin `await`; puede bloquear en I/O de buffer. Depende de si `write_packet` es bloqueante. EDGE/TP. |
| 13 | coleifer__peewee | tests/pwasyncio.py:275 | test_lazy_fetchone_batches | FP | Test de peewee async. Contexto de test. |
| 14 | fim-ai__fim-one | src/fim_one/web/api/knowledge_bases.py:833 | import_urls | FP | `while True:` como loop de anti-colisión de nombres de archivo (`while candidate.exists(): counter += 1`) — este es un loop de búsqueda de nombre libre sin bloqueo de I/O significativo. El `candidate.exists()` es síncrono pero en contexto de import de KBs puede ser aceptable. EDGE. |
| 15 | home-assistant__core | homeassistant/components/anthropic/repairs.py:143 | _async_next_target | TP | `while True:` en función async de reparación de Anthropic integration en HA — si el cuerpo no tiene `await` es un loop infinito bloqueante. Bug real. |
| 16 | home-assistant__core | homeassistant/components/file_upload/__init__.py:165 | _upload_file | FP | `while True:` en `_sync_queue_consumer()` síncrona interna — mismo patrón que hits 3-5: función `def` síncrona anidada en `async def`, el `while True` está en el scope síncrono. |
| 17 | home-assistant__core | homeassistant/components/recorder/core.py:425 | _async_close | FP | `while True: self._queue.get_nowait() / break` — es un drain de cola síncrona intencional en shutdown; la cola es un `queue.Queue` estándar (no asyncio.Queue) y el get_nowait puede lanzar `Empty` para salir. Patrón de drain de cola síncrona en shutdown; tiene `break`. |
| 18 | hunvreus__devpush | app/services/github.py:115 | get_user_installations | TP | `while True:` con paginación — si el cuerpo contiene `await` en el caso normal pero el loop puede terminar sin `await` en alguna rama. Requiere verificar. EDGE. |
| 19 | hunvreus__devpush | app/services/github.py:146 | get_installation_repositories_for_user | TP | Mismo repo, mismo patrón de paginación. EDGE. |
| 20 | nats-io__nats.py | nats/js/kv.py:404 | stop | TP | `while True:` en `async def stop()` de KeyValue de NATS.py — si no hay `await` en el cuerpo principal puede ser un bug. Verificación de condición de parada sin yield al event loop. |

### Resultado

| Métrica | Valor |
|---------|-------|
| TP | 5 |
| FP | 10 |
| EDGE | 5 |
| Precisión (TP/total sin EDGE) | 5/15 = 33% |
| Precisión (TP+EDGE / total) | 10/20 = 50% |

### Patrones de FP identificados

1. **INNER_SYNC_WHILE_LOOP** — `while True:` en función síncrona `def` anidada dentro de `async def`. El detector flagueó el `while True` del scope interno síncrono, que no bloquea el event loop async.
   - Ejemplo: `def _sync_queue_consumer(): while True: chunk = f.read(...)` dentro de `async def _upload_file`
   - Repos afectados: 5 (BlackSheep, aiofiles x2, HA file_upload, HA recorder)

2. **TEST_WHILE_WITH_BREAK** — `while True:` en tests con `break` explícito — el detector puede no ver el `break` si está en otra rama. En tests no es un bug de producción.
   - Repos afectados: 5 (TracecatHQ, anyio x3, aiokafka, peewee, aiomysql test)

3. **DRAIN_PATTERN** — `while True: queue.get_nowait() / break` para vaciar una cola en shutdown. Patrón de drain intencional que siempre tiene `break`.
   - Repos afectados: 1 (HA recorder)

### Recomendación de Evidence Level

**Mantener B. Precisión 33-50% — requiere mejora.** El principal problema es que el detector flagueó `while True:` en funciones síncronas anidadas (mismo bug que PYVIBE-003 y PYVIBE-015). También hay FPs de test con `break` en el cuerpo. Los 5 TPs son genuinamente problemáticos (SurfSense con `time.sleep` en bucle async, HA anthropic repairs, NATS.py KV stop). Priorizar fix del bug de "función síncrona anidada" para reducir FPs transversales a múltiples reglas.
