# PYVIBE-007 — subprocess.run/call en async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/subprocess_async.py`  
**Patrón:** `subprocess.run(...)` / `subprocess.call(...)` / `subprocess.check_output(...)` dentro de `async def`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 6/100 (6.0%) | 12/250 (4.8%) |
| Total hits | 16 | 61 |
| Estabilidad 100→250 | Alta (−1.2 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `pmh1314520/WebRPA` — 31 hits (nuevo en sweep 250)
- `IBM/mcp-context-forge` — 8 hits
- `nats-io/nats.py` — 8 hits (nuevo en sweep 250)
- `chopratejas/headroom` — 2 hits
- `plastic-labs/honcho` — 2 hits

## Evidence Level: B

- ✅ Validada en repos reales: 12 repos, 61 hits — los hits se multiplican en sweep 250 por `pmh1314520/WebRPA` y `nats-io/nats.py`
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0
