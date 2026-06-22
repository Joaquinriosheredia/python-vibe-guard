# python-vibe-guard — Catálogo de Reglas

**Versión:** 0.7.2 · 20 reglas activas · 145 tests  
**Última actualización:** 2026-06-22  
**Fuente de datos:** sweep 250 repos (95,678 .py files) · `research/datasets/250-repos.json`

---

## Evidence Review Progress

```
[██████░░░░░░░░░░░░░░]  6/20 (30%)
```

| Completado | Pendiente |
|-----------|----------|
| PYVIBE-001 (A+), PYVIBE-005 (A), PYVIBE-009 (B), PYVIBE-013 (A), PYVIBE-017 (A), PYVIBE-019 (A) | 14 reglas restantes |

---

## Nota sobre los dos ejes del catálogo

Este catálogo usa dos ejes independientes que no tienen que coincidir:

**Evidence Level** — cuánto sabemos que el patrón representa un problema real.
Responde a: ¿existe documentación oficial que lo describa como antipatrón? ¿hay incidentes de producción documentados? ¿qué tan fuertes son los datos empíricos y el consenso comunitario? Se asigna tras aplicar el Evidence Review Protocol v1 (6 pasos: docs, incidente, comunidad, empírica, refutación, evolución).

| Nivel | Significado |
|-------|-------------|
| **A+** | Docs oficiales nombran el patrón explícitamente + incidente real + 0 excepciones legítimas |
| **A**  | Docs oficiales cubren el problema + incidente real confirmado |
| **B**  | Validado empíricamente en repos reales; docs y/o incidente pendientes de confirmación |
| **C**  | Solo hipótesis de diseño — sin validación empírica |

**Recomendación** — qué hace el detector cuando encuentra el patrón (severidad en el código).
Responde a: cuando el patrón aparece en producción real, ¿cómo de urgente es el impacto? Se asigna al implementar la regla, y puede ajustarse tras el Evidence Review.

**Relación entre ambos ejes:** Una regla Evidence B puede seguir siendo CRITICAL si su mecanismo de daño es bien conocido aunque el incidente específico aún no esté documentado públicamente. Una regla Evidence A podría rebajarse a WARNING si el impacto depende del contexto (como PYVIBE-009, donde hot-paths son CRITICAL pero startup es inofensivo).

---

## Tabla consolidada

Leyenda columna Recomendación:
- `CRITICAL` — severidad base en producción
- `¹` — downgraded a WARNING en archivos de test (`test_*.py`, `*_test.py`, `tests/`)
- `†` — severidad variable por subtipo (ver nota de pie)

| Regla | Categoría | Evidence | Recomendación | Detection | Runtime Impact | External Evidence | Repos 250 | Estado |
|-------|-----------|----------|--------------|-----------|----------------|-------------------|-----------|--------|
| [PYVIBE-001](accepted/PYVIBE-001.md) — `time.sleep()` en async def | Bloqueo de event loop | **A+** | CRITICAL ¹ | High | High | High | 12.4% (31/250) | ✅ Protocolo v1 |
| [PYVIBE-002](accepted/PYVIBE-002.md) — `requests` sync en async def | Bloqueo de event loop | B | CRITICAL | — | — | — | 4.0% (10/250) | ⏳ Pendiente |
| [PYVIBE-003](accepted/PYVIBE-003.md) — `asyncio.run()` dentro de async def | Primitiva incorrecta | B | CRITICAL | — | — | — | 0.4% (1/250) | ⏳ Pendiente |
| [PYVIBE-004](accepted/PYVIBE-004.md) — `threading.Lock()` en async def | Primitiva incorrecta | B | CRITICAL | — | — | — | 2.0% (5/250) | ⏳ Pendiente |
| [PYVIBE-005](accepted/PYVIBE-005.md) — Celery task sin `time_limit` | Resiliencia | **A** | CRITICAL | Medium-High | High | Medium-High | 12.8% (32/250) | ✅ Protocolo v1 |
| [PYVIBE-006](accepted/PYVIBE-006.md) — `ContextVar` sin `reset()` | Estado / Contexto | B | CRITICAL | — | — | — | 6.0% (15/250) | ⏳ Pendiente |
| [PYVIBE-007](accepted/PYVIBE-007.md) — `subprocess.run` en async def | Bloqueo de event loop | B | CRITICAL ¹ | — | — | — | 4.8% (12/250) | ⏳ Pendiente |
| [PYVIBE-008](accepted/PYVIBE-008.md) — `sqlite3` en async def | Bloqueo de event loop | B | CRITICAL | — | — | — | 8.8% (22/250) | ⏳ Pendiente |
| [PYVIBE-009](accepted/PYVIBE-009.md) — `open()` en lugar de `aiofiles` | Bloqueo de event loop | **B** | CRITICAL (hot path) ¹ | High | Medium-High | Medium | 24.0% (60/250) | ✅ Protocolo v1 |
| [PYVIBE-010](accepted/PYVIBE-010.md) — `httpx.get/post` sync en async def | Bloqueo de event loop | B | CRITICAL | — | — | — | 0.8% (2/250) | ⏳ Pendiente |
| [PYVIBE-011](accepted/PYVIBE-011.md) — `os.blocking` en async def | Bloqueo de event loop | B | CRITICAL | — | — | — | 0.0% (0/250) ² | ⏳ Pendiente |
| [PYVIBE-012](accepted/PYVIBE-012.md) — `create_task()` huérfano | Gestión de tareas | B | CRITICAL | — | — | — | 12.0% (30/250) | ⏳ Pendiente |
| [PYVIBE-013](accepted/PYVIBE-013.md) — `gather()` sin `return_exceptions` | Gestión de tareas | **A** | CRITICAL ¹ | High | High | High | 35.2% (88/250) | ✅ Protocolo v1 |
| [PYVIBE-014](accepted/PYVIBE-014.md) — `ensure_future()` huérfano | Gestión de tareas | B | CRITICAL | — | — | — | 5.6% (14/250) | ⏳ Pendiente |
| [PYVIBE-015](accepted/PYVIBE-015.md) — `loop.run_until_complete()` en async def | Primitiva incorrecta | B | CRITICAL | — | — | — | 2.0% (5/250) | ⏳ Pendiente |
| [PYVIBE-016](accepted/PYVIBE-016.md) — `httpx.Client()` sync en async def | Bloqueo de event loop | B | CRITICAL | — | — | — | 0.8% (2/250) | ⏳ Pendiente |
| [PYVIBE-017](accepted/PYVIBE-017.md) — `except` silencioso en async def | Manejo de errores | **A** | CRITICAL / WARNING † | Medium-High | Medium | Medium | 48.8% (122/250) | ✅ Protocolo v1 + FP Audit |
| [PYVIBE-018](accepted/PYVIBE-018.md) — `while True` sin `await` | Gestión de tareas | B | CRITICAL | — | — | — | 6.8% (17/250) | ⏳ Pendiente |
| [PYVIBE-019](accepted/PYVIBE-019.md) — Retry sin backoff | Resiliencia | **A** | WARNING ‡ | High | High (I/O) | High | 2.8% (7/250) | 🔵 Limited Scope |
| [PYVIBE-020](accepted/PYVIBE-020.md) — `put_nowait()` sin handler `QueueFull` | Manejo de errores | B | WARNING | — | — | — | 16.4% (41/250) ³ | ⏳ Pendiente |

² PYVIBE-011: 0 hits en 250 repos — Evidence B se mantiene porque el patrón es real aunque infrecuente en repos de alta estrella.  
³ PYVIBE-020: debut en sweep 250 (sin baseline en 100 repos). Tasa de debut 16.4% es sólida para regla nueva.

**‡ PYVIBE-019 — Limited Scope (Heurística de intención):**
- Scope: `for _ in range(N)` / `for attempt in range(N)` en `async def`. While excluido.
- Scan v4 (jun 2026): 18 hits / 7 repos → auditoría 100% → **12 TP, 6 FP, 67% precisión**.
- FP rate 33% < 40% umbral para heurísticas. Mejora vs. estado anterior (88% → 33%).
- 3 FP residuales no reducibles con AST: BENCHMARK_LOOP, TRY_ALTERNATIVES, GRAPH_TRAVERSAL.
- Ver análisis completo en `research/accepted/PYVIBE-019.md` sección "Scan v4".

**† PYVIBE-017 Recomendación detallada:**
- `bare except: pass` → `CRITICAL` (captura `KeyboardInterrupt`/`SystemExit`)
- `except Exception: pass` / `except Exception: ...` → `WARNING`
- Excepciones específicas (`except ValueError: pass`) → no se flagea
- `# nosec B110` en la línea del except → suprimido

**¹ TEST_FILE_DOWNGRADE activo en:** PYVIBE-001, PYVIBE-007, PYVIBE-009, PYVIBE-013  
En archivos `test_*.py`, `*_test.py`, o rutas bajo `tests/`: CRITICAL → WARNING automáticamente.

**PYVIBE-009 contexto adicional:** CRITICAL en hot paths (handlers HTTP/WS); impacto real cero en funciones de startup/lifespan (la app no sirve requests aún). La forma idiomática para startup file I/O es usar `def` en lugar de `async def`, evitando el flag. Ver [`PYVIBE-009.md`](accepted/PYVIBE-009.md) sección "Distinción de contexto".

---

## Resumen por categoría

| Categoría | Reglas | Reglas con protocolo completo |
|-----------|--------|-------------------------------|
| Bloqueo de event loop | 001, 002, 007, 008, 009, 010, 011, 016 | 001 ✅, 009 ✅ |
| Gestión de tareas | 012, 013, 014, 018 | 013 ✅ |
| Manejo de errores | 017, 020 | 017 ✅ |
| Resiliencia | 005, 019 | 005 ✅, 019 ✅ |
| Primitiva incorrecta | 003, 004, 015 | — |
| Estado / Contexto | 006 | — |

---

## Progreso del Evidence Review Protocol v1

| Nivel | Reglas |
|-------|--------|
| A+ | PYVIBE-001 |
| A  | PYVIBE-005, PYVIBE-013, PYVIBE-017, PYVIBE-019 |
| B (protocolo completo) | PYVIBE-009 |
| B (protocolo pendiente) | PYVIBE-002, 003, 004, 006, 007, 008, 010, 011, 012, 014, 015, 016, 018, 020 |
| C  | — |

**Protocolo completado:** 6/20 reglas (30%)

---

## Nota sobre las reglas en estado B (protocolo pendiente)

Las 14 reglas marcadas como "B (pendiente de protocolo completo)" no son menos
válidas que las cinco ya investigadas. Evidence B significa que la regla está
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
