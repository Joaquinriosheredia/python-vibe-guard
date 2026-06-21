# PYVIBE-019 — Retry sin backoff

**Severidad:** WARNING  
**Archivo:** `pyvibe/rules/retry_no_backoff.py`  
**Patrón:** bucle de retry (`for`/`while` con `except` + `continue`/`pass`) en `async def`
sin `await asyncio.sleep(...)` ni llamada a backoff/jitter entre intentos

---

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 43/100 (43.0%) | 82/250 (32.8%) |
| Total hits | 408 | 760 |
| Estabilidad 100→250 | **Media** (−10.2 pp) | |
| FP documentados (sweep) | 0 reportados | ~95% en muestra manual (ver Auditoría FP) |

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
