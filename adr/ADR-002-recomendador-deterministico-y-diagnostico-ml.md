---
status: Aceptado
date: 2026-09-18
decision-makers: Equipo Nafta2Go
consulted: PRD, propuesta y notebook de exploración
informed: Cátedra, pendiente de validación
---

# Separar el recomendador determinístico del diagnóstico estadístico

## Context and Problem Statement

El producto debe elegir estaciones respetando restricciones físicas y económicas, explicar descartes y ofrecer resultados reproducibles. También debe incorporar machine learning de manera sustantiva, sin reemplazar el precio oficial por una predicción ni afirmar que un precio atípico es incorrecto.

La decisión debe separar, o no, el cálculo de factibilidad y ranking del diagnóstico estadístico de precios.

## Decision Drivers

* Reproducibilidad y explicabilidad de las recomendaciones.
* Prevención de fuga temporal en las variables de ML.
* Capacidad de operar aunque el modelo no supere al baseline.
* Cumplimiento del alcance funcional del PRD.
* Facilidad para probar restricciones, descartes y casos de borde.

## Considered Options

* Resolver todo con reglas determinísticas y no incorporar ML al producto.
* Usar un modelo de ML para decidir directamente el ranking de estaciones.
* Usar un motor determinístico para recomendar y un componente ML separado para diagnosticar precios.

## Decision Outcome

Chosen option: **motor determinístico para factibilidad, cálculos y ranking, con un componente ML separado para diagnosticar referencia, atipicidad y nivel de confianza del precio**, because las restricciones críticas quedan auditables y el ML aporta valor sin convertirse en una fuente opaca de decisiones ni alterar el precio oficial.

### Consequences

* Good, because los cálculos de autonomía, reserva, presupuesto, capacidad y desvío son reproducibles.
* Good, because un fallo o desempeño insuficiente del modelo no impide ejecutar el recomendador base.
* Good, because el usuario puede comparar ranking general y ranking conservador.
* Bad, because hay dos componentes que versionar, probar y observar.
* Bad, because el modelo requiere validación temporal, baseline y monitoreo antes de producir alertas.
* Bad, because la confianza del precio debe explicarse como diagnóstico y no como verdad.

### Confirmation

La decisión se confirma cuando una misma consulta produce los mismos cálculos con la misma versión de datos y reglas, y el componente ML se evalúa contra la mediana comparable sin usar información futura.

## Pros and Cons of the Options

### Todo determinístico, sin ML

* Good, because minimiza complejidad y riesgo de fuga.
* Good, because es fácil de explicar y probar.
* Bad, because no cubre el diagnóstico de confianza requerido en el PRD ni el área de ML del proyecto.
* Bad, because no permite detectar precios atípicos más allá de reglas simples.

### ML decide directamente el ranking

* Good, because podría capturar patrones difíciles de expresar con reglas.
* Bad, because vuelve opacas las restricciones críticas de autonomía y presupuesto.
* Bad, because aumenta el riesgo de fuga temporal y de resultados difíciles de defender.
* Bad, because si el modelo no supera el baseline se degrada el camino principal.

### Motor determinístico más diagnóstico ML

* Good, because combina explicabilidad operacional y uso sustantivo de ML.
* Good, because permite comparar el resultado general con uno conservador.
* Good, because el baseline puede permanecer como respaldo explícito.
* Bad, because requiere contratos claros entre reglas, modelo y respuesta de la API.

## More Information

* `docs/PRD.md`, RF04, RF07, RF10, RF11 y RNF10.
* `docs/Propuesta nafta2go.md`, sección Enfoque de Machine Learning.
* La exploración todavía no demuestra mejora del modelo frente al baseline; esa validación queda para la POC/MVP.
