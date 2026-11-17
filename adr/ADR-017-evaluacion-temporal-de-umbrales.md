---
status: Propuesto
date: 2026-11-16
decision-makers: Equipo Nafta2Go
consulted: ADR-013, ADR-014, ADR-015, issues 19 y 20
informed: Cátedra
---

# Evaluación temporal de umbrales candidatos

## Context and Problem Statement

Una referencia de precio no valida una alerta. Sin etiquetas de errores reales,
podemos medir desviaciones y frecuencia de exclusión, pero no precisión ni recall.
Antes de cambiar el ranking se necesita evidencia de una política explícita.

## Considered Options

* Porcentaje fijo: sencillo y explicable, pero arbitrario sin evidencia de escala.
* Cuantil empírico con auditoría temporal posterior: deriva candidatos de datos
  anteriores y permite observar su comportamiento posterior; requiere suficientes
  ejemplos y no garantiza tasas futuras ante inflación o cambios de población.
* Mantener sólo abstención: conserva seguridad, pero no permite evaluar políticas.

## Decision Outcome

Evaluar la segunda opción fuera de producción y conservar ADR-015 al servir.
El método ya elegido permanece congelado; no se carga el modelo no seleccionado.
Se divide la antigua validación en calibración anterior al corte explícito y
auditoría desde ese corte. Esa calibración deja de ser validación independiente.
Cuantil y corte deben fijarse antes de examinar la auditoría: reajustarlos exige
otro período de evaluación. El software no elige el cuantil por sus resultados.

La desviación es `abs(publicado-referencia)/referencia`, con el mismo redondeo
y fallback del serving. Cada producto/franja tiene su candidato por rango más
cercano superior; se compara con `>` para tratar empates explícitamente. Se
abstiene con soporte insuficiente. Hashes, parámetros y código quedan registrados.

### Consequences and Confirmation

El reporte declara `runtime_enabled=false`. No activa alertas, no estima precios
actuales ni excluye estaciones. Una excedencia no demuestra un precio erróneo.
Pruebas verifican separación temporal, integridad, fallback, abstención y salida
reproducible. Hacen falta corrida histórica real, revisión de segmentos/política
e integración independiente antes de completar #19 o #20.
