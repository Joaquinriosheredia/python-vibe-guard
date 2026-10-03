# PYVIBE-012 — asyncio.create_task() huérfano

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/create_task_orphan.py`  
**Patrón:** `asyncio.create_task(coro())` como statement sin capturar la referencia devuelta

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 13/100 (13.0%) | 30/250 (12.0%) |
| Total hits | 58 | 135 |
| Estabilidad 100→250 | Alta (−1.0 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `learning-at-home/hivemind` — 17 hits
- `chenyme/grok2api` — 16 hits
- `Amm1rr/WebAI-to-API` — 16 hits (nuevo en sweep 250)
- `fim-ai/fim-one` — 14 hits (nuevo en sweep 250)
- `nats-io/nats.py` — 11 hits (nuevo en sweep 250)

## Evidence Level: B

- ✅ Validada en repos reales: 30 repos, 135 hits — estabilidad muy alta (solo −1 pp)
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

---

## Auditoría de Precisión (Sweep 250)

**Muestra analizada:** 20 hits de 135 totales (30 repos)
**Metodología:** Muestra estratificada (max 3 por repo)

### Clasificación hit-by-hit

| # | Repo | File:Line | Function | Clasificación | Razón |
|---|------|-----------|----------|---------------|-------|
| 1 | Amm1rr__WebAI-to-API | session.py:558 | _autosave_loop | TP | `asyncio.create_task(self.handle_session_failure())` sin capturar referencia — en manejo de error de un loop de autosave. Si la tarea falla silenciosamente, el session failure no se maneja. Bug real. |
| 2 | Amm1rr__WebAI-to-API | session.py:635 | _eviction_loop | TP | `asyncio.create_task(...)` sin capturar en loop de evicción de sesiones. Tarea huérfana en background crítico. |
| 3 | Amm1rr__WebAI-to-API | session.py:741 | _reaper_loop | TP | Mismo patrón en loop de reaper de sesiones. |
| 4 | CJackHwang__AIstudioProxyAPI | tests/api_utils/routers/test_chat.py:33 | test_chat_completions_success | FP | `asyncio.create_task(...)` en test — setup de tarea concurrente para verificar comportamiento de chat. Contexto de test. |
| 5 | CJackHwang__AIstudioProxyAPI | tests/api_utils/routers/test_chat.py:132 | test_chat_completions_cancelled | FP | Test de cancelación — el `create_task` sin captura es intencional para testear comportamiento de cancelación. |
| 6 | CJackHwang__AIstudioProxyAPI | tests/api_utils/routers/test_chat.py:181 | test_chat_completions_http_exception_499 | FP | Test de excepción HTTP 499. Mismo contexto de test. |
| 7 | IBM__mcp-context-forge | test_elicitation_service.py:73 | test_create_elicitation_and_complete | FP | Test de servicio de elicitación — `create_task()` en setup de test. |
| 8 | Kludex__uvicorn | tests/test_server.py:82 | test_server_interrupt | FP | Test de interrupción de servidor uvicorn — `create_task()` para simular interrupt en test. |
| 9 | Kludex__uvicorn | tests/test_server.py:118 | test_shutdown_on_early_exit_during_startup | FP | Test de shutdown. Contexto de test. |
| 10 | MagicStack__asyncpg | asyncpg/connect_utils.py:1243 | _connect | EDGE | `asyncio.create_task(_close_candidates(...))` sin capturar — en el bloque `finally` de una conexión para cerrar candidatos no elegidos. En asyncpg (librería de bajo nivel), el patrón fire-and-forget en `finally` para limpiar recursos puede ser intencional. EDGE: el argumento "best effort cleanup" es válido en librerías de conexión. |
| 11 | Neoteroi__BlackSheep | blacksheep/client/connection.py:1164 | _wait_for_100_continue | TP | `asyncio.create_task(self._read_response_body(incoming_content))` — inicia lectura del cuerpo de respuesta en background. Si la tarea falla (excepción de red), el error se pierde silenciosamente. Bug real en cliente HTTP de producción. |
| 12 | Neoteroi__BlackSheep | blacksheep/client/connection.py:1316 | _receive_response | TP | Mismo repo — otro `create_task()` sin captura en recepción de respuesta HTTP. |
| 13 | Soju06__codex-lb | app/modules/oauth/service.py:438 | manual_callback | TP | `asyncio.create_task(...)` sin captura en callback OAuth manual. Tarea huérfana en flujo de autenticación crítico. |
| 14 | Soju06__codex-lb | app/modules/oauth/service.py:521 | _handle_callback | TP | Mismo repo — `create_task()` en handler de callback OAuth. |
| 15 | Soju06__codex-lb | tests/unit/test_work_admission_wait.py:62 | test_admission_succeeds... | FP | Test unitario de codex-lb. |
| 16 | TracecatHQ__tracecat | tracecat/api/app.py:206 | lifespan | EDGE | `asyncio.create_task(add_temporal_search_attributes())` en lifespan de startup — el comentario dice "Run in background to avoid blocking startup". Uso intencional de fire-and-forget en startup de app. EDGE: en lifespan, la tarea se ejecutará en el contexto de la app y puede ser recogida por el event loop. |
| 17 | aio-libs__aiocache | aiocache/decorators.py:74 | decorator | EDGE | `asyncio.create_task(self.set_in_cache(key, result))` — el TODO en el código dice "Use aiojobs to avoid warnings". El proyecto es consciente del huérfano y planea corregirlo. EDGE: antipatrón conocido que el autor planea arreglar. |
| 18 | aio-libs__aiocache | aiocache/decorators.py:276 | decorator | EDGE | Mismo patrón en aiocache decorators. |
| 19 | aiogram__aiogram | tests/test_dispatcher/test_dispatcher.py:1157 | startup | FP | Test de dispatcher de aiogram. |
| 20 | beenuar__AiSOC | services/fusion/app/services/ml_scorer.py:324 | _maybe_retrain | TP | `asyncio.create_task(self._retrain_background(...))` sin captura — inicia reentrenamiento de modelo ML en background. Si el reentrenamiento falla silenciosamente, el modelo deja de actualizarse sin notificación. Bug real en sistema de producción. |

### Resultado

| Métrica | Valor |
|---------|-------|
| TP | 8 |
| FP | 8 |
| EDGE | 4 |
| Precisión (TP/total sin EDGE) | 8/16 = 50% |
| Precisión (TP/total con EDGE como FP) | 8/20 = 40% |

### Patrones de FP identificados

1. **TEST_CONCURRENT_TASK** — `create_task()` sin captura en tests para crear concurrencia de prueba. El huérfano es intencional en el contexto de test.
   - Repos afectados: 6 (CJackHwang, IBM, uvicorn, Soju06 test, aiogram)

2. **INTENTIONAL_FIRE_AND_FORGET_STARTUP** — `create_task()` en lifespan de startup para ejecutar tareas no bloqueantes. Diseño intencional del autor con comentario explicativo.
   - Repos afectados: 1 (TracecatHQ/tracecat)

3. **KNOWN_ISSUE_PENDING_FIX** — el autor es consciente del antipatrón y planea corregirlo (TODO en código).
   - Repos afectados: 1 (aio-libs/aiocache)

### Recomendación de Evidence Level

**Confirmar B. Precisión 40-50%.** Los 8 TPs son genuinamente problemáticos: bucles de background de sesión (WebAI), cliente HTTP (BlackSheep), flujos OAuth críticos (codex-lb), reentrenamiento ML (AiSOC). Los FPs son principalmente tests. Aplicar `TEST_FILE_DOWNGRADE` elevaría la precisión en producción a ~65-75%. Los EDGE de asyncpg y aiocache representan trade-offs de librería de bajo nivel (valid design decisions que merecen configuración de supresión).
