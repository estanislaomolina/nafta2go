---
status: Aceptado
date: 2026-11-21
decision-makers: Estanislao Molina Abeniacar, Felipe Sidiropulos
consulted: PRD, issues 19, 20 y 23
informed: Equipo Nafta2Go, cátedra
---

# Validación técnica de diez escenarios sin participantes

## Context and Problem Statement

El PRD propone medir utilidad y comprensión con al menos diez conductores.
Estanislao decidió el 21/11, con acuerdo de Felipe en la revisión de #142,
reemplazar esa actividad de la entrega por una
simulación técnica. Debe ser reproducible sin inventar personas ni respuestas.
La simulación no mide comportamiento humano ni acredita esos objetivos del PRD.
El recorte se comunica en la defensa; no se presume aprobación de la cátedra.

## Decision Drivers

- Completar una comprobación repetible del flujo y de sus restricciones.
- Diferenciar evidencia automática, datos históricos y servicios reales.
- Conservar visibles los objetivos no acreditados y las limitaciones.

## Considered Options

1. Mantener el estudio moderado con diez conductores reales.
2. Ejecutar diez escenarios técnicos sin participantes.
3. Omitir la actividad sin evidencia adicional.

## Decision Outcome

Se elige la opción 2 por decisión de alcance del integrante. El ejecutable
`scripts/validate_simulated_scenarios.py` cubre cinco consultas UC01 y cinco UC02,
variando producto, horario, consumo, presupuesto y cantidad de candidatas.
Verifica respuesta, rótulo histórico, restricciones físicas y motivos de descarte;
audita trazabilidad, frescura relativa al escenario y privacidad de lo persistido.
Usa una base temporal y no modifica la operación real.

Por defecto utiliza distancias sintéticas constantes. `--live-routes` utiliza ORS
real (hasta diez matrices), requiere clave y consume cuota; el lote se identifica
por separado. En ambos casos los precios son la captura histórica rotulada del
repositorio. No son viajes reales ni precios actuales. No usa ni provisiona AWS.

### Consequences

- La entrega tendrá evidencia técnica de diez casos, no diez participantes.
- Utilidad y comprensión quedan **no acreditadas por recorte de alcance**.
- No se calculan porcentajes de respuestas humanas ni se simulan entrevistas.
- Las mediciones HTTP en proceso excluyen la red del cliente y el teléfono físico.
- Cinco solicitudes por caso de uso son una muestra pequeña, sin garantía de SLA.

### Confirmation

Pruebas del ejecutable verifican que una caída de rutas no cuenta como éxito,
que no permite modo real sin clave y que el modo por defecto no usa la red.
El reporte informa `real_participants=0`, procedencia de código, precios, rutas,
resultados de cada caso y auditoría. El CI conserva las pruebas de navegador de
#19/#20 como evidencia separada de presentación y accesibilidad automatizada.

## Pros and Cons of the Options

### Estudio con conductores

- A favor: mide elección, explicaciones y dificultades observadas.
- En contra: requiere reclutamiento y moderación; se recorta por decisión del integrante.

### Escenarios técnicos

- A favor: repetible, automatizable, detecta fallos de contrato y restricciones.
- En contra: no permite inferir utilidad ni comprensión, aunque todos los casos pasen.

### Omitir

- A favor: no agrega trabajo.
- En contra: no aporta evidencia del flujo y deja el recorte menos verificable.
