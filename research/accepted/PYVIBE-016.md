# PYVIBE-016 — httpx.Client() (sync) en async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/httpx_client_sync.py`  
**Patrón:** `httpx.Client()` instanciado dentro de `async def` (en lugar de `httpx.AsyncClient()`)

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 1/100 (1.0%) | 2/250 (0.8%) |
| Total hits | 1 | 2 |
| Estabilidad 100→250 | Alta (−0.2 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `plastic-labs/honcho` — 1 hit
- `pydantic/logfire` — 1 hit (nuevo en sweep 250)

## Evidence Level: B

- ✅ Validada en repos reales: 2 repos afectados en sweep 250
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0
