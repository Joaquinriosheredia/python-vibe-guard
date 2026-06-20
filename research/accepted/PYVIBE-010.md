# PYVIBE-010 — httpx.get/post (sync) en async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/httpx_sync.py`  
**Patrón:** `httpx.get(...)` / `httpx.post(...)` / funciones sync de nivel módulo httpx dentro de `async def`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 2/100 (2.0%) | 2/250 (0.8%) |
| Total hits | 17 | 17 |
| Estabilidad 100→250 | Alta (−1.2 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `hunvreus/devpush` — 16 hits (único en ambos sweeps)
- `aiortc/aioquic` — 1 hit

## Evidence Level: B

- ✅ Validada en repos reales: presente en ambas muestras; total de hits idéntico (17) — los 150 repos nuevos no añaden ningún hit
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0
