# PYVIBE-001 — time.sleep() en async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/async_sleep.py`  
**Patrón:** `time.sleep(N)` llamado directamente dentro de `async def`

---

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 16/100 (16.0%) | 31/250 (12.4%) |
| Total hits | 55 | 87 |
| Estabilidad 100→250 | Alta (−3.6 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `home-assistant/core` — 17 hits
- `pmh1314520/WebRPA` — 9 hits
- `MODSetter/SurfSense` — 7 hits
- `IBM/mcp-context-forge` — 6 hits
- `learning-at-home/hivemind` — 5 hits

---

## Evidence Review Protocol v1

### Paso 1 — Documentación oficial

**Resultado: CONFIRMADO — mención explícita en docs.python.org**

`docs.python.org/3/library/asyncio-task.html` (sección `asyncio.to_thread()`) usa `time.sleep()` como el ejemplo canónico de llamada bloqueante, con la nota explícita:

> *"Note that time.sleep() can be replaced with any blocking IO-bound operation, such as file operations."*

y el efecto documentado:

> *"Directly calling blocking_io() in any coroutine would block the event loop for its duration, resulting in an additional 1 second of run time."*

El ejemplo de código en la doc muestra `time.sleep(1)` dentro de una función sync (correctamente) y la llamada bloqueante desde una coroutine como el antipatrón a evitar, mostrando `asyncio.to_thread(blocking_io)` como la solución.

`docs.python.org/3/library/asyncio-dev.html` (Developing with asyncio) añade:

> *"Blocking (CPU-bound) code should not be called directly. For example, if a function performs a CPU-intensive calculation for 1 second, all concurrent asyncio Tasks and IO operations would be delayed by 1 second."*

Este texto no nombra `time.sleep()` explícitamente, pero lo describe de forma genérica.

**Tornado FAQ** (framework de referencia para async Python predecesor de asyncio):

> *"time.sleep is a blocking function: it doesn't allow control to return to the IOLoop so that other handlers can be run."*

**Veredicto paso 1:** documentación oficial Python nombra `time.sleep()` explícitamente como el ejemplo estándar de llamada bloqueante que no debe usarse directamente en coroutines.

---

### Paso 2 — Incidentes reales

**Resultado: CONFIRMADO — issue real en producción**

**[home-assistant/core#119628](https://github.com/home-assistant/core/issues/119628)** (cerrado):  
`time.sleep(0.3)` en la librería `pyserial-asyncio` (línea 104 de `serial/urlhandler/protocol_socket.py`) era llamado desde dentro del event loop de Home Assistant. Home Assistant 2024.6.2 introdujo detección activa de llamadas bloqueantes y produjo el warning:

> *"Detected blocking call to sleep inside the event loop by integration 'config'..."*

La issue fue reportada en core-2024.6.2 y no ocurría en core-2024.4.4. Issue cerrada — el impacto fue degradación de responsividad durante reloads de integration.

**[MagicStack/uvloop#29](https://github.com/MagicStack/uvloop/issues/29)** (aparece en búsqueda, no verificado con fetch):  
Mencionado en el contexto de que "el tiempo del loop no avanza cuando el loop está bloqueado por time.sleep()" — consistente con el comportamiento documentado.

**DEV.to "3-Hour Debugging: How time.sleep in Async Functions Killed Our asyncio Concurrency":**  
Post con formato de caso de debugging. El síntoma: un servicio de recolección de datos que no mejoró al convertirse a async, tomando los mismos 30 minutos por ejecución. Causa raíz: `time.sleep(0.5)` enterrado en una función anidada. **No es un postmortem con nombre de empresa verificable** — es contenido educativo presentado como caso de estudio. No cuenta como incidente público confirmado.

**Veredicto paso 2:** un incidente real confirmado en GitHub (home-assistant/core#119628, cerrado). El impacto fue observable en producción.

---

### Paso 3 — Comunidad

**Resultado: CONSENSO UNIVERSAL — sin casos de desacuerdo**

La búsqueda no encontró ninguna discusión en Stack Overflow, DEV.to, Medium o foros que sugiera que `time.sleep()` dentro de `async def` sea aceptable. El consenso es unánime:

- La causa síntomática más reportada: *"convertí mi código a async pero no mejora la velocidad"*
- Solución universal documentada: reemplazar `time.sleep(n)` por `await asyncio.sleep(n)`, o por `await asyncio.to_thread(time.sleep, n)` si la intención es bloquear en un thread aparte
- El Mergify blog documenta la detección de event loop blocking mediante medición de latencia; usa `time.sleep()` como ejemplo paradigmático del problema a detectar

**Veredicto paso 3:** la comunidad no tiene posiciones encontradas sobre este patrón. Es tratado como bug obvio.

---

### Paso 4 — Evidencia empírica propia

**Resultado: FUERTE**

- 31/250 repos afectados (12.4%) — estabilidad Alta (−3.6 pp entre 100 y 250 repos)
- 87 hits totales en proyectos de alta estrella con asyncio
- Presente en repos de referencia: `home-assistant/core`, `MODSetter/SurfSense`, `IBM/mcp-context-forge`
- 0 falsos positivos documentados en 250 repos escaneados

---

### Paso 5 — Intento de refutación

**Búsqueda activa de excepciones legítimas.**

**¿Existe algún caso donde `time.sleep()` dentro de `async def` sea intencional y correcto?**

La búsqueda encontró tres escenarios candidatos:

**Candidato A — Testing de comportamiento bloqueante**  
Usar `time.sleep()` en un test `async def` para simular una llamada bloqueante y verificar que el detector de blocking funciona. *Técnicamente funciona, pero:*
- `asynctest` y `sleepfake` (librerías de testing para asyncio) proveen `advance()` y mocking de clock precisamente para evitar `time.sleep()` real en tests
- Ningún framework de testing Python recomienda `time.sleep()` real en async tests; se recomienda mockear o usar `asyncio.sleep()` con un loop de testing
- **Veredicto: no es una excepción legítima que invalide la regla**

**Candidato B — Delay deliberado en un sistema sin concurrencia**  
Código que usa `async def` pero en la práctica solo ejecuta una tarea a la vez y quiere añadir un delay. `time.sleep()` funciona en este caso porque no hay otra coroutine esperando.  
- Esto es una antipatrón de diseño: si no se necesita concurrencia, no debería usarse asyncio
- Si se necesita asyncio pero se quiere bloquear un momento, `await asyncio.sleep(n)` es siempre equivalente y correcto
- **Veredicto: funciona técnicamente pero nunca es la opción correcta**

**Candidato C — Wrapper para `asyncio.to_thread()`**  
`await asyncio.to_thread(time.sleep, n)` — llamar `time.sleep` desde `async def` *como argumento de `to_thread`*, no como llamada directa. Esto ES correcto.  
- PYVIBE-001 **no flagea este patrón**: la regla detecta `time.sleep(...)` como expresión directa en el cuerpo de `async def`, no como argumento de otra función
- **Veredicto: caso correcto, y la regla ya lo maneja bien**

**Excepción conocida documentada:**  
No se encontró ningún caso donde `time.sleep(n)` directamente en el cuerpo de `async def` sea la opción técnicamente correcta sobre `await asyncio.sleep(n)`. Tornado FAQ, Python docs y comunidad son unánimes.

**Límite honesto:** los 31 repos con hits no han sido auditados manualmente para verificar si algún hit está en un test que específicamente testea comportamiento bloqueante. Este caso extremo existe en teoría pero no se ha verificado en el scan actual.

---

## Clasificación final

**Evidence Level: A+**

| Criterio | Estado |
|----------|--------|
| Validada en repos reales (31/250, 12.4%) | ✅ |
| Documentación oficial Python nombra `time.sleep()` explícitamente | ✅ |
| Incidente público confirmado (HA core#119628, cerrado) | ✅ |
| Falsos positivos documentados en campo | ✅ 0 |
| Excepción legítima conocida | ✅ ninguna para llamada directa |

---

## Confidence

```
Confidence:
  Detection:         High — AST directo sobre name="sleep" en module time;
                            0 FP documentados en 250 repos; el Candidato C
                            (to_thread) no es flagueado correctamente
  Runtime impact:    High — bloquea el event loop completo para toda la
                            duración del sleep; efecto demostrado en HA prod
  External evidence: High — docs.python.org nombra time.sleep() explícitamente
                            + HA issue real cerrado + consenso comunitario unánime
```

---

## Fuentes verificadas

- [asyncio-task.html — asyncio.to_thread() example](https://docs.python.org/3/library/asyncio-task.html)
- [asyncio-dev.html — Developing with asyncio](https://docs.python.org/3/library/asyncio-dev.html)
- [Tornado FAQ — time.sleep is a blocking function](https://www.tornadoweb.org/en/stable/faq.html)
- [home-assistant/core#119628 — Blocking call to sleep inside event loop](https://github.com/home-assistant/core/issues/119628)
- [Mergify — Detecting Blocking Tasks in Asyncio](https://mergify.com/blog/detecting-blocking-tasks-in-asyncio-by-measuring-event-loop-latency/)
- [DEV.to — 3-Hour Debugging case study (educativo, sin empresa verificable)](https://dev.to/_eb7f2a654e97a60ae9f96e/3-hour-debugging-how-timesleep-in-async-functions-killed-our-asyncio-concurrency-43c3)
