---
status: Propuesto
date: 2026-11-11
decision-makers: Equipo Nafta2Go
consulted: ADR-004, ADR-005, MVP-08
informed: Cátedra
---

# Base de red reproducible con CloudFormation

## Context and Problem Statement

El sandbox académico está aprobado, pero no se observaron VPCs en Ohio ni en
Virginia del Norte. Hay que versionar la red sin depender de una VPC predeterminada
ni consumir el presupuesto en recursos de aplicación antes de estimarlos.

## Decision Drivers

* Red revisable, reproducible y eliminable desde CloudShell con SSO.
* Presupuesto total de USD 17 y permisos administrados por la universidad.
* No introducir credenciales ni publicar servicios durante la preparación.

## Considered Options

* CloudFormation con plantilla JSON y estado administrado por AWS.
* Terraform con estado remoto y proveedor AWS.
* Comandos manuales de AWS CLI o consola.

## Decision Outcome

Proponer **CloudFormation** para la base de red de Ohio: VPC, subred, gateway,
ruta y grupo sin entrada. No agrega NAT, cómputo, discos ni direcciones públicas.
El formato JSON permite revisar la plantilla con herramientas estándar.
La elección de cómputo y persistencia se resolverá en otro incremento; este ADR
no resuelve la arquitectura completa del despliegue ni habilita gasto de servidor.

### Consequences

* Good, because el estado del stack y sus dependencias los administra AWS.
* Good, because no requiere credenciales permanentes ni backend de estado propio.
* Bad, because requiere permisos de CloudFormation además de los de EC2.
* Bad, because acopla la definición a AWS y la red propuesta usa una sola subred.

### Confirmation

Tests locales de invariantes de costo/exposición y topología. Validar con AWS y
crear/eliminar un stack de prueba quedan pendientes de ejecución por el titular;
ver [procedimiento y límites](../docs/AWS.md). El dry-run reportado solo confirmó
`CreateVpc`, no permisos para desplegar la plantilla completa.

## Pros and Cons of the Options

* **CloudFormation:** estado y rollback administrados; sintaxis específica de AWS.
* **Terraform:** ecosistema amplio y planes locales; suma instalación, proveedor y
  protección del estado, que puede contener datos sensibles.
* **CLI/consola:** acceso inmediato en CloudShell; exige implementar idempotencia,
  dependencias y eliminación, con mayor riesgo de diferencias no versionadas.

## More Information

* [Buenas prácticas de CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html).
