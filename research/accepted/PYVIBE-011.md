# PYVIBE-011 — os.blocking en async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/os_blocking.py`  
**Patrón:** `os.path.exists(...)` / `os.listdir(...)` / `os.stat(...)` / llamadas bloqueantes de `os.*` dentro de `async def`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 0/100 (0.0%) | 0/250 (0.0%) |
| Total hits | 0 | 0 |
| Estabilidad 100→250 | Alta (0.0 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

Ninguno — 0 hits en ambos sweeps.

## Evidence Level: B

- ✅ Validada contra repos reales: 250 repos escaneados, 0 hits
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0 (no hay hits que puedan ser FP)

## Nota sobre 0 hits

La ausencia de hits en 250 repos no implica que el patrón no exista en código real.
Los repos del sweep son proyectos de alta estrella en GitHub que tienden a seguir buenas
prácticas y a usar `pathlib` en lugar de `os.*` directamente. El patrón es más probable
en código legacy o de integración no representado en la muestra actual.

Mantener la regla. Revisar si se añaden repos de código legacy al dataset en sweeps futuros.
