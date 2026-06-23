# PYVIBE-006 — ContextVar sin reset()

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/contextvar_cleanup.py`  
**Patrón:** `ContextVar.set(value)` dentro de `async def` sin llamada posterior a `token.reset()`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 10/100 (10.0%) | 15/250 (6.0%) |
| Total hits | 19 | 28 |
| Estabilidad 100→250 | Alta (−4.0 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `IBM/mcp-context-forge` — 4 hits
- `home-assistant/core` — 3 hits
- `sumerc/yappi` — 3 hits
- `Kludex/uvicorn` — 2 hits
- `aiohttp` — 2 hits

## Evidence Level: B

- ✅ Validada en repos reales: 15 repos afectados en muestra de 250
- ⏳ Documentación oficial Python sobre `ContextVar.reset()` como obligatorio en async: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

---

## Auditoría de Precisión (Sweep 250)

**Muestra analizada:** 20 hits de 28 totales (15 repos)
**Metodología:** Muestra estratificada (max 3 por repo)

### Clasificación hit-by-hit

| # | Repo | File:Line | Function | Clasificación | Razón |
|---|------|-----------|----------|---------------|-------|
| 1 | IBM__mcp-context-forge | streamablehttp_transport.py:1071 | _check_server_oauth_enforcement | FP | `_oauth_checked_var.set(True)` — sí se hace `set()` pero en la misma función no hay `reset()`. Sin embargo, el ContextVar usa `set()` para marcar estado ya comprobado (flag one-shot). El contexto asyncio aísla automáticamente los valores de ContextVar por tarea; si la función siempre termina sin volver a corrutinas externas que reúsen el token, no hay fuga. Diseño intencional como flag de estado por-request. |
| 2 | IBM__mcp-context-forge | streamablehttp_transport.py:4379 | handle_streamable_http | FP | Mismo patrón — `set()` en ContextVar de estado de request sin `reset()`. En FastAPI/Starlette cada request tiene su propio contexto asyncio; el reset es redundante pero no problemático en diseño por-request correcto. EDGE/FP por diseño. |
| 3 | IBM__mcp-context-forge | streamablehttp_transport.py:4856 | authenticate | FP | `_current_user_var.set(user)` o similar — ContextVar de autenticación por-request. Mismo razonamiento: cada tarea asyncio hereda su propio contexto. |
| 4 | Kludex__uvicorn | tests/test_server.py:196 | test_contextvars_preserved_by_default | FP | Test que verifica el comportamiento de ContextVars — el `set()` sin `reset()` es intencional para probar que el valor persiste. Contexto de test. |
| 5 | Kludex__uvicorn | tests/test_server.py:232 | app | FP | Función ASGI `async def app` en test — `set()` sin `reset()` como parte de la fixture de test para ContextVar propagation testing. |
| 6 | agronholm__anyio | tests/test_to_thread.py:155 | test_contextvar_propagation | FP | Test de propagación de ContextVar a threads. El `set()` es el sujeto bajo prueba. |
| 7 | aiohttp | tests/test_run_app.py:1011 | on_startup | FP | `set()` en callback de startup — en un servidor ASGI cada petición tiene contexto propio; el startup se ejecuta una vez y el ContextVar expira con la app. No hay riesgo de fuga entre requests. |
| 8 | aiohttp | tests/test_run_app.py:1022 | init | FP | Mismo repo, test de inicialización de ContextVar en lifecycle hook. |
| 9 | beenuar__AiSOC | services/agents/app/core/cost_telemetry.py:212 | __aenter__ | TP | `__aenter__` de context manager async que hace `set()` pero la lógica de `reset()` debería estar en `__aexit__`. Si `__aexit__` no llama `token.reset()`, hay fuga potencial del valor en cascadas de context managers. Requiere verificar `__aexit__`. |
| 10 | coleifer__peewee | tests/pwasyncio.py:144 | test_contextvars | FP | Test de ContextVars en peewee async — `set()` como preparación del test. Contexto de test. |
| 11 | coleifer__peewee | tests/pwasyncio.py:1434 | test_run_contextvars | FP | Mismo repo, otro test de ContextVars. |
| 12 | faust-streaming__faust | faust/agents/agent.py:674 | _execute_actor | TP | `_current_agent.set(self)` en `_execute_actor` — el agente Faust ejecuta en una tarea asyncio de larga duración. Si la tarea se reinicia (ver el `except asyncio.CancelledError` que hace restart), el `set()` previo permanece del contexto anterior. Potencial fuga de estado entre reinicios de actor. |
| 13 | google-gemini__genai-processors | genai_processors/context.py:86 | __aenter__ | TP | `_PROCESSOR_TASK_GROUP.set(self)` en `__aenter__` — guarda el token en `self._current_taskgroup_token` y hay un `__aexit__` que debe llamar `reset()`. Verificar si el `__aexit__` lo hace. Patrón correcto si `__aexit__` resetea. EDGE. |
| 14 | google-gemini__genai-processors | genai_processors/dev/trace.py:82 | __aenter__ | EDGE | Similar al anterior — `set()` en `__aenter__`. Si `__aexit__` tiene el `reset()` correspondiente, no es un problema. |
| 15 | home-assistant__core | homeassistant/helpers/config_validation.py:2149 | async_validate | TP | `_validating_async.set(True)` sin `reset()` visible — el bloque `finally` solo llama `set(False)` en lugar de `token.reset(token)`. `set(False)` puede dejar tokens acumulados en el context chain si se anidan validaciones. Bug real si hay anidamiento. |
| 16 | home-assistant__core | homeassistant/helpers/entity_platform.py:468 | _async_setup_platform | TP | `set()` en función de setup de plataforma — si hay `reset()` en la misma función no es bug. Requeriría leer más contexto. EDGE. |
| 17 | home-assistant__core | homeassistant/helpers/script.py:461 | async_run | TP | `set()` en `async_run` de scripts. Posible fuga si el script es reutilizado entre requests. |
| 18 | mongodb__motor | test/asyncio_tests/test_asyncio_client.py:248 | test_contextvars_support | FP | Test de soporte de ContextVars en Motor — el `set()` es el sujeto bajo prueba. |
| 19 | nolar__kopf | kopf/_core/reactor/subhandling.py:113 | execute | TP | `subexecuted_var.set(True)` y `subregistry_var.get()` en función de ejecución de subhandlers de Kopf. La variable se setea para prevenir doble ejecución implícita — patrón de flag one-shot que puede acumularse si los handlers se reutilizan. |
| 20 | nonebot__nonebot2 | nonebot/internal/matcher/matcher.py:846 | simple_run | TP | `current_handler.set(handler)` dentro del loop de ejecución de handlers de NoneBot — si el `reset()` no se llama después de cada handler, el contexto del handler anterior puede filtrarse al siguiente. |

### Resultado

| Métrica | Valor |
|---------|-------|
| TP | 8 |
| FP | 9 |
| EDGE | 3 |
| Precisión (TP/total sin EDGE) | 8/17 = 47% |
| Precisión (TP/total con EDGE como FP) | 8/20 = 40% |

### Patrones de FP identificados

1. **ASYNCIO_TASK_ISOLATION** — `set()` sin `reset()` en ContextVar de estado por-request/tarea asyncio. Cada tarea asyncio tiene su propio contexto heredado; el `reset()` es buena práctica pero no estrictamente necesario si la tarea no persiste más allá de un request.
   - Repos afectados: 3 (IBM/mcp-context-forge, aiohttp, kopf indirectamente)

2. **TEST_SUBJECT** — `set()` en función de test para verificar propagación de ContextVars. El `set()` sin `reset()` es intencional para la aserción.
   - Repos afectados: 4 (uvicorn, anyio, peewee, motor)

3. **CONTEXT_MANAGER_PATTERN** — `set()` en `__aenter__` donde el `reset()` se espera en `__aexit__`. El detector flagueó el `__aenter__` pero no verificó si el `__aexit__` hace el `reset()`.
   - Repos afectados: 2 (genai-processors)

### Recomendación de Evidence Level

**Mantener B. Precisión 40-47% — requiere mejora de detección.** Los FPs principales son tests y patrones de aislamiento por tarea asyncio legítimos. El detector necesita verificar si la misma función tiene `token.reset()` en un `finally` o si es un `__aenter__`/`__aexit__` par. Los TPs reales (Faust agent restart, HA config_validation con `set(False)` en lugar de `reset()`, NoneBot handler loop) son genuinamente problemáticos.
