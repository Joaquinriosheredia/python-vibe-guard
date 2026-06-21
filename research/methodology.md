# python-vibe-guard — Research Methodology

## Evidence Levels

Cada regla implementada recibe un Evidence Level basado en tres criterios objetivos.
No se asigna ningún score numérico: los niveles son cualitativos.

| Nivel | Criterios requeridos |
|-------|----------------------|
| **Evidence A** | (1) Validada en repos reales con hits confirmados **+** (2) documentación oficial Python/librería que describe el problema como bug/antipatrón, o incidente público documentado **+** (3) 0 falsos positivos documentados en campo |
| **Evidence B** | (1) Validada en repos reales con hits confirmados **+** (2) sin incidentes públicos confirmados todavía (pendiente de investigación manual) |
| **Evidence C** | Solo hipótesis de diseño — sin validación en repos reales |

### Notas de aplicación

- "Validada en repos reales" significa aparición confirmada en ≥1 repo del sweep automatizado
  (actualmente 250 repos públicos de GitHub con >100 estrellas).
- "Documentación oficial" incluye: Python docs, PEP, issue tracker oficial de la librería,
  o post-mortem publicado por el equipo. Requiere verificación manual — no se infiere.
- "Incidente público" incluye: post-mortem de empresa, issue de GitHub resuelto con impacto
  en producción documentado, o CVE. Requiere verificación manual.
- "Falsos positivos documentados" se refiere a reports de campo (usuarios reales en producción),
  no a casos de test diseñados para verificar la lógica de supresión.
- PYVIBE-011 tiene 0 hits en 250 repos. Sigue siendo Evidence B: la ausencia de hits
  en el sweep no implica que el patrón no exista en código real; indica baja prevalencia
  en repos de alta estrella con asyncio.

## Proceso de promoción de candidato a regla

```
candidates/PYVIBE-XXX.md
  → validar en ≥5 repos reales del sweep
  → confirmar ausencia de falsos positivos en los top repos
  → implementar + tests
  → mover a accepted/PYVIBE-XXX.md
  → actualizar aggregate.json en siguiente sweep
```

## Auditoría de falsos positivos

Cualquier regla cuya auditoría manual de muestra revele >20% de falsos positivos estructurales
entra automáticamente en estado **"Needs Redesign"**. No se considera estable ni se mantiene
en producción sin advertencia hasta que una nueva heurística reduzca esa tasa por debajo del
umbral, verificado con una nueva auditoría de muestra.

El umbral del 20% refleja que una tasa superior implica que el detector genera más ruido que
señal: los desarrolladores aprenden a ignorarlo, erosionando la confianza en todas las reglas.

**Proceso:**
```
regla activa
  → auditoría manual de muestra (mín. 30 hits estratificados por repo)
  → si FP rate > 20% → estado "Needs Redesign"
  → diseñar heurística que elimine la categoría dominante de FP
  → implementar + nueva auditoría de muestra
  → si FP rate ≤ 20% → volver a estado "Estable"
```

## Proceso de rechazo

```
candidates/PYVIBE-XXX.md
  → documentar motivo técnico de rechazo
  → mover a rejected/PYVIBE-XXX.md
```

## Estructura de archivos

```
research/
├── methodology.md          ← este archivo
├── accepted/               ← reglas implementadas (PYVIBE-001 a PYVIBE-020)
├── candidates/             ← en evaluación (PYVIBE-021, PYVIBE-022, ...)
├── rejected/               ← candidatos rechazados con motivo técnico
├── incidents/              ← incidentes públicos documentados por regla
└── datasets/               ← resultados de sweeps por campaña
    ├── 100-repos.json      ← sweep v0.6.0 (100 repos, 19 reglas)
    ├── 250-repos.json      ← sweep v0.7.0 (250 repos, 20 reglas)
    ├── stability-report.md ← comparativa 100 vs 250 repos
    └── gaps-found.md       ← análisis de gaps no cubiertos por reglas actuales
```
