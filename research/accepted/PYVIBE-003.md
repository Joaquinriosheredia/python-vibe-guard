# PYVIBE-003 — asyncio.run() dentro de async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/asyncio_run.py`  
**Patrón:** `asyncio.run(coro())` llamado dentro de `async def`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 1/100 (1.0%) | 1/250 (0.4%) |
| Total hits | 1 | 1 |
| Estabilidad 100→250 | Alta (−0.6 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `piccolo-orm/piccolo` — 1 hit (único repo afectado en ambos sweeps)

## Evidence Level: B

- ✅ Validada en repos reales: 1 repo afectado confirmado en ambas muestras
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

## Nota

Baja prevalencia (0.4% en 250 repos) pero el patrón es siempre incorrecto:
`asyncio.run()` crea un nuevo event loop y falla si ya hay uno activo,
lo que dentro de `async def` genera `RuntimeError: This event loop is already running`.
