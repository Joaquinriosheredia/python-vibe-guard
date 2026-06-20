# PYVIBE-015 — loop.run_until_complete() dentro de async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/loop_run_until_complete.py`  
**Patrón:** `loop.run_until_complete(coro())` llamado dentro de `async def`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 1/100 (1.0%) | 5/250 (2.0%) |
| Total hits | 1 | 8 |
| Estabilidad 100→250 | Alta (+1.0 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `pmh1314520/WebRPA` — 4 hits (nuevo en sweep 250)
- `aio-libs/aiomysql` — 1 hit
- `mongodb/motor` — 1 hit (nuevo en sweep 250)
- `ormar-orm/ormar` — 1 hit (nuevo en sweep 250)
- `omnilib/aiosqlite` — 1 hit (nuevo en sweep 250)

## Evidence Level: B

- ✅ Validada en repos reales: 5 repos afectados en sweep 250 (era 1 repo en sweep 100 — la regla gana más validación)
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0
