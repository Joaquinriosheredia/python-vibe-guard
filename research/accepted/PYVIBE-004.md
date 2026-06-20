# PYVIBE-004 — threading.Lock() en async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/threading_lock.py`  
**Patrón:** `threading.Lock()` / `threading.RLock()` instanciado o usado dentro de `async def`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 5/100 (5.0%) | 5/250 (2.0%) |
| Total hits | 60 | 60 |
| Estabilidad 100→250 | Alta (−3.0 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `agronholm/anyio` — 36 hits
- `BeanieODM/beanie` — 11 hits
- `home-assistant/core` — 8 hits
- `IBM/mcp-context-forge` — 3 hits
- `polarsource/polar` — 2 hits

## Evidence Level: B

- ✅ Validada en repos reales: 5 repos afectados; el total de hits (60) se mantiene igual en ambos sweeps, concentrado en los mismos repos
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

## Nota

El total de hits es idéntico entre 100 y 250 repos (60), lo que indica que los 5 repos afectados ya estaban en el sweep de 100. Los 150 repos nuevos no añaden ningún hit.
