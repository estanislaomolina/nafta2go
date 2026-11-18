---
status: Propuesto
date: 2026-11-18
decision-makers: Equipo Nafta2Go
consulted: ADR-002, ADR-015, ADR-017, issues 19 y 20
informed: Cátedra
---

# Ranking conservador con una regla provisional de desvío

## Context and Problem Statement

RF11 pide un ranking conservador que excluya las estaciones con alerta y explique la
diferencia con el ranking general (#20). RF10 pide un nivel de alerta en el diagnóstico
(#19). Hoy el diagnóstico de ADR-015 sirve una referencia, pero responde
`not_calibrated` porque no había umbrales evaluados.

La auditoría de ADR-017 ([evidencia](../docs/evidencia/alertas-precios-2026-11-17/README.md))
dejó un umbral candidato por producto sobre el desvío relativo
`abs(publicado - referencia) / referencia`: 5,4244 % para súper y 5,4570 % para premium.
En la auditoría hubo **0 excedencias en 574 casos**. Eso muestra que el umbral casi no
excluye precios normales, pero no muestra que detecte precios mal publicados: no hay
etiquetas de errores reales. La pregunta es si alcanza para ofrecer un ranking
alternativo rotulado, sin tocar el ranking general.

## Decision Drivers

* No presentar un desvío como prueba de que el precio esté mal (RF11).
* El ranking general no cambia: sigue determinístico y trazable (ADR-002).
* Usar umbrales fijados antes de la auditoría, no elegidos después.
* No agregar llamadas a rutas ni servicios externos.

## Considered Options

* Mantener la abstención: no ofrecer ranking conservador.
* Activar como regla provisional los umbrales candidatos de la auditoría.
* Usar un porcentaje fijo, por ejemplo 10 %.

## Decision Outcome

Opción propuesta: "Activar como regla provisional los umbrales candidatos de la
auditoría", porque son los únicos valores derivados con un protocolo fijado antes de
ver los resultados y porque el ranking conservador se agrega al general en lugar de
reemplazarlo. La decisión queda sujeta a la confirmación del equipo.

Reglas:

* Versión `conservative-v1`. Súper (producto 2): `0.05424409844299347`. Premium
  (producto 3): `0.054570259208731244`. Ambos salen de `alert-evaluation.json`.
* Comparación estricta (`>`), igual que en la auditoría: un desvío igual al umbral no
  excluye.
* La referencia es la misma que sirve ADR-015, con la misma preparación temporal.
* Una estación sin referencia (sin historia suficiente) se mantiene en el ranking
  conservador y se lista aparte como sin referencia.
* Sin configuración de ML compatible, o con el escenario histórico congelado, el
  ranking conservador informa que no está disponible. Nunca copia el general.
* El texto habla de desvío respecto de una referencia. Ningún campo ni texto dice que el
  precio sea incorrecto.

Para las estaciones sin referencia se compararon dos alternativas:

* **Mantenerlas y listarlas aparte (elegida).** El ranking conservador no se vacía en
  zonas con poca historia, y el conductor ve qué estaciones no se pudieron revisar.
* **Excluirlas.** Es más estricta, pero castiga la falta de datos como si fuera un
  desvío y puede dejar el ranking vacío sin una razón sobre el precio.

### Consequences

* Good, because el conductor puede comparar el ranking general con uno que deja afuera
  los precios más alejados de su referencia, y ver por qué.
* Good, because reutiliza las evaluaciones ya enrutadas: no hay costo de rutas extra.
* Bad, because la regla no tiene sensibilidad ni precisión medidas: con 0 excedencias en
  la auditoría no se sabe cuántos precios mal publicados detecta.
* Bad, because los 574 casos no son independientes: hay 288 grupos de estación,
  producto e instante, porque las franjas comparten publicaciones.

### Confirmation

Tests de la regla (desvío relativo, umbral por producto, empate, entradas inválidas), del
nivel de alerta en el diagnóstico, del ranking conservador (exclusión, sin referencia,
todas excluidas, sin configuración, escenario histórico) y de la presentación web. La
regla se revisa cuando haya datos nuevos o etiquetas de errores. Si cambian los umbrales,
cambia la versión.

## Pros and Cons of the Options

### Mantener la abstención

* Good, because nunca sugiere que un precio publicado tenga un problema.
* Bad, because deja RF10 y RF11 sin cumplir, aunque ya hay una auditoría con umbrales.

### Umbrales candidatos de la auditoría, como regla provisional

* Good, because los valores salen de un protocolo pre-registrado y reproducible.
* Good, because en la auditoría no excluyeron ningún precio normal.
* Bad, because no se validó que detecten errores, sólo que casi no molestan.

### Porcentaje fijo (10 %)

* Good, because es simple de explicar.
* Bad, because es arbitrario: no surge de la distribución de desvíos de los datos.
* Bad, because en calibración el 95 % de los desvíos queda por debajo de 5,5 %: no hay
  evidencia de qué pasa entre ese valor y 10 %.

## More Information

Complementa ADR-015: el diagnóstico pasa de `not_calibrated` a un nivel de alerta
provisional. ADR-017 sigue vigente para el protocolo de evaluación. ADR-002 sigue
vigente: el ranking general no cambia.
