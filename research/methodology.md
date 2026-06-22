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

## Clasificación de reglas por naturaleza

Las reglas se clasifican en tres categorías según la naturaleza de lo que detectan.
Esta clasificación define el FP esperado orientativo para calibrar expectativas, **no es
un umbral de aprobación automática**. La decisión de estado (Estable / Needs Redesign /
Limited Scope) combina esta categoría con la evolución histórica de la regla y si la
precisión es razonable para su tipo.

| Categoría | Descripción | FP orientativo |
|-----------|-------------|----------------|
| **Determinística** | Misuse directo de API: la llamada o ausencia de parámetro es siempre incorrecta en el contexto dado. No depende de semántica de dominio. | < 5% |
| **Patrón estructural** | Combinación de patrones AST que casi siempre indica un bug: la estructura del código es suficiente para diagnosticar el problema. Algún FP es esperado pero infrecuente. | < 15% |
| **Heurística de intención** | El detector infiere la intención del código desde la forma del AST, pero esa forma puede tener múltiples semánticas. Requiere análisis adicional (semántico, de llamadas, de tipos) para certeza. FP estructuralmente inevitables con AST puro. | < 40% |

### Criterio de estado según naturaleza

- **Estable**: FP rate dentro del rango orientativo de su categoría **Y** la regla
  ha mejorado sustancialmente respecto a versiones anteriores.
- **Limited Scope**: El detector es preciso dentro de un subconjunto acotado del patrón
  original, pero excluye explícitamente casos que no son distinguibles con AST puro.
  Adecuado cuando el subconjunto detectado es valioso y el scope excluido está documentado.
- **Needs Redesign**: FP rate supera el rango de su categoría **Y** no hay mejora
  demostrable con las heurísticas actuales. Requiere análisis semántico adicional
  (grafos de llamadas, análisis de tipos, análisis de flujo) para reducir FPs.

### Límite del AST puro

Si el problema de distinguir "patrón peligroso" vs "iteración normal" no es resoluble
con análisis de árbol sintáctico sin análisis semántico adicional (tipos, flujo de datos,
grafos de llamadas), el estado correcto es **Limited Scope** con scope documentado, no
"Needs Redesign" indefinido. La distinción importa: "Needs Redesign" implica que hay
una heurística AST mejor esperando ser encontrada; "Limited Scope" declara explícitamente
que el problema requiere más que AST.

## Auditoría de falsos positivos

Una regla que genere >20% de falsos positivos en muestra estratificada entra en revisión.
El proceso y el estado resultante dependen de la categoría de la regla:

- Si es **Determinística**: >5% FP implica bug en el detector → corregir.
- Si es **Patrón estructural**: >15% FP implica heurística mal calibrada → redesign.
- Si es **Heurística de intención**: >40% FP implica que el scope definido no es
  distinguible con AST puro → restringir scope a subconjunto distinguible (Limited Scope)
  o documentar como fuera de alcance del análisis estático.

**Proceso:**
```
regla activa
  → auditoría manual de muestra (mín. 20 hits estratificados por repo)
  → si FP rate supera el umbral de su categoría → estado "Needs Redesign" o "Limited Scope"
  → diseñar restricción de scope O nueva heurística
  → implementar + nueva auditoría
  → si mejora dentro del umbral de su categoría → "Estable" o "Limited Scope"
  → si sigue superando umbral después de restricción → documentar límite del AST puro
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
