# PYVIBE-018 — while True sin await

**Severidad:** CRITICAL  
**Archivo:** `pyvibe/rules/while_true_no_await.py`  
**Patrón:** bucle `while True:` dentro de `async def` sin ningún `await` en el cuerpo del bucle

## Datos objetivos

| Métrica | 100 repos | 250 repos |
|---------|-----------|-----------|
| Repos afectados | 10/100 (10.0%) | 17/250 (6.8%) |
| Total hits | 36 | 49 |
| Estabilidad 100→250 | Alta (−3.2 pp) | |
| Falsos positivos documentados | 0 (post-fix v0.5.0) | |

## Repos representativos (sweep 250)

- `home-assistant/core` — 21 hits
- `pmh1314520/WebRPA` — 5 hits (nuevo en sweep 250)
- `agronholm/anyio` — 3 hits
- `MODSetter/SurfSense` — 2 hits
- `Tinche/aiofiles` — 2 hits

## Evidence Level: B

- ✅ Validada en repos reales: 17 repos afectados en sweep 250
- ⏳ Documentación oficial o incidentes públicos: **PENDIENTE — requiere investigación manual**
- ✅ Falsos positivos documentados en campo: 0

## Historial de falsos positivos

**Falso positivo documentado y corregido en v0.5.0 (sesión S232, 2026-06-19):**  
Async generators con `while True: yield ...` dentro de `async def` eran incorrectamente
flagueados. El patrón `while True` + `yield` en `async def` es un generador asíncrono
válido (no bloquea el event loop). Fix: la regla ahora excluye funciones que contienen
`yield` en el cuerpo del bucle.

Post-fix, 0 falsos positivos documentados en campo.
