# PYVIBE-007 — subprocess.run/call en async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/subprocess_async.py`  
**Patrón:** `subprocess.run(...)` / `subprocess.call(...)` / `subprocess.check_output(...)` dentro de `async def`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 6/100 (6.0%) | 12/250 (4.8%) |
| Total hits | 16 | 61 |
| Estabilidad 100→250 | Alta (−1.2 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `pmh1314520/WebRPA` — 31 hits (nuevo en sweep 250)
- `IBM/mcp-context-forge` — 8 hits
- `nats-io/nats.py` — 8 hits (nuevo en sweep 250)
- `chopratejas/headroom` — 2 hits
- `plastic-labs/honcho` — 2 hits

## Evidence Level: B

- ✅ Validada en repos reales: 12 repos, 61 hits — los hits se multiplican en sweep 250 por `pmh1314520/WebRPA` y `nats-io/nats.py`
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

---

## Auditoría de Precisión (Sweep 250)

**Muestra analizada:** 20 hits de 61 totales (12 repos)
**Metodología:** Muestra estratificada (max 3 por repo)

### Clasificación hit-by-hit

| # | Repo | File:Line | Function | Clasificación | Razón |
|---|------|-----------|----------|---------------|-------|
| 1 | BetaStreetOmnis__xhs_ai_publisher | write_xiaohongshu.py:686 | _auto_install_playwright_chromium | FP | `subprocess.run(cmd, ...)` dentro de `loop.run_in_executor(None, _run)` — la función `_run` es un wrapper síncrono que se pasa al executor. El `subprocess.run` está en `def _run()` síncrono. El detector no vio el executor wrapper. |
| 2 | Evil0ctal__Douyin_TikTok_Download_API | download.py:85 | merge_bilibili_video_audio | TP | `subprocess.run(ffmpeg_cmd, ...)` directo en `async def merge_bilibili_video_audio()` sin executor. Bloquea el event loop durante el merge de video con FFmpeg (potencialmente varios segundos). Bug real. |
| 3 | IBM__mcp-context-forge | test_mcp_client.py:16 | main | FP | Script de test/utility — `main()` es una función que lanza un cliente MCP. Contexto de script de test/CLI, no servidor de producción. |
| 4 | IBM__mcp-context-forge | test_session_registry_redis_integration.py:67 | test_redis_broadcast_integration | FP | Test de integración con Redis — `subprocess.run()` para lanzar un proceso Redis de test. Uso legítimo en test de integración. |
| 5 | IBM__mcp-context-forge | test_session_registry_redis_integration.py:96 | test_redis_broadcast_integration | FP | Mismo test, otra instancia. |
| 6 | TracecatHQ__tracecat | benchmark/executor_load_api.py:129 | get_postgres_connections | FP | Script de benchmark — `subprocess.run()` para obtener conexiones de Postgres en benchmark. Script CLI, no servidor. |
| 7 | TracecatHQ__tracecat | benchmark/executor_load_api.py:172 | get_postgres_connections | FP | Mismo script de benchmark. |
| 8 | XiaoYouChR__Ghost-Downloader-3 | app/supports/hidden_subprocess.py:19 | createHiddenSubprocess | TP | `subprocess.run()` en `async def createHiddenSubprocess()` — bloquea el event loop. Bug real en función helper de la app. |
| 9 | beenuar__AiSOC | services/api/app/services/plugin_manager.py:670 | install_from_oci | TP | `subprocess.run()` o similar en `async def install_from_oci()` — instalación de plugin desde OCI. Puede tardar segundos o minutos. Bug real en producción. |
| 10 | chopratejas__headroom | tests/e2e_ws_codex_usage_headers.py:135 | main_async | FP | Test e2e — `subprocess.run()` para lanzar servidor en test e2e. Uso legítimo en test. |
| 11 | chopratejas__headroom | tests/e2e_ws_responses_compression.py:155 | main_async | FP | Otro test e2e del mismo repo. |
| 12 | nats-io__nats.py | nats-core/tests/test_examples.py:81 | test_pub_sub_example | FP | Test de ejemplos de NATS — `subprocess.run()` para lanzar servidor NATS en test. |
| 13 | nats-io__nats.py | nats-core/tests/test_examples.py:99 | test_pub_sub_example | FP | Mismo test, distinta instancia. |
| 14 | nats-io__nats.py | nats-core/tests/test_examples.py:128 | test_request_reply_example | FP | Test de ejemplo de request/reply de NATS. |
| 15 | plastic-labs__honcho | tests/bench/harness.py:777 | cleanup | FP | Función de cleanup de benchmark — `subprocess.run()` para limpiar procesos en harness de benchmark. Contexto de test/benchmark. |
| 16 | plastic-labs__honcho | tests/bench/harness.py:794 | cleanup | FP | Segundo cleanup en el mismo harness. |
| 17 | pmh1314520__WebRPA | backend/app/api/system_media.py:118 | convert_audio | TP | `subprocess.run(ffmpeg_cmd, ...)` directo en `async def convert_audio()` sin executor. Bug real — FFmpeg puede tardar varios segundos bloqueando el event loop del servidor. |
| 18 | pmh1314520__WebRPA | backend/app/api/system_media.py:172 | convert_audio | TP | Otra instancia en el mismo handler de conversión de audio. |
| 19 | pmh1314520__WebRPA | backend/app/api/system_media.py:321 | convert_video | TP | `subprocess.run(ffmpeg_cmd, ...)` en `async def convert_video()`. Bug real — conversión de video es intensiva. |
| 20 | ronf__asyncssh | examples/redirect_local_pipe.py:27 | run_client | FP | `subprocess.Popen(...)` en ejemplo de asyncssh — este es `subprocess.Popen` (no bloqueante por defecto al usar `.stdout` como pipe) en un ejemplo/script. EDGE: Popen sin `.wait()` no bloquea pero el detector lo flagueó. |

### Resultado

| Métrica | Valor |
|---------|-------|
| TP | 6 |
| FP | 13 |
| EDGE | 1 |
| Precisión (TP/total sin EDGE) | 6/19 = 32% |
| Precisión (TP/total con EDGE como FP) | 6/20 = 30% |

### Patrones de FP identificados

1. **TEST_PROCESS_LAUNCHER** — `subprocess.run()` para lanzar servidores/procesos de test (NATS, Redis, servidores e2e). Uso legítimo en tests de integración: desde un test async se lanza un proceso externo para el test.
   - Repos afectados: 4 (nats-io, chopratejas, IBM mcp-forge tests, honcho bench)

2. **EXECUTOR_WRAPPER** — `subprocess.run()` dentro de una función síncrona interna (`def _run()`) que se pasa a `run_in_executor()`. El detector no rastreó el executor wrapper.
   - Repos afectados: 1 (xhs_ai_publisher)

3. **SCRIPT_BENCHMARK_CLI** — `subprocess.run()` en scripts de benchmark, CLI o herramientas de desarrollo, no en servidores async de producción.
   - Repos afectados: 2 (TracecatHQ benchmark, IBM scripts)

### Recomendación de Evidence Level

**Mantener B. Precisión 30-32% — baja, pero los TPs son genuinamente críticos.** El patrón de FP dominante es `subprocess.run()` en tests para lanzar servidores externos (legítimo). Los 6 TPs son bugs reales graves: ffmpeg bloqueando event loops de servidores web (pmh1314520/WebRPA, Evil0ctal), instalación de plugins en producción. Aplicar `TEST_FILE_DOWNGRADE` (ya activo en PYVIBE-007 según catalog.md) mejoraría la precisión en producción a ~60-70%. Necesita además detectar el patrón executor wrapper para eliminar otro FP.
