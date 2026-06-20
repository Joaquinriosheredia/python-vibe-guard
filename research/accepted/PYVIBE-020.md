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
