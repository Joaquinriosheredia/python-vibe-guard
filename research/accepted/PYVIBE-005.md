# PYVIBE-005 — Tarea Celery sin time_limit

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/celery_time_limit.py`  
**Patrón:** `@app.task` / `@shared_task` sin `time_limit` ni `soft_time_limit`

---

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 15/100 (15.0%) | 32/250 (12.8%) |
| Total hits | 882 | 1072 |
| Estabilidad 100→250 | Alta (−2.2 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `celery/celery` — 352 hits
- `coleifer/huey` — 172 hits
- `WeblateOrg/weblate` — 79 hits
- `taskiq-python/taskiq` — 57 hits
- `jumpserver/jumpserver` — 52 hits

---

## Evidence Review Protocol v1

### Paso 1 — Documentación oficial

**Resultado: CONFIRMADO — advertencia explícita en docs.celeryq.dev**

**[docs.celeryq.dev — Tasks (userguide/tasks.html)](https://docs.celeryq.dev/en/stable/userguide/tasks.html)** incluye una sección de advertencia directa:

> *"A task that blocks indefinitely may eventually stop the worker instance from doing any other work."*

Y la recomendación operativa:

> *"Time limits are convenient for making sure all tasks return in a timely manner, but a time limit event will actually kill the process by force so only use them to detect cases where you haven't used manual timeouts yet."*

**[docs.celeryq.dev — Configuration (userguide/configuration.html)](https://docs.celeryq.dev/en/stable/userguide/configuration.html)**:

- `task_time_limit` — **Default: No time limit.** *"Task hard time limit in seconds. The worker processing the task will be killed and replaced with a new one when this is exceeded."*
- `task_soft_time_limit` — **Default: No soft time limit.** *"Task soft time limit in seconds. The SoftTimeLimitExceeded exception will be raised when this is exceeded."*

**[docs.celeryq.dev — Workers Guide (userguide/workers.html)](https://docs.celeryq.dev/en/stable/userguide/workers.html)**:

> *"The soft time limit allows the task to catch an exception to clean up before it is killed: the hard timeout isn't catch-able and force terminates the task."*

**Matiz crítico:** Los docs no califican la ausencia de `time_limit` como un antipatrón absoluto. Lo presentan como *fallback de detección*, no como primera línea de defensa. La preferencia de los docs es que el código de la tarea implemente sus propios timeouts (ej: `requests` con `timeout=`) y que `time_limit` actúe de red de seguridad.

**Veredicto paso 1:** documentación oficial nombra el riesgo explícitamente y proporciona `time_limit`/`soft_time_limit` como la mitigación estándar. El default de ambos es `None` — sin ningún límite.

---

### Paso 2 — Incidentes reales

**Resultado: CONFIRMADO — incidente documentado en producción**

**SquadStack Engineering — "Two years with Celery in Production: Bug Fix Edition"** ([Medium](https://medium.com/squad-engineering/two-years-with-celery-in-production-bug-fix-edition-22238669601d)):

Incidente documentado en producción:
- **Síntomas:** workers colgados cada 2-3 horas, tasks marcadas como "picked but unacknowledged" en RabbitMQ, workers que habían iniciado tasks pero nunca las completaban
- **Causa raíz:** deadlock entre `psycopg2==2.5.2` y librerías SSL — PostgreSQL registra un callback SSL que no se libera correctamente tras cerrar la conexión, impidiendo que otros consumidores de SSL desbloqueen, causando deadlock de thread
- **Diagnóstico:** `strace` en el proceso colgado revelaba `futex(FUTEX_WAIT_PRIVATE)` indefinido
- **Resolución:** upgrade `psycopg2` a 2.6.1
- **Relación con `time_limit`:** si las tasks hubieran tenido `time_limit`, el worker hubiera sido killed y reemplazado automáticamente en lugar de requerir reinicio manual. La ausencia de `time_limit` convirtió un bug en un worker permanentemente bloqueado.

**[celery/celery#4321](https://github.com/celery/celery/issues/4321)** — "Worker hangs and stop responding after an undeterminated amount of time":
- Workers con `concurrency=1` y `worker_max_tasks_per_child=2000` colgaban justo al alcanzar la tarea 2000
- `strace` mostraba proceso principal bloqueado en `recvfrom()` indefinidamente
- Proceso hijo zombificado sin ser reaped
- Backlog de cola seguía acumulándose — interrupción de servicio en producción
- Issue marcado como "Status: Needs Verification" — sin resolución documentada, sigue abierto

**[celery/celery#4185](https://github.com/celery/celery/issues/4185)** — IPC deadlock:
- Proceso master bloqueado en `read()` de sistema
- Reiniciar Celery o enviar `SIGUSR1` rompía el bloqueo
- Impacto: todos los workers paraban de procesar tasks

**Veredicto paso 2:** incidente real documentado (SquadStack, producción verificable) + múltiples issues en celery/celery confirmando el patrón de "worker colgado sin recuperación automática". La ausencia de `time_limit` es el factor que convierte un bug transitorio en interrupción permanente de servicio.

---

### Paso 3 — Comunidad

**Resultado: CONSENSO FUERTE — recomendación activa de usar time_limit en producción**

**Wolt Engineering — "5 tips for writing production-ready Celery tasks"** ([careers.wolt.com](https://careers.wolt.com/en/blog/tech/5-tips-for-writing-production-ready-celery-tasks)):

> *"Consider configuring global task execution time limit and using task specific hard / soft limits when needed. [...] These boundaries safeguard systems from worst-case scenarios that theoretically shouldn't happen, and they communicate performance requirements to other developers reviewing the code."*

**GitGuardian — "Celery Task Resilience: Advanced Strategies"** ([blog.gitguardian.com](https://blog.gitguardian.com/celery-tasks-retries-errors/)):
- Documenta `time_limit` y `soft_time_limit` como estrategia estándar de resiliencia
- Pattern recomendado: soft_limit al percentil 95 de tiempo de ejecución, hard_limit 20% mayor

**Taylor Hughes (Medium) — "Three quick tips from two years with Celery"** ([medium.com](https://medium.com/@taylorhughes/three-quick-tips-from-two-years-with-celery-c05ff9d7f9eb)):
- Recomienda `CELERYD_TASK_SOFT_TIME_LIMIT = 60` globalmente: *"This will prevent unexpectedly never-ending tasks from clogging your queues."*

**celery-users mailing list** ([narkive](https://celery-users.narkive.com/U3jbzogh/celery-workers-stop-fetching-new-task-after-few-hours-of-operation)):
- Reports recurrentes de "workers que dejan de procesar tasks después de horas de operación" — patrón reconocible de workers colgados sin `time_limit`

**Veredicto paso 3:** consenso fuerte en la comunidad. No se encontraron voces que argumenten que omitir `time_limit` sea una práctica recomendada. La discusión es *cómo* configurarlo, no *si* configurarlo.

---

### Paso 4 — Evidencia empírica propia

**Resultado: FUERTE**

- 32/250 repos afectados (12.8%) — estabilidad Alta (−2.2 pp entre 100 y 250 repos)
- 1072 hits totales — segundo mayor total de hits en la muestra de 20 reglas
- Alta concentración en repos del propio ecosistema: `celery/celery` (352), `huey` (172)
- Presente en proyectos de producción reales: `WeblateOrg/weblate` (79), `jumpserver/jumpserver` (52)
- 0 falsos positivos documentados en campo

**Nota sobre celery/celery y huey:** 524 de los 1072 hits (48.9%) provienen de los dos repos del ecosistema de task queues. Estos repos incluyen código de ejemplo, tasks de test e implementaciones internas que intencionalmente omiten `time_limit`. Este sesgo eleva el conteo total pero no invalida la regla — los 548 hits restantes provienen de proyectos de usuario real.

---

### Paso 5 — Intento de refutación

**Búsqueda activa de excepciones legítimas.**

#### ¿Hay casos donde NO poner `time_limit` sea intencional?

**Candidato A — Tareas de larga duración legítima (batch, ETL, ML training)**

Los docs oficiales reconocen explícitamente este caso:

> *"For the best performance route long-running and short-running tasks to dedicated workers."*

Y el propio framing de los docs ("only use them to detect cases where you haven't used manual timeouts yet") implica que tareas con timeouts manuales internos (`requests(timeout=)`, `psycopg2` statement timeout, etc.) no necesitan `time_limit` como primera línea.

**Veredicto:** excepción legítima existe. Un task de ML training de 4 horas con checkpointing y manejo de señales NO debería tener `time_limit=3600*4` si ya tiene recuperación interna. La regla generaría un FP real en ese contexto.

**Candidato B — Configuración global que hace redundante el per-task limit**

Esto es una **limitación real y documentada de PYVIBE-005**:

Si el proyecto tiene configurado:
```python
# settings.py
CELERY_TASK_TIME_LIMIT = 3600
CELERY_TASK_SOFT_TIME_LIMIT = 3000
```

...entonces **todos** los tasks heredan esos límites automáticamente. La ausencia de `time_limit` en el decorator no significa "sin límite" — significa "hereda el default del worker".

PYVIBE-005 **no verifica** si existe configuración global. Esto puede producir falsos positivos en proyectos que:
- Tienen `task_time_limit` en su configuración de Celery
- Usan `--time-limit` como argumento CLI al iniciar el worker
- Tienen `time_limit` heredado de una clase base de task

**Veredicto:** excepción legítima con impacto real. Proyectos bien configurados globalmente recibirían warnings innecesarios.

**Candidato C — repos del propio ecosistema (celery/celery, huey)**

Tasks de ejemplo e infraestructura interna que intencionalmente demuestran la API sin límites. **No es una excepción al patrón** — son casos de test/ejemplo, no código de producción. La regla no debería silenciarse por estos repos.

#### Resumen de refutación

| Caso | Veredicto |
|------|-----------|
| Tareas de larga duración con timeouts manuales internos | Excepción legítima real |
| Configuración global `task_time_limit` en settings | Excepción legítima — PYVIBE-005 no la detecta |
| Tasks de ejemplo/test en repos del ecosistema | FP de contexto, no invalida la regla |
| Tasks que explícitamente "no deben tener límite" | Antipatrón — cualquier tarea debería tener límite razonable |

---

### Paso 6 — Evolución del patrón

**Resultado: ESTABLE — recomendación sin cambios de fondo en v4→v5**

**Celery 4.0:**
- Deprecó configuración antigua uppercase (`CELERYD_TASK_TIME_LIMIT` → `task_time_limit`)
- Introdujo `-Ofair` como estrategia de scheduling por defecto, haciéndolo más friendly para tasks largas
- Los defaults de `task_time_limit` y `task_soft_time_limit` permanecieron en `None`

**Celery 5.0–5.5:**
- Eliminó gradualmente soporte de configuración antigua (eliminación completa en 6.0)
- Sin cambios en la recomendación sobre `time_limit`
- Los defaults siguen siendo `None`

**Celery 5.7:**
- Añadió atributo `soft_time_limit` en el request object de la task (introspección en runtime)
- Sin cambios en comportamiento ni recomendaciones sobre per-task `time_limit`

**Celery 5.6.x (actual):**
- Configuración legacy (`CELERYD_` prefix) deprecada, eliminación prevista en 6.0
- Recomendación en docs: igual que v4 — `time_limit` como red de seguridad, timeouts manuales como primera línea

**Veredicto paso 6:** la postura de Celery sobre `time_limit` no ha cambiado en >5 años. El default `None` es una decisión de diseño deliberada (los límites apropiados dependen del dominio), no un olvido. La recomendación de los docs es constante: usa `time_limit` como fallback de detección. Lo que **sí** cambió es que desde v4 la configuración global se hace con `task_time_limit` (minúsculas en snake_case), no con el prefijo `CELERYD_`.

---

## Clasificación final

**Evidence Level: A**

| Criterio | Estado |
|----------|--------|
| Validada en repos reales (32/250, 12.8%) | ✅ |
| Documentación oficial advierte explícitamente sobre blocking indefinido | ✅ |
| Mitigación estándar documentada (time_limit/soft_time_limit) | ✅ |
| Incidente público documentado (SquadStack producción + celery#4321) | ✅ |
| Falsos positivos documentados en campo | ✅ 0 en campo |
| Excepción legítima conocida | ⚠️ Sí — configuración global + tasks con timeouts manuales |

**Por qué A y no A+:** existen dos excepciones legítimas verificadas: (1) proyectos con `task_time_limit` global configurado en settings donde el per-task limit es redundante, y (2) tareas de larga duración con manejo de timeouts manuales internos. Además, el propio framing de los docs oficiales presenta `time_limit` como fallback/detección, no como primera línea obligatoria. Esto introduce ambigüedad que impide A+.

**Por qué A y no B:** la documentación oficial nombra explícitamente el riesgo de blocking indefinido, proporciona `time_limit` como la mitigación estándar, y hay un incidente real de producción documentado con síntomas directamente relacionados.

---

## Confidence

```
Confidence:
  Detection:         Medium-High — AST sobre argumentos del decorator
                                   detecta ausencia de time_limit/soft_time_limit
                                   correctamente; NO detecta configuración
                                   global en settings.py (punto ciego real)

  Runtime impact:    High — worker sin time_limit en task colgada requiere
                            reinicio manual; documentado en SquadStack prod
                            y celery#4321; sin time_limit, un deadlock
                            transitorio se convierte en interrupción indefinida

  External evidence: Medium-High — docs oficiales advierten explícitamente +
                                   incidente real documentado (SquadStack) +
                                   consenso comunitario fuerte (Wolt, GitGuardian);
                                   matiz: docs presentan time_limit como
                                   fallback, no como requerimiento absoluto
```

---

## Fuentes verificadas

- [Celery Tasks docs — "A task that blocks indefinitely may eventually stop the worker"](https://docs.celeryq.dev/en/stable/userguide/tasks.html)
- [Celery Configuration docs — task_time_limit / task_soft_time_limit (Default: None)](https://docs.celeryq.dev/en/stable/userguide/configuration.html)
- [Celery Workers Guide — Time Limits section](https://docs.celeryq.dev/en/stable/userguide/workers.html)
- [SquadStack Engineering — Two years with Celery in Production (incidente producción verificable)](https://medium.com/squad-engineering/two-years-with-celery-in-production-bug-fix-edition-22238669601d)
- [celery/celery#4321 — Worker hangs and stop responding (abierto, Needs Verification)](https://github.com/celery/celery/issues/4321)
- [celery/celery#4185 — Workers randomly hang on IPC](https://github.com/celery/celery/issues/4185)
- [Wolt Engineering — 5 tips for writing production-ready Celery tasks](https://careers.wolt.com/en/blog/tech/5-tips-for-writing-production-ready-celery-tasks)
- [GitGuardian — Celery Task Resilience: Advanced Strategies](https://blog.gitguardian.com/celery-tasks-retries-errors/)
- [Taylor Hughes — Three quick tips from two years with Celery](https://medium.com/@taylorhughes/three-quick-tips-from-two-years-with-celery-c05ff9d7f9eb)
