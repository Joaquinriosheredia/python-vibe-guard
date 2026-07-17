# Candidate Public Findings

Hallazgos más sólidos del sweep de 902 repos, seleccionados para revisión manual antes
de decidir si se abre un issue público. Ninguno de estos issues ha sido abierto — esta
lista es material de trabajo para pasar el checklist de `research/public-findings.md`
("Checklist before opening an issue") repo por repo.

**Fuente:** `research/datasets/1000-repos.json` + `validation/raw/*.json` (v0.12.1, 2026-07-17)
**Selección:** solo hits en severidad CRITICAL, fuera de archivos de test/example/demo/benchmark,
verificados manualmente leyendo el archivo completo y el call site (no solo el JSON crudo).

---

## 1. hotosm/tasking-manager — PYVIBE-001

**Archivo:** `backend/services/messaging/message_service.py:241` (función `_push_messages`, `async def`)

**Explicación:** `_push_messages` recorre una lista de notificaciones y, cada 10 mensajes
enviados, ejecuta `time.sleep(0.5)` como throttle. Al estar dentro de un `async def`, ese
`time.sleep` bloquea el event loop completo del proceso durante 500ms cada 10 mensajes —
no solo la corrutina actual. Si este proceso asyncio también sirve peticiones HTTP u otras
tareas concurrentes, cualquier envío masivo de notificaciones (p. ej. tras cambios en un
proyecto de mapeo con muchos contribuidores) introduce pausas de 500ms perceptibles en
todo el resto del tráfico servido por ese worker.

**Nivel de confianza:** Alta. PYVIBE-001 es Evidence A+ (100% precisión excl. EDGE cases
en la auditoría de 250 repos). El código confirma `async def _push_messages` y la llamada
`time.sleep(0.5)` está directamente en el cuerpo de la función, sin wrapping en executor.

**Propuesta de fix:** `await asyncio.sleep(0.5)` en lugar de `time.sleep(0.5)` — cambio de
una línea, cero impacto funcional en el throttling.

---

## 2. home-assistant/core — PYVIBE-013

**Archivo:** `homeassistant/bootstrap.py:478` (función `_async_set_up_registries` / bloque de arranque)

**Explicación:** El arranque de Home Assistant carga 15 registries (entity, area,
category, device, floor, issue, label, config entries, etc.) con un único
`asyncio.gather(...)` sin `return_exceptions=True`, envuelto en un `try/except` que solo
captura `UnsupportedStorageVersionError`. Si cualquier otro registry lanza una excepción
distinta durante la carga concurrente, `gather()` cancela silenciosamente el resto de
tareas en vuelo (sin loguear cuáles quedaron a medias) y propaga solo la primera excepción
no relacionada con storage version — dificultando el diagnóstico de fallos de arranque
parciales en un componente que se ejecuta en cada inicio de HA.

**Nivel de confianza:** Alta. PYVIBE-013 es la regla más determinística del catálogo
(~100% precisión, corpus completo auditado). Código confirmado: `try: await
asyncio.gather(...) except UnsupportedStorageVersionError:` — el except no cubre el caso
general.

**Propuesta de fix:** `results = await asyncio.gather(*tasks, return_exceptions=True)`
seguido de una comprobación explícita de qué resultado es una excepción, para loguear
individualmente qué registry falló antes de decidir si se re-lanza o se activa modo
recovery.

---

## 3. ronf/asyncssh — PYVIBE-009

**Archivo:** `asyncssh/sftp.py:8077` (método `LocalFS.open`, `async def`)

**Explicación:** `LocalFS.open()` es el backend que asyncssh usa para servir peticiones
SFTP sobre el sistema de archivos local (cuando la librería actúa de servidor SFTP
exponiendo disco local). Dentro de este `async def`, la apertura real del archivo usa el
`open()` builtin de Python — una llamada bloqueante — en el hot path de **cada** petición
`open` que un cliente SFTP remoto envíe. En un servidor SFTP con múltiples clientes
concurrentes sobre el mismo event loop, cada apertura de archivo (especialmente en
almacenamiento lento o remoto montado) bloquea el loop completo.

**Nivel de confianza:** Alta. Hit único con severidad CRITICAL (no en archivo de test).
De los 94 hits de PYVIBE-009 en este repo, 92 están en `tests/test_sftp.py` (correctamente
irrelevantes); este es uno de los 2 hits de producción reales.

**Propuesta de fix:** `file_obj = await asyncio.get_event_loop().run_in_executor(None,
open, _to_local_path(path), mode)`, o migrar a `aiofiles.open()` si se acepta la
dependencia adicional.

---

## 4. CenterForOpenScience/osf.io — PYVIBE-005

**Archivo:** `api/caching/tasks.py:117` (tarea `update_storage_usage_cache`, `@app.task(max_retries=5, default_retry_delay=10)`)

**Explicación:** La tarea Celery `update_storage_usage_cache` llama a
`compute_storage_usage_total`, que ejecuta una consulta SQL cruda con `JOIN` sobre
`osf_basefileversionsthrough`, `osf_basefilenode` y `osf_fileversion`, paginada en bloques
de hasta 500.000 filas, sin ningún `time_limit`/`soft_time_limit` en el decorador de la
tarea. Si la consulta se bloquea (lock de base de datos, tabla grande sin índice
adecuado, contención), el worker Celery queda ocupado indefinidamente — sin el `time_limit`
no hay mecanismo de Celery que la mate.

**Nivel de confianza:** Alta. PYVIBE-005 es Evidence A con 86% precisión en la auditoría
de 250 repos. Código confirmado: decorador sin `time_limit` y una consulta SQL cruda sin
timeout propio dentro de la tarea.

**Propuesta de fix:** `@app.task(max_retries=5, default_retry_delay=10, time_limit=300,
soft_time_limit=270)` — con manejo de `SoftTimeLimitExceeded` para loguear qué target_id
estaba procesando al expirar.

---

## 5. judahpaul16/gpt-home — PYVIBE-012

**Archivo:** `src/backend.py:2029` (función `spotify_auth_poll`, endpoint FastAPI)

**Explicación:** Tras confirmar la autorización de Spotify, el endpoint ejecuta
`asyncio.create_task(_provision_spotifyd_credentials(data["access_token"]))` sin guardar
la referencia a la tarea, e inmediatamente devuelve la `JSONResponse`. Si
`_provision_spotifyd_credentials` lanza una excepción, esta nunca se propaga a ningún
log visible más allá del warning interno de asyncio ("Task exception was never
retrieved"), y el usuario recibe "authorized successfully" aunque el aprovisionamiento
real de credenciales para el daemon `spotifyd` haya fallado silenciosamente.

**Nivel de confianza:** Media-Alta. PYVIBE-012 alcanza ~100% precisión CRITICAL en la
muestra auditada tras el fix TEST_FILE_DOWNGRADE. Proyecto de menor tamaño/adopción que
los anteriores (asistente doméstico para Raspberry Pi), pero el bug es real y afecta un
flujo de autenticación de usuario.

**Propuesta de fix:** `task = asyncio.create_task(_provision_spotifyd_credentials(...));
task.add_done_callback(lambda t: logger.error(...) if t.exception() else None)` para
surface del error sin bloquear la respuesta HTTP.

---

## 6. GACWR/OpenUBA — PYVIBE-001

**Archivo:** `core/fastapi_app.py:159` (función `lifespan`, decorada con `@asynccontextmanager`)

**Explicación:** El `lifespan` de la app FastAPI reintenta la inicialización de la base
de datos hasta `max_retries` veces; en cada reintento fallido ejecuta `time.sleep(retry_delay)`
para esperar antes del siguiente intento. Al estar en un `async def` dentro de un
`@asynccontextmanager`, este `time.sleep` bloquea el event loop durante el arranque. El
impacto es menor que en un hot path de request-serving (normalmente no hay tráfico aún
durante el arranque), pero en despliegues donde el health-check / readiness probe
comparte el mismo event loop desde el primer instante, los reintentos de conexión a BD
pueden retrasar la respuesta a esos probes.

**Nivel de confianza:** Media. El mecanismo de daño es real y el código confirma
`async def lifespan` + `time.sleep(retry_delay)`, pero el impacto práctico depende del
patrón de despliegue (si hay tráfico real durante el arranque o no).

**Propuesta de fix:** `await asyncio.sleep(retry_delay)`.

---

## Notas de selección

- Se excluyeron deliberadamente `IBM/mcp-context-forge`, `MODSetter/SurfSense` y
  `jumpserver/jumpserver` por ya tener issues abiertos en `research/public-findings.md`
  para evitar duplicar contacto con esos proyectos.
- La mayoría de hits de alto volumen (p. ej. PYVIBE-017 en `braedonsaunders/homerun`,
  440 hits) no se incluyeron como candidatos individuales: un volumen tan alto en un solo
  archivo suele indicar un patrón sistemático del proyecto (todo el codebase usa
  `except Exception: pass` como convención) más que un bug puntual explicable en 3
  frases — encajan mejor como nota de auditoría de precisión que como issue individual.
- Ningún candidato de esta lista ha sido convertido en issue. Pasar cada uno por el
  checklist de `research/public-findings.md` antes de abrir nada.
