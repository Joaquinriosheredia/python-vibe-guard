# PYVIBE-003 — asyncio.run() dentro de async def

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/asyncio_run.py`  
**Patrón:** `asyncio.run(coro())` llamado dentro de `async def`

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 1/100 (1.0%) | 1/250 (0.4%) |
| Total hits | 1 | 1 |
| Estabilidad 100→250 | Alta (−0.6 pp) | |
| Falsos positivos documentados | 0 | |

## Repos representativos (sweep 250)

- `piccolo-orm/piccolo` — 1 hit (único repo afectado en ambos sweeps)

## Evidence Level: B

- ✅ Validada en repos reales: 1 repo afectado confirmado en ambas muestras
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

## Nota

Baja prevalencia (0.4% en 250 repos) pero el patrón es siempre incorrecto:
`asyncio.run()` crea un nuevo event loop y falla si ya hay uno activo,
lo que dentro de `async def` genera `RuntimeError: This event loop is already running`.

---

## Auditoría de Precisión (Sweep 250)

**Muestra analizada:** 1 hit de 1 total (1 repo)
**Metodología:** 100% audit (1 hit)

### Clasificación hit-by-hit

| # | Repo | File:Line | Function | Clasificación | Razón |
|---|------|-----------|----------|---------------|-------|
| 1 | piccolo-orm__piccolo | tests/table/test_batch.py:129 | test_batch | FP | Llamada dentro de un método de `unittest.TestCase` (`def test_batch`, no `async def`); el hit es en la línea donde el patrón AST lo detecta pero la función contenedora es síncrona — se usa `asyncio.run()` para ejecutar la corrutina desde un test síncrono, que es el uso correcto |

**Nota:** La función `test_batch` es un método de `TestCase` (síncrono, no `async def`). El uso de `asyncio.run()` para ejecutar una corrutina desde código síncrono de test es el patrón idiomático correcto. El linter parece haber flagueado este caso porque la línea con `asyncio.run()` está dentro de un método de clase que hereda de `TestCase`, sin verificar si la función es `async def` o `def` regular.

### Resultado

| Métrica | Valor |
|---------|-------|
| TP | 0 |
| FP | 1 |
| EDGE | 0 |
| Precisión (TP/total) | 0% |

### Patrones de FP identificados

1. **TEST_SYNC_METHOD** — `asyncio.run()` llamado desde método síncrono de `TestCase` para ejecutar una corrutina. Uso idiomático correcto.
   - Ejemplo: `asyncio.run(self.run_batch(batch_size=batch_size), debug=True)`
   - Repos afectados: 1 (piccolo-orm/piccolo)

### Recomendación de Evidence Level

**Revisar detección.** Con 1/1 FP la muestra es mínima, pero el FP indica una posible debilidad en la regla: si el detector no verifica que la función inmediata contenedora sea `async def`, va a flagear `asyncio.run()` en métodos síncronos que legítimamente lanzan corrutinas. Confirmar que `pyvibe/rules/asyncio_run.py` comprueba que el nodo padre directo es un `AsyncFunctionDef`, no solo cualquier `FunctionDef`. Si la regla ya lo verifica, este FP es un bug del detector a corregir. Mantener Evidence B hasta ampliar muestra.
