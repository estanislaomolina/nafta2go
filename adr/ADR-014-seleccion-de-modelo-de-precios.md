---
status: Propuesto
date: 2026-11-15
decision-makers: Equipo Nafta2Go (pendiente de revisión)
consulted: ADR-002, ADR-013, PRD RF10/RNF10, issues 18 y 56
informed: Equipo y cátedra
---

# Selección del método de referencia de precios sin usar la validación

## Context and Problem Statement

[ADR-013](ADR-013-evaluacion-temporal-de-precios.md) separa los ejemplos en train y
validación con un corte temporal. Con eso se pueden entrenar modelos, pero falta decidir
**cómo se elige** entre ellos y las referencias que no aprenden nada, y qué se hace si
ningún modelo las supera (#56: “no inventar mejoras para la demo”).

Si la misma validación sirve para elegir y para informar el resultado, el número
informado deja de ser una estimación honesta del error futuro.

## Decision Drivers

* La validación reservada no puede influir en la elección.
* El modelo tiene que superar a la referencia trivial **más fuerte**, no solo a la
  mediana: con inflación alta, una mediana de 30 días es una vara baja.
* El resultado tiene que poder repetirse exactamente (RNF10).
* Costo de cómputo y de explicación acotado para el alcance del TP.

## Considered Options

* Elegir el método con mejor resultado en la validación del dataset.
* Elegir con un período interno de train (2025) y usar la validación solo para informar.
* Elegir con varios cortes anuales dentro de train (validación cruzada temporal).

## Decision Outcome

Chosen option: **período interno de selección dentro de train**, porque es la opción
más simple que mantiene la validación sin tocar. Los candidatos se entrenan con train
anterior a 2025 y se comparan en 2025. Gana el de menor MAE en ARS/L, **sea modelo o
referencia**. Después se reentrenan con todo train y se informan todos en la
validación, sin cambiar la elección.

Referencias que compiten: mediana de 30 días del dataset, último precio de la estación
y mediana de la misma bandera en la última semana. Candidatos: regresión Ridge y
árboles potenciados, con hiperparámetros fijos declarados en el código. Ambos aprenden
una corrección relativa al último precio para no depender del nivel nominal.

### Consequences

* Good, because el error informado en validación no se usó para elegir nada.
* Good, because si una referencia gana, el sistema la usa y lo declara, como pide #56.
* Good, because todo queda fijado en código y manifiesto: dos corridas dan archivos
  idénticos.
* Bad, because un único año de selección puede no representar el siguiente: en la
  corrida del 15/11 la referencia ganó en 2025 y los modelos ganaron en 2026.
* Bad, because no se exploran hiperparámetros; un ajuste fino podría mejorar los modelos.

### Confirmation

`tests/ml/test_models.py` verifica que alterar los precios de validación no cambia la
selección ni el método elegido, y que dos entrenamientos producen los mismos archivos.
La corrida real está en
[docs/ML.md](../docs/ML.md#comparación-de-modelos-del-15112026).

## Pros and Cons of the Options

### Elegir con la validación del dataset

* Good, because usa los datos más cercanos al período de uso.
* Bad, because el error informado queda optimista: es el mejor de varios intentos sobre
  los mismos datos.
* Bad, because no queda ningún dato reservado para confirmar la elección.

### Período interno de selección (elegida)

* Good, because es simple de explicar y de reproducir.
* Good, because deja la validación intacta para informar.
* Neutral, because reduce los datos de entrenamiento durante la selección.
* Bad, because depende de que un solo año sea representativo.

### Validación cruzada temporal dentro de train

* Good, because promedia varios años y reduce la dependencia de uno solo.
* Bad, because multiplica el costo y complica el reporte.
* Bad, because adoptarla ahora, después de ver la validación, sería ajustar el protocolo
  con datos reservados. Queda como alternativa para una próxima captura.

## More Information

* Comando: `python -m nafta2go.ml.train --dataset DIR --output DIR`.
* Si se cambia el protocolo, se registra en un ADR nuevo y se evalúa sobre una
  validación que no se haya mirado antes.
