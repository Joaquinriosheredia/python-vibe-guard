# PYVIBE-006 — ContextVar sin reset()

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/contextvar_cleanup.py`  
**Patrón:** `ContextVar.set(value)` dentro de `async def` sin llamada posterior a `token.reset()`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 10/100 (10.0%) | 15/250 (6.0%) |
| Total hits | 19 | 28 |
| Estabilidad 100→250 | Alta (−4.0 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `IBM/mcp-context-forge` — 4 hits
- `home-assistant/core` — 3 hits
- `sumerc/yappi` — 3 hits
- `Kludex/uvicorn` — 2 hits
- `aiohttp` — 2 hits

## Evidence Level: B

- ✅ Validada en repos reales: 15 repos afectados en muestra de 250
- ⏳ Documentación oficial Python sobre `ContextVar.reset()` como obligatorio en async: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0
