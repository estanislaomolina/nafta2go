---
status: Propuesto
date: 2026-11-13
decision-makers: Equipo Nafta2Go
consulted: ADR-004, ADR-009, MVP-03
informed: Cátedra
---

# Web local con assets propios y API del mismo origen

## Context and Problem Statement

La API ya expone el recomendador. Falta una interfaz para consultar y entender
alternativas, errores y cobertura, sin duplicar el motor ni publicar servicios
antes de definir costos y autenticación de usuarios.

## Decision Drivers

* Formularios accesibles y resultados explicados en celular y escritorio.
* Reutilizar FastAPI y Docker, sin un servidor o build adicional en ejecución.
* No guardar código de acceso ni ubicaciones en almacenamiento del navegador.

## Considered Options

* HTML, CSS y JavaScript propios servidos por FastAPI.
* SPA con React/Vue y servidor o build independiente.
* Plantillas de servidor con formularios y sesiones.

## Decision Outcome

Proponer **assets propios** del mismo origen que la API. El navegador valida
entradas básicas y presenta la respuesta; las reglas, ranking y persistencia
siguen en aplicación/dominio. El código de acceso de la demo vive en memoria.
No es autenticación de usuarios ni habilita despliegue público.

### Consequences

* Good, because conserva un solo servicio e imagen, sin CDN ni librerías de UI.
* Good, because permite CSP sin scripts inline y peticiones solo al mismo origen.
* Bad, because exige probar explícitamente estados, foco y actualización del DOM.
* Bad, because el acceso de demo requiere un código compartido; no sustituye
  sesiones, HTTPS y permisos por usuario del despliegue futuro.

### Confirmation

Pruebas HTTP de página, headers y assets, más navegador con servidor aislado,
teclado y axe-core. Ver [WEB](../docs/WEB.md). Las rutas de QA son fixtures;
no se usan como evidencia de rutas reales ni de un teléfono físico.

## Pros and Cons of the Options

* **Assets propios:** menos piezas y mismo origen; más DOM y estado manuales.
* **React/Vue:** componentes y ecosistema de pruebas; suma build y dependencias.
* **Plantillas/sesiones:** lógica de presentación concentrada en servidor;
  exige otro contrato de formularios/sesión frente a la API ya construida.
