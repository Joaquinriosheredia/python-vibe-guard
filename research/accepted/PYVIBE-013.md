# PYVIBE-013 — asyncio.gather() sin return_exceptions=True

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/gather_no_return_exceptions.py`  
**Patrón:** `await asyncio.gather(*coros)` sin `return_exceptions=True`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 47/100 (47.0%) | 88/250 (35.2%) |
| Total hits | 766 | 1095 |
| Estabilidad 100→250 | **Media** (−11.8 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `home-assistant/core` — 331 hits
- `aiortc/aiortc` — 54 hits
- `TracecatHQ/tracecat` — 51 hits (nuevo en sweep 250)
- `IBM/mcp-context-forge` — 43 hits
- `MODSetter/SurfSense` — 38 hits

## Evidence Level: B

- ✅ Validada en repos reales: 88 repos afectados — **regla más prevalente por número de repos**; presente en 1 de cada 3 repos async del sweep
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

## Nota sobre estabilidad Media

La bajada de 11.8 pp refleja dilución estructural por incorporación de repos Django/general.
La tasa absoluta (35.2%) sigue siendo la segunda más alta de todas las reglas.
