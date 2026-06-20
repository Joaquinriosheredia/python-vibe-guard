# Rejected Candidate — SQLAlchemy N+1 en contexto async

**Estado:** RECHAZADO  
**Motivo:** limitación técnica del análisis AST estático

---

## Patrón objetivo

Detección de N+1 queries en código que usa SQLAlchemy (sync o async)
dentro de funciones `async def`: un `await session.execute(...)` o
`session.query(...)` dentro de un bucle sin eager loading configurado.

## Motivo técnico de rechazo

El patrón N+1 requiere **análisis de flujo de datos**, no solo análisis AST local:

1. Para saber si una query está en un bucle N+1 es necesario conocer si la
   colección iterada proviene de una query previa que no incluyó `joinedload`/`selectinload`.
2. La relación entre la query exterior (que genera la colección) y la query
   interior (que itera sobre ella) puede estar separada por múltiples llamadas
   a funciones, pasos de kwargs, o contextos de request — invisibles en un
   visitor AST de archivo único.
3. La tasa de falsos positivos sería inaceptable: cualquier `await session.execute`
   dentro de un `for` se marcaría, incluyendo loops legítimos sobre datos no relacionados.

## Alternativa documentada

El análisis N+1 requiere un linter con análisis interprocedural o un profiler
de queries en runtime (e.g. `sqlalchemy-utils` query counter, Django Debug Toolbar
equivalente para SQLAlchemy). No es implementable con fiabilidad mediante visitor AST.

## Fecha de evaluación

2026-06-20
