# PYVIBE-009 — open() en lugar de aiofiles en async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/open_async.py`  
**Patrón:** `open(path, ...)` (builtin) dentro de `async def`, sin `async with`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 33/100 (33.0%) | 60/250 (24.0%) |
| Total hits | 178 | 443 |
| Estabilidad 100→250 | **Media** (−9.0 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `ronf/asyncssh` — 94 hits (nuevo en sweep 250)
- `pmh1314520/WebRPA` — 50 hits (nuevo en sweep 250)
- `Neoteroi/BlackSheep` — 32 hits
- `nats-io/nats.py` — 23 hits (nuevo en sweep 250)
- `Tinche/aiofiles` — 21 hits

## Evidence Level: B

- ✅ Validada en repos reales: 60 repos afectados — tercera regla más frecuente por repos en sweep 250
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

## Nota sobre estabilidad Media

La bajada de 9 pp refleja dilución estructural: los 150 repos nuevos incluyen más proyectos Django/general con menos código async intensivo. No indica problema con la regla.
