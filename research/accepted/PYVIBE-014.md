# PYVIBE-014 — asyncio.ensure_future() huérfano

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/ensure_future_orphan.py`  
**Patrón:** `asyncio.ensure_future(coro())` como statement sin capturar la referencia devuelta

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 8/100 (8.0%) | 14/250 (5.6%) |
| Total hits | 16 | 33 |
| Estabilidad 100→250 | Alta (−2.4 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `faust-streaming/faust` — 5 hits
- `Kav-K/GPTDiscord` — 4 hits (nuevo en sweep 250)
- `pmh1314520/WebRPA` — 4 hits (nuevo en sweep 250)
- `postlund/pyatv` — 4 hits (nuevo en sweep 250)
- `aiortc/aiortc` — 3 hits

## Evidence Level: B

- ✅ Validada en repos reales: 14 repos, 33 hits
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

---

## Auditoría de Precisión (Sweep 250)

**Muestra analizada:** 20 hits de 33 totales (14 repos)
**Metodología:** Muestra estratificada (max 3 por repo)

### Clasificación hit-by-hit

| # | Repo | File:Line | Function | Clasificación | Razón |
|---|------|-----------|----------|---------------|-------|
| 1 | Kav-K__GPTDiscord | cogs/image_service_cog.py:71 | draw_command | TP | `asyncio.ensure_future(ImageService.encapsulated_send(...))` como statement sin capturar referencia — la tarea puede silenciar excepciones y ser cancelada sin aviso. Bug real en handler de Discord. |
| 2 | Kav-K__GPTDiscord | cogs/image_service_cog.py:121 | draw_old_command | TP | Mismo patrón — `ensure_future()` sin capturar referencia en handler de comando antiguo. |
| 3 | Kav-K__GPTDiscord | services/image_service.py:339 | callback | TP | `asyncio.ensure_future(...)` en callback de servicio de imagen. Tarea huérfana. |
| 4 | MagicStack__asyncpg | tests/test_pool.py:483 | test_pool_no_acquire_deadlock | FP | Test que verifica comportamiento de deadlock — el `ensure_future()` sin capturar referencia es parte del setup del escenario de test (crear tareas que competirán por una conexión). Uso intencional en test. |
| 5 | aiogram__aiogram | aiogram/dispatcher/dispatcher.py:472 | feed_webhook_update | EDGE | `asyncio.ensure_future(self.process_update(update))` en dispatcher de aiogram — en el contexto de webhook el framework gestiona el ciclo de vida de las tareas a través del event loop. Puede ser diseño intencional del framework. |
| 6 | aiortc__aiortc | examples/datachannel-cli/cli.py:81 | run_offer | TP | `asyncio.ensure_future(consume(channel))` en ejemplo de WebRTC — tarea huérfana que procesa datos de canal. Si `run_offer` termina antes que la tarea, la tarea se cancela silenciosamente. |
| 7 | aiortc__aiortc | src/aiortc/rtcpeerconnection.py:868 | setLocalDescription | TP | `asyncio.ensure_future(self.__connect())` en método de conexión RTC — tarea huérfana crítica. Si la conexión falla la excepción se pierde silenciosamente. Bug real en código de producción. |
| 8 | aiortc__aiortc | src/aiortc/rtcpeerconnection.py:1057 | setRemoteDescription | TP | Mismo patrón — `ensure_future(self.__connect())` sin capturar referencia. Bug real. |
| 9 | elliotgao2__gain | gain/parser.py:77 | task | TP | `asyncio.ensure_future(...)` en parser de scraper — tarea huérfana. |
| 10 | faust-streaming__faust | examples/livecheck.py:139 | create_order | FP | Ejemplo de livecheck de Faust — el `ensure_future()` en un ejemplo/script de demostración. Contexto de ejemplo, no producción crítica. |
| 11 | faust-streaming__faust | tests/consistency/test_consistency.py:82 | start | FP | Test de consistencia de Faust — `ensure_future()` en setup de test. |
| 12 | faust-streaming__faust | tests/functional/test_streams.py:674 | test_noack_take__10 | FP | Test funcional de streams de Faust. |
| 13 | home-assistant__core | tests/components/anova/conftest.py:81 | connect | FP | Fixture de test en Home Assistant — `ensure_future()` para simular conexión de dispositivo en test. |
| 14 | mirumee__ariadne | ariadne/asgi/handlers/graphql_ws.py:247 | handle_websocket_connection_init_message | TP | `asyncio.ensure_future(...)` en handler WebSocket de Ariadne — tarea huérfana en código de producción. |
| 15 | mirumee__ariadne | ariadne/asgi/handlers/graphql_ws.py:340 | start_websocket_operation | TP | Mismo repo — `ensure_future()` para operación WebSocket. Bug real. |
| 16 | modoboa__modoboa | modoboa/policyd/core.py:150 | decrement_limit | TP | `asyncio.ensure_future(...)` en daemon de policy de email — tarea huérfana en producción. |
| 17 | modoboa__modoboa | modoboa/policyd/core.py:273 | reset_counters | TP | Mismo repo — `ensure_future()` sin capturar en función de reset de contadores. |
| 18 | nats-io__nats.py | nats/tests/test_client.py:635 | test_subscribe_iterate | FP | Test del cliente NATS — `ensure_future()` para setup de suscriptor concurrente en test. |
| 19 | pallets__quart | tests/wrappers/test_request.py:28 | test_full_body | FP | Test de Quart — `ensure_future()` en test de request body. |
| 20 | pallets__quart | tests/wrappers/test_request.py:36 | test_body_streaming | FP | Mismo repo, test de streaming. |

### Resultado

| Métrica | Valor |
|---------|-------|
| TP | 11 |
| FP | 8 |
| EDGE | 1 |
| Precisión (TP/total sin EDGE) | 11/19 = 58% |
| Precisión (TP/total con EDGE como FP) | 11/20 = 55% |

### Patrones de FP identificados

1. **TEST_CONCURRENT_SETUP** — `ensure_future()` para crear tareas concurrentes en setup de tests o fixtures. El huérfano es intencional en el contexto de test (se espera que el test gestione el lifecycle).
   - Repos afectados: 7 (asyncpg, faust tests, HA conftest, nats.py test, quart tests)

2. **FRAMEWORK_FIRE_AND_FORGET** — `ensure_future()` en dispatcher/handler de framework donde el framework gestiona el event loop (aiogram webhook dispatcher). Puede ser diseño intencional del framework.
   - Repos afectados: 1 (aiogram)

### Recomendación de Evidence Level

**Confirmar B. Precisión 55-58%.** Los TPs son genuinamente problemáticos: aiortc usa `ensure_future` para conectar streams RTC sin capturar errores, Ariadne para operaciones WebSocket, modoboa para política de email. Los FPs son principalmente tests (8/9). Aplicar `TEST_FILE_DOWNGRADE` reduciría FPs significativamente. Precisión en código de producción estimada en ~70-80%.
