# Public Findings

Este documento registra hallazgos realizados por python-vibe-guard en proyectos
open source públicos.

El objetivo no es demostrar que la herramienta "siempre tiene razón", sino
documentar casos reales, las conversaciones mantenidas con los proyectos y el
resultado final. Incluye tanto hallazgos confirmados como casos donde el
contexto cambió la prioridad o la decisión del equipo mantenedor.

| Proyecto | Repo | Regla | Finding | Resultado | Fecha |
|----------|------|-------|---------|-----------|-------|
| IBM/mcp-context-forge | github.com/IBM/mcp-context-forge | PYVIBE-008 | sqlite3.connect() dentro de async def | Se abrió el PR #5628 para sustituir sqlite3 por aiosqlite. El equipo aclaró posteriormente que el código solo se utiliza para desarrollo/testing y decidió mantener baja prioridad. El caso queda documentado como ejemplo de contexto que afecta a la severidad. | 2026-07-15 |
| MODSetter/SurfSense | github.com/MODSetter/SurfSense | PYVIBE-009 | open() bloqueante en agente TTS async | Issue abierto (#1603). Pendiente de respuesta del proyecto. | 2026-07-15 |
| jumpserver/jumpserver | github.com/jumpserver/jumpserver | PYVIBE-005 | @shared_task sin time_limit en automatización de cuentas | Issue abierto (#17042). Pendiente de respuesta del proyecto. | 2026-07-15 |

## Philosophy

- Every finding is manually reviewed before opening an issue.
- Context always takes precedence over the rule.
- False positives are documented publicly and used to improve future versions.
- The objective is to reduce production risk, not maximize the number of findings.
