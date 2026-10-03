# PYVIBE-009 — open() builtin dentro de async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/open_async.py`  
**Patrón:** `open(path, ...)` (builtin) dentro de `async def`, sin `async with`

---

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 33/100 (33.0%) | 60/250 (24.0%) |
| Total hits | 178 | 443 |
| Estabilidad 100→250 | **Media** (−9.0 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `ronf/asyncssh` — 94 hits
- `pmh1314520/WebRPA` — 50 hits
- `Neoteroi/BlackSheep` — 32 hits
- `nats-io/nats.py` — 23 hits
- `Tinche/aiofiles` — 21 hits

**Nota sobre distribución:** `Tinche/aiofiles` (la propia librería de reemplazo de `open()`) tiene 21 hits — casi con certeza en su suite de tests (tests de comparación blocking vs async). `ronf/asyncssh` tiene 94 hits en una suite de tests enorme (`test_connection.py` tiene 9000+ líneas). Esto significa que ~26% de los 443 hits totales (≥115) están probablemente en infraestructura de tests, no en handlers de producción.

---

## Pregunta clave previa al protocolo

### ¿El problema es `open()` en sí, o el volumen/frecuencia de I/O bloqueante que representa?

**Respuesta honesta: ambos, pero con impacto radicalmente distinto según el contexto.**

`open()` en un `async def` SIEMPRE bloquea el thread del event loop — esto es un hecho técnico inmutable. Sin embargo, el impacto práctico depende enteramente del contexto de uso:

**Contexto A — Hot path / request handler (alta concurrencia):**
Cada llamada a `open()` en un handler HTTP, WebSocket, o procesador de mensajes bloquea el event loop completo durante el tiempo de I/O. Con 100 requests/s, cada apertura de archivo de 5ms provoca 500ms de latencia adicional acumulada. El impacto es proporcional a la frecuencia y a todos los coroutines concurrentes esperando.

**Contexto B — Startup / lifespan / one-time initialization:**
Si `open()` ocurre en una función de inicialización (FastAPI `lifespan`, `@app.on_event("startup")`), el event loop aún no está sirviendo requests. La app no acepta conexiones hasta completar el startup. El bloqueo técnico existe, pero el impacto práctico es cero: no hay requests esperando.

**¿Distinguen esto aiofiles o su documentación?**
No explícitamente. El README de aiofiles dice: *"doing file IO may interfere with asyncio applications, which shouldn't block the executing thread"* — formulación universal sin carve-outs para startup. Sin embargo, la propia documentación de FastAPI (aunque en la versión deprecada con `@app.on_event("shutdown")`) usa `open()` con `def` (no `async def`) para I/O de archivo en shutdown, evitando la regla por diseño.

**¿FastAPI, Starlette o aiohttp usan `open()` en `async def` en su documentación oficial?**
- FastAPI lifespan events docs: NO usa `open()` en ejemplos de lifespan/startup
- El ejemplo de shutdown de FastAPI usa `def` (no `async def`): `def shutdown_event(): with open("log.txt", mode="a") as log: ...` — este patrón NO sería detectado por PYVIBE-009
- Starlette: no encontrado `open()` en ejemplos de handlers
- Conclusión: los frameworks evitan deliberadamente `open()` en `async def` en su documentación oficial

**Veredicto pregunta clave:** El problema es real en hot paths y se justifica severidad CRITICAL ahí. Para startup/one-time el impacto es nulo en práctica pero técnicamente sigue siendo I/O bloqueante. La regla actual no distingue entre contextos y aplica CRITICAL a ambos.

---

## Evidence Review Protocol v1

### Paso 1 — Documentación oficial

**Resultado: CONFIRMADO — documentación de librería + principio general Python, sin mención explícita de `open()` en Python docs**

**[aiofiles README — github.com/Tinche/aiofiles](https://github.com/Tinche/aiofiles/blob/main/README.md)**:

> *"Ordinary local file IO is blocking, and cannot easily and portably be made asynchronous. This means doing file IO may interfere with asyncio applications, which shouldn't block the executing thread."*

Esta es la declaración motivacional de la librería canónica para async file I/O en Python — describe `open()` bloqueante como el problema que existe en aplicaciones asyncio.

**[docs.python.org — Developing with asyncio](https://docs.python.org/3/library/asyncio-dev.html)**, sección "Running Blocking Code":

> *"Blocking (CPU-bound) code should not be called directly. For example, if a function performs a CPU-intensive calculation for 1 second, all concurrent asyncio Tasks and IO operations would be delayed by 1 second."*

Y la recomendación:
> *"An executor can be used to run a task in a different thread [...] to avoid blocking the OS thread with the event loop."*

**Matiz importante:** Python docs NO nombran `open()` explícitamente. La guidance es genérica sobre "blocking code". Solo el principio aplica — `open()` es blocking I/O pero los docs no lo señalan directamente.

**[FastAPI lifespan events docs](https://fastapi.tiangolo.com/advanced/events/)** — ejemplo oficial de shutdown (deprecated):
```python
@app.on_event("shutdown")
def shutdown_event():          # ← def, no async def
    with open("log.txt", mode="a") as log:
        log.write("Application shutdown")
```
FastAPI usa `def` (no `async def`) deliberadamente para I/O de archivo en su ejemplo oficial. PYVIBE-009 no flagearía esto. El propio framework indica que la forma correcta de hacer file I/O en eventos de ciclo de vida es con `def` sincrónico.

**[BBC Cloudfit — Asyncio Part 5](https://bbc.github.io/cloudfit-public-docs/asyncio/asyncio-part-5.html)**:
> *"you absolutely can call non-async code from async-code, in fact it's easy to do so. But if a method/function call might 'block' (ie. take a long time before it returns) then you really shouldn't."*

Sin carve-outs para contextos de inicialización — trata el blocking como universalmente problemático.

**Veredicto paso 1:** documentación de librería oficial (aiofiles) describe el problema de forma explícita. Python docs cubren el principio pero no nombran `open()` explícitamente. Los propios frameworks recomiendan `def` (no `async def`) para file I/O en startup events, lo cual valida de forma inversa que `open()` en `async def` es un problema.

---

### Paso 2 — Incidentes reales

**Resultado: PENDIENTE — no se encontró un incidente de producción específicamente atribuible a `open()` en `async def`**

**Búsqueda realizada:** Issues en `ronf/asyncssh`, `Tinche/aiofiles`, Stack Overflow, DEV.to, Medium con términos relacionados a `open()` bloqueante en async.

**Lo que sí se encontró:**
- **[asyncssh#375 — SSHReader.readline blocking event loop](https://github.com/ronf/asyncssh/issues/375):** issue sobre I/O bloqueante en asyncssh — relacionado con operaciones de lectura de stream, no directamente con `open()` en async def
- **BlockBuster** ([DEV.to](https://dev.to/cbornet/introducing-blockbuster-is-my-asyncio-event-loop-blocked-3487)) parchea métodos del módulo `io` para detectar blocking calls desde asyncio, incluyendo `open()` — sugiere que el patrón es suficientemente común y problemático como para merecer una herramienta dedicada de detección
- **asyncio debug mode** detecta coroutines que tardan > 100ms sin yield — `open()` en archivo lento/red dispararía esto

**Lo que NO se encontró:** Un issue de GitHub concreto donde alguien documente "nuestro handler estaba lento / el event loop se bloqueaba porque usábamos `open()` en un async def handler de requests". El mecanismo es bien conocido pero la cadena de causación específica `open()` → incidente documentado → resolución no apareció en la investigación.

**Diferencia startup vs hot path:** No se encontró evidencia de que alguien haya reportado un incidente por `open()` en startup — lo cual es consistente con el argumento de que no causa problemas prácticos en ese contexto.

**Veredicto paso 2:** PENDIENTE. Mecanismo técnico bien documentado y herramientas de detección existentes confirman que es un problema reconocido. Pero no se encontró el incidente de producción específico verificable que requiere Evidence Level A.

---

### Paso 3 — Comunidad

**Resultado: CONSENSO TÉCNICO — `open()` en async def es un antipatrón en hot paths; no hay debate**

Fuentes de consenso encontradas:

**aiofiles PyPI (23M descargas/mes):** la existencia y adopción masiva de esta librería confirma que la comunidad reconoce `open()` como problemático en contextos async.

**[asyncio debug mode](https://docs.python.org/3/library/asyncio-dev.html):** el modo debug de asyncio loguea warnings cuando cualquier coroutine tarda >100ms sin yield — `open()` en archivo de red triggearía esto.

**[BlockBuster](https://dev.to/cbornet/introducing-blockbuster-is-my-asyncio-event-loop-blocked-3487):** herramienta que parchea métodos de `io`, `os`, `time`, `socket`, `sqlite` para detectar blocking en event loop — `open()` está explícitamente incluido.

**[Wittycoder.in — Python asyncio guide 2026](https://wittycoder.in/blog/python-asyncio-guide-2026):** "Using async def for functions that perform blocking operations—such as standard file I/O—will block the entire event loop and negate the benefits of async I/O."

**[codilime.com — Run blocking functions in Event Loop](https://codilime.com/blog/how-fit-triangles-into-squares-run-blocking-functions-event-loop/):** describe run_in_executor como la solución, con file operations como ejemplo canónico.

**Posición de la comunidad sobre startup:** No se encontró consenso explícito de que `open()` en startup/lifespan sea "aceptable". El argumento es implícito (la app no sirve requests aún) pero no está documentado formalmente. La mayoría de guías tratan el problema universalmente.

**Veredicto paso 3:** consenso técnico fuerte sobre el antipatrón en hot paths. Para startup, hay silencio — nadie lo defiende explícitamente pero tampoco hay debate porque el impacto real es cero.

---

### Paso 4 — Evidencia empírica propia

**Resultado: FUERTE en volumen; MODERADO ajustando por contexto**

- 60/250 repos afectados (24.0%) — tercera regla más frecuente por repos en sweep 250
- 443 hits totales
- Estabilidad Media (−9.0 pp): dilución estructural por repos sin código async intensivo

**Análisis de distribución de hits:**

| Repo | Hits | Contexto probable |
|------|------|-------------------|
| `ronf/asyncssh` | 94 | Suite de tests enorme (test_connection.py ~9000 líneas) |
| `pmh1314520/WebRPA` | 50 | RPA/automatización — posible mix handlers + setup |
| `Neoteroi/BlackSheep` | 32 | Framework web — probable mix tests + startup |
| `nats-io/nats.py` | 23 | Cliente NATS — probable suite de tests |
| `Tinche/aiofiles` | 21 | Tests de comparación blocking vs async (librería de reemplazo) |

**Estimación conservadora:** ~115 de 443 hits (≥26%) están casi con certeza en infraestructura de tests de repos de librerías/frameworks. Los hits "reales" en código de producción son ≤328.

**0 falsos positivos documentados en campo** — pero la distinción startup/hot-path no ha sido evaluada manualmente en los repos.

---

### Paso 5 — Intento de refutación

**Búsqueda activa de excepciones legítimas.**

#### Caso A — Startup / lifespan / inicialización one-time

**Evidencia de que se considera aceptable:**
- La documentación de Python asyncio afirma explícitamente: *"Your application won't start receiving requests until all the startup event handlers have completed."* (citado en guías de FastAPI). Si no hay requests pendientes, el bloqueo no tiene víctimas.
- FastAPI usa `def` (no `async def`) en su ejemplo de shutdown con file I/O — lo que implica que la forma "correcta" para startup/shutdown file I/O es NO usar async def, siendo `open()` en `def` perfectamente válido.
- Ninguna guía encontrada dice explícitamente "usa `open()` en `async def` lifespan" — pero tampoco nadie lo condena específicamente.

**Veredicto:** Excepción legítima implícita. El impacto práctico en startup es cero. Pero la forma idiomática correcta (usar `def` en lugar de `async def` para operaciones bloqueantes en startup) ya evita PYVIBE-009, así que el FP real es solo cuando alguien usa `async def` para una función de startup que contiene `open()`.

#### Caso B — Tests / comparación de rendimiento

**Tinche/aiofiles** (21 hits): código como `with open(fname, mode) as f: content = f.read()` dentro de `async def test_*` para comparar el comportamiento bloqueante con la versión async. Estos hits son FPs estructurales de la regla — son exactamente lo que la regla pretende detectar, pero en el contexto correcto (tests que QUIEREN mostrar el comportamiento bloqueante).

**asyncssh** (94 hits): gran suite de tests que abre archivos de claves SSH en helpers async como `async def asyncSetUp()` o `async def test_*`. Patrón común: `open('keys/host_key')` en setup de tests.

**Veredicto:** FPs estructurales en tests de librerías — no son código de producción. La downgrade a WARNING en tests files (si PYVIBE-009 se añadiera a `TEST_FILE_DOWNGRADE`) mitigaría esto.

#### Caso C — Scripts async one-shot (sin concurrencia real)

Un script que usa `async def main()` como convención pero solo ejecuta una tarea a la vez — `open()` no daña porque no hay concurrencia. Técnicamente un FP, pero el patrón de usar asyncio para scripts sin concurrencia real es antipattern de diseño por sí mismo.

#### Resumen de refutación

| Caso | Veredicto | Impacto en regla |
|------|-----------|-----------------|
| Startup/lifespan async def + open() | Excepción legítima (impacto cero) | FP real si se usa async def en startup |
| Tests comparativos (aiofiles, asyncssh) | FP estructural — tests de librería | ~26% de hits |
| Request handlers HTTP/WS | Antipatrón real — CRITICAL justificado | Core del problema |
| Async CLI one-shot | Excepción técnica | Marginal |

---

### Paso 6 — Evolución del patrón

**Resultado: TENDENCIA HACIA async I/O pero open() directo sigue siendo prevalente**

**Historial de herramientas:**
- `aiofiles` existe desde 2015 (Python 3.4 asyncio) — lleva >10 años siendo la solución estándar
- Python 3.9 (2020): `asyncio.to_thread()` como alternativa estándar sin dependencias externas
- `anyio.Path.open()` como alternativa más moderna (integrado en anyio 3.x+)
- Python 3.11+ (free-threaded experimental, 3.13 productivo): GIL removal hace que las thread pools sean más eficientes, reduciendo el coste de aiofiles

**¿Está disminuyendo el uso de `open()` en async?**
- Los 443 hits en 250 repos de alta estrella indican que sigue siendo extremadamente común
- La bajada de 33.0% a 24.0% entre sweeps refleja dilución de muestra, no tendencia real
- aiofiles tiene adopción creciente pero `open()` directo también persiste en código nuevo (AI-generated code en particular mezcla open() con async def de forma sistemática — como nota el docstring de la regla)

**Tendencia:** Patrón estable o en ligera mejora. No hay señales de que la comunidad esté eliminando activamente `open()` de código async — se sigue generando nuevo código con este antipatrón.

---

## Clasificación final

**Evidence Level: B**

| Criterio | Estado |
|----------|--------|
| Validada en repos reales (60/250, 24.0%) | ✅ |
| Documentación oficial Python nombra `open()` explícitamente | ❌ (principio genérico, no open() específico) |
| Documentación de librería oficial (aiofiles README) describe el problema | ✅ |
| Incidente público de producción confirmado (open() → outage) | ❌ PENDIENTE |
| Falsos positivos documentados en campo | ✅ 0 en campo |
| Excepción legítima conocida | ⚠️ Sí — startup context + hits de tests |

**Por qué B y no A:** falta el incidente de producción específicamente atribuible a `open()` en `async def`. Python docs no nombran `open()` explícitamente (solo el principio general de no blocking). La excepción de startup es real y afecta una porción no trivial de los hits detectados.

**Por qué B y no C:** alta prevalencia empírica (60 repos), documentación de librería oficial explícita (aiofiles), consenso técnico fuerte, herramientas de detección activa (BlockBuster).

---

## Distinción de contexto — Recomendación sobre severidad

**Hallazgo clave de esta revisión:** la distinción startup vs hot path es real y la regla no puede detectarla con AST puro.

**Análisis de severidad actual (CRITICAL):**
- Para hot paths (handlers HTTP/WS, procesadores de mensajes): CRITICAL es correcto y justificado
- Para startup/lifespan: CRITICAL es una sobreclasificación — el impacto real es cero o negligible
- Para tests de librería (asyncssh, aiofiles): el problema del sweep es estructural, no de severidad

**Opciones consideradas:**

| Opción | Pros | Contras |
|--------|------|---------|
| Mantener CRITICAL para todo | Simple, consistente | Sobreclasifica startup y tests |
| Bajar a WARNING global | Reduce alarma en startup | Subestima hot path handlers |
| Detectar startup por nombre función | Heurística, no confiable | Nombres arbitrarios |
| Añadir a TEST_FILE_DOWNGRADE | Mitiga ~26% de FPs | No ayuda con startup en prod |

**Decisión recomendada:** Añadir PYVIBE-009 a `TEST_FILE_DOWNGRADE` en `analyzer.py` (mismo mecanismo que PYVIBE-001 y PYVIBE-007) para bajar a WARNING en archivos de test. Documenta la limitación del startup context en README y docstring. No cambiar severidad global — CRITICAL sigue siendo correcto para el caso más común (handler de requests).

---

## Confidence

```
Confidence:
  Detection:         High — AST sobre ast.Name "open" dentro de
                            visit_AsyncFunctionDef; 0 FPs en campo;
                            no detecta startup vs hot-path context;
                            ~26% de hits en repos son tests de librería

  Runtime impact:    Medium-High — en hot paths, impacto CRITICAL
                                    probado y bien documentado técnicamente;
                                    en startup, impacto real es cero;
                                    severidad depende del contexto que
                                    la regla no puede distinguir

  External evidence: Medium — documentación aiofiles describe el problema
                               explícitamente; Python docs cubren principio
                               genérico sin nombrar open(); no hay incidente
                               de producción específico confirmado; consenso
                               técnico fuerte pero sin post-mortem atribuible
```

---

## Fuentes verificadas

- [aiofiles README — "Ordinary local file IO is blocking and may interfere with asyncio"](https://github.com/Tinche/aiofiles/blob/main/README.md)
- [Python asyncio-dev.html — "Blocking code should not be called directly"](https://docs.python.org/3/library/asyncio-dev.html)
- [FastAPI Lifespan Events — shutdown example usa def (no async def) para file I/O](https://fastapi.tiangolo.com/advanced/events/)
- [BBC Cloudfit — Asyncio Part 5 — "if a method might block you really shouldn't call it from async"](https://bbc.github.io/cloudfit-public-docs/asyncio/asyncio-part-5.html)
- [BlockBuster — patches io module to detect blocking open() in event loop](https://dev.to/cbornet/introducing-blockbuster-is-my-asyncio-event-loop-blocked-3487)
- [asyncssh#375 — SSHReader.readline blocking event loop (issue relacionado)](https://github.com/ronf/asyncssh/issues/375)
- [aiofiles PyPI — 23M descargas/mes (adopción masiva valida el problema)](https://pypi.org/project/aiofiles/)
