# PYVIBE-019 — Retry sin backoff

> **🔵 Estado: Limited Scope**  
> Auditoría completa de 18 hits (Scan v4, jun 2026): **12 TP / 6 FP → 67% precisión (33% FP)**.  
> Dentro del umbral orientativo de la categoría "Heurística de intención" (< 40% FP).  
> Scope restringido a `for _ in range(N)` / `for attempt in range(N)` en `async def`.  
> While loops excluidos explícitamente (FP rate ~90%, no reducible con AST puro).  
> 3 categorías de FP residuales documentadas (BENCHMARK_LOOP, TRY_ALTERNATIVES, GRAPH_TRAVERSAL).

**Severidad:** WARNING  
**Naturaleza:** Heurística de intención  
**Archivo:** `pyvibe/rules/retry_no_backoff.py`  
**Patrón:** `for _ in range(N)` / `for attempt in range(N)` con `except ...: continue`
en `async def` sin sleep o backoff en el handler del except

---

## Datos objetivos

| Métrica | 100 repos | 250 repos (pre-fix) | 250 repos (post-fix) |
|---------|-----------|---------------------|----------------------|
| Repos afectados | 43/100 (43.0%) | 82/250 (32.8%) | 55/250 (22.0%) |
| Total hits | 408 | 760 | 214 |
| Estabilidad | **Media** (−10.2 pp) | — | −71.8% vs pre-fix |
| FP documentados (sweep) | 0 reportados | ~95% (muestra 61 hits) | ~84% (muestra 25 hits) |

## Repos representativos (sweep 250)

| Repo | Hits | Nota |
|------|------|------|
| `zhinianboke/xianyu-auto-reply` | 75 | Integración con API externa, retries sin backoff |
| `home-assistant/core` | 73 | Proyecto de producción serio — ver nota Paso 5 |
| `pmh1314520/WebRPA` | 65 | Scraping web, nuevo en sweep 250 |
| `MODSetter/SurfSense` | 60 | — |
| `IBM/mcp-context-forge` | 53 | Proyecto empresarial — confirma presencia en prod |

---

## Evidence Review Protocol v1

### Paso 1 — Documentación oficial

**AWS Architecture Blog (Marc Brooker, 2015; actualizado mayo 2023):**
> "If all the failed calls back off to the same time, they cause contention or overload again
> when they are retried."

> "When failures are caused by overload, retries that increase load can make matters
> significantly worse. They can even delay recovery by keeping the load high long after
> the original issue is resolved."

El blog introduce la fórmula `delay = random(0,1) × min(cap, base × 2^attempt)` y demuestra
mediante simulación que N clientes retrying simultáneamente sin jitter producen O(N²) trabajo
total en el servidor.

**AWS Prescriptive Guidance:**
Documenta "Retry with backoff" como design pattern nombrado en el catálogo oficial de AWS
Cloud Design Patterns. Forma parte de la misma familia que Circuit Breaker y Bulkhead.

**AWS Builders' Library:**
> "Instead of retrying immediately and aggressively, the client waits some amount of time
> between tries."

**Microsoft Azure Architecture Center — "Retry Storm Antipattern" (última actualización
marzo 2026):**
Nombra explícitamente el patrón como antipatrón con ejemplo de código en C#:

```csharp
public async Task<string> GetDataFromServer()
{
    while(true)  // ← esto es el antipatrón
    {
        var result = await httpClient.GetAsync(...);
        if (result.IsSuccessStatusCode) break;
    }
}
```

> "Pause between retry attempts and increase wait time. If a service is unavailable,
> retrying immediately is unlikely to succeed. Gradually increase the amount of time
> between attempts, for example by using an exponential backoff strategy."

> "Excessive connection attempts during recovery can overwhelm the service and intensify
> the original problem. This situation is sometimes called a *thundering herd*."

La página enlaza a "Retry pattern" y "Circuit Breaker pattern" como soluciones.

**Google Cloud Storage — Retry Strategy:**
> "You should generally use exponential backoff with jitter to retry requests."

> "Retrying without delays can lead to cascading failures which are failures that might
> trigger other failures."

Google no distingue contextos donde el retry inmediato sea aceptable — la recomendación
de backoff+jitter es universal en su documentación.

**Veredicto Paso 1:** ✅ Las tres grandes nubes (AWS, Azure, Google) documentan el problema
de forma explícita, con el mismo diagnóstico y la misma solución. El antipatrón está
nombrado en Azure Architecture Center. Evidence A+.

---

### Paso 2 — Incidente real

**Cloudflare — Outage control plane, noviembre 2023:**
- Inicio: 2 noviembre 2023, 11:43 UTC. Duración: ~41 horas.
- Cuando los servicios se reactivaron en el sitio DR, "the API calls that had been failing
  overwhelmed our services" — thundering herd clásico.
- Mitigación inmediata: implementar rate limits para controlar el volumen de requests.
- Fuente: https://blog.cloudflare.com/post-mortem-on-cloudflare-control-plane-and-analytics-outage/

**Cloudflare — Dashboard outage, 12 septiembre 2025:**
- Cuando se reinició el Tenant Service, todos los dashboards comenzaron a re-autenticarse
  simultáneamente con la API, haciéndola inestable de nuevo.
- Fix implementado: "introducing changes to the dashboard that include **random delays** to
  spread out retries and reduce contention" — la solución es exactamente jitter.
- Fuente: https://blog.cloudflare.com/deep-dive-into-cloudflares-sept-12-dashboard-and-api-outage/

**Google — Service Control, incidente (fecha exacta no verificada en búsqueda):**
- Un cambio de política causó crash loops en los binarios de Service Control globalmente.
- La recuperación en regiones grandes (us-central-1) tardó hasta 2h40m debido a un
  thundering herd cuando las instancias reiniciaron y sobrecargaron Spanner.
- Fuente secundaria: citado en análisis de postmortem de Google; URL original PENDIENTE
  de verificación directa.

**Discord:**
- Un servicio flapping causó un thundering herd cuando se reconectaron simultáneamente.
- Fuente secundaria: citado en recursos de análisis de postmortems; URL original PENDIENTE.

**Azure docs — ejemplo diagnóstico:**
- Muestran un dashboard de Application Insights con 21,034 dependency failures en una
  ventana de 30 minutos, producto de retry storm desde un único cliente.
- No es un postmortem externo, pero es evidencia observacional de la escala del problema.

**Veredicto Paso 2:** ✅ El incidente de Cloudflare septiembre 2025 es especialmente sólido:
el patrón exacto (restart → retries sin delay → thundering herd → fix con random delays)
está documentado en el postmortem oficial. Los otros incidentes son confirmaciones
adicionales del mismo mecanismo. Evidence A.

---

### Paso 3 — Consenso comunitario

**Ecosistema Python:**
- `tenacity` (el estándar de facto para retries en Python): `wait_exponential()`,
  `wait_exponential_jitter()`, `wait_random_exponential()` son las estrategias
  recomendadas en la documentación. `wait_none()` existe pero se documenta para
  casos especiales (ver Paso 5).
- `backoff` (PyPI): decorador específico para backoff exponencial con jitter.
  "function decorators which can be used to wrap a function such that it will be retried
  until some condition is met" — la librería NO existe sin backoff; es su razón de ser.
- `urllib3`: `Retry(total=3, backoff_factor=0.5)` — `backoff_factor` está en el
  constructor porque la librería asume que el backoff es el caso normal, no la excepción.
- `aiohttp-retry`: paquete dedicado con ExponentialRetry como estrategia por defecto.

**Literatura técnica:**
- Marc Brooker (AWS): 2015 — establece que exponential backoff + full jitter es la
  estrategia óptima por análisis matemático (reduce work done O(N²) → O(N)).
- La entrada de Wikipedia "Thundering herd problem" documenta backoff como solución
  estándar desde los sistemas UNIX clásicos.
- "Retries, Backoff and Jitter" (CodeReliant, 2024): análisis independiente de por
  qué backoff sin jitter es insuficiente — los clientes aún sincronizarían sus reintentos.

**Veredicto Paso 3:** ✅ Consenso universal en el ecosistema Python y en literatura de
sistemas distribuidos. No existe un artículo técnico serio que recomiende retry inmediato
sin backoff para operaciones de red.

---

### Paso 4 — Evidencia empírica

Datos del sweep 250 repos (95,678 archivos .py):

| Métrica | Valor |
|---------|-------|
| Repos afectados | 82/250 (32.8%) |
| Total hits | 760 |
| Ranking por repos | 3ª regla más frecuente del sweep |
| Repos de producción confirmados | home-assistant/core, IBM/mcp-context-forge |

La presencia en home-assistant/core (73 hits) y IBM/mcp-context-forge (53 hits) confirma
que el patrón aparece en código de producción serio, no solo en scripts ad-hoc.

La bajada de 10.2 pp (43% → 32.8%) entre sweeps refleja dilución estructural: los repos
añadidos en sweep 250 incluyen más código Django/boilerplate con menos retries de red.

**Veredicto Paso 4:** ✅ Prevalencia alta y confirmada en producción.

---

### Paso 5 — Refutación

**¿Hay casos donde retry inmediato sin backoff sea aceptable?**

Sí. Se identifican tres categorías legítimas:

**Categoría A — Operaciones en memoria sin I/O de red:**
`tenacity` documenta `wait_none()` como estrategia válida para "low-latency retries" y
"in-memory operations" donde el fallo se resuelve inmediatamente. Ejemplos:
- Retry de decodificación con distintos encodings: `try: data.decode('utf-8'); except: try: data.decode('latin-1')`
- Retry de adquisición de lock local (aunque en async esto normalmente usa `asyncio.Lock`)
- Parsing con fallback a formatos alternativos

La regla detecta todos estos casos porque solo analiza la estructura AST (loop + except +
continue/pass sin sleep), no la naturaleza de la operación que se reintenta.

**Categoría B — Un único retry inmediato antes del backoff (AWS-sancionado):**
AWS explicitly notes: "one immediate retry can be attempted before moving to exponential
back-off." Para N=1, el retry inmediato tiene impacto mínimo. El patrón problemático es
el retry en bucle sin límite y sin delay.

El detector tiene en cuenta el escalation pattern (if → raise/break), lo que excluye
algunos casos de un único retry, pero no todos.

**Categoría C — Retries de base de datos con locking pesimista:**
PostgreSQL en modo pesimista puede bloquear hasta que el lock se libere a nivel de DB.
El retry en el código puede ser inmediato porque la espera ya ocurre a nivel de base de
datos. Sin embargo, en código async esto raramente aplica porque las operaciones de DB
async usan `await`, y si la DB hace espera interna, el event loop no se bloquea.

**¿Impacto en el FP rate del detector?**

La Categoría A es la más relevante para los 760 hits. Los repos con scraping intensivo
(`WebRPA`, `xianyu-auto-reply`) son probablemente True Positives (retries de red). Pero
algunos de los 73 hits en home-assistant/core podrían incluir retries no-red.

**No se encontró:** ningún estándar de industria que recomiende retry sin backoff como
patrón general para operaciones de red en sistemas distribuidos. La refutación es
específica a operaciones locales/en-memoria.

**Lección de PYVIBE-009 aplicada:** La severidad WARNING (no CRITICAL) ya refleja esta
ambigüedad — el impacto requiere coordinación entre múltiples clientes y no es
automáticamente destructivo para un único proceso.

**Veredicto Paso 5:** ⚠️ Existen casos legítimos de retry inmediato, principalmente para
operaciones en memoria y un único retry inicial. El detector tiene FP estructurales para
estas categorías. Sin embargo, en código async la mayoría de retry loops son de I/O de
red, por lo que la tasa real de FP es baja pero no nula.

---

### Paso 6 — Evolución del estándar

**Línea temporal:**

| Año | Hito |
|-----|------|
| 2012-2015 | Backoff exponencial se adopta en SDKs de AWS (documentado en código, no en blog aún) |
| 2015 | AWS Architecture Blog: Marc Brooker publica análisis matemático de backoff + jitter — establece el estándar de facto |
| 2016 | AWS SDK añade throttling behavior con backoff automático |
| 2017 | `tenacity` (sucesor de `retrying`) lanzado con backoff por defecto como patrón recomendado |
| 2019 | Azure Architecture Center publica "Retry Storm" como antipatrón oficial nombrado |
| 2020 | `urllib3` adopta `backoff_factor` como parámetro estándar de `Retry()` |
| 2023 | AWS Builders' Library actualiza artículo; AWS Prescriptive Guidance incluye "Retry with backoff" como design pattern de catálogo |
| 2025-2026 | Azure Architecture Center actualiza documentación (última revisión 2026-03-17) |

**Estado actual (2026):**
- Backoff exponencial + jitter es el estándar universal y no controvertido para retries de red.
- El antipatrón "retry sin backoff" está oficialmente nombrado en Azure, AWS, y Google.
- La industria Python tiene múltiples librerías maduras: `tenacity`, `backoff`, `stamina`.
- Ningún proyecto de código abierto serio recomienda retry inmediato para I/O de red.

**Veredicto Paso 6:** ✅ El estándar es sólido desde 2015 y unánime desde ~2019. La
evolución ha sido hacia más sofisticación (jitter, retry budgets, circuit breakers), no
en la dirección de relajar el requerimiento de backoff.

---

## Confidence (3 dimensiones)

| Dimensión | Score | Justificación |
|-----------|-------|---------------|
| **Detection** | **High** | El AST check es correcto para el patrón objetivo; FP estructurales identificados pero acotados a ops no-red. En async code, la mayoría de retry loops son I/O. |
| **Runtime Impact** | **High (I/O) / Low (in-memory)** | Para retries de red: impacto demostrado en incidentes reales (Cloudflare, Google). Para ops en memoria: impacto negligible — no hay thundering herd posible. |
| **External Evidence** | **High** | AWS + Azure + Google documentan el problema explícitamente; múltiples incidentes reales; ecosistema Python tiene librerías maduras dedicadas. |

---

## Evidence Level: **A**

**Justificación:**

Cumple criterios de Evidence A:
- ✅ Documentación oficial de múltiples proveedores (AWS, Azure, Google) nombra el
  antipatrón explícitamente con el mismo diagnóstico
- ✅ Incidente real confirmado con postmortem público: Cloudflare septiembre 2025 —
  el fix implementado fue exactamente "random delays to spread out retries" (jitter)
- ✅ Consenso comunitario unánime en ecosistema Python y literatura de distributed systems

**Por qué no A+:**
- ⚠️ Existen casos legítimos donde retry inmediato es aceptable (ops en-memoria, 1 retry
  inicial, locking pesimista de DB). A+ requiere cero excepciones legítimas.
- La regla no discrimina entre retries de red (siempre problemáticos) y retries locales
  (potencialmente aceptables), generando FP estructurales.

**Comparación con otras reglas:**
- PYVIBE-001 (A+): time.sleep() en async def bloquea el event loop en CUALQUIER contexto.
  Zero exceptions.
- PYVIBE-019 (A): retry sin backoff es destructivo en retries de red, aceptable en
  operaciones locales. Context-dependent como PYVIBE-009, pero con evidencia de docs
  oficiales que PYVIBE-009 no tenía.

---

## Recomendación: WARNING ✅ (severidad actual confirmada como correcta)

**Justificación de WARNING vs CRITICAL:**

El patrón es potencialmente destructivo pero requiere condiciones adicionales para
causar daño de producción:
1. Múltiples instancias del servicio deben fallar simultáneamente (coordinación)
2. El endpoint retried debe ser un servicio externo compartido (no local)
3. La tasa de fallo debe ser alta (si los retries raramente fallan, el impacto es mínimo)

Un único proceso con retry-without-backoff no causa thundering herd por sí solo.
Contraste con PYVIBE-001 (CRITICAL): `time.sleep()` bloquea el event loop en ese proceso
inmediatamente y con certeza, sin dependencia de contexto externo.

**Fix recomendado:**
```python
# Antes (detectado)
async def fetch_with_retry():
    for attempt in range(3):
        try:
            return await client.get(url)
        except httpx.RequestError:
            continue  # sin backoff

# Después (correcto)
import asyncio

async def fetch_with_retry():
    for attempt in range(3):
        try:
            return await client.get(url)
        except httpx.RequestError:
            await asyncio.sleep(2 ** attempt)  # backoff exponencial

# O mejor: usar tenacity
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
async def fetch_with_retry():
    return await client.get(url)
```

---

## Auditoría de Falsos Positivos — Muestra Manual (61 hits)

### Metodología

Se clonaron 5 repos con hits PYVIBE-019 confirmados, se corrió el analyzer y se
examinó el código fuente real de cada hit. Se tomó una muestra estratificada de 61
hits distribuidos entre repos de distintos rangos de hit-count:

| Repo | Hits en sweep | Hits analizados | Descripción |
|------|--------------|-----------------|-------------|
| `zhinianboke/xianyu-auto-reply` | 75 | 15 | App de marketplace con UI automation (Playwright) |
| `MODSetter/SurfSense` | 60 | 15 | Backend de indexación (Airtable, Slack, Discord, etc.) |
| `pmh1314520/WebRPA` | 65 | 15 | RPA / automatización de browser |
| `IBM/mcp-context-forge` | 53 | 15 | Gateway MCP empresarial |
| `MagicStack/asyncpg` | 1 | 1 | Driver PostgreSQL (DB-level) |
| **Total** | **254** | **61** | |

### Resultado de clasificación manual

| Categoría | N | % | Descripción |
|-----------|---|---|-------------|
| **TRUE POSITIVE** | **2** | **3.3%** | Retry genuino de I/O con riesgo de thundering herd |
| **BORDERLINE** | **1** | **1.6%** | Probe HTTP sobre URLs fallback (sin backoff, pero diferente URL cada vez) |
| **FALSE POSITIVE — FOREACH** | 25 | 41.0% | `for item in collection: try: ...; except: continue` — no es retry |
| **FALSE POSITIVE — UI_SELECTOR** | 15 | 24.6% | `for selector in selectors: page.query_selector()` — Playwright |
| **FALSE POSITIVE — MEM_PARSE** | 10 | 16.4% | `int()`, `json.loads()`, `datetime.fromisoformat()` en bucles |
| **FALSE POSITIVE — POLL_LOOP** | 4 | 6.6% | `except asyncio.TimeoutError: continue` en polling |
| **FALSE POSITIVE — BENCHMARK** | 2 | 3.3% | Warmup loops de benchmarks |
| **FALSE POSITIVE — LOCAL** | 2 | 3.3% | Socket local, desktop UI polling |
| **Total FP** | **58** | **95.1%** | |

**Tasa de falso positivo en muestra: 95.1%**

### Casos verdaderos positivos encontrados (2/61)

**TP-1** — `xianyu-auto-reply/backend-web/app/api/routes/distribution.py:242`
```python
# Retry de DB: genera clave única, reintenta hasta 10 veces si hay conflicto
for _ in range(10):
    key = _generate_secret_key()
    key_owner.secret_key = key
    try:
        await session.commit()
        break
    except Exception:
        await session.rollback()
        key_owner.secret_key = None
        continue  # ← sin backoff entre intentos
```
Patrón genuino: `for _ in range(N)`, variable `_` (unnamed), DB I/O.

**TP-2** — `asyncpg/tests/test_connect.py:236`
```python
# Retry de conexión en Windows (3 intentos, sin backoff)
for tried in range(3):
    try:
        return await self.connect(**kwargs)
    except asyncpg.ConnectionDoesNotExistError:
        pass  # ← sin delay entre intentos
```
Patrón genuino: `for variable in range(N)`, red I/O. (En tests, contexto Windows-specific.)

### El patrón dominante de falso positivo

El 65.6% de los FPs responden a la misma estructura: **for-each con manejo de errores**,
no retry:

```python
# PATRÓN DETECTADO (FP) — for-each sobre colección:
for item in collection:        # ← variable semántica, no contador
    try:
        process(item)
    except Exception:
        continue               # ← "saltar este ítem", no "reintentar"
```

```python
# PATRÓN OBJETIVO (TP) — retry con contador:
for _ in range(N):             # ← _ o attempt, iterable es range()
    try:
        await network_call()
    except Exception:
        continue               # ← "reintentar la misma operación"
```

La distinción es observable en el AST: si el iterable del `for` es una llamada a
`range()`, es probable retry. Si es un nombre de variable o atributo (colección),
es probable for-each.

### Ejemplos reales de falso positivo por subcategoría

**FOREACH** — `SurfSense/connector_indexers/airtable_indexer.py:428`
```python
# Indexa registros de Airtable: for-each, no retry del mismo registro
for record in airtable_records:
    try:
        doc = await build_document(record)
        await session.commit()
    except Exception as e:
        logger.error(f"Error processing record: {e}")
        continue  # ← pasar al siguiente registro
```

**UI_SELECTOR** — `xianyu-auto-reply/services/xianyu_publisher.py:433`
```python
# Itera selectores CSS probando cuál existe en el DOM
for selector in add_image_selectors:
    try:
        add_image_button = await self.page.wait_for_selector(selector, timeout=3000)
        if add_image_button:
            break
    except Exception:
        continue  # ← "ese selector no existe, prueba el siguiente"
```

**MEM_PARSE** — `xianyu-auto-reply/services/listing_monitor_service.py:696`
```python
# Parseo de IDs: convierte strings a int, salta los inválidos
for raw_id in task_ids:
    try:
        task_id = int(raw_id)
    except (TypeError, ValueError):
        continue  # ← parseo en memoria, sin I/O de red
```

**POLL_LOOP** — `mcp-context-forge/mcpgateway/services/event_service.py:232`
```python
# Polling de pub/sub: TimeoutError significa "no hay mensaje aún"
while True:
    try:
        message = await asyncio.wait_for(
            pubsub.get_message(ignore_subscribe_messages=True, timeout=poll_timeout),
            timeout=poll_timeout + 0.5,
        )
    except asyncio.TimeoutError:
        continue  # ← timeout esperado, no retry de operación fallida
```

### Diagnóstico raíz del problema

La regla usa `_ends_with_retry()` para detectar `continue`/`pass` en cualquier
`except` dentro de cualquier bucle. Esto no distingue entre:

1. **Retry loop**: la misma operación se reintenta → riesgo real de thundering herd
2. **For-each**: se procesa el siguiente elemento → sin riesgo de thundering herd
3. **Polling loop con timeout esperado**: el `continue` es control flow normal

El criterio actual captura patrones de aspecto similar pero semántica radicalmente
diferente.

### Recomendación sobre refinamiento del detector

**La tasa de FP (95%) supera ampliamente el umbral de 10-15%. Se recomienda
refinamiento del detector.**

El cambio con mayor impacto (estimado ~80% reducción de FPs) es distinguir
`for item in collection` de `for _ in range(N)`:

```python
# Añadir a RetryNoBackoffRule — check antes de procesar el loop
def _is_retry_loop(loop_node: ast.AST) -> bool:
    """True si el loop parece retry, no for-each."""
    if isinstance(loop_node, ast.While):
        return True  # while loops son candidatos a retry
    if isinstance(loop_node, ast.For):
        # Solo flagear si itera sobre range() — no sobre colecciones semánticas
        iter_node = loop_node.iter
        return (
            isinstance(iter_node, ast.Call)
            and isinstance(iter_node.func, ast.Name)
            and iter_node.func.id == 'range'
        )
    return False
```

Refinamientos adicionales de menor impacto:
- Excluir `except asyncio.TimeoutError: continue` en `while` loops (POLL_LOOP FP)
- Añadir PYVIBE-019 a TEST_FILE_DOWNGRADE (el hit de asyncpg está en tests/)

**Impacto estimado si se aplica solo el check de `range()`:**
- Eliminaría: FOREACH (41.0%) + UI_SELECTOR (24.6%) = 65.6% de hits actuales
- Dejaría: TP genuinos + POLL_LOOP + MEM_PARSE + algunos BENCHMARK
- TP rate estimado post-refinamiento: ~20-30% de los hits restantes

**Esta sección es investigación/recomendación. No se implementa ningún cambio de
código aquí — el refinamiento requiere decisión de diseño y regresión de tests.**

---

## Nota sobre home-assistant/core (73 hits)

home-assistant/core es un proyecto de producción con millones de usuarios y revisión
técnica estricta. Sus 73 hits probablemente incluyen mezcla similar a la muestra:
- Probable mayoría FP: retries de parsing de mensajes de protocolo, for-each sobre
  dispositivos/integraciones (patrón FOREACH), iteración sobre configuraciones
- Probable minoría TP: retries de conexión a APIs de dispositivos IoT (ej: Zigbee,
  Z-Wave, MQTT) sin backoff

No se realizó análisis de código fuente directo en home-assistant para clasificar
los hits individuales (repo demasiado grande para clonar en análisis). Dada la tasa
de FP del 95% en la muestra, estimar ~3-7 TPs reales de los 73 hits parece razonable.

---

## Fuentes verificadas

- AWS Architecture Blog — Exponential Backoff and Jitter (2015, actualizado 2023):
  https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
- AWS Builders' Library — Timeouts, retries and backoff with jitter:
  https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/
- AWS Prescriptive Guidance — Retry with backoff pattern:
  https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/retry-backoff.html
- Microsoft Azure Architecture Center — Retry Storm Antipattern:
  https://learn.microsoft.com/en-us/azure/architecture/antipatterns/retry-storm/
- Google Cloud Storage — Retry Strategy:
  https://cloud.google.com/storage/docs/retry-strategy
- Cloudflare postmortem — Control Plane Outage nov 2023:
  https://blog.cloudflare.com/post-mortem-on-cloudflare-control-plane-and-analytics-outage/
- Cloudflare postmortem — Dashboard Outage sept 2025:
  https://blog.cloudflare.com/deep-dive-into-cloudflares-sept-12-dashboard-and-api-outage/
- tenacity documentation: https://tenacity.readthedocs.io/en/latest/
- Marc Brooker blog — "What is Backoff For?" (2022):
  https://brooker.co.za/blog/2022/08/11/backoff.html

**PENDIENTE de verificación directa:**
- URL original del postmortem de Google Service Control (citado en fuentes secundarias,
  no verificado con fetch directo)
- URL original del postmortem de Discord thundering herd (citado en análisis de
  postmortems, no verificado con fetch directo)

---

## Validación post-fix — `_is_retry_loop()` (jun 2026)

**Fix implementado:** `_is_retry_loop()` en `pyvibe/rules/retry_no_backoff.py` restringe
la detección de `for` loops a iterables `range(...)`. Bucles `for item in collection`
ya no disparan el detector.

### Comparativa de cobertura

| Métrica | Pre-fix | Post-fix | Δ |
|---------|---------|----------|---|
| Total hits | 760 | 214 | −546 (−71.8%) |
| Repos afectados | 82/250 (32.8%) | 55/250 (22.0%) | −27 repos |

### Auditoría de muestra post-fix (25 hits estratificados)

Muestra tomada de los 3 repos con más hits (Soju06/codex-lb, CJackHwang/AIstudioProxyAPI,
pmh1314520/WebRPA, zhinianboke/xianyu-auto-reply).

| Categoría | N | % | Descripción |
|-----------|---|---|-------------|
| **TRUE POSITIVE** | **4** | **16.0%** | `for _ in range(N): except: continue` DB retry (unique key generation) |
| **FALSE POSITIVE — POLL_LOOP** | 10 | 40.0% | `while ...: asyncio.TimeoutError: continue/pass` tras `wait_for()` |
| **FALSE POSITIVE — MEM_PARSE** | 4 | 16.0% | `json.JSONDecodeError: continue` en stream/websocket loops |
| **FALSE POSITIVE — CLEANUP_PASS** | 7 | 28.0% | `except Exception: pass` en bloque nested dentro de while, no retry |

**Tasa FP post-fix en muestra: 84%** (antes: 95.1%)

### Diagnóstico de los FPs restantes

Los 3 subtipos de FP restantes son **todos de `while` loops**, no de `for` loops:

1. **POLL_LOOP** (~40%): `while ...: try: await asyncio.wait_for(..., timeout=T): except asyncio.TimeoutError: continue`
   → El timeout es comportamiento esperado, no error a reintentar. El `continue` reanuda
   el polling loop, no reintenta la misma operación fallida.

2. **MEM_PARSE** (~16%): `while True: data = await ws.receive(); try: json.loads(data); except json.JSONDecodeError: continue`
   → Parsing en memoria. El `continue` salta al siguiente mensaje del stream.

3. **CLEANUP_PASS** (~28%): `except Exception: pass` en try blocks nested dentro de while
   → El `pass` no es retry — es supresión silenciosa de errores en cleanup. El while
   loop continúa por caída natural, no por `continue`.

### Impacto neto del fix

La categoría dominante de FP en la auditoría original era **FOREACH** (for-each, 41%) +
**UI_SELECTOR** (24.6%) — ambas eran `for item in collection`. Ambas categorías están
**completamente eliminadas** por `_is_retry_loop()`.

Los FPs restantes son inherentes a la detección de `while` loops, que el usuario del
proyecto ha decidido mantener en scope por su naturaleza retry-like. Para eliminar
POLL_LOOP FPs se requeriría un check adicional: `except asyncio.TimeoutError` en un
`while` con `await asyncio.wait_for(...)` es poll, no retry — pero ese refinamiento
se deja para una iteración futura.

**TP rate estimado mejoró: ~5% (pre-fix) → ~16% (post-fix).** Reducción total de 71.8%.
El estado sigue siendo "Needs Redesign" hasta que una nueva auditoría de muestra confirme
tasa de FP ≤ 20% en el universo completo (requiere también atacar los while-loop FPs).

---

## Validación post-POLL_LOOP — Scan v3 (jun 2026)

**Fix implementado:** `_is_timeout_only_handler()` + `_try_body_has_timeout_kwarg()` en
`pyvibe/rules/retry_no_backoff.py`. Los handlers `except asyncio.TimeoutError` dentro de
un `while` que tiene `timeout=` kwarg en el try body se excluyen como polling loops.

### Comparativa de cobertura

| Métrica | Post-_is_retry_loop() | Post-POLL_LOOP | Δ |
|---------|-----------------------|----------------|---|
| Total hits | 214 | 168 | −46 (−21.5%) |
| Repos afectados | 55/250 (22.0%) | 46/250 (18.4%) | −9 repos |

### Auditoría de muestra Scan v3 (25 hits estratificados)

Muestra tomada de los repos con más hits tras el fix POLL_LOOP.

| Categoría | N | % | Descripción |
|-----------|---|---|-------------|
| **TRUE POSITIVE** | **3** | **12%** | `for _ in range(N): except: continue` DB/unique-key retry sin backoff |
| **FALSE POSITIVE — CLEANUP_PASS** | 11 | 45% | `except Exception: pass` en try nested dentro de while — supresión de errores en cleanup, no retry |
| **FALSE POSITIVE — MEM_PARSE** | 4 | 16% | `json.JSONDecodeError: continue` en stream/websocket parsers |
| **FALSE POSITIVE — RANGE_FOREACH** | 1 | 4% | `for i in range(N)` usado como índice, no como contador de intentos |
| **BORDERLINE** | 3 | 12% | Retries en while con lógica compleja — semánticamente ambiguos |

**Tasa FP en muestra Scan v3: ~88%** (antes del POLL_LOOP fix: 84%)

### Diagnóstico de los FPs restantes

Todos los FPs son de `while` loops. El fix POLL_LOOP eliminó esa categoría (antes 40%),
pero reveló que **CLEANUP_PASS** es el nuevo dominante:

1. **CLEANUP_PASS** (~45%): `except Exception/SpecificError: pass` en try nested dentro de
   `while True` — el `pass` suprime el error en un paso de cleanup; el `while` continúa
   por flujo natural, no porque `pass` fuera un retry explícito.

2. **MEM_PARSE** (~16%): `while True: data = ws.receive(); try: json.loads(data); except json.JSONDecodeError: continue`
   → Parsing en memoria. El `continue` salta al siguiente mensaje, no reintenta el mismo.

3. **RANGE_FOREACH** (~4%): `for i in range(N)` donde `i` se usa como índice de acceso
   a lista, no como contador de intentos. Patrón raro pero existente.

### Decisión de scope para `while` loops

**Decisión documentada (no cambio de código):** Los `while` loops se mantienen en scope
por su naturaleza semánticamente retry-like, pero se documenta que la tasa de FP es alta
(~88% en Scan v3). El detector actual es más útil como sensor de alerta que como regla
de alta precisión para `while`.

Para reducir FPs en `while` se necesitaría al menos:
- **CLEANUP_PASS**: detectar que el `except: pass` está en un try anidado dentro del while
  (no en el nivel directo del while) → el `continue` que importa está en el while externo
- **MEM_PARSE**: detectar que la excepción capturada es de parsing en memoria (ValueError,
  JSONDecodeError) vs. error de IO de red

Estos refinamientos requieren análisis de contexto más profundo y se dejan para la
próxima iteración del protocolo de Evidence Review.

**TP rate con POLL_LOOP fix: ~12% en Scan v3** (sin mejora neta respecto al 16% previo
porque el POLL_LOOP fix eliminó hits FP y los TPs son constantes).
El estado permanece "Needs Redesign" hasta tasa de FP ≤ 20%.

---

## Análisis profundo CLEANUP_PASS — pre-decisión de scope (jun 2026)

### Metodología

Scan fresco sobre los 250 repos clonados con el código actual (post-POLL_LOOP fix).
Total: **186 hits, 48 repos**. Clasificación AST completa de todos los hits.

### Hallazgo 1: descomposición por tipo de loop × tipo de handler

| Categoría | N | % | Descripción |
|-----------|---|---|-------------|
| `while` + `[pass]` | 77 | 41.4% | `except: pass` como único statement en while — TODOS FP |
| `while` + `continue` | 59 | 31.7% | `except ...: ...; continue` en while — mixto |
| `for range()` + `continue` | 30 | 16.1% | `except ...: ...; continue` en for range — mixto |
| `for range()` + `[pass]` | 20 | 10.8% | `except: pass` como único statement en for range — TODOS FP |

**Consecuencia directa**: 97 de 186 hits (52.2%) son `[pass]` como único statement.
Estos son **todos falsos positivos** sin excepción: `pass` solo no indica retry explícito;
el loop continúa por caída natural, no por intención de reintentar.

### Hallazgo 2: confirmación y refutación de la hipótesis

**Hipótesis original**: "el `except: pass` está siempre en un try anidado DENTRO del while,
mientras el `continue`/retry real está en el nivel del while externo".

**Resultado**: PARCIALMENTE CONFIRMADA, pero el mecanismo correcto es más simple.

La hipótesis asume que el `continue` en el while es el marcador relevante. Pero en el 100%
de los CLEANUP_PASS hits, el handler body es **`[pass]`** — no hay `continue` en ningún
nivel. El while continúa por caída natural (`pass` → end of except → next iteration), no
por `continue` explícito. La nesting depth del try dentro del while es irrelevante.

**Cuatro ejemplos reales que confirman el patrón:**

**Ejemplo A** — `browser.py:83` (xhs_ai_publisher):
```python
while True:   # outer retry loop
    ...
    if self.poster:
        try:
            await self.poster.close(force=True)  # cleanup
        except Exception:   # ← FLAGGED
            pass             # ← sole statement, no continue
        self.poster = None
    # main operation follows
```
El `pass` silencia el error de cleanup. El `while` continúa solo porque es `while True`.

**Ejemplo B** — `queue_worker.py:348` (AIstudioProxyAPI):
```python
while True:
    ...
    if client_disconnected_early:
        if submit_btn_loc:
            try:
                await submit_btn_loc.click(timeout=5000)
            except Exception:   # ← FLAGGED
                pass             # ← no retry intent
```
UI cleanup post-stream. El `pass` ignora fallos en un intento de UI; no es retry.

**Ejemplo C** — `stream.py:136` (AIstudioProxyAPI):
```python
while True:  # streaming loop
    ...
    try:
        await page.evaluate("...scroll JS...", [...])
    except Exception:   # ← FLAGGED
        pass             # ← scroll failures silenced
    if GlobalState.IS_QUOTA_EXCEEDED: ...
```
El JS de scroll es accesorio. `pass` ignora fallos; la iteración continúa.

**Ejemplo D** — `input.py:108` (AIstudioProxyAPI):
```python
while True:  # polling loop
    try:
        if await submit_button.is_enabled(timeout=500):
            break
    except Exception:   # ← FLAGGED
        pass             # ← sole statement, then loop continues with sleep(0.5)
    await asyncio.sleep(0.5)
```
Polling con backoff en el loop body (no en el except). El `pass` silencia errores de UI.
Este hit también tiene backoff (`await asyncio.sleep(0.5)`) en el loop body, invisible
para `_body_has_backoff()` que solo mira el handler body.

### Hallazgo 3: evaluación del gate propuesto

**Gate propuesto**: "Solo flaggear si el `continue`/retry está en el MISMO nivel de
anidación que el `try/except` — no si hay un try anidado de cleanup entre medias"

**Resultado**: NO ES EFECTIVO para el problema dominante.

El gate de nesting level apuntaría a los `while_continue` FPs donde el try está anidado.
Pero el 52.2% de todos los hits son `[pass]`-only y el gate de nesting no los toca
(no tienen `continue` en ningún nivel).

El gate que SÍ funciona: **eliminar `[pass]` como único statement de `_ends_with_retry()`**.

### Hallazgo 4: estimación de reducción de FP con distintos gates

| Gate | Hits restantes | FP rate est. | Mejora |
|------|----------------|--------------|--------|
| Baseline (actual) | 186 | 88% | — |
| Eliminar `[pass]` only | 89 | ~55% | −97 hits |
| Solo `for range()` | 50 | ~55% | −136 hits |
| Solo `for range()` + no `[pass]` | 30 | ~45-50% | −156 hits |
| Solo `for _ in range(N)` + no `[pass]` | 12 | ~40-45% | −174 hits |

**Ningún gate individual alcanza el objetivo de ≤ 30-40% FP.**

La causa raíz es que incluso en el mejor segmento (`for _ in range(N) + continue`, 12 hits)
persisten dos FP estructurales:

1. **MISSED_BACKOFF**: código con `sleep(N)` (import directo, sin `asyncio.`) o
   `await backoff.asleep()` (método Backoff class) que `_body_has_backoff()` no detecta:
   - `wassim249/evaluator.py`: `sleep(SLEEP_TIME); continue` → FP
   - `aiogram/dispatcher.py`: `await backoff.asleep(); continue` → FP

2. **RANGE_FOREACH_SCAN**: `for _ in range(count)` donde `count` es el número de elementos,
   no un límite de reintentos. No distinguible sin semántica del dominio:
   - `test_translate.py`: `for _ in range(10): try: s.bind(port); except OSError: continue`
     → TP-borderline (test code, bajo riesgo)

### Hallazgo 5: análisis del grupo `while + continue` (59 hits)

Distribución por tipo de excepción:

| Tipo excepción | N | Clasificación |
|----------------|---|---------------|
| `Exception` (bare) | 19 | AMBIGUO — requiere inspección manual |
| `json.JSONDecodeError` | 7 | FP (MEM_PARSE) |
| `ProxyResponseError` | 4 | TP-candidato (retry de proxy) |
| `TimeoutError` | 3 | AMBIGUO (puede ser poll o retry) |
| `ValueError`, `(Empty, ValueError)` | 4 | FP (parse) |
| `Errors.KafkaError` | 2 | TP-candidato (Kafka consumer retry) |
| Otros específicos | 20 | mixto |

Estimado: ~25-30% TP en el grupo `while_continue`. La mayoría de FPs son MEM_PARSE (parse
de mensajes en stream) y bare Exception (donde el código tiene backoff no detectado).

### Conclusión: caso para restricción de scope

Los while loops presentan una tasa de FP estructuralmente alta que **no es reducible a
≤ 40% con gates AST** sin introducir complejidad desproporcionada, por tres razones:

1. **Pass-only FPs** (41.4% del total): `except: pass` en while siempre ambiguo — es
   cleanup silencioso, no retry. El loop continúa por caída natural.

2. **MEM_PARSE sistémico** (≥ 12% del total): `while True: data = recv(); try: parse(data);
   except ParseError: continue` — el detector no puede distinguir "reintentar parse" de
   "saltar mensaje malformado" sin semántica de red vs. memoria.

3. **MISSED_BACKOFF** (% desconocido): `while + except: sleep(N); continue` o
   `while + except: await backoff.asleep(); continue` — backoff presente pero invisible
   para `_body_has_backoff()` que solo reconoce `asyncio.sleep` y `time.sleep` con prefijo.

**Alternativa más simple**: restringir PYVIBE-019 a `for range()` loops únicamente y
documentar `while` como out-of-scope explícitamente. Resultado:
- 50 hits restantes (de 186 → −73%)
- FP rate: ~55% aún (RANGE_FOREACH_SCAN + BULK_CHUNK_SKIP dominan)
- Pero la categoría CLEANUP_PASS (la más confusa) queda completamente eliminada
- Opción de siguiente paso: filtrar también `for i in range(N)` (var≠`_`) → 12 hits,
  ~40% FP — primer umbral manejable

**Decisión implementada: Opción C** (ver Scan v4 más abajo).

---

## Scan v4 — Implementación final + auditoría completa (jun 2026)

### Cambios implementados

**`pyvibe/rules/retry_no_backoff.py` v3:**

1. **`_is_retry_loop()`**: Ahora requiere que la variable de loop sea `_` (anónima) o
   contenga `attempt`/`retry`/`retries` en el nombre. `for i in range(N)` y
   `for chunk_start in range(...)` ya no disparan.

2. **`_ends_with_retry()`**: `[pass]` eliminado como trigger. Solo `continue` explícito
   cuenta como intención de retry.

3. **`visit_While()`**: Empuja `False` en lugar de `True`. While loops completamente fuera
   de scope. Nested `for _ in range(N)` dentro de while todavía se detecta.

4. **`_is_sleep_call()`**: Añadido bare `sleep(N)` (sin prefijo de módulo, para
   `from time import sleep` / `from asyncio import sleep`).

5. **`_has_backoff_name()`**: Añadido `attr == 'asleep'` (para `await backoff.asleep()`)
   y receiver check (para `backoff.sleep()` donde receiver contiene 'backoff'/'jitter').

**Tests actualizados:** 145 tests (140 previos − 3 tests de while como TP + 8 nuevos tests
para las restricciones añadidas).

### Scan v4 — Resultados

**250 repos clonados, código actual (post-v3):**
- **18 hits, 7 repos** (reducción desde 186/48 → −90.3% hits, −85.4% repos)

Distribución por repo:
- IBM__mcp-context-forge: 5
- zhinianboke__xianyu-auto-reply: 5
- Soju06__codex-lb: 4
- MODSetter__SurfSense: 1
- jwadow__kiro-gateway: 1
- lxf746__any-auto-register: 1
- skernelx__tavily-key-generator: 1

### Auditoría completa de los 18 hits

Auditoría del 100% de los hits (no estratificada — son solo 18).

| Hit | Repo/archivo | Tipo exc. | Clasificación | Razón |
|-----|-------------|-----------|---------------|-------|
| 01 | IBM benchmark_middleware.py:69 | Exception | **FP** BENCHMARK_LOOP | `for _ in range(iterations)` mide latencia; los fallos se loguean y se saltan, no se reintentan |
| 02 | IBM test_translate.py:130 | OSError | **FP** TRY_ALTERNATIVES | `for _ in range(10)` prueba 10 puertos aleatorios distintos — cada intento usa input diferente |
| 03 | IBM test_translate.py:761 | OSError | **FP** TRY_ALTERNATIVES | Igual que #02 (port binding en test) |
| 04 | IBM test_translate.py:817 | OSError | **FP** TRY_ALTERNATIVES | Igual que #02 |
| 05 | IBM test_translate.py:890 | OSError | **FP** TRY_ALTERNATIVES | Igual que #02 |
| 06 | MODSetter change_tracker.py:118 | Exception | **FP** GRAPH_TRAVERSAL | `for _ in range(max_depth=20)` = profundidad BFS árbol Drive; except salta el nodo, no reintenta |
| 07 | Soju06 compact.py:630 | (ClientError, TimeoutError) | **TP** | Retry de conexión a cuenta upstream en LB; sin sleep entre intentos |
| 08 | Soju06 retry.py:882 | `_RetryableStreamError` | **TP** | Nombre explícito retryable; failover de cuenta sin backoff |
| 09 | Soju06 retry.py:1229 | `RefreshError` | **TP** | Auth refresh fallido; rotation de cuenta sin sleep |
| 10 | Soju06 retry.py:961 | `RefreshError` | **TP** | Igual que #09 |
| 11 | jwadow kiro-gateway streaming_core.py:463 | `FirstTokenTimeoutError` | **TP** | Función `stream_with_first_token_retry`; modelo sin 1er token en timeout, retry inmediato |
| 12 | lxf746 api_solver.py:907 | Exception | **TP** | Captcha solving: `asyncio.sleep(wait_time)` en el try body pero se saltea en excepción; exception path retry inmediato |
| 13 | skernelx api_solver.py:892 | Exception | **TP** | Igual que #12 (misma librería captcha) |
| 14 | zhinianboke distribution.py:242 | Exception | **TP** | DB unique key commit retry: `session.rollback(); continue`; hasta 10 intentos sin sleep |
| 15 | zhinianboke users.py:78 | Exception | **TP** | Dock code unique generation retry; misma estructura que #14 |
| 16 | zhinianboke users.py:129 | Exception | **TP** | Dock code reset retry; ídem |
| 17 | zhinianboke users.py:149 | Exception | **TP** | Secret key unique generation retry; ídem |
| 18 | zhinianboke users.py:174 | Exception | **TP** | Secret key rotation retry; ídem |

**Resultado final:**
- **True Positives: 12** (hits #07–#18)
- **False Positives: 6** (hits #01–#06)
- **Precisión: 66.7% | FP rate: 33.3%**

### Tabla comparativa antes/después

| Métrica | Antes (Scan v3) | Después (Scan v4) | Δ |
|---------|-----------------|-------------------|---|
| Hits totales | 186 | 18 | −168 (−90.3%) |
| True Positives (estimado/auditoría) | ~22 | 12 | −10 |
| False Positives | ~164 | 6 | −158 |
| Precisión | ~12% | 67% | +55 pp |
| FP rate | ~88% | 33% | −55 pp |
| Repos afectados | 48/250 | 7/250 | −41 |

### Categorías de FP residuales y límite del AST puro

Las 6 FPs restantes pertenecen a 3 categorías que **no son distinguibles con AST puro**:

1. **BENCHMARK_LOOP** (1 hit): `for _ in range(N)` como contador de mediciones de latencia.
   Indistinguible de retry sin análisis semántico (¿la operación es IO o benchmark?).

2. **TRY_ALTERNATIVES** (4 hits, puerto binding): `for _ in range(N)` probando N inputs
   distintos hasta encontrar uno que funcione. La distinción requiere saber si el input
   cambia entre iteraciones.

3. **GRAPH_TRAVERSAL** (1 hit): `for _ in range(max_depth)` como límite de profundidad
   de un BFS. Requiere análisis de flujo de datos para distinguir "depth counter" de
   "retry counter".

**Conclusión sobre el límite del AST:** Los 3 patrones comparten la misma forma AST
(`for _ in range(N): try: op(); except: continue`) pero tienen semánticas distintas.
La reducción a < 33% FP requeriría análisis de flujo de datos, grafo de llamadas, o
análisis de tipos — fuera del alcance del análisis estático básico de pyvibe.

### Decisión de estado

**Estado: Limited Scope**

Justificación:
- FP rate 33% < 40% umbral orientativo de "Heurística de intención" ✓
- Mejora sustancial respecto a estado anterior (88% → 33% FP) ✓
- While loops excluidos con justificación documentada ✓
- 3 categorías de FP residuales documentadas y explicadas ✓
- El problema de distinguir retry de iteration no es resoluble con AST puro (declarado) ✓

El estado "Limited Scope" (no "Estable") refleja que:
- El scope es más estrecho que el patrón original (while excluido, solo for-range con var retry)
- Las 3 categorías FP son inherentes al problema, no defectos de la heurística
- La regla es útil y accionable dentro de su scope declarado
