---
status: Aceptado
date: 2026-09-18
decision-makers: Equipo Nafta2Go
consulted: Propuesta, PRD y roadmap
informed: Cátedra, pendiente de validación
---

# Arquitectura modular por capas

## Context and Problem Statement

El sistema deberá integrar interfaz web, API, reglas de recomendación, diagnóstico estadístico, ingesta, persistencia, proveedor de rutas y operación. El equipo necesita una arquitectura que permita repartir trabajo y mantener trazabilidad sin introducir infraestructura distribuida antes de validar el flujo principal.

## Decision Drivers

* Separación clara de responsabilidades.
* Facilidad para probar reglas y contratos.
* Desarrollo local simple.
* Preparación para contenedores y cloud sin exigir microservicios prematuros.
* Capacidad de incorporar ingesta programada y adaptadores externos.
* Complejidad compatible con el tiempo disponible.

## Considered Options

* Aplicación modular por capas con adaptadores externos.
* Microservicios independientes desde el inicio.
* Arquitectura orientada a eventos como mecanismo central.

## Decision Outcome

Chosen option: **aplicación modular por capas**, con presentación web, API, dominio de recomendación/diagnóstico, servicios de datos y adaptadores para fuentes y rutas, because permite aislar decisiones de negocio, probarlas localmente y evolucionar hacia contenedores y servicios separados sólo cuando la evidencia lo justifique.

La ingesta programada podrá emitir métricas o eventos operativos, pero el flujo principal de recomendación no dependerá inicialmente de una plataforma de streaming.

### Consequences

* Good, because cada capa tiene contratos y responsabilidades identificables.
* Good, because el dominio puede probarse sin depender de la interfaz o del proveedor de rutas.
* Good, because un despliegue inicial puede ser simple y portable.
* Bad, because el componente inicial puede concentrar más responsabilidades que un sistema distribuido.
* Bad, because habrá que definir límites claros para evitar que los módulos se acoplen.
* Bad, because no se obtiene desde el inicio la independencia operativa de microservicios.

### Confirmation

La decisión se confirma si el flujo completo puede ejecutarse localmente, las reglas tienen pruebas independientes, los adaptadores pueden reemplazarse y los componentes pueden empaquetarse sin modificar el dominio.

## Pros and Cons of the Options

### Aplicación modular por capas

* Good, because reduce la complejidad inicial y favorece pruebas aisladas.
* Good, because es adecuada para un equipo pequeño y un alcance controlado.
* Good, because permite extraer servicios más adelante si aparecen cuellos de botella reales.
* Bad, because requiere disciplina para preservar las fronteras entre capas.

### Microservicios independientes desde el inicio

* Good, because separa despliegues y escalado por componente.
* Good, because representa explícitamente algunos límites operativos.
* Bad, because agrega redes, contratos, observabilidad, despliegues y fallos distribuidos antes de tener evidencia.
* Bad, because aumenta el costo de desarrollo y de ejecución local para la POC.

### Arquitectura orientada a eventos como mecanismo central

* Good, because encaja con ingestas programadas, métricas y procesamiento desacoplado.
* Good, because puede facilitar reintentos y auditoría de ejecuciones.
* Bad, because el caso principal es una consulta síncrona que necesita una respuesta explicada.
* Bad, because introduce broker, consistencia eventual y debugging distribuido sin ser necesarios para validar la recomendación.

## More Information

* `docs/Propuesta nafta2go.md`, sección Solución propuesta a alto nivel.
* `docs/PRD.md`, RNF05, RNF06, RNF07 y RNF08.
* `docs/ROADMAP.md`, issues POC-05, POC-06 y POC-07.
