---
status: Aceptado
date: 2026-11-10
decision-makers: Equipo Nafta2Go
consulted: PRD (RF03, RNF01, RNF02, RNF03), ADR-003, issue 55
informed: Cátedra
---

# Caché volátil y cupo por proceso para matrices de rutas

## Context and Problem Statement

Las consultas repetidas consumen cuota aunque las coordenadas no cambien. Hay
que reducir llamadas sin conservar ubicaciones del conductor en disco ni
reutilizar precios o recomendaciones que deben recalcularse.

## Decision Drivers

* Privacidad, vencimiento explícito y tamaño acotado.
* Menos llamadas sin alterar distancias, orden ni reglas del recomendador.
* Cuidar la cuota aun cuando las solicitudes no coincidan en caché.

## Considered Options

* LRU en memoria con TTL y cupo local por credencial.
* Caché persistida en SQLite.
* Redis compartido entre procesos.

## Decision Outcome

Chosen option: **LRU en memoria**, porque el primer despliegue tiene un proceso
y no necesita un servicio adicional ni persistir ubicaciones. La clave incluye
endpoint/perfil, credencial aislada mediante hash, métricas/unidades y listas
exactas y ordenadas de coordenadas. Se conserva fecha y hash del primer resultado.
El proveedor valida la matriz antes de ingresarla; los errores no se guardan.
Los precios y las recomendaciones se recalculan desde su versión de datos.

### Consequences

* Good, because una repetición vigente evita una llamada, incluso durante un
  bloqueo por cuota, y no renueva artificialmente su fecha de captura.
* Good, because los cupos cuentan intentos fallidos y atienden `Retry-After` o
  reinicio anunciado; sin indicación válida, un 429 bloquea nuevos intentos 60 s.
* Bad, because los faltantes se serializan y esperan como máximo dos segundos;
  si el proveedor sigue ocupado se devuelve error, sin inventar rutas.
* Bad, because cuota, caché y contadores se reinician con el proceso. Con varios
  workers o clientes de la misma key se necesita coordinación compartida.

### Confirmation

Tests sin red verifican TTL, LRU, aislamiento, concurrencia, cuotas y errores;
la integración compara recomendaciones con/sin caché y cambia precios sin volver
a consultar rutas. No constituye una medición de p95 del sistema completo.

## Pros and Cons of the Options

* **Memoria:** simple, acotada y volátil; no comparte estado entre procesos.
* **SQLite:** sobrevive reinicios; persistiría ubicaciones y sumaría escrituras.
* **Redis:** coordina workers; agrega infraestructura, costo y controles de retención.

## More Information

En el [foro oficial del proveedor](https://ask.openrouteservice.org/t/persistent-storage-and-reuse-of-matrix-api-duration-results/8010)
se admite reutilización sujeta a sus términos y se advierte que datos/grafos
pueden cambiar. Se mantiene atribución ORS/OpenStreetMap y un TTL conservador.
Configuración y límites operativos en [RUTAS](../docs/RUTAS.md).
