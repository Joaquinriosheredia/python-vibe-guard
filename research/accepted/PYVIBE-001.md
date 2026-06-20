# PYVIBE-001 — time.sleep() en async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/async_sleep.py`  
**Patrón:** `time.sleep(N)` llamado dentro de `async def`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 16/100 (16.0%) | 31/250 (12.4%) |
| Total hits | 55 | 87 |
| Estabilidad 100→250 | Alta (−3.6 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `home-assistant/core` — 17 hits
- `pmh1314520/WebRPA` — 9 hits
- `MODSetter/SurfSense` — 7 hits
- `IBM/mcp-context-forge` — 6 hits
- `learning-at-home/hivemind` — 5 hits

## Evidence Level: B

- ✅ Validada en repos reales: 31 repos afectados en muestra de 250
- ⏳ Documentación oficial o incidentes públicos confirmando `time.sleep` como bug en async: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0
