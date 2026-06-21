# python-vibe-guard — Catálogo de Reglas

**Versión:** 0.7.1 · 20 reglas activas · 127 tests  
**Última actualización:** 2026-06-21  
**Fuente de datos:** sweep 250 repos (95,678 .py files) · `research/datasets/250-repos.json`

---

## Tabla consolidada

Las tres columnas de confianza (Detection / Runtime Impact / External Evidence)
se completan únicamente tras aplicar el Evidence Review Protocol v1.
Para reglas en estado ⏳ esas columnas muestran `—` hasta que se realice la investigación.

| Regla | Categoría | Evidence | Detection | Runtime Impact | External Evidence | Repos 250 | Estado |
|-------|-----------|----------|-----------|----------------|-------------------|-----------|--------|
| [PYVIBE-001](accepted/PYVIBE-001.md) — `time.sleep()` en async def | Bloqueo de event loop | **A+** | High | High | High | 12.4% (31/250) | ✅ Protocolo v1 |
| [PYVIBE-002](accepted/PYVIBE-002.md) — `requests` sync en async def | Bloqueo de event loop | B (pendiente) | — | — | — | 4.0% (10/250) | ⏳ Pendiente |
| [PYVIBE-003](accepted/PYVIBE-003.md) — `asyncio.run()` dentro de async def | Primitiva incorrecta | B (pendiente) | — | — | — | 0.4% (1/250) | ⏳ Pendiente |
| [PYVIBE-004](accepted/PYVIBE-004.md) — `threading.Lock()` en async def | Primitiva incorrecta | B (pendiente) | — | — | — | 2.0% (5/250) | ⏳ Pendiente |
| [PYVIBE-005](accepted/PYVIBE-005.md) — Celery task sin `time_limit` | Resiliencia | B (pendiente) | — | — | — | 12.8% (32/250) | ⏳ Pendiente |
| [PYVIBE-006](accepted/PYVIBE-006.md) — `ContextVar` sin `reset()` | Estado / Contexto | B (pendiente) | — | — | — | 6.0% (15/250) | ⏳ Pendiente |
| [PYVIBE-007](accepted/PYVIBE-007.md) — `subprocess.run` en async def | Bloqueo de event loop | B (pendiente) | — | — | — | 4.8% (12/250) | ⏳ Pendiente |
| [PYVIBE-008](accepted/PYVIBE-008.md) — `sqlite3` en async def | Bloqueo de event loop | B (pendiente) | — | — | — | 8.8% (22/250) | ⏳ Pendiente |
| [PYVIBE-009](accepted/PYVIBE-009.md) — `open()` en lugar de `aiofiles` | Bloqueo de event loop | B (pendiente) | — | — | — | 24.0% (60/250) | ⏳ Pendiente |
| [PYVIBE-010](accepted/PYVIBE-010.md) — `httpx.get/post` sync en async def | Bloqueo de event loop | B (pendiente) | — | — | — | 0.8% (2/250) | ⏳ Pendiente |
| [PYVIBE-011](accepted/PYVIBE-011.md) — `os.blocking` en async def | Bloqueo de event loop | B (pendiente) | — | — | — | 0.0% (0/250) ¹ | ⏳ Pendiente |
| [PYVIBE-012](accepted/PYVIBE-012.md) — `create_task()` huérfano | Gestión de tareas | B (pendiente) | — | — | — | 12.0% (30/250) | ⏳ Pendiente |
| [PYVIBE-013](accepted/PYVIBE-013.md) — `gather()` sin `return_exceptions` | Gestión de tareas | **A** | High | High | High | 35.2% (88/250) | ✅ Protocolo v1 |
| [PYVIBE-014](accepted/PYVIBE-014.md) — `ensure_future()` huérfano | Gestión de tareas | B (pendiente) | — | — | — | 5.6% (14/250) | ⏳ Pendiente |
| [PYVIBE-015](accepted/PYVIBE-015.md) — `loop.run_until_complete()` en async def | Primitiva incorrecta | B (pendiente) | — | — | — | 2.0% (5/250) | ⏳ Pendiente |
| [PYVIBE-016](accepted/PYVIBE-016.md) — `httpx.Client()` sync en async def | Bloqueo de event loop | B (pendiente) | — | — | — | 0.8% (2/250) | ⏳ Pendiente |
| [PYVIBE-017](accepted/PYVIBE-017.md) — `except` silencioso en async def | Manejo de errores | **A** | Medium-High | Medium | Medium | 48.8% (122/250) | ✅ Protocolo v1 + FP Audit |
| [PYVIBE-018](accepted/PYVIBE-018.md) — `while True` sin `await` | Gestión de tareas | B (pendiente) | — | — | — | 6.8% (17/250) | ⏳ Pendiente |
| [PYVIBE-019](accepted/PYVIBE-019.md) — Retry sin backoff | Resiliencia | B (pendiente) | — | — | — | 32.8% (82/250) | ⏳ Pendiente |
| [PYVIBE-020](accepted/PYVIBE-020.md) — `put_nowait()` sin handler `QueueFull` | Manejo de errores | B (pendiente) | — | — | — | 16.4% (41/250) ² | ⏳ Pendiente |

¹ PYVIBE-011: 0 hits en 250 repos — Evidence B se mantiene porque el patrón es real aunque infrecuente en repos de alta estrella.  
² PYVIBE-020: debut en sweep 250 (sin baseline en 100 repos). Tasa de debut 16.4% es sólida para regla nueva.

---

## Resumen por categoría

| Categoría | Reglas | Reglas con protocolo |
|-----------|--------|---------------------|
| Bloqueo de event loop | 001, 002, 007, 008, 009, 010, 011, 016 | 001 ✅ |
| Gestión de tareas | 012, 013, 014, 018 | 013 ✅ |
| Manejo de errores | 017, 020 | 017 ✅ |
| Resiliencia | 005, 019 | — |
| Primitiva incorrecta | 003, 004, 015 | — |
| Estado / Contexto | 006 | — |

---

## Progreso del Evidence Review Protocol v1

| Nivel | Reglas |
|-------|--------|
| A+ | PYVIBE-001 |
| A | PYVIBE-013, PYVIBE-017 |
| B (protocolo completo pendiente) | PYVIBE-002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 014, 015, 016, 018, 019, 020 |
| C | — |

**Protocolo completado:** 3/20 reglas (15%)

---

## Nota sobre las reglas en estado B

Las 17 reglas marcadas como "B (pendiente de protocolo completo)" no son menos
válidas que las tres ya investigadas. Evidence B significa que la regla está
validada en repos reales con hits confirmados — el patrón existe en código de
producción y el detector funciona. Lo que falta es el recorrido sistemático de
6 pasos (documentación oficial, incidentes, comunidad, empírica, refutación,
evolución) que permite asignar niveles de confianza en las tres dimensiones y
documentar explícitamente los casos legítimos conocidos.

En la práctica, las reglas B son suficientemente fiables para uso en producción.
El protocolo completo añade transparencia, calibración de la severidad y
documentación de excepciones — no es un prerrequisito de validez.

Las reglas se irán actualizando progresivamente priorizando por:
1. Score de severidad (prevalencia × peso CRITICAL/WARNING)
2. Número de repos afectados en sweep 250
3. Casos donde haya candidatos a excepción legítima sin documentar
