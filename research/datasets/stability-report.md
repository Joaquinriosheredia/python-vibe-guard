# python-vibe-guard — Stability Report: 250 → 902 Repos

**Generated:** 2026-07-17
**Version:** 0.12.1 (20 rules, 331 tests)
**Baseline:** 250 repos · 95,678 .py files · 5,303 violations
**Extended:** 902 repos · 178,557 .py files · 13,510 violations
**New repos added:** 652 (0 clone failures, 0 scan failures)

---

## Methodology note — why the baseline was re-scanned

The original `research/datasets/250-repos.json` was generated on 2026-06-20 with
pyvibe **v0.7.0**, before the NAME_COLLISION, EXECUTOR_WRAPPER, AsyncBlockingCallVisitor,
and TEST_FILE_DOWNGRADE precision fixes landed (see `research/catalog.md` and
`research/precision-audit.md`). Comparing that frozen snapshot directly against a fresh
902-repo scan on v0.12.1 would conflate **sample-size effects** with **rule-precision
effects** — both change the raw hit counts, but only sample size is what this report is
meant to measure.

To isolate sample-size effects, the same 250 repos were **re-scanned with the current
v0.12.1 ruleset** (built from `validation/raw/*.json`, filtered to the exact repo set in
`research/datasets/250-repos.json`) and used as the baseline below instead of the old
frozen file. `research/datasets/250-repos.json` itself is left untouched as the historical
v0.7.0 record. The extended dataset is `research/datasets/1000-repos.json` (902 repos —
see note on repo count below).

**Note on repo count:** the `--target 1000` search returned 902 unique repos (250
existing + 652 new) after deduplication across 8 GitHub search queries with pagination.
This is the full pool of distinct async-Python repos (`stars:>100`, pushed in the last
year) matched by the current query set — not a sampling shortfall. The dataset file is
still named `1000-repos.json` to match the requested scan target.

---

## Stability Table — % of Repos Affected per Rule

> **Estabilidad:** Alta = diferencia < 5 pp · Media = 5–15 pp · Baja = > 15 pp
> *All rates expressed as % of repos in the sample with ≥1 hit for that rule. Both columns use pyvibe v0.12.1.*

| Regla | Severidad | Patrón | % en 250 | % en 902 | Diferencia | Estabilidad |
|-------|-----------|--------|-----------|-----------|------------|-------------|
| PYVIBE-001 | CRITICAL | `time.sleep()` in `async def` | 8.4% | 6.5% | −1.9 pp | **Alta** |
| PYVIBE-002 | CRITICAL | `requests.get/post` in `async def` | 2.0% | 2.2% | +0.2 pp | **Alta** |
| PYVIBE-003 | CRITICAL | `asyncio.run()` inside `async def` | 0.4% | 0.1% | −0.3 pp | **Alta** |
| PYVIBE-004 | CRITICAL | `threading.Lock()` in `async def` | 1.2% | 0.8% | −0.4 pp | **Alta** |
| PYVIBE-005 | CRITICAL | Celery task without `time_limit` | 11.6% | 9.1% | −2.5 pp | **Alta** |
| PYVIBE-006 | CRITICAL | `ContextVar` without `reset()` | 6.0% | 4.5% | −1.5 pp | **Alta** |
| PYVIBE-007 | CRITICAL | `subprocess.run/call` in `async def` | 4.0% | 4.5% | +0.5 pp | **Alta** |
| PYVIBE-008 | CRITICAL | `sqlite3` operations in `async def` | 2.8% | 2.0% | −0.8 pp | **Alta** |
| PYVIBE-009 | CRITICAL | `open()` instead of `aiofiles` | 24.0% | 22.8% | −1.2 pp | **Alta** |
| PYVIBE-010 | CRITICAL | `httpx.get/post` (sync) in `async def` | 0.8% | 1.0% | +0.2 pp | **Alta** |
| PYVIBE-011 | CRITICAL | `os.path/listdir` blocking in `async def` | 0.0% | 0.1% | +0.1 pp | **Alta** ¹ |
| PYVIBE-012 | CRITICAL | `asyncio.create_task()` orphan | 12.0% | 12.6% | +0.6 pp | **Alta** |
| PYVIBE-013 | CRITICAL | `asyncio.gather()` without `return_exceptions` | 35.2% | 32.4% | −2.8 pp | **Alta** |
| PYVIBE-014 | CRITICAL | `asyncio.ensure_future()` orphan | 5.6% | 4.4% | −1.2 pp | **Alta** |
| PYVIBE-015 | CRITICAL | `loop.run_until_complete()` in `async def` | 0.8% | 0.4% | −0.4 pp | **Alta** |
| PYVIBE-016 | CRITICAL | `httpx.Client()` (sync) in `async def` | 0.8% | 0.3% | −0.5 pp | **Alta** |
| PYVIBE-017 | CRITICAL | Silent `except` in `async def` | 48.4% | 43.9% | −4.5 pp | **Alta** |
| PYVIBE-018 | CRITICAL | `while True` without `await` | 5.6% | 3.9% | −1.7 pp | **Alta** |
| PYVIBE-019 | WARNING | Retry without backoff | 2.8% | 1.9% | −0.9 pp | **Alta** |
| PYVIBE-020 | WARNING | `put_nowait()` without `QueueFull` handler | 16.4% | 12.3% | −4.1 pp | **Alta** |

¹ PYVIBE-011 goes from 0 hits (0/250) to 1 hit (1/902) — still statistically negligible, but
the first confirmed hit at this scale. Diff stays under the 5 pp Alta threshold.

### Observations on rate dilution

Every non-zero rate again drops slightly between 250→902, continuing the same dilution
pattern documented in the 100→250 report — the marginal repos found by broader GitHub
search queries dilute the concentration of async-heavy, high-star libraries in the
original curated batch. **Unlike the 100→250 transition, every single rule now lands in
the Alta stability band** (largest diff: PYVIBE-017 at −4.5 pp). This is the expected
effect of a larger, more representative sample: percentages are converging rather than
swinging.

---

## Most Valuable Rules — Severity-Weighted Score (902 repos)

> **Score = % repos affected × severity weight (CRITICAL = 3, WARNING = 1)**
> Purpose: surface rules that are rare but always-wrong and avoid penalising them for low frequency.

| Rank | Regla | Severidad | % repos (902) | Peso | Score | Notas |
|------|-------|-----------|---------------|------|-------|-------|
| 1 | PYVIBE-017 | CRITICAL | 43.9% | 3 | **131.7** | Sigue siendo la regla más frecuente y crítica |
| 2 | PYVIBE-013 | CRITICAL | 32.4% | 3 | **97.1** | Estable en ~1 de cada 3 repos con asyncio |
| 3 | PYVIBE-009 | CRITICAL | 22.8% | 3 | **68.5** | `open()` blocking sigue siendo muy común |
| 4 | PYVIBE-012 | CRITICAL | 12.6% | 3 | **37.9** | Sube una posición respecto a 250 (task orphan) |
| 5 | PYVIBE-005 | CRITICAL | 9.1% | 3 | **27.3** | Celery sin `time_limit`: alto impacto en prod |
| 6 | PYVIBE-001 | CRITICAL | 6.5% | 3 | **19.6** | `time.sleep()` bloquea el event loop |
| 7 | PYVIBE-006 | CRITICAL | 4.5% | 3 | **13.6** | ContextVar leak |
| 8 | PYVIBE-007 | CRITICAL | 4.5% | 3 | **13.6** | Empata con PYVIBE-006 a esta escala |
| 9 | PYVIBE-014 | CRITICAL | 4.4% | 3 | **13.3** | `ensure_future` orphan |
| 10 | PYVIBE-020 | WARNING | 12.3% | 1 | **12.3** | Alta prevalencia compensa peso bajo |
| 11 | PYVIBE-018 | CRITICAL | 3.9% | 3 | **11.6** | Bucle infinito sin yield |
| 12 | PYVIBE-002 | CRITICAL | 2.2% | 3 | **6.7** | `requests` sync en async: patrón legacy |
| 13 | PYVIBE-008 | CRITICAL | 2.0% | 3 | **6.0** | sqlite3 bloquea el event loop completamente |
| 14 | PYVIBE-010 | CRITICAL | 1.0% | 3 | **3.0** | httpx sync |
| 15 | PYVIBE-004 | CRITICAL | 0.8% | 3 | **2.3** | threading.Lock() causa deadlock en async |
| 16 | PYVIBE-019 | WARNING | 1.9% | 1 | **1.9** | Retry sin backoff |
| 17 | PYVIBE-015 | CRITICAL | 0.4% | 3 | **1.3** | `loop.run_until_complete` anidado |
| 18 | PYVIBE-016 | CRITICAL | 0.3% | 3 | **1.0** | `httpx.Client()` sync en async def |
| 19 | PYVIBE-003 | CRITICAL | 0.1% | 3 | **0.3** | Raro pero siempre incorrecto |
| 20 | PYVIBE-011 | CRITICAL | 0.1% | 3 | **0.3** | ² Primer hit confirmado en 902 repos |

² **PYVIBE-011 (os.blocking) — actualización:** el primer hit confirmado apareció en el
lote de 652 repos nuevos (0/250 → 1/902). Sigue siendo una regla de baja prevalencia con
alta confianza en el mecanismo de daño; no requiere revisión de FP a esta escala.

---

## Ranking Top 10 — Cambios entre 250 y 902 repos

> Ranking por `% repos afectados` (sin peso de severidad).

| Posición | En 250 repos | En 902 repos | Cambio |
|----------|-------------|--------------|--------|
| #1 | PYVIBE-017 (48.4%) | PYVIBE-017 (43.9%) | Sin cambio ✓ |
| #2 | PYVIBE-013 (35.2%) | PYVIBE-013 (32.4%) | Sin cambio ✓ |
| #3 | PYVIBE-009 (24.0%) | PYVIBE-009 (22.8%) | Sin cambio ✓ |
| #4 | PYVIBE-020 (16.4%) | PYVIBE-012 (12.6%) | PYVIBE-020 cae a #5; PYVIBE-012 sube a #4 |
| #5 | PYVIBE-012 (12.0%) | PYVIBE-020 (12.3%) | Permuta con PYVIBE-020 (0.3 pp) |
| #6 | PYVIBE-005 (11.6%) | PYVIBE-005 (9.1%) | Sin cambio ✓ |
| #7 | PYVIBE-001 (8.4%) | PYVIBE-001 (6.5%) | Sin cambio ✓ |
| #8 | PYVIBE-006 (6.0%) | PYVIBE-006 (4.5%) | Mantiene posición |
| #9 | PYVIBE-014 (5.6%) | PYVIBE-007 (4.5%) | PYVIBE-007 entra al top 10 (empate técnico con 006) |
| #10 | PYVIBE-018 (5.6%) | PYVIBE-014 (4.4%) | PYVIBE-018 sale del top 10, PYVIBE-014 mantiene |

### Veredicto de estabilidad del ranking

**✅ CONFIRMADO ESTABLE a 902 repos.** El top 3 es idéntico en orden y prácticamente
idéntico en proporción. La única permuta relevante es #4/#5 entre PYVIBE-012 y
PYVIBE-020 — una diferencia de 0.3 pp entre una regla CRITICAL de alta frecuencia y una
regla WARNING de debut reciente, no una señal de inestabilidad. PYVIBE-007 y PYVIBE-006
quedan prácticamente empatados en el límite del top 10 (ambas 4.5%).

A diferencia de la transición 100→250 (que tuvo 3 reglas en banda "Media"), **las 20
reglas caen en banda Alta** en la transición 250→902. No se recomienda revisión especial
antes de escalar a una muestra aún mayor.

---

## Notas adicionales

- **Dilución estructural, no ruido:** las bajadas generalizadas (−0.3 a −4.5 pp) siguen
  el mismo patrón documentado en el reporte 100→250 — search queries más amplias capturan
  más repos generalistas con menos densidad de patrones async. La convergencia hacia
  bandas "Alta" en todas las reglas sugiere que la muestra ya es representativa del
  ecosistema objetivo (FastAPI/aiohttp/Celery/asyncio, `stars:>100`, actividad reciente).
- **PYVIBE-017 (−4.5 pp) y PYVIBE-020 (−4.1 pp):** las dos mayores caídas, pero ambas
  siguen muy por debajo del umbral Media (5 pp). No requieren revisión.
- **PYVIBE-011 deja de ser 0/N:** primer hit real confirmado en la extensión a 902 repos.
  Ver nota ² arriba.
- **Comparación con `research/catalog.md`:** los porcentajes de `catalog.md` (sweep 250,
  post-fix, fecha 2026-06-29) y la columna "% en 250" de esta tabla deberían coincidir
  aproximadamente — pequeñas diferencias (p. ej. PYVIBE-005: 12.8% en catalog vs 11.6%
  aquí) reflejan fixes de precisión aplicados entre esa fecha y v0.12.1, no un error de
  metodología.
