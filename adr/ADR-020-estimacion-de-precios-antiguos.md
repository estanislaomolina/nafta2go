---
status: Propuesto
date: 2026-11-17
decision-makers: Equipo Nafta2Go
consulted: ADR-002, ADR-013, ADR-014, ADR-015, issues 57 y 19
informed: Cátedra
---

# Estimación rotulada para precios de 31 a 120 días

## Context and Problem Statement

La devolución de la Entrega 2 preguntó si las estaciones con precios de más de 30
días podrían mostrar una estimación del precio actual, rotulada como estimada (#57).
Hoy el sistema las excluye: RF09 prohíbe presentar precios antiguos como actuales.
El precio actual de una estación que no volvió a publicar no es observable, así que
cualquier estimación tiene que evaluarse con un proxy y no puede validarse de forma
directa.

## Decision Drivers

* No presentar un precio antiguo ni una estimación como precio oficial vigente (RF09).
* Decidir con evidencia temporal y un protocolo fijado antes de ver los resultados.
* Mantener el ranking normal determinístico y trazable (ADR-002).
* Ampliar la cobertura, que es la principal limitación del producto según el PRD.

## Considered Options

* Abstención: mostrar sólo estaciones con precio vigente, como hoy.
* Mostrar el precio viejo con su antigüedad, sin estimar.
* Estimación separada y rotulada, dentro del rango de antigüedad evaluado.

## Decision Outcome

Opción elegida: "Estimación separada y rotulada, dentro del rango de antigüedad
evaluado", porque el protocolo pre-registrado da `adopt=true` sobre 768 reingresos
de 2026 ([evidencia](../docs/evidencia/estimacion-antiguos-2026-11/README.md)). La
mediana reciente de la bandera, elegida con 2025, tiene un MAPE de 1,14 % frente a
2,37 % del precio viejo, y le gana en todos los tramos de antigüedad.

El alcance se limita a precios de **31 a 120 días**. Ahí hay 720 reingresos de
validación; más allá hay 48, con mediana de 129 días, que no representan los precios
de cientos de días del conjunto vigente. Para precios de más de 120 días se mantiene
la abstención.

Este límite **no estaba en el protocolo**: se decidió después de la corrida real. Con
48 casos (mínimo 30), el tramo de más de 120 días tenía soporte y también cumplía la
regla de adopción. Achicar el alcance es más conservador que el protocolo, pero es una
decisión posterior a ver los resultados y queda declarada como tal.

Reglas para una futura integración, a implementar en una issue aparte:

* La estimación va en campos separados del precio oficial: precio oficial, fecha
  oficial, estimación, fecha de referencia de la estimación, método y versión.
* No renueva la vigencia del precio oficial ni entra al ranking normal.
* Se rotula como estimada. Un presupuesto calculado con ella no garantiza el importe
  real en surtidor.
* Usa el mismo método y la misma preparación temporal que la referencia servida por
  ADR-015 (`bandera_reciente`).

### Consequences

* Good, because la cobertura puede crecer con estaciones de precios de 31 a 120 días,
  con un error medido y menor que mostrar el precio viejo.
* Good, because reutiliza la referencia ya servida y su preparación temporal, sin un
  modelo nuevo en producción.
* Bad, because el proxy de reingresos favorece a los métodos que estiman cambios: una
  estación cuyo precio no cambió no aparece en la evaluación.
* Bad, because agrega un tipo de dato que la interfaz tiene que distinguir con
  claridad del precio oficial.

### Confirmation

La evaluación es reproducible desde el tag `evidencia/estimacion-antiguos-2026-11`
con `python -m nafta2go.ml.evaluate_stale`. La cátedra aprobó el alcance el
18/11/2026; falta la confirmación del resto del equipo para pasar a Aceptado.

La integración (#117) calcula la mediana sobre la ingesta vigente, que guarda la
última publicación de cada estación, mientras que la evaluación usó todas las
publicaciones del histórico. Tests de la API verifican el rango de antigüedad, la
abstención sin referencia y que las estaciones estimadas no entren al ranking.

## Pros and Cons of the Options

### Abstención

* Good, because nunca muestra un precio que no fue publicado como vigente.
* Bad, because deja sin cubrir estaciones que podrían orientar la decisión.

### Precio viejo con su antigüedad

* Good, because es simple y no introduce un modelo.
* Bad, because en 2026 se equivoca más que la estimación en todos los tramos: 2,89 %
  de 61 a 120 días y 8,76 % con más de 120.
* Bad, because un precio viejo junto a precios vigentes puede leerse como actual.

### Estimación separada y rotulada

* Good, because en el rango evaluado tiene menor error que el precio viejo.
* Neutral, because depende de que la bandera tenga publicaciones recientes; si no,
  la referencia cae al último precio propio, como en ADR-015.
* Bad, because no puede validarse contra el precio actual real, sólo contra
  reingresos.

## More Information

Con más de 120 días, Ridge rinde mejor que el método elegido (MAPE 2,07 % contra
2,91 %). No se cambia la elección porque surge de la validación ya inspeccionada;
evaluarlo requiere otro protocolo y otro período. Con la corrección de `market_change`
(#119), Ridge da 2,14 % en ese tramo y la elección y la adopción no cambian.
ADR-002 y ADR-015 siguen vigentes: la estimación no modifica el precio oficial ni
el ranking normal.
