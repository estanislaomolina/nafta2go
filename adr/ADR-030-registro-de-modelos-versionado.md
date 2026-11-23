---
status: Propuesto
date: 2026-11-23
decision-makers: Equipo Nafta2Go
consulted: ADR-014, ADR-021, issue 161
informed: Cátedra
---

# Registro de modelos versionado en el repositorio con alias de campeón

## Context and Problem Statement

Hasta ahora, `model.joblib`, los manifiestos, los reportes y las predicciones
quedaban en carpetas locales. Las versiones habilitadas para la política
`conservative-v1` estaban escritas en `domain/price_alert.py`, y por eso #150 tuvo que
agregar a mano el hash nuevo. No había un lugar único con las corridas, sus métricas,
su linaje y cuál es el campeón vigente. Se necesita un registro que permita promover o
revertir sin cambiar código, sin romper la regla de selección de ADR-014 ni habilitar
umbrales que no se auditaron.

## Decision Drivers

* Cada corrida con parámetros, métricas de selección y validación, linaje y hashes.
* Referencias y modelos en el mismo registro, con su naturaleza explícita.
* Alias `champion` y `challengers`; la promoción aplica ADR-014 y la política auditada.
* Revisable en una PR y reproducible sin servicios externos ni cuentas.
* Poco agregado para la escala del proyecto: un campeón que es una regla estadística y
  dos retadores que no se sirven.

## Considered Options

* Archivo JSON versionado en el repositorio con un comando para registrar y promover.
* MLflow (tracking y Model Registry con aliases, local con SQLite y carpeta de artefactos).
* DVC con almacenamiento remoto.
* Tabla propia en la base SQLite de la aplicación.
* Servicio externo (Weights & Biases).

## Decision Outcome

Chosen option: "Archivo JSON versionado", porque el registro queda en Git junto a la
evidencia que lo respalda, y cada promoción es un diff revisado en una PR con el CI en
verde. Esa misma traza es la que exige la cátedra. `nafta2go/ml/registry.json` guarda
las corridas, identificadas por el SHA-256 de su manifiesto, que es la versión que usa
el serving. También guarda las políticas auditadas, los alias y el inventario de lo que
no se conserva. `python -m nafta2go.ml.registry` registra, promueve y muestra:

* La promoción elige el menor MAE de selección y rechaza la corrida si el método elegido
  no coincide, si no conserva el reporte o si su política no corresponde al método.
* Un rechazo no modifica el archivo.
* `domain/price_alert.py` toma del registro las corridas habilitadas para
  `conservative-v1`, en lugar de tener los hashes escritos en el código.

Se importaron las corridas del 15/11, el 17/11 (la auditada y la corregida) y el 22/11,
solo con los archivos que existen. El campeón es `bandera_reciente` de la corrida del
22/11, y Ridge y boosting de esa corrida son retadores.

### Consequences

* Good, because promover o revertir es un cambio de datos revisable, sin tocar código.
* Good, because no agrega dependencias ni servicios, y la imagen ya incluye el registro.
* Bad, because `model.joblib` y las predicciones siguen fuera de Git: se registran sus
  hashes, pero el registro no los almacena ni los sirve.
* Bad, because el serving sigue cargando el manifiesto desde
  `NAFTA2GO_PRICE_MODEL_DIR`. El registro decide qué versiones son válidas, pero no
  descarga el artefacto.
* Bad, because no hay interfaz web ni comparación gráfica de corridas como en MLflow.

### Confirmation

`tests/ml/test_registry.py` verifica lo siguiente:

* los hashes de cada corrida contra sus archivos conservados;
* que el campeón sea el ganador de selección aunque boosting gane en validación;
* que el serving acepte exactamente las corridas auditadas;
* que una promoción incompatible se rechace sin cambiar el campeón.

## Pros and Cons of the Options

### Archivo JSON versionado

* Good, because es legible en una PR, no requiere servicios y viaja con el código.
* Bad, because la concurrencia de escritura se resuelve con Git, no con transacciones.

### MLflow

* Good, because es el estándar visto en la materia, con tracking, interfaz web, Model
  Registry y aliases nativos (`champion`).
* Bad, because agrega una dependencia pesada a la imagen y una base o un servidor más
  para operar.
* Bad, because el campeón no es un modelo serializable sino una regla estadística: habría
  que envolverla como `pyfunc` para registrarla.

### DVC con almacenamiento remoto

* Good, because versiona los artefactos grandes junto a Git y resuelve el faltante de
  `model.joblib`.
* Bad, because necesita un almacenamiento remoto con credenciales y no tiene alias de
  campeón; habría que sumarle un registro igual.

### Tabla propia en SQLite

* Good, because tiene transacciones y la aplicación ya usa la base.
* Bad, because los cambios de campeón quedan fuera de las PRs y de la historia de Git, y
  cada entorno tendría su propio registro.

### Weights & Biases

* Good, because tiene interfaz completa, registro de artefactos y aliases.
* Bad, because es un servicio externo con cuenta, y los datos y la disponibilidad
  quedan fuera del control del equipo.
