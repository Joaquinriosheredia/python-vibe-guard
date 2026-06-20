# PYVIBE-017 — except silencioso en async def

**Severidad:** CRITICAL (WARNING para patrones de supresión intencional)  
**Archivo:** `pyvibe/rules/silent_except.py`  
**Patrón:** bloque `except` vacío o con solo `pass` / `...` dentro de `async def`, que silencia excepciones sin loguearlas

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 57/100 (57.0%) | 122/250 (48.8%) |
| Total hits | 999 | 2510 |
| Estabilidad 100→250 | **Media** (−8.2 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `pmh1314520/WebRPA` — 352 hits (nuevo en sweep 250)
- `IBM/mcp-context-forge` — 238 hits
- `BetaStreetOmnis/xhs_ai_publisher` — 193 hits (nuevo)
- `lxf746/any-auto-register` — 192 hits (nuevo)
- `zhinianboke/xianyu-auto-reply` — 104 hits

## Evidence Level: B

- ✅ Validada en repos reales: 122 repos — **regla más frecuente por número de repos** (48.8%)
- ✅ Mayor total de hits absoluto: 2,510 — más del doble del siguiente (PYVIBE-019 con 760)
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

## Nota sobre severidad mixta

`silent_except.py` emite CRITICAL para excepciones que suprimen totalmente el error,
y WARNING para patrones de supresión controlada (e.g. `except asyncio.CancelledError: raise`
no se flagea). La lógica de diferenciación está en el código de la regla.
