---
status: Aceptado
date: 2026-09-18
decision-makers: Equipo Nafta2Go
consulted: PRD, propuesta y notebook de exploración
informed: Cátedra, pendiente de validación
---

# Alcance en CABA y estrategia de datos actuales e históricos

## Context and Problem Statement

La fuente oficial tiene una estructura utilizable, pero la cobertura reciente no alcanza para sostener una recomendación representativa en toda CABA: sólo 8 registros de 2 estaciones cumplen el umbral de 30 días. En cambio, el histórico filtrado contiene 20.522 observaciones, 76 identificadores de estación y aproximadamente 142 meses.

La decisión debe definir el alcance inicial y evitar que precios antiguos se presenten como actuales.

## Decision Drivers

* Honestidad sobre la vigencia y cobertura de los precios.
* Viabilidad para un equipo de 2 o 3 personas durante la cursada.
* Reproducibilidad de la POC.
* Disponibilidad de datos suficientes para validar reglas y una referencia estadística.
* Alcance compatible con la evidencia observada en el notebook.

## Considered Options

* Usar únicamente precios actuales de toda CABA.
* Ampliar desde el inicio el producto a todo el país.
* Mantener CABA y combinar precios actuales con escenarios históricos explícitamente rotulados.

## Decision Outcome

Chosen option: **mantener CABA y nafta súper/premium como alcance del producto, usar precios recientes para recomendaciones actuales y habilitar escenarios históricos sólo como fallback claramente identificado**, because preserva la honestidad del resultado y permite validar el flujo con el histórico disponible sin presentar datos viejos como vigentes.

### Consequences

* Good, because el alcance es acotado y defendible para la cursada.
* Good, because el histórico permite probar continuidad, features temporales y escenarios reproducibles.
* Good, because la falta de cobertura se comunica en lugar de ocultarse.
* Bad, because actualmente habrá pocas recomendaciones actuales en CABA.
* Bad, because los escenarios históricos no pueden interpretarse como disponibilidad o precio presente.
* Bad, because ampliar el entrenamiento a datos nacionales queda como plan alternativo y no como garantía.

### Confirmation

La decisión se confirma si la POC puede demostrar un caso actual con cobertura suficiente o un caso histórico rotulado, conserva la fecha de vigencia y rechaza fechas ambiguas o futuras hasta normalizarlas.

## Pros and Cons of the Options

### Usar únicamente precios actuales de toda CABA

* Good, because la interpretación para el usuario sería simple.
* Bad, because la evidencia actual no ofrece cobertura suficiente.
* Bad, because podría producir una interfaz sin resultados o inducir falsa representatividad.

### Ampliar desde el inicio el producto a todo el país

* Good, because aumenta la cantidad potencial de observaciones y estaciones.
* Neutral, because podría servir para entrenar una referencia estadística.
* Bad, because aumenta la complejidad de calidad, geografía, pruebas y explicación.
* Bad, because no resuelve por sí sola la frescura de cada precio.

### CABA actual más escenarios históricos rotulados

* Good, because se ajusta a la evidencia y al alcance aprobado.
* Good, because permite validar el flujo sin falsear actualidad.
* Bad, because exige comunicar con claridad la fecha y el tipo de escenario.
* Bad, because la cobertura actual sigue siendo una limitación del producto.

## More Information

* `docs/PRD.md`, secciones Contexto y evidencia, Supuestos y Limitaciones.
* `notebooks/data_exploration.ipynb`, puertas de cobertura, fechas y profundidad histórica.
