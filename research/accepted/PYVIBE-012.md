# PYVIBE-012 — asyncio.create_task() huérfano

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/create_task_orphan.py`  
**Patrón:** `asyncio.create_task(coro())` como statement sin capturar la referencia devuelta

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 13/100 (13.0%) | 30/250 (12.0%) |
| Total hits | 58 | 135 |
| Estabilidad 100→250 | Alta (−1.0 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `learning-at-home/hivemind` — 17 hits
- `chenyme/grok2api` — 16 hits
- `Amm1rr/WebAI-to-API` — 16 hits (nuevo en sweep 250)
- `fim-ai/fim-one` — 14 hits (nuevo en sweep 250)
- `nats-io/nats.py` — 11 hits (nuevo en sweep 250)

## Evidence Level: B

- ✅ Validada en repos reales: 30 repos, 135 hits — estabilidad muy alta (solo −1 pp)
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0
