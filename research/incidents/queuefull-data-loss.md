# Incident Research — QueueFull / Data Loss (PYVIBE-020)

**Regla relacionada:** PYVIBE-020  
**Patrón:** `asyncio.Queue.put_nowait()` sin handler de `QueueFull`

---

## Dato objetivo disponible

En el sweep de 100 repos (v0.6.0, 2026-06-20) que originó PYVIBE-020,
`Queue.put_nowait()` sin handler de `asyncio.QueueFull` fue detectado en
**25 de 100 repos (25%)** mediante grep manual previo a la implementación.

Tras implementar PYVIBE-020 y ejecutar el sweep de 250 repos (v0.7.0):
- **41 de 250 repos** tienen al menos un hit (16.4%)
- **295 total de hits** en 250 repos
- Top repo: `google-gemini/genai-processors` con 56 hits

Repos representativos con el patrón confirmado:
- `nolar/kopf` — cola de eventos Kubernetes
- `strawberry-graphql/strawberry` — cola de mensajes WebSocket
- `google-gemini/genai-processors` — pipeline de streaming

---

## Pendiente de investigación manual

- **Incidentes públicos documentados:** PENDIENTE — no se han verificado post-mortems,
  issues de GitHub con impacto en producción, ni CVEs relacionados con pérdida de datos
  por `QueueFull` no capturado.
- **Documentación oficial Python sobre el riesgo:** PENDIENTE — verificar si
  la docs de `asyncio.Queue.put_nowait` advierte explícitamente sobre pérdida de datos
  vs `await queue.put()`.

---

## Nota de clasificación

PYVIBE-020 tiene Evidence Level **B** hasta que se confirme al menos un incidente
público o referencia oficial. Ver `research/accepted/PYVIBE-020.md`.
