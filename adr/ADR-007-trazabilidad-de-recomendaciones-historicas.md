---
status: Aceptado
date: 2026-10-26
decision-makers: Estanislao Molina Abeniacar
consulted: ADR-005, ADR-006, RF15, RNF03, RNF05
---

# Origen de datos de las recomendaciones históricas

## Contexto

El escenario de ADR-006 no se ingiere como vigente. El esquema inicial exigía
`recommendations.data_run_id`, por lo que no podía registrar su resultado sin
atribuirlo incorrectamente a una ingesta. POC-05 necesita trazabilidad también
cuando usa ese respaldo, sin conservar las ubicaciones del conductor.

## Alternativas

| Alternativa | Ventajas | Desventajas |
|---|---|---|
| Crear una ingesta ficticia para el escenario | Conserva el esquema inicial | La consulta puede elegirla como captura vigente; atribución engañosa |
| No registrar resultados históricos | No cambia el esquema | Pierde la evidencia y trazabilidad de esas recomendaciones |
| Permitir un origen alternativo identificado | Conserva el historial sin mezclar fuentes; migración pequeña | El repositorio debe validar dos formas de procedencia |

## Decisión

Usar la tercera opción. La migración `0002` permite `data_run_id` nulo y agrega
`scenario` en JSON. Un CHECK exige exactamente uno de los dos orígenes. El
repositorio valida que la ingesta esté `succeeded`, o que el escenario incluya
identificador, fecha con zona y hashes SHA-256 del original y del recorte.

El flujo guarda versión del motor, proveedor, referencia de rutas, parámetros y
resultado. No incluye las coordenadas del usuario en el registro. Una captura
explícita de la matriz para la demo controlada es un artefacto separado.

## Consecuencias y verificación

Las recomendaciones existentes conservan su ejecución y reciben escenario
nulo. El escenario no crea una ingesta y nunca puede convertirse en la última
captura vigente. Los tests cubren ambas procedencias, la migración con datos y
el rechazo de un origen ausente o mezclado. La vuelta a `0001` se rechaza si hay
recomendaciones históricas, para evitar perderlas o inventarles una ejecución.

## Confirmación al cierre de Entrega 2

Aceptado el 27/10/2026 al cerrar la entrega. La migración 0002, el registro de
ambas procedencias y sus pruebas están integrados en #41. La consulta completa
verifica la persistencia sin convertir el escenario en una ingesta vigente.
