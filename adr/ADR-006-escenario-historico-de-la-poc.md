---
status: Propuesto
date: 2026-10-25
decision-makers: Felipe Sidiropulos (POC-02), a revisar por el equipo
consulted: PRD (RF09, RF15), ADR-001, issue POC-02 (#7), PR #35, PR #37
informed: Cátedra
---

# Captura vigente congelada como escenario histórico de la POC

## Context and Problem Statement

La cobertura de precios recientes de la fuente oficial varía mucho. En la
Entrega 1 solo 2 de 184 estaciones de CABA tenían precio de hasta 30 días; en la
captura del 24/10/2026 son 47. El ADR-001 ya decidió que, cuando la cobertura no
alcance, la POC debe usar un escenario histórico claramente rotulado, sin
presentar nunca precios viejos como actuales (RF09, RF15).

Falta decidir **qué datos forman ese escenario**, cómo se conservan para que la
demo sea reproducible y cuándo se activa.

## Decision Drivers

* Reproducibilidad: la demo y los tests tienen que dar lo mismo en cualquier
  máquina y en cualquier fecha.
* Trazabilidad: el escenario tiene que poder vincularse con una captura oficial
  verificable (SHA-256, URL, fecha y licencia).
* Honestidad: el escenario nunca puede confundirse con la captura actual.
* Esfuerzo acotado a la POC.
* Reutilizar la normalización de POC-01 y la selección de #37.

## Considered Options

* (a) Captura vigente congelada con fecha de referencia fija, versionada en el repo.
* (b) La última captura vigente guardada que sí alcanzaba la cobertura.
* (c) Precios reconstruidos a una fecha pasada desde el CSV histórico normalizado.

## Decision Outcome

Chosen option: "(a) captura vigente congelada", because es la única que se
reproduce igual en cualquier máquina sin depender de capturas acumuladas, ya
tiene una captura real verificada (la del 24/10/2026, usada también por #35 y
#36) y reutiliza sin cambios la normalización y la selección existentes.

El escenario se activa **automáticamente** cuando la captura actual no tiene
al menos 3 estaciones con precio reciente en el corredor del recorrido. Se
rotula con el estado `historical_scenario`, su ID y su fecha de referencia. Los
parámetros están en `nafta2go/application/coverage_rules.py` y el detalle en
[docs/COBERTURA.md](../docs/COBERTURA.md).

### Consequences

* Good, because la demo es reproducible y verificable: el recorte y su ficha
  con hashes están en `docs/evidencia/escenario-vigente-2026-10-24/`.
* Good, because el escenario no se ingiere en la base, así que la consulta
  actual nunca puede tomarlo como la última captura.
* Good, because con una captura vigente hay una sola fila por estación,
  producto y franja, así que no aparece el problema de selección por estación
  comentado en #37.
* Bad, because los precios del escenario envejecen: muestran el mercado del
  24/10/2026, sin importar la fecha de la consulta. Lo compensa el rótulo.
* Bad, because suma un archivo de 200 KB al repositorio y, para cambiar de
  escenario, hay que congelar otro y actualizar dos constantes.

### Confirmation

Los tests de `tests/application/test_stored_query.py` y
`tests/application/test_scenario.py` verifican:
* Que el escenario se activa solo cuando la captura actual no alcanza.
* Que la vigencia se mide contra la fecha de referencia del escenario.
* Que ningún precio del escenario lleva `data_run_id`.
* Que un recorte alterado se rechaza por su SHA-256.

## Pros and Cons of the Options

### (a) Captura vigente congelada

* Good, because es reproducible y no depende de la fecha ni de la máquina.
* Good, because ya existe una captura real verificada.
* Neutral, because hay que elegir a mano qué captura congelar.
* Bad, because los precios no se actualizan nunca.

### (b) Última captura guardada que alcanzaba

* Good, because se actualiza sola a medida que se acumulan ingestas.
* Bad, because hoy hay una sola captura guardada, así que no aporta nada todavía.
* Bad, because depende de la base local de cada máquina: no es reproducible.
* Bad, because distinguirla de la captura actual exige cambios en la selección
  de la última ingesta.

### (c) Reconstrucción desde el CSV histórico

* Good, because permite cualquier fecha pasada y más profundidad (2015-2026).
* Bad, because el histórico tiene muchas filas por estación: hay que resolver
  qué precio regía en cada fecha y aparece el problema de selección de #37.
* Bad, because cada corrida requiere el archivo de 780 MB.
* Bad, because es el que más trabajo lleva para la POC.

## More Information

* Las decisiones que acompañan a este ADR (mínimo de 3 candidatas, ventana de
  30 días, corredor de 5 km, activación automática y rótulo en el resultado) se
  tomaron el 2026-10-25 y están documentadas en
  [docs/COBERTURA.md](../docs/COBERTURA.md).
* El plan de POC-01 reservaba el número 006 para un posible ADR sobre las reglas
  de normalización. Como ese ADR no se escribió, este usa el siguiente número
  libre. Si se escribe más adelante, le corresponde el ADR-007.
