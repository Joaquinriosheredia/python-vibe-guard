# PYVIBE-005 — Tarea Celery sin time_limit

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/celery_time_limit.py`  
**Patrón:** `@app.task` / `@shared_task` sin `time_limit` ni `soft_time_limit`

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

## Evidence Level: B

- ✅ Validada en repos reales: 32 repos, 1072 hits — segundo mayor total de hits en la muestra
- ⏳ Documentación oficial Celery sobre `time_limit` como práctica obligatoria: **PENDIENTE — requiere investigación manual**
- ⏳ Incidentes públicos de workers colgados sin `time_limit`: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

## Nota

Alta concentración en `celery/celery` (352 hits) y `coleifer/huey` (172 hits) — repos del propio ecosistema de task queues. Esto puede incluir código de ejemplo o tests que intencionalmente omiten `time_limit`. Valor del análisis de FP pendiente para estos repos específicos.
