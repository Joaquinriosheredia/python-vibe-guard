# PYVIBE-008 — sqlite3 en async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/sqlite_async.py`  
**Patrón:** `sqlite3.connect(...)` / operaciones de cursor sqlite3 dentro de `async def`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 10/100 (10.0%) | 22/250 (8.8%) |
| Total hits | 121 | 436 |
| Estabilidad 100→250 | Alta (−1.2 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `nats-io/nats.py` — 128 hits (nuevo en sweep 250)
- `aio-libs/aiopg` — 122 hits (nuevo en sweep 250)
- `Kludex/uvicorn` — 45 hits
- `aiortc/aioquic` — 26 hits
- `IBM/mcp-context-forge` — 25 hits

## Evidence Level: B

- ✅ Validada en repos reales: 22 repos, 436 hits — los hits se triplican en sweep 250 por `nats-io/nats.py` y `aio-libs/aiopg`
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

## Nota

El salto de 121 a 436 hits (3.6×) con solo 2.2× más repos indica alta concentración en los nuevos repos `nats-io/nats.py` (128 hits) y `aio-libs/aiopg` (122 hits). Pueden ser wrappers de bajo nivel donde sqlite3 se usa intencionalmente en contexto de pruebas o compatibility layer. Candidato a revisión manual de FP.
