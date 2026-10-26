# ADRs de Nafta2Go

Los Architecture Decision Records documentan decisiones de diseño relevantes, las alternativas consideradas y sus consecuencias. Cada decisión debe poder contrastarse con el PRD, el notebook y la implementación futura.

## Decisiones de la Entrega 1

| ADR | Decisión | Estado |
|---|---|---|
| [ADR-001](ADR-001-alcance-y-estrategia-de-datos.md) | Alcance en CABA y estrategia frente a la baja cobertura reciente | Aceptado |
| [ADR-002](ADR-002-recomendador-deterministico-y-diagnostico-ml.md) | Recomendador determinístico con diagnóstico ML separado | Aceptado |
| [ADR-003](ADR-003-proveedor-de-rutas.md) | OpenRouteService como proveedor principal y OSRM como alternativa | Aceptado |
| [ADR-004](ADR-004-arquitectura-por-capas.md) | Arquitectura modular por capas | Aceptado |

## Decisiones de la Entrega 2

| ADR | Decisión | Estado |
|---|---|---|
| [ADR-005](ADR-005-persistencia-de-la-poc.md) | SQLite con SQLAlchemy y Alembic para la persistencia de la POC | Aceptado |
| [ADR-006](ADR-006-escenario-historico-de-la-poc.md) | Captura vigente congelada como escenario histórico de la POC | Propuesto |

La decisión sobre el proveedor de rutas se aceptó con la prueba autenticada de POC-03; el resultado está en [docs/RUTAS.md](../docs/RUTAS.md).
