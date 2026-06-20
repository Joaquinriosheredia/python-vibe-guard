# PYVIBE-019 — Retry sin backoff

**Severidad:** WARNING  
**Archivo:** `pyvibe/rules/retry_no_backoff.py`  
**Patrón:** bucle de retry (for/while con `except` + continue/retry lógica) en `async def` sin `await asyncio.sleep(...)` o backoff entre intentos

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 43/100 (43.0%) | 82/250 (32.8%) |
| Total hits | 408 | 760 |
| Estabilidad 100→250 | **Media** (−10.2 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `zhinianboke/xianyu-auto-reply` — 75 hits
- `home-assistant/core` — 73 hits
- `pmh1314520/WebRPA` — 65 hits (nuevo en sweep 250)
- `MODSetter/SurfSense` — 60 hits
- `IBM/mcp-context-forge` — 53 hits

## Evidence Level: B

- ✅ Validada en repos reales: 82 repos, 760 hits — tercera regla más frecuente por repos en sweep 250
- ⏳ Documentación oficial o incidentes públicos sobre retry sin backoff causando thundering herd: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

## Nota sobre estabilidad Media

La bajada de 10.2 pp refleja dilución estructural. El patrón de retry es más frecuente
en código de integración con servicios externos; los repos Django/boilerplate añadidos
en el sweep 250 tienen menos de este tipo de código.
