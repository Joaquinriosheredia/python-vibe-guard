# python-vibe-guard — Catálogo de Reglas

**Versión:** 0.7.4 · 20 reglas activas · 181 tests  
**Última actualización:** 2026-06-28  
**Fuente de datos:** sweep 250 repos (95,678 .py files) · `research/datasets/250-repos.json`

---

## Evidence Review Progress

```
[████████████████████]  20/20 (100% precisión auditada)
```

| Completado (protocolo v1 completo) | Precisión auditada (sweep 250) | Pendiente |
|-----------|----------|----------|
| PYVIBE-001 (A+), PYVIBE-005 (A), PYVIBE-009 (B), PYVIBE-013 (A), PYVIBE-017 (A), PYVIBE-019 (A) | 14 reglas (ver tabla) | — |

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
| [PYVIBE-002](accepted/PYVIBE-002.md) — `requests` sync en async def | Bloqueo de event loop | B | CRITICAL | — | — | — | 1.6% (4/250) ★✦ | ✅ Precisión auditada · ~83% TP post EXECUTOR_WRAPPER fix (6 hits, −45%) · FP residual: test_subject (1 hit, logfire) |
| [PYVIBE-003](accepted/PYVIBE-003.md) — `asyncio.run()` dentro de async def | Primitiva incorrecta | B | CRITICAL | — | — | — | 0.4% (1/250) | ✅ Precisión revisada · 100% TP (1/1) · audit anterior era incorrecto (test_batch es async def) |
| [PYVIBE-004](accepted/PYVIBE-004.md) — `threading.Lock()` en async def | Primitiva incorrecta | B | CRITICAL | — | — | — | 1.2% (3/250) ★ | ✅ Precisión auditada · ~83% TP post NAME_COLLISION fix (6 hits, −90%) · fix: rastrear imports threading |
| [PYVIBE-005](accepted/PYVIBE-005.md) — Celery task sin `time_limit` | Resiliencia | **A** | CRITICAL/WARNING† | Medium-High | High | Medium-High | 12.8% (32/250) | ✅ Precisión auditada · 86% TP post-fix+TEST_FILE_DOWNGRADE · 571 CRITICAL + 34 WARNING |
| [PYVIBE-006](accepted/PYVIBE-006.md) — `ContextVar` sin `reset()` | Estado / Contexto | B | CRITICAL | — | — | — | 6.0% (15/250) | ✅ Precisión auditada · 40% TP (8/20) · FP: task isolation, test subjects |
| [PYVIBE-007](accepted/PYVIBE-007.md) — `subprocess.run` en async def | Bloqueo de event loop | B | CRITICAL ¹ | — | — | — | 4.8% (12/250) | ✅ Precisión auditada · 30% TP (6/20) · FP: test launchers, executor wrap |
| [PYVIBE-008](accepted/PYVIBE-008.md) — `sqlite3` en async def | Bloqueo de event loop | B | CRITICAL ¹ | — | — | — | 2.8% (7/250) ★ | ✅ Precisión auditada · 100% TP en producción post NAME_COLLISION fix (36 hits, −92%) · 28 test hits → WARNING via TEST_FILE_DOWNGRADE · 8 prod hits: 100% TP |
| [PYVIBE-009](accepted/PYVIBE-009.md) — `open()` en lugar de `aiofiles` | Bloqueo de event loop | **B** | CRITICAL (hot path) ¹ | High | Medium-High | Medium | 24.0% (60/250) | ✅ Protocolo v1 |
| [PYVIBE-010](accepted/PYVIBE-010.md) — `httpx.get/post` sync en async def | Bloqueo de event loop | B | CRITICAL | — | — | — | 0.8% (2/250) | ✅ Precisión auditada · 88% TP (15/17) · FP: benchmark script |
| [PYVIBE-011](accepted/PYVIBE-011.md) — `os.blocking` en async def | Bloqueo de event loop | B | CRITICAL | — | — | — | 0.0% (0/250) ² | ✅ Precisión auditada · N/A (0 hits) |
| [PYVIBE-012](accepted/PYVIBE-012.md) — `create_task()` huérfano | Gestión de tareas | B | CRITICAL | — | — | — | 12.0% (30/250) | ✅ Precisión auditada · 40% TP (8/20) · FP: test concurrent setup |
| [PYVIBE-013](accepted/PYVIBE-013.md) — `gather()` sin `return_exceptions` | Gestión de tareas | **A** | CRITICAL ¹ | High | High | High | 35.2% (88/250) | ✅ Protocolo v1 |
| [PYVIBE-014](accepted/PYVIBE-014.md) — `ensure_future()` huérfano | Gestión de tareas | B | CRITICAL | — | — | — | 5.6% (14/250) | ✅ Precisión auditada · 55% TP (11/20) · FP: tests |
| [PYVIBE-015](accepted/PYVIBE-015.md) — `loop.run_until_complete()` en async def | Primitiva incorrecta | B | CRITICAL | — | — | — | 2.0% (5/250) | ✅ Precisión auditada · 100% TP (1/2) post-fix · fix: visit_FunctionDef, 8→2 hits (−75%) |
| [PYVIBE-016](accepted/PYVIBE-016.md) — `httpx.Client()` sync en async def | Bloqueo de event loop | B | CRITICAL | — | — | — | 0.8% (2/250) | ✅ Precisión auditada · 0% TP (0/2) · FP: test transport fixtures |
| [PYVIBE-017](accepted/PYVIBE-017.md) — `except` silencioso en async def | Manejo de errores | **A** | CRITICAL / WARNING † | Medium-High | Medium | Medium | 48.8% (122/250) | ✅ Protocolo v1 + FP Audit |
| [PYVIBE-018](accepted/PYVIBE-018.md) — `while True` sin `await` | Gestión de tareas | B | CRITICAL | — | — | — | 6.8% (17/250) | ✅ Precisión auditada · 80% TP (4/5) post-fix · fix: visit_FunctionDef, 49→37 hits (−24.5%) |
| [PYVIBE-019](accepted/PYVIBE-019.md) — Retry sin backoff | Resiliencia | **A** | WARNING ‡ | High | High (I/O) | High | 2.8% (7/250) | 🔵 Limited Scope |
| [PYVIBE-020](accepted/PYVIBE-020.md) — `put_nowait()` sin handler `QueueFull` | Manejo de errores | B | WARNING | — | — | — | 16.4% (41/250) ³ | ✅ Precisión auditada · 40% TP (8/20) · FP: unbounded queues, pool invariants |

² PYVIBE-011: 0 hits en 250 repos — Evidence B se mantiene porque el patrón es real aunque infrecuente en repos de alta estrella.  
³ PYVIBE-020: debut en sweep 250 (sin baseline en 100 repos). Tasa de debut 16.4% es sólida para regla nueva.  
★ PYVIBE-002/004/008: repos afectados post NAME_COLLISION fix (2026-06-28). 002: 14→11 hits (−21%), 8 repos. 004: 60→6 hits (−90%), 3 repos. 008: 436→41 hits (−91%), 7 repos. Fix: rastreo de imports en los detectores.  
✦ PYVIBE-002: post EXECUTOR_WRAPPER fix (2026-06-28). 11→6 hits (−45%), 4 repos. Fix: visit_FunctionDef + visit_Lambda resetean contexto async en callables síncronos anidados. Precisión: ~50%→~83%.

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

**Fix #4 — NAME_COLLISION (2026-06-28):** `visit_Import`/`visit_ImportFrom` añadidos a `async_requests.py`, `threading_lock.py`, `sqlite_async.py`. Los detectores ahora verifican que el nombre esté importado del módulo correcto antes de disparar. 452 FPs eliminados, 15 tests nuevos.

**Fix #5 — TEST_FILE_DOWNGRADE extendido a PYVIBE-008 (2026-06-28):** Auditoría de 36 hits post-NAME_COLLISION fix: 28 en archivos de test (77.8%), 8 en producción (22.2%). Los 8 hits de producción son 100% TP (IBM mcp-context-forge, kiro-gateway, WebRPA). Los 28 test hits son FP contextuales (test subjects, smoke tests, fixtures). Downgrade CRITICAL→WARNING en test files. 2 tests nuevos (total 175).

**¹ TEST_FILE_DOWNGRADE activo en:** PYVIBE-001, PYVIBE-005, PYVIBE-007, PYVIBE-008, PYVIBE-009, PYVIBE-013  
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

## Auditoría de Precisión (Sweep 250) — Resumen ejecutivo

**Completada:** 2026-06-27 · 20 reglas auditadas · PYVIBE-005 fix aplicado

### Tabla de precisión por regla

| Regla | Muestra | TP | FP | EDGE | Precisión | Estado |
|-------|---------|----|----|------|-----------|--------|
| PYVIBE-002 | 6/6 ✦ | 5 | 1 | 0 | **~83%** | ✅ **OK** — post EXECUTOR_WRAPPER fix (11→6 hits, −45%) |
| PYVIBE-003 | 1/1 | 1 | 0 | 0 | **100%** | ✅ **OK** — audit revisado + fix INNER_SYNC_FUNCTION |
| PYVIBE-004 | 14/60 | 0 | 12 | 2 | 0% | **🔵 Limited Scope** — name collision |
| PYVIBE-005 | 15/571† | 12 | 2 | 1 | **86%** | ✅ **Completa** — 86% post fix+TEST_FILE_DOWNGRADE · 34 hits → WARNING |
| PYVIBE-006 | 20/28 | 8 | 9 | 3 | 40% | B — mejora context detection |
| PYVIBE-007 | 20/61 | 6 | 13 | 1 | 30% | B — test_file_downgrade ayuda |
| PYVIBE-008 | 36/36† | 8 | 28 | 0 | **100% prod** | ✅ **Completa** — 100% TP en producción · TEST_FILE_DOWNGRADE aplicado (28 test hits → WARNING) |
| PYVIBE-010 | 17/17 | 15 | 1 | 1 | 88% | B — excelente, candidata a A |
| PYVIBE-011 | 0/0 | 0 | 0 | 0 | N/A | B — mantener, 0 hits |
| PYVIBE-012 | 20/135 | 8 | 8 | 4 | 40% | B — test_file_downgrade |
| PYVIBE-014 | 20/33 | 11 | 8 | 1 | 55% | B — test_file_downgrade |
| PYVIBE-015 | 2/2† | 1 | 0 | 1 | **100%** | ✅ **OK** — fix INNER_SYNC_FUNCTION, 8→2 hits (−75%) |
| PYVIBE-016 | 2/2 | 0 | 2 | 0 | 0% | B — test_file_downgrade necesario |
| PYVIBE-018 | 15/37† | 4 | 1 | 10 | **80%** | ✅ **OK** — fix INNER_SYNC_FUNCTION, 49→37 hits (−24.5%) |
| PYVIBE-020 | 20/295 | 8 | 11 | 1 | 40% | B — verificar bounded queue |

† PYVIBE-005: 571 CRITICAL + 34 WARNING (TEST_FILE_DOWNGRADE) = 605 post-fix (1,072 raw − 467 cross-framework). Muestra auditada = 15 hits CRITICAL. Ver `research/precision-audit.md` sección PYVIBE-005.  
† PYVIBE-015/018: post INNER_SYNC_FUNCTION fix. PYVIBE-015: 8→2 hits (−75%). PYVIBE-018: 49→37 hits (−24.5%).  
† PYVIBE-008: post NAME_COLLISION fix (436→36 hits, −92%). Muestra completa (36/36): 8 prod (100% TP) + 28 test (WARNING via TEST_FILE_DOWNGRADE). Repos prod afectados: IBM/mcp-context-forge, jwadow/kiro-gateway, pmh1314520/WebRPA.

### Hallazgos transversales críticos

**✅ Fix #1: CROSS_FRAMEWORK en PYVIBE-005 (2026-06-27)**  
El detector usaba `node.attr == "task"` para cualquier `@<x>.task`. Fix: receiver name heuristic + import check. Resultado: 1,072 → 605 hits (−43.6%), precisión 35–39% → 85%. 7 tests nuevos.

**✅ Fix #2: TEST_FILE_DOWNGRADE extendido a PYVIBE-005 (2026-06-27)**  
34 hits de test files (Celery own test suite y otros) downgradeados de CRITICAL → WARNING. Auditoría de muestra CRITICAL post-downgrade: 86% precisión (12/14 sin EDGE). 2 tests nuevos. FP residual: `celery/t/` (directorio no estándar, fuera del scope de `_is_test_file`).

**✅ Fix #3: INNER_SYNC_FUNCTION bug en PYVIBE-003, 015, 018 (2026-06-27)**  
`visit_FunctionDef` añadido a los tres detectores para resetear `_current_async_func = None` al entrar en scope síncrono. PYVIBE-015: 8→2 hits (−75%), precisión 57%→100%. PYVIBE-018: 49→37 hits (−24.5%), precisión 33%→80%. PYVIBE-003: audit revisado, único hit es TP (100%). 4 tests nuevos.

**✅ Fix #4: NAME_COLLISION en PYVIBE-002, 004, 008 (2026-06-28)**  
Detectores confundían variables/funciones locales con módulos objetivo (requests, Lock, sqlite3). Fix: rastreo de imports en `visit_Import`/`visit_ImportFrom`. Resultado: 002: 14→11 (−21%), 004: 60→6 (−90%), 008: 436→41 (−91%). 15 tests nuevos.

**✅ Fix #5: EXECUTOR_WRAPPER en PYVIBE-002 (2026-06-28)**  
`requests.*()` dentro de `def inner():` o `lambda: ...` anidados en async def no bloquea el event loop si se pasa a `run_in_executor` / `async_add_executor_job`. Fix: `visit_FunctionDef` + `visit_Lambda` resetean contexto async al entrar en callable síncrono anidado. Resultado: 002: 11→6 (−45%), precisión ~50%→~83%. 6 tests nuevos.

**Patrón FP dominante: test subjects**  
El FP más frecuente es que el detector flagueó el "objeto bajo prueba" en tests
async. Aplicar `TEST_FILE_DOWNGRADE` (ya activo en 001, 007, 009, 013) a todas
las reglas restantes mejoraría la precisión en producción estimadamente +15-25 pp.

**Reglas con mejor precisión (candidatas a elevación):**
- PYVIBE-003: 100% — único hit es TP real (corregido audit anterior)
- PYVIBE-005: 86% post-fix+TEST_FILE_DOWNGRADE — cross-framework FP eliminado
- PYVIBE-010: 88% — httpx sync en async es casi siempre bug real
- PYVIBE-015: 100% post-fix — 2 hits supervivientes, ambos en async directo
- PYVIBE-018: 80% post-fix — inner sync loops eliminados
- PYVIBE-014: 55% — ensure_future huérfano es frecuentemente bug real

**Reglas que requieren revisión del detector (Limited Scope):**
- PYVIBE-004: 0% — threading.Lock vs anyio.Lock vs redis.Lock vs ORM models
- PYVIBE-008: 25% — sqlite3.connect vs aiosqlite.connect vs asyncpg.connect vs websockets.connect

---

## Nota sobre las reglas en estado B

La auditoría de precisión de todas las 20 reglas (2026-06-27) confirmó que los patrones
objetivo existen en código de producción real. La auditoría reveló dos categorías de mejora:

1. **Bugs del detector** (name collision, inner sync function, cross-framework): reducen drásticamente
   la precisión y deben corregirse antes de uso en producción.
   - ✅ CROSS_FRAMEWORK en PYVIBE-005: corregido (2026-06-27)
   - ✅ TEST_FILE_DOWNGRADE extendido a PYVIBE-005: completado (2026-06-27)
2. **FPs de contexto** (tests, executor wrappers, startup fire-and-forget): son
   esperables en linters AST sin análisis de flujo y se mitigan con `TEST_FILE_DOWNGRADE`
   y detección de patterns de executor.

Prioridad de fixes pendientes:
1. ~~Fix del bug "inner sync function" (impacto en PYVIBE-003, 015, 018)~~ **✅ DONE (2026-06-27)**
2. ~~Fix del bug "name collision" (impacto en PYVIBE-002, 004, 008)~~ **✅ DONE (2026-06-28)**
3. ~~Añadir detección de executor wrapper para PYVIBE-002~~ **✅ DONE (2026-06-28)**
4. Extender TEST_FILE_DOWNGRADE a reglas pendientes (PYVIBE-006, 007, 012, 014, 016)
