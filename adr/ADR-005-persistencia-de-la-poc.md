---
status: Aceptado
date: 2026-10-24
decision-makers: Equipo Nafta2Go
consulted: PRD (RF08, RNF03, RNF05, RNF07), ADR-001, ADR-004, issue POC-06
informed: Cátedra
---

# SQLite con SQLAlchemy y Alembic para la persistencia de la POC

## Context and Problem Statement

La POC tiene que conservar cada ejecución de ingesta, la referencia al archivo original, los precios normalizados, los rechazos con su motivo y el reporte de calidad. Además, cada recomendación tiene que poder vincularse con la versión de datos que usó (RNF05). El volumen de la POC es chico: unas 730 filas por captura del vigente y unas 80.000 del histórico de CABA. El sistema tiene que poder levantarse localmente de forma simple (RNF07) y las pruebas no deben depender de servicios externos.

Hay que elegir dónde y cómo guardar esos datos sin bloquear el camino al MVP, donde puede hacer falta un motor de base de datos con servidor.

## Decision Drivers

* Trazabilidad completa de cada ejecución, con integridad transaccional.
* Levantar el sistema y correr las pruebas sin infraestructura adicional.
* Esquema versionado y reproducible mediante migraciones.
* Posibilidad de pasar a un motor con servidor en el MVP sin reescribir la lógica.
* Volumen y concurrencia reales de la POC.

## Considered Options

* SQLite con SQLAlchemy (Core) y migraciones de Alembic.
* PostgreSQL (con PostGIS) desde la POC.
* Archivos Parquet versionados por ejecución, sin base de datos.

## Decision Outcome

Chosen option: **SQLite con SQLAlchemy y Alembic**, because cubre transacciones, claves foráneas y migraciones sin agregar un servicio que levantar ni en local ni en CI, y SQLAlchemy permite apuntar a PostgreSQL cambiando `DATABASE_URL` cuando el MVP lo justifique.

### Consequences

* Good, because el sistema y los tests funcionan con Python solo: cada test crea un SQLite temporal y corre las migraciones reales.
* Good, because las dos transacciones de la ingesta garantizan que una ejecución fallida no deje datos parciales ni aparezca como exitosa.
* Good, because el esquema queda versionado en `migrations/` y un test verifica que la migración coincide con el esquema declarado.
* Bad, because SQLite admite un solo escritor a la vez; alcanza para una ingesta programada, pero no para escrituras concurrentes del MVP.
* Bad, because no hay consultas geográficas nativas: la preselección de estaciones cercanas se calcula en Python, lo que es viable con menos de 200 estaciones en CABA.
* Bad, because pasar a PostgreSQL exige correr las migraciones contra ese motor y revisar tipos (JSON, Numeric) antes de darlo por compatible.

### Confirmation

La decisión se confirma con los tests de `tests/persistence` y `tests/services`, que migran la base, ingieren, fuerzan errores y verifican el rollback. Se revisa si el MVP necesita escrituras concurrentes, consultas geográficas en la base o despliegue con varias instancias: en ese caso se reemplaza por un ADR que adopte PostgreSQL.

## Pros and Cons of the Options

### SQLite con SQLAlchemy y Alembic

* Good, because no requiere servidor, credenciales ni contenedores para desarrollar o corregir.
* Good, because tiene transacciones ACID y claves foráneas (activadas explícitamente por conexión).
* Good, because SQLAlchemy y Alembic son los mismos que se usarían con PostgreSQL.
* Neutral, because el archivo de la base vive en `data/` y no se versiona.
* Bad, because un solo escritor y sin funciones geográficas.

### PostgreSQL (con PostGIS) desde la POC

* Good, because es el motor más probable para producción y resuelve concurrencia y consultas geográficas.
* Good, because evita una migración de motor más adelante.
* Bad, because obliga a levantar un contenedor para desarrollar, correr tests y corregir, y a gestionar credenciales.
* Bad, because agrega trabajo de infraestructura antes de validar el flujo principal, que es el objetivo de la POC.

### Archivos Parquet versionados por ejecución

* Good, because es simple, eficiente para lecturas analíticas y fácil de inspeccionar con pandas.
* Good, because cada ejecución queda como un conjunto de archivos inmutable.
* Bad, because no hay transacciones: una escritura cortada puede dejar archivos parciales que parecen válidos.
* Bad, because vincular recomendaciones con ejecuciones y consultar la última versión exitosa requiere reimplementar a mano lo que una base ya resuelve.

## More Information

* `docs/PERSISTENCIA.md`: esquema, ciclo de vida de una ejecución y contrato con la normalización (POC-01).
* `nafta2go/persistence/` y `nafta2go/services/ingestion.py`.
