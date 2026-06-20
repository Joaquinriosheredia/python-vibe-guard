# PYVIBE-002 — requests.get/post en async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/async_requests.py`  
**Patrón:** `requests.get(...)` / `requests.post(...)` / etc. dentro de `async def`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 3/100 (3.0%) | 10/250 (4.0%) |
| Total hits | 5 | 14 |
| Estabilidad 100→250 | Alta (+1.0 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `paulpierre/RasaGPT` — 3 hits
- `home-assistant/core` — 2 hits
- `learning-at-home/hivemind` — 2 hits
- `bmoscon/cryptofeed` — 1 hit
- `pydantic/logfire` — 1 hit

## Evidence Level: B

- ✅ Validada en repos reales: 10 repos afectados en muestra de 250
- ⏳ Documentación oficial o incidentes públicos confirmando `requests` sync en async como bug: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0
