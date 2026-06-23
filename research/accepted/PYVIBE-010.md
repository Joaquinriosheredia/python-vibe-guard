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

---

## Auditoría de Precisión (Sweep 250)

**Muestra analizada:** 17 hits de 17 totales (2 repos)
**Metodología:** 100% audit (17 hits)

### Clasificación hit-by-hit

| # | Repo | File:Line | Function | Clasificación | Razón |
|---|------|-----------|----------|---------------|-------|
| 1 | aiortc__aioquic | examples/interop.py:434 | test_throughput | EDGE | `httpx.get()` (sync) dentro de `async def test_throughput` — es un ejemplo/script de interoperabilidad (no servidor de producción). La función compara latencia HTTP/TCP vs QUIC, y la llamada síncrona es parte de la medición. Script de benchmark, no código de producción. |
| 2 | hunvreus__devpush | app/services/github.py:71 | get_user_access_token | TP | `httpx.post()` directo en `async def get_user_access_token()` — bloquea el event loop durante OAuth. Bug real en servicio de producción FastAPI. |
| 3 | hunvreus__devpush | app/services/github.py:87 | get_user_info | TP | `httpx.get()` directo en `async def get_user_info()`. Bug real. |
| 4 | hunvreus__devpush | app/services/github.py:97 | get_user_primary_email | TP | `httpx.get()` directo en `async def`. Bug real. |
| 5 | hunvreus__devpush | app/services/github.py:116 | get_user_installations | TP | `httpx.get()` directo en `async def`. Bug real. |
| 6 | hunvreus__devpush | app/services/github.py:147 | get_installation_repositories_for_user | TP | `httpx.get()` directo en `async def`. Bug real. |
| 7 | hunvreus__devpush | app/services/github.py:173 | search_user_repositories | TP | `httpx.get()` directo en `async def`. Bug real. |
| 8 | hunvreus__devpush | app/services/github.py:188 | get_repository | TP | `httpx.get()` directo en `async def`. Bug real. |
| 9 | hunvreus__devpush | app/services/github.py:199 | get_repository_branches | TP | `httpx.get()` directo en `async def`. Bug real. |
| 10 | hunvreus__devpush | app/services/github.py:231 | get_repository_commits | TP | `httpx.get()` directo en `async def`. Bug real. |
| 11 | hunvreus__devpush | app/services/github.py:256 | get_repository_commit | TP | `httpx.get()` directo en `async def`. Bug real. |
| 12 | hunvreus__devpush | app/services/github.py:264 | get_installation | TP | `httpx.get()` directo en `async def`. Bug real. |
| 13 | hunvreus__devpush | app/services/github.py:275 | get_installation_access_token | TP | `httpx.post()` directo en `async def`. Bug real. |
| 14 | hunvreus__devpush | app/services/github.py:286 | get_installation_repositories | TP | `httpx.get()` directo en `async def`. Bug real. |
| 15 | hunvreus__devpush | app/services/github.py:295 | get_repository_installation | TP | `httpx.get()` directo en `async def`. Bug real. |
| 16 | hunvreus__devpush | app/services/github.py:324 | get_git_tree | TP | `httpx.get()` directo en `async def`. Bug real. |
| 17 | hunvreus__devpush | app/services/github.py:351 | get_file_content | TP | `httpx.get()` directo en `async def`. Bug real. |

**Nota:** hunvreus/devpush usa `httpx` en su API sincrónica en lugar de `httpx.AsyncClient` en todo el servicio GitHub — los 16 hits del repo son un error sistemático de arquitectura (debería ser `async with httpx.AsyncClient() as client: await client.get(...)`).

### Resultado

| Métrica | Valor |
|---------|-------|
| TP | 15 |
| FP | 0 |
| EDGE | 1 |
| Precisión (TP/total sin EDGE) | 15/16 = 94% |
| Precisión (incluyendo EDGE como FP) | 15/17 = 88% |

### Patrones de FP identificados

1. **BENCHMARK_INTEROP_SCRIPT** — `httpx.get()` síncrono en script de interoperabilidad/benchmark para medir latencia TCP vs QUIC. No es código de servidor de producción.
   - Ejemplo: `response = httpx.get("https://" + server.host + path, verify=False)` en `examples/interop.py`
   - Repos afectados: 1 (aiortc/aioquic)

### Recomendación de Evidence Level

**Confirmar B. Precisión 88-94% — excelente.** Esta regla tiene una de las tasas de TP más altas de las auditadas. El único borderline es un script de ejemplo/benchmark, no código de producción. Los 15 TPs son sistemáticos: el autor de hunvreus/devpush usó la API sync de httpx en todo su módulo GitHub, lo cual es un antipatrón claro en un servicio FastAPI async. Candidata a elevación a Evidence A una vez se documente bibliografía oficial httpx.
