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

---

## Auditoría de Precisión (Sweep 250)

**Muestra analizada:** 2 hits de 2 totales (2 repos)
**Metodología:** 100% audit (2 hits)

### Clasificación hit-by-hit

| # | Repo | File:Line | Function | Clasificación | Razón |
|---|------|-----------|----------|---------------|-------|
| 1 | plastic-labs__honcho | tests/sdk/conftest.py:46 | honcho_async_test_client | FP | `httpx.Client()` se crea con `transport=client._transport` de un `TestClient` de ASGI — es una fixture de test que deliberadamente usa el cliente síncrono para calentar la aplicación antes de la fase async; comentario en código lo explica explícitamente |
| 2 | pydantic__logfire | tests/otel_integrations/test_httpx.py:872 | test_httpx_client_capture_all_environment_variable | FP | Uso dentro de función `async def` de test para verificar instrumentación de `httpx.Client` síncrono — se testea específicamente el cliente síncrono instrumentado, no es código de producción; el `httpx.Client` es el objeto bajo prueba |

### Resultado

| Métrica | Valor |
|---------|-------|
| TP | 0 |
| FP | 2 |
| EDGE | 0 |
| Precisión (TP/total) | 0% |

### Patrones de FP identificados

1. **TEST_TRANSPORT_FIXTURE** — `httpx.Client()` creado con transport de `TestClient` de ASGI como fixture de test. Uso técnicamente correcto: el cliente síncrono se usa para inicializar la app antes del test async.
   - Ejemplo: `httpx.Client(transport=client._transport, base_url=str(client.base_url))`
   - Repos afectados: 1 (plastic-labs/honcho)

2. **TEST_SUBJECT_UNDER_TEST** — La función async de test verifica explícitamente el comportamiento del cliente síncrono (`httpx.Client`) como objeto bajo prueba para instrumentación de observabilidad.
   - Ejemplo: `with httpx.Client(transport=create_transport()) as client: logfire.instrument_httpx(client)`
   - Repos afectados: 1 (pydantic/logfire)

### Recomendación de Evidence Level

**Mantener B con nota sobre FP en tests.** Con 0/2 TP en la muestra, ambos hits son en archivos de test con uso legítimo. La regla debe aplicar `TEST_FILE_DOWNGRADE` (como PYVIBE-001, PYVIBE-007, PYVIBE-009, PYVIBE-013). La muestra es mínima (2 hits) — con el patrón tan raro en 250 repos no es posible generalizar, pero los FPs documentados son consistentes con el patrón "httpx.Client en tests para verificar código de instrumentación síncrona". En producción el patrón sería genuinamente problemático.
