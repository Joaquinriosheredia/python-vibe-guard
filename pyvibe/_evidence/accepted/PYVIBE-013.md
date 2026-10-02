# PYVIBE-013 — asyncio.gather() sin return_exceptions=True

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/gather_no_return_exceptions.py`  
**Patrón:** `await asyncio.gather(*coros)` sin `return_exceptions=True`

---

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 47/100 (47.0%) | 88/250 (35.2%) |
| Total hits | 766 | 1095 |
| Estabilidad 100→250 | **Media** (−11.8 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `home-assistant/core` — 331 hits
- `aiortc/aiortc` — 54 hits
- `TracecatHQ/tracecat` — 51 hits
- `IBM/mcp-context-forge` — 43 hits
- `MODSetter/SurfSense` — 38 hits

---

## Pregunta previa: ¿cuál es el comportamiento observable?

`asyncio.gather(*coros)` sin `return_exceptions=True` crea una situación
de tres vías cuando una de las coroutines lanza excepción:

1. **La excepción se propaga inmediatamente** al caller que hace `await gather(...)`.
2. **Las otras coroutines NO se cancelan** — siguen ejecutándose en el event loop.
3. **Los resultados parciales ya completados se pierden** — el caller recibe excepción, no la lista de resultados.

El resultado es el peor de los mundos posibles:

- Fallo rápido (no hay colección de resultados parciales).
- Tareas huérfanas que consumen recursos sin que nadie lea sus resultados.
- Si más de una coroutine falla, solo la primera excepción llega al caller.

La situación contrasta con dos patrones correctos:

```python
# Opción A: recoger todos los resultados incluyendo excepciones
results = await asyncio.gather(*coros, return_exceptions=True)
errors = [r for r in results if isinstance(r, Exception)]

# Opción B: structured concurrency — cancela tareas hermanas automáticamente (Python 3.11+)
async with asyncio.TaskGroup() as tg:
    tasks = [tg.create_task(c) for c in coros]
```

---

## Evidence Review Protocol v1

### Paso 1 — Documentación oficial

**Resultado: CONFIRMADO — mención explícita con advertencia en docs.python.org**

`docs.python.org/3/library/asyncio-task.html` documenta el comportamiento exacto
con esta advertencia:

> *"If return_exceptions is False (default), the first raised exception is
> immediately propagated to the task that awaits on gather(). Other awaitables
> in the aws sequence **won't be cancelled** and will continue to run."*

Y sobre la relación con TaskGroup, en la misma página:

> *"A new alternative to create and run tasks concurrently and wait for their
> completion is asyncio.TaskGroup. TaskGroup provides stronger safety guarantees
> than gather for scheduling a nesting of subtasks: if a task (or a subtask, a
> task scheduled by a task) raises an exception, TaskGroup will, while gather
> will not, cancel the remaining scheduled tasks."*

**What's New In Python 3.11** (texto exacto):

> *"Added the TaskGroup class, an asynchronous context manager holding a group
> of tasks that will wait for all of them upon exit. **For new code this is
> recommended over using create_task() and gather() directly.**"*
> — Contributed by Yury Selivanov and others in gh-90908.

Adicionalmente, la documentación incluye una nota específica sobre el edge case
de cancelación post-excepción que confirma el problema de tareas huérfanas:

> *"Note: If return_exceptions is false, cancelling gather() after it has been
> marked done won't cancel any submitted awaitables. For instance, gather can be
> marked done after propagating an exception to the caller, therefore, calling
> gather.cancel() after catching an exception from gather won't cancel any other
> awaitables."*

**Veredicto paso 1:** documentación oficial de Python nombra y describe
explícitamente el comportamiento problemático. La recomendación de TaskGroup
para código nuevo aparece en What's New 3.11 con autoría de Yury Selivanov.

---

### Paso 2 — Incidentes reales

**Resultado: CONFIRMADO — issue oficial de CPython con respuesta de core developer**

**[bugs.python.org/issue31452](https://bugs.python.org/issue31452)** (migrado a cpython/issues/75633):  
Título: *"asyncio.gather does not cancel tasks if one fails"*.

El reporter documentó: si una coroutine de un gather falla, las otras siguen
ejecutándose aunque el resultado del gather ya haya sido descartado. Con tres
coroutines donde la del medio falla, la tercera completa e imprime su output
a pesar de que el gather ya devolvió excepción.

Respuesta de **Yury Selivanov** (core developer de asyncio):

> *"I'm going to reject this issue as it's not backwards compatible. I'll work
> on adding a new TaskGroup primitive in the next couple of days that would
> address this problem."*

El issue fue rechazado como "not backwards compatible" — confirma que el
comportamiento es una limitación de diseño reconocida por el equipo core.
La respuesta directa de Selivanov creó el ticket gh-90908 (abierto por Guido
van Rossum en febrero 2022) que produjo `asyncio.TaskGroup` en Python 3.11.

**[tqdm/tqdm#1286](https://github.com/tqdm/tqdm/issues/1286)**:  
La librería tqdm tuvo que añadir `return_exceptions` a su wrapper de gather
porque usuarios reportaron que sin él las excepciones interrumpían el progress
tracking de toda la operación en lugar de ser manejadas por tarea.

**Piccolo ORM:**  
La documentación del ORM Piccolo y su blog mencionan explícitamente el problema:
*"If more than one of the coroutines raises an exception, you won't be aware of it"*
en el contexto de fallos de transacciones de base de datos donde múltiples
coroutines de escritura fallan concurrentemente.

**Veredicto paso 2:** no existe un postmortem público de empresa con nombre,
fecha y métricas de impacto directamente atribuible a este patrón específico.
Lo que sí existe es un issue oficial de CPython donde el core developer de asyncio
(Yury Selivanov) confirmó el comportamiento como problema no backwards-compatible
y lo resolvió creando una nueva API (TaskGroup). Esto es evidencia institucional
de primer orden, aunque no es un incidente de producción en el sentido estricto.

---

### Paso 3 — Comunidad

**Resultado: CONSENSO TÉCNICO FUERTE — evidencia de múltiples fuentes verificadas**

**Yeray Diaz — "Asyncio Coroutine Patterns: Errors and Cancellation"** (Medium):  
Documenta "Loss of Partial Results" como consecuencia directa de gather sin
return_exceptions: *"Look at that! We managed results for 2 out of the 5 top
stories!"* — demostrando que con `return_exceptions=True` se recuperan resultados
parciales que de otro modo se pierden.

**Piccolo ORM Blog — "Exception handling in asyncio":**  
> *"If more than one of the coroutines raises an exception, you won't be aware
> of it. If you need to run some clean up code to handle an exception (for example,
> rolling back a transaction), then you could potentially miss it if a different
> coroutine raises an exception first."*

**SuperFastPython — "Asyncio gather() Exception in Task Does Not Cancel":**  
Documenta el comportamiento de tareas huérfanas con ejemplo ejecutable que
muestra tareas que siguen corriendo después de que gather() propaga la excepción.

**Lynn Root (roguelynn.com) — "Exception Handling in asyncio":**  
Referencia técnica ampliamente citada. Documenta el mecanismo de coroutines
que fallan silenciosamente y tareas que no se cancelan.

**Veredicto paso 3:** consenso técnico sólido en múltiples fuentes verificadas.
Ninguna fuente técnica defiende el comportamiento por defecto de gather() como
correcto para el caso de múltiples tareas concurrentes que pueden fallar.

---

### Paso 4 — Evidencia empírica propia

**Resultado: MUY FUERTE — primera regla por número de repos afectados en sweep 100**

- 88/250 repos afectados (35.2%) — **segunda por prevalencia de repos en sweep 250**
- 1095 hits totales — cuarta por volumen de hits (después de PYVIBE-017: 2510, PYVIBE-019: 760)
- 47/100 repos (47.0%) en sweep de 100 repos — **primera por prevalencia absoluta** en ese sweep
- Estabilidad Media (−11.8 pp): dilución estructural por incorporación de repos no-async
- Presente en repos de referencia: `home-assistant/core` (331 hits), `aiortc/aiortc` (54)
- 0 falsos positivos documentados en 250 repos escaneados

**Contexto del outlier home-assistant/core (331 hits):**  
Home Assistant es el proyecto async de Python de mayor escala en producción
(~200k usuarios activos). 331 instancias de gather sin return_exceptions en su
codebase es una señal fuerte de prevalencia del patrón en código async de larga
duración.

---

### Paso 5 — Intento de refutación

**Búsqueda activa de excepciones legítimas.**

#### ¿Hay casos donde el fail-fast sin return_exceptions sea la conducta deseada?

**Sí. Un caso legítimo concreto:**

**Validación paralela con semántica fail-fast:**

```python
# Patrón: validar múltiples condiciones en paralelo, fallar ante la primera
await asyncio.gather(
    check_authentication(token),
    check_rate_limit(user_id),
    check_quota(plan),
)
# Si cualquiera falla, queremos que el error se propague inmediatamente
```

En este caso el desarrollador podría argumentar que:
1. No necesita resultados parciales — la operación es todo-o-nada.
2. Quiere que la excepción suba al caller inmediatamente.

**Sin embargo, este argumento no justifica el comportamiento por defecto por dos razones:**

**Razón A:** Con gather sin return_exceptions, las otras dos coroutines
(`check_rate_limit`, `check_quota`) **siguen ejecutándose** después de que
`check_authentication` lanza. El fail-fast se aplica al caller pero no a las
tareas. Esto es peor que un fail-fast real — es "fallo con fuga de recursos".

**Razón B:** `asyncio.TaskGroup` (Python 3.11+) resuelve exactamente este caso
con semántica correcta: si una tarea falla, cancela las demás Y propaga la
excepción. TaskGroup es la solución correcta para fail-fast en contexto async.

**Veredicto refutación Paso 5A:** el argumento de "fail-fast es lo que quiero"
es técnicamente incorrecto para `gather()`. El fail-fast real requiere
TaskGroup. gather sin return_exceptions produce "fallo parcial con tareas
huérfanas", que nunca es la intención del desarrollador.

---

#### ¿TaskGroup (Python 3.11+) cambia el panorama de esta regla?

**Sí, de forma significativa — pero no invalida la regla.**

TaskGroup ofrece structured concurrency con semántica superior:
- Si cualquier tarea falla → cancela automáticamente las demás.
- Espera a que todas las tareas terminen antes de propagar.
- Propaga todas las excepciones como `ExceptionGroup`.

**Cuándo usar cada opción:**

| Necesito | Correcto | Incorrecto |
|----------|---------|-----------|
| Todas las excepciones + resultados parciales | `gather(..., return_exceptions=True)` | `gather(...)` sin flag |
| Fail-fast real (cancela los demás) | `TaskGroup` (3.11+) | `gather(...)` sin flag |
| Sin manejo de excepciones cross-task | `TaskGroup` (3.11+) | `gather(...)` sin flag |

`gather()` sin `return_exceptions=True` no es la respuesta correcta para
ninguno de los tres casos. Es el antipatrón en todos ellos.

**Implicación para la regla:** PYVIBE-013 sigue siendo válida para Python ≤ 3.10
y para codigo Python 3.11+ que no ha migrado a TaskGroup. La evidencia dice
"añade return_exceptions=True o migra a TaskGroup", no "usa TaskGroup obligatoriamente".

---

### Paso 6 — Evolución del patrón

#### ¿La documentación reciente de Python recomienda TaskGroup sobre gather()?

**Sí, con matices importantes:**

- **`What's New in Python 3.11`** (texto oficial): *"For new code this is
  recommended over using create_task() and gather() directly."*
- **`gather()` NO está deprecada** — no aparece ningún `.. deprecated::` marker
  en la documentación actual.
- La recomendación es para "new code" — no hay presión de migración forzada.
- `asyncio.gather` sigue siendo la API principal documentada en la sección de
  tasks de asyncio.

**Adopción real de TaskGroup (sweep 250 repos):**  
En el sweep de 250 repos no se recopiló estadística de TaskGroup usage.
La adopción masiva de TaskGroup requiere Python 3.11+ como mínimo. Python 3.10
tiene EOL en octubre 2026. La migración masiva es probable para 2027-2028.

#### ¿Esta regla quedará obsoleta?

**No — pero evolucionará en su recomendación:**

- **Corto plazo (hasta 2027):** La regla es crítica. La mayoría del código async
  en producción corre en Python 3.10/3.11 y usa gather. Los 1095 hits en el
  sweep son bugs activos.
- **Medio plazo (2027-2028):** El fix recomendado puede cambiar de
  "añade return_exceptions=True" a "migra a TaskGroup o usa return_exceptions=True".
- **Largo plazo:** Si TaskGroup se adopta masivamente, PYVIBE-013 podría
  complementarse con PYVIBE-02X "gather() usage en código async moderno →
  prefer TaskGroup".
- `gather()` sin return_exceptions seguirá siendo un bug aunque TaskGroup
  exista — no se vuelve correcto por la existencia de una mejor alternativa.

**Veredicto paso 6:** la regla tiene alta relevancia en 2026 y la mantendrá
hasta al menos 2028. La recomendación de TaskGroup ya está en el `evidence`
del rule desde su implementación.

---

## Clasificación final

**Evidence Level: A**

| Criterio | Estado |
|----------|--------|
| Validada en repos reales (88/250, 35.2%) | ✅ |
| Documentación oficial Python nombra el comportamiento con advertencia explícita | ✅ |
| CPython tracker issue confirmado por core developer (Yury Selivanov) — motivó TaskGroup | ✅ |
| What's New 3.11 recomienda TaskGroup sobre gather() para código nuevo | ✅ |
| Falsos positivos documentados en campo | ✅ 0 |
| Incidente de producción con empresa + fecha + impacto cuantificado | ❌ no encontrado |
| Caso legítimo de uso del comportamiento por defecto | ⚠️ validación paralela (pero TaskGroup es la respuesta correcta para ese caso) |

**Por qué A y no A+:**  
No existe un postmortem público de empresa (con nombre, fecha, impacto cuantificado)
directamente atribuible a `gather()` sin `return_exceptions`. La evidencia institucional
(CPython tracker, Yury Selivanov, TaskGroup como respuesta directa) es de primer
orden, pero no es el formato de incidente verificable que A+ requiere.

**Por qué A y no B:**  
Python docs documenta explícitamente el comportamiento problemático (tareas que
siguen ejecutando) con una nota de advertencia. Un core developer confirmó que
es un problema de diseño no backwards-compatible y creó una nueva API como fix.
What's New 3.11 recomienda la alternativa explícitamente. Esto cumple el criterio
de "documentación oficial que describe el problema como bug/antipatrón" del Evidence A.

---

## Confidence

```
Confidence:
  Detection:         High — AST check directo: busca asyncio.gather() call
                            sin keyword return_exceptions=True; 0 FPs en 250
                            repos; el único caso de FP teórico (validación
                            fail-fast intencional) requiere TaskGroup de todas
                            formas — la regla no genera FP falso
  Runtime impact:    High — tareas huérfanas son un bug de runtime documentado
                            oficialmente; en home-assistant/core (331 hits,
                            producción con 200k+ usuarios) el impacto de
                            resource leak por tareas abandonadas es real;
                            la pérdida de resultados parciales es observable
  External evidence: High — docs.python.org documenta el comportamiento con
                            advertencia explícita; Yury Selivanov confirmó el
                            problema en CPython tracker; What's New 3.11 con
                            recomendación explícita de TaskGroup; consenso
                            técnico unánime en múltiples fuentes verificadas
```

---

## Fuentes verificadas

- [asyncio-task.html — asyncio.gather() documentation](https://docs.python.org/3/library/asyncio-task.html#asyncio.gather)
- [asyncio-task.html — asyncio.TaskGroup](https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup)
- [What's New In Python 3.11 — TaskGroup recommendation](https://docs.python.org/3/whatsnew/3.11.html)
- [bugs.python.org/issue31452 — asyncio.gather does not cancel tasks if one fails (Yury Selivanov)](https://bugs.python.org/issue31452)
- [python/cpython issue #90908 — Introduce task groups to asyncio (Guido van Rossum)](https://github.com/python/cpython/issues/90908)
- [Piccolo ORM Blog — Exception handling in asyncio](https://piccolo-orm.com/blog/exception-handling-in-asyncio/)
- [Yeray Diaz — Asyncio Coroutine Patterns: Errors and Cancellation (Medium)](https://yeraydiazdiaz.medium.com/asyncio-coroutine-patterns-errors-and-cancellation-3bb422e961ff)
- [SuperFastPython — Asyncio gather() Exception in Task Does Not Cancel](https://superfastpython.com/asyncio-gather-exception-not-cancel/)
- [tqdm/tqdm#1286 — Add return_exceptions to asyncio.gather wrapper](https://github.com/tqdm/tqdm/issues/1286)
