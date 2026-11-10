---
status: Aceptado
date: 2026-11-10
decision-makers: Equipo Nafta2Go
consulted: PRD (RF01 a RF09), ADR-004, ADR-005, MVP-02
informed: Cátedra
---

# API HTTP con FastAPI sobre la capa de aplicación

## Context and Problem Statement

La web y el despliegue necesitan una entrada HTTP al recomendador. El motor y
`application.query.recommend` ya resuelven el caso de uso; hay que exponerlos sin
duplicar reglas ni introducir lógica de precios o rutas en la presentación.

## Decision Drivers

* Contratos de entrada verificables y documentación OpenAPI.
* Pruebas sin red y reutilización del motor determinístico.
* Ejecución local y en la misma imagen Docker, con acceso controlado.

## Considered Options

* FastAPI con Pydantic y Uvicorn.
* Flask con validadores y documentación añadidos.
* Django con Django REST Framework.

## Decision Outcome

Chosen option: **FastAPI**, porque permite definir el contrato tipado y OpenAPI
manteniendo el caso de uso en aplicación. La validación física sigue en
`FuelRequest`. Las funciones HTTP síncronas usan las dependencias bloqueantes
existentes. La migración se ejecuta antes del servidor, no durante una consulta.

### Consequences

* Good, because el cliente web dispone de un contrato y errores explícitos.
* Good, because permite tests HTTP con rutas inyectadas y SQLite migrado.
* Bad, because suma dependencias de servidor y validación que hay que versionar.
* Bad, because el token de esta API local requiere configuración y no reemplaza
  la autenticación de usuarios, cuotas y HTTPS del despliegue público.

### Confirmation

Probar autorización, entradas inválidas, flujo completo, rollback, privacidad y
readiness sin migración. Ver [API](../docs/API.md). La numeración 008 está
reservada para la programación de ingesta de MVP-01, pendiente de integración.

## Pros and Cons of the Options

* **FastAPI:** contrato y documentación integrados; requiere ASGI y Pydantic.
* **Flask:** núcleo pequeño y conocido; exige más piezas para contrato y OpenAPI.
* **Django/DRF:** autenticación y administración completas; introduce más
  estructura y un ORM adicional frente a la persistencia existente.

## More Information

* [FastAPI: pruebas](https://fastapi.tiangolo.com/tutorial/testing/).
* [FastAPI: servidor](https://fastapi.tiangolo.com/deployment/manually/).
