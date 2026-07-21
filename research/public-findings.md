# Public Findings

Este documento registra hallazgos realizados por python-vibe-guard en proyectos
open source públicos.

El objetivo no es demostrar que la herramienta "siempre tiene razón", sino
documentar casos reales, las conversaciones mantenidas con los proyectos y el
resultado final. Incluye tanto hallazgos confirmados como casos donde el
contexto cambió la prioridad o la decisión del equipo mantenedor.

## Status legend

- ✅ Accepted fix — maintainer merged or accepted the fix
- 🟢 Confirmed by maintainer — maintainer confirmed the issue
- 🟡 Intended design — pattern exists but was an intentional design decision
- 🔵 False positive — detector was incorrect
- ⚪ Pending — awaiting maintainer feedback

Every finding must include the public issue or PR link.

| Project | Repository | Rule | Finding | Status | Reference | Date |
|---------|------------|------|---------|--------|-----------|------|
| IBM/mcp-context-forge | github.com/IBM/mcp-context-forge | PYVIBE-008 | Blocking sqlite3.connect() inside async flow | 🟡 PR #5628 opened, maintainer classified as dev/testing | #5627 / #5628 | 2026-07-15 |
| MODSetter/SurfSense | github.com/MODSetter/SurfSense | PYVIBE-009 | Blocking open() inside async TTS agent | ⚪ Pending | issue #1603 | 2026-07-15 |
| jumpserver/jumpserver | github.com/jumpserver/jumpserver | PYVIBE-005 | Celery task without time_limit | 🟡 Intended design — global Celery soft_time_limit of 3600s already exists; ansible worker uses threads pool which changes how task-level limits behave; fixed limit could break large-scale automation jobs. Finding documented as context-dependent. | issue #17042 | 2026-07-15 |
| HOTOSM/tasking-manager | github.com/hotosm/tasking-manager | PYVIBE-001 | time.sleep() inside async _push_messages | ⚪ Pending (Linear TECH-1246) | issue #7303 | 2026-07-17 |
| CenterForOpenScience/osf.io | github.com/CenterForOpenScience/osf.io | PYVIBE-005 | Celery task without time_limit in paginated SQL task | ⚪ Pending | issue #11816 | 2026-07-17 |
| judahpaul16/gpt-home | github.com/judahpaul16/gpt-home | PYVIBE-012 | asyncio.create_task() without retained reference | ✅ Accepted fix — maintainer fixed in commit 41345b7 | issue #122 | 2026-07-17 |
| ronf/asyncssh | github.com/ronf/asyncssh | PYVIBE-009 | Blocking open() inside LocalFS.open() async method | 🟡 Intended design — maintainer confirmed deliberate decision; sync open() preferred over executor overhead for local filesystems. aiofiles support planned but opt-in. | issue #824 | 2026-07-17 |
| GACWR/OpenUBA | github.com/GACWR/OpenUBA | PYVIBE-001 | time.sleep() inside FastAPI async lifespan | ⚪ Pending | issue #140 | 2026-07-17 |

## Checklist before opening an issue

- [ ] Have I manually validated the finding?
- [ ] Have I read the full file, not just the flagged line?
- [ ] Have I checked where this code is called from?
- [ ] Is this production code, development code, benchmark code, or test code?
- [ ] Is there official documentation supporting the suggested fix?
- [ ] Can I explain the real-world impact in 3 sentences?
- [ ] Do I have a reasonable fix proposal?
- [ ] Would I still open this issue if I had found it without python-vibe-guard?

If any box is unchecked, postpone the issue until it can be answered.

## Philosophy

- Every finding is manually reviewed before opening an issue.
- Context always takes precedence over the rule.
- False positives are documented publicly and used to improve future versions.
- The objective is to reduce production risk, not maximize the number of findings.
