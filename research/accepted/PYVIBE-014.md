# PYVIBE-014 — asyncio.ensure_future() huérfano

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/ensure_future_orphan.py`  
**Patrón:** `asyncio.ensure_future(coro())` como statement sin capturar la referencia devuelta

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 8/100 (8.0%) | 14/250 (5.6%) |
| Total hits | 16 | 33 |
| Estabilidad 100→250 | Alta (−2.4 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `faust-streaming/faust` — 5 hits
- `Kav-K/GPTDiscord` — 4 hits (nuevo en sweep 250)
- `pmh1314520/WebRPA` — 4 hits (nuevo en sweep 250)
- `postlund/pyatv` — 4 hits (nuevo en sweep 250)
- `aiortc/aiortc` — 3 hits

## Evidence Level: B

- ✅ Validada en repos reales: 14 repos, 33 hits
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0
