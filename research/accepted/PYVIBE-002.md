# PYVIBE-002 — requests.get/post en async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/async_requests.py`  
**Patrón:** `requests.get(...)` / `requests.post(...)` / etc. dentro de `async def`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 3/100 (3.0%) | 10/250 (4.0%) |
| Total hits | 5 | 14 |
| Estabilidad 100→250 | Alta (+1.0 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `paulpierre/RasaGPT` — 3 hits
- `home-assistant/core` — 2 hits
- `learning-at-home/hivemind` — 2 hits
- `bmoscon/cryptofeed` — 1 hit
- `pydantic/logfire` — 1 hit

## Evidence Level: B

- ✅ Validada en repos reales: 10 repos afectados en muestra de 250
- ⏳ Documentación oficial o incidentes públicos confirmando `requests` sync en async como bug: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

---

## Auditoría de Precisión (Sweep 250)

**Muestra analizada:** 14 hits de 14 totales (10 repos)
**Metodología:** 100% audit (14 hits)

### Clasificación hit-by-hit

| # | Repo | File:Line | Function | Clasificación | Razón |
|---|------|-----------|----------|---------------|-------|
| 1 | BetaStreetOmnis__xhs_ai_publisher | src/core/pages/tools.py:63 | async_process | FP | `requests.post()` dentro de `loop.run_in_executor(None, lambda: requests.post(...))` — la llamada síncrona está correctamente delegada al executor de threads; el comentario en código incluso menciona que se podría usar aiohttp |
| 2 | Kav-K__GPTDiscord | models/openai_model.py:1312 | save_image_urls_and_return | FP | `requests.get()` dentro de `asyncio.get_running_loop().run_in_executor(None, lambda: [...])` — correctamente envuelto en executor |
| 3 | bmoscon__cryptofeed | cryptofeed/exchanges/binance.py:158 | _refresh_token | TP | `requests.put()` directo en `async def _refresh_token`, sin executor. Bug real — bloquea el event loop durante token refresh en un bucle while True |
| 4 | home-assistant__core | homeassistant/components/downloader/services.py:64 | download_file | FP | `requests.get()` dentro de `def do_download()` (función síncrona), que se llama luego con `await service.hass.async_add_executor_job(do_download)` — el detector flagueó la línea del requests.get pero está en una función def interna que se ejecuta en executor |
| 5 | home-assistant__core | homeassistant/components/xmpp/notify.py:274 | upload_file_from_url | FP | `requests.get()` en `def get_url(url)` síncrona interna, llamada con `await hass.async_add_executor_job(get_url, url)` — mismo patrón que hit 4 |
| 6 | learning-at-home__hivemind | hivemind/p2p/p2p_daemon.py:440 | _read_stream | FP | La variable `requests` en este contexto es `asyncio.Queue(max_prefetch)` — no es el módulo `requests`. El detector tiene un FP por colisión de nombre de variable: `requests = asyncio.Queue(...)`, luego `request = await requests.get()` |
| 7 | learning-at-home__hivemind | hivemind/p2p/p2p_daemon.py:477 | _handle_stream | FP | Mismo contexto que hit 6 — `requests` es una `asyncio.Queue`, no el módulo HTTP |
| 8 | paulpierre__RasaGPT | app/rasa-credentials/main.py:65 | get_active_tunnels | TP | `requests.get()` directo en `async def get_active_tunnels()`, sin executor. Bug real. |
| 9 | paulpierre__RasaGPT | app/rasa-credentials/main.py:78 | stop_tunnel | TP | `requests.delete()` directo en `async def stop_tunnel()`. Bug real. |
| 10 | paulpierre__RasaGPT | app/rasa-credentials/main.py:118 | create_tunnel | TP | `requests.post()` directo en `async def create_tunnel()`. Bug real. |
| 11 | pydantic__logfire | tests/otel_integrations/test_requests.py:41 | test_requests_instrumentation | FP | Test async que verifica instrumentación del módulo `requests` — `requests.get()` es el objeto bajo prueba (test de observabilidad). Uso legítimo en test. |
| 12 | python-kasa__python-kasa | kasa/protocols/smartprotocol.py:299 | _execute_multiple_query | FP | La variable `requests` es un `dict` local (mapa de requests al protocolo KASA), no el módulo `requests`. `requests.get(method)` es `dict.get()` en un dict llamado `requests`. Colisión de nombre. |
| 13 | raullenchai__Rapid-MLX | tests/evals/gsm8k/gsm8k_eval.py:136 | evaluate_with_server | EDGE | `requests.post()` en bucle de evaluación async — es un test/benchmark que llama a un servidor local; técnicamente bloquea el loop pero es un script de evaluación no de producción. Contexto borderline. |
| 14 | wyeeeee__hajimi | app/utils/version.py:23 | check_version | TP | `requests.get()` directo en `async def check_version()`, sin executor. Bug real — bloquea el loop en cada check de versión. |

### Resultado

| Métrica | Valor |
|---------|-------|
| TP | 5 |
| FP | 8 |
| EDGE | 1 |
| Precisión (TP/total sin EDGE) | 5/13 = 38% |
| Precisión (TP/total con EDGE) | 5/14 = 36% |

### Patrones de FP identificados

1. **EXECUTOR_WRAPPER** — `requests.*()` dentro de `run_in_executor(None, lambda: ...)` o `async_add_executor_job()`. La llamada síncrona está correctamente delegada al pool de threads.
   - Ejemplo: `await loop.run_in_executor(None, lambda: requests.post(...))`
   - Repos afectados: 2 (xhs_ai_publisher, GPTDiscord) + 2 en Home Assistant (como inner def)

2. **INNER_SYNC_FUNCTION_EXECUTOR** — `requests.*()` en una función `def` interna que luego se pasa a `executor_job`. El detector flagueó la llamada en el scope síncrono pero no detectó que se ejecutará en executor.
   - Ejemplo: `def do_download(): requests.get(...)` → `await hass.async_add_executor_job(do_download)`
   - Repos afectados: 1 (home-assistant/core, 2 instancias)

3. **VARIABLE_NAME_COLLISION** — variable local llamada `requests` que no es el módulo HTTP (puede ser un dict, una Queue, etc.).
   - Ejemplo: `requests = asyncio.Queue(max_prefetch)` → detector flagueó `requests.get()` como llamada HTTP
   - Ejemplo: `requests = {}` (dict) → `requests.get(method)` es un dict lookup
   - Repos afectados: 2 (hivemind, python-kasa)

4. **TEST_SUBJECT** — test async que verifica el módulo `requests` como objeto bajo prueba para instrumentación.
   - Repos afectados: 1 (pydantic/logfire)

### Recomendación de Evidence Level

**Mantener B. Precisión preocupante: 36-38%.** El problema principal es triple: (a) colisiones de nombre de variable (`requests` como nombre de dict/Queue), (b) `requests.*()` en funciones `def` síncronas internas que se pasan a executor, (c) test subjects. El detector necesita mejorar: verificar que `requests` sea realmente el módulo importado (no una variable local), y detectar el patrón `run_in_executor` en el contexto inmediato. Los 5 TP reales son genuinamente problemáticos. **FP rate alto (62%) requiere acción antes de considerar elevación a Evidence A.**
