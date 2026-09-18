---
status: Propuesto
date: 2026-09-18
decision-makers: Equipo Nafta2Go
consulted: PRD, propuesta y notebook de exploración
informed: Cátedra, pendiente de validación
---

# Proveedor de rutas para la POC

## Context and Problem Statement

El recomendador necesita distancias y tiempos para comprobar alcanzabilidad, consumo y desvío. La POC debe evaluar hasta diez estaciones y el MVP hasta veinte. El notebook estima 22 ubicaciones por matriz y 40 solicitudes diarias, pero la cuota, la latencia y las condiciones de uso todavía no fueron verificadas con una cuenta autenticada.

## Decision Drivers

* Cuota y límites compatibles con el uso académico.
* Distancias y tiempos suficientemente realistas.
* Latencia y manejo de errores.
* Costo operativo y facilidad de ejecución local.
* Posibilidad de cambiar de proveedor sin reescribir el recomendador.

## Considered Options

* OpenRouteService Standard como proveedor externo principal.
* OSRM ejecutado sobre un extracto regional de OpenStreetMap.
* Distancia geográfica aproximada sin un motor de rutas.

## Decision Outcome

Chosen option: **proponer OpenRouteService como proveedor principal, encapsulado detrás de un adaptador, y conservar OSRM como alternativa técnica**, because ofrece rutas y matrices sin administrar inicialmente la infraestructura del grafo, mientras que el adaptador reduce el costo de cambiar si la prueba autenticada falla.

Esta decisión queda `Propuesta` hasta comprobar cuota, autenticación, contrato, errores, latencia y atribución con una prueba reproducible.

### Consequences

* Good, because la POC puede concentrarse en el recomendador y no en operar un grafo vial.
* Good, because una matriz permite limitar el número de solicitudes por consulta.
* Good, because el adaptador permite evaluar OSRM sin acoplar las reglas de negocio al proveedor.
* Bad, because existe dependencia externa, cuota y posible latencia variable.
* Bad, because se necesita una credencial y respetar condiciones de uso y atribución.
* Bad, because OSRM requiere datos, infraestructura y mantenimiento adicionales.

### Confirmation

La decisión se acepta si una prueba autenticada confirma el contrato, los límites, la latencia y una matriz representativa. Si no se confirma, se reduce el número de candidatas, se aplica caché sólo cuando sea compatible y se prueba OSRM regional.

## Pros and Cons of the Options

### OpenRouteService Standard

* Good, because ofrece Directions y Matrix listos para integrar.
* Good, because evita administrar inicialmente un grafo regional.
* Neutral, because depende de una cuota gratuita que debe verificarse.
* Bad, because requiere credenciales y puede fallar por cuota o disponibilidad.

### OSRM regional administrado por el equipo

* Good, because reduce la dependencia de una cuota externa una vez operativo.
* Good, because permite controlar la versión del extracto y reproducir el entorno.
* Bad, because exige descargar, actualizar y operar el grafo vial.
* Bad, because agrega costo de infraestructura y complejidad para la POC.

### Distancia geográfica aproximada

* Good, because es barata, local y simple de probar.
* Good, because puede servir como fallback de diagnóstico.
* Bad, because no representa la red vial ni los tiempos de recorrido.
* Bad, because puede producir recomendaciones incorrectas cuando el desvío real no sigue la distancia en línea recta.

## More Information

* `docs/PRD.md`, RF03, RF04, RNF01 y los supuestos de rutas.
* `notebooks/data_exploration.ipynb`, sección de viabilidad del proveedor de rutas.
* `docs/Propuesta nafta2go.md`, fuentes y plan alternativo de rutas.
