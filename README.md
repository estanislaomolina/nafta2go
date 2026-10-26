# Nafta2Go

Nafta2Go es un recomendador de estaciones de servicio para conductores de CABA. Combina precio publicado, presupuesto, autonomía, capacidad del tanque y desvío del recorrido para mostrar alternativas explicadas.

Este repositorio contiene el diseño de la **Entrega 1** y el desarrollo en curso de la **Entrega 2: POC y SRD** del Trabajo Práctico Integrador. El motor y el adaptador de rutas tienen pruebas automáticas; el flujo de punta a punta con datos y rutas reales se ejecuta desde un comando y conserva evidencia reproducible.

## Integrantes

Estanislao Molina Abeniacar

Felipe Sidiropulos

Santiago Bunge

## Accesos principales

- [PRD](docs/PRD.md): problema, usuarios, casos de uso, requisitos, criterios de éxito, supuestos y limitaciones.
- [Propuesta inicial](docs/Propuesta%20nafta2go.md): problema, solución de alto nivel, fuentes, viabilidad preliminar y alcance tentativo.
- [Notebook de exploración](notebooks/data_exploration.ipynb): descubrimiento de recursos oficiales, calidad, cobertura, histórico, riesgo de fechas, rutas y esfuerzo.
- [Roadmap](docs/ROADMAP.md): hitos, dependencias, orden de construcción y vínculo con GitHub Projects.
- [ADRs](adr/README.md): decisiones de diseño y comparación de alternativas.
- [SRD](docs/SRD.md): especificación técnica de la POC: arquitectura y diagramas, stack, modelo de datos, contratos y estrategia de datos.
- [Consulta completa de POC-05](docs/POC-05.md): ejecución, ranking, evidencia real y simplificaciones.
- [Proveedor de rutas](docs/RUTAS.md): adaptador de OpenRouteService, contrato, errores, límites y prueba autenticada (POC-03).
- [Motor determinístico](docs/MOTOR.md): fórmulas, contrato de integración, motivos de descarte y ejemplo ejecutable (POC-04).
- [Normalización de precios](docs/NORMALIZACION.md): formato real de las fechas, reglas de rechazo y alertas, duplicados y corrida real (POC-01).
- [Cobertura de precios](docs/COBERTURA.md): mínimo de cobertura en el corredor del recorrido, escenario histórico rotulado y reporte (POC-02).
- [Consigna del TP](res/%5BSHR%5D%5BS2%5D%20-%20Consigna%20TP%20I408.pdf): requisitos y formato de las entregas.
- [GitHub Project](https://github.com/users/estanislaomolina/projects/1): seguimiento operativo del roadmap.

## Evidencia y conclusión de viabilidad

La exploración del 18 de septiembre de 2026 utilizó el catálogo oficial de precios en surtidor de la Secretaría de Energía. Para el conjunto vigente se observaron 36.667 registros, 1.630 filas de CABA y 732 filas de nafta. Sólo 8 registros correspondientes a 2 estaciones tenían una antigüedad de hasta 30 días.

El histórico filtrado de nafta en CABA reunió 20.522 observaciones, 76 identificadores de estación y aproximadamente 142 meses de cobertura. Se detectaron 84 fechas posteriores a la ejecución, por lo que las reglas de normalización deben confirmarse antes de unir fuentes o entrenar modelos. En la POC se confirmó que esas fechas salían de leer el histórico con el mes primero: con el día primero coincide con `anio`/`mes` en el 99,99 % de las filas y queda una sola fecha futura real (ver [docs/NORMALIZACION.md](docs/NORMALIZACION.md)).

El proyecto es **viable con condiciones y/o recorte de alcance**. La POC debe validar fechas, cobertura y proveedor de rutas. Si no existe cobertura reciente suficiente, el sistema deberá informar la limitación o utilizar escenarios históricos claramente rotulados; nunca presentar precios antiguos como actuales.

## Reproducir la exploración

La notebook es la evidencia de la Entrega 1. Consulta recursos públicos y necesita conexión a Internet.

> **Aviso:** la notebook ya no se puede ejecutar completa. El DataStore (`datastore_search_sql`) de la Secretaría de Energía dejó de existir y el portal redirige HTTPS a HTTP. Los datos se obtienen ahora con el comando de ingesta de la POC, que descarga los CSV completos (ver [docs/NORMALIZACION.md](docs/NORMALIZACION.md)).

### Requisitos

- Python 3.10 o superior.
- JupyterLab o Jupyter Notebook.
- Conexión a Internet durante la ejecución.

### Instalación y ejecución

Desde la raíz del repositorio:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install jupyterlab pandas numpy requests matplotlib
jupyter lab
```

Luego abrir `notebooks/data_exploration.ipynb` y ejecutar todas las celdas en orden. La notebook descubre el recurso vigente desde el catálogo, descarga el CSV, consulta el histórico filtrado y muestra las tablas y gráficos usados para las conclusiones del PRD.

La ejecución puede tardar según la disponibilidad del catálogo oficial. Si se vuelve a ejecutar en otra fecha, los valores de cobertura y vigencia pueden cambiar; debe registrarse la fecha de ejecución y actualizarse la evidencia correspondiente.

## Decisiones de diseño

Los ADRs de la Entrega 1 documentan las alternativas evaluadas para:

- alcance en CABA y uso de datos actuales o históricos;
- recomendador determinístico y diagnóstico estadístico con ML separado;
- proveedor de rutas y alternativa OSRM;
- arquitectura modular por capas.

## Desarrollo local

Requiere Python 3.12. Desde la raíz del repositorio:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
alembic upgrade head
pytest -v --strict-markers --cov=nafta2go --cov-report=term-missing --cov-precision=2 --cov-fail-under=90
ruff check . && ruff format --check .
```

`alembic upgrade head` crea la base local (SQLite en `data/`); ver [docs/PERSISTENCIA.md](docs/PERSISTENCIA.md). Para cargar precios reales: `python -m nafta2go.normalization --source vigente` (ver [docs/NORMALIZACION.md](docs/NORMALIZACION.md)).

Los tests y controles de estilo coinciden con los de integración continua. Los tests de persistencia verifican las migraciones en bases temporales. El detalle de cada check, cuáles bloquean el merge y cómo se manejan las credenciales está en [docs/CALIDAD.md](docs/CALIDAD.md).

## Levantar con Docker

Requiere Docker con Compose v2. Desde la raíz del repositorio:

```bash
docker compose up --build
```

Construye la imagen de la aplicación y corre las migraciones sobre una base SQLite guardada en el volumen `nafta2go-data`. El contenedor `migrate` termina cuando el esquema queda actualizado. Para borrar la base: `docker compose down --volumes`. La consulta completa se ejecuta con `docker compose run --rm query`; ver [POC-05](docs/POC-05.md). La interfaz web y la API corresponden al MVP.

## Estado del desarrollo

La Entrega 2 (POC) está en curso. Esta tabla declara qué partes existen, cuáles están simuladas y cuáles faltan; se actualiza en la misma PR que cambia el estado de un componente.

| Componente | Tarea | Estado |
|---|---|---|
| Integración continua: links, lint, tests y secretos | POC-07 | Implementado |
| Normalización de precios | POC-01 | Implementado: descarga verificada, reglas con rechazos y alertas, y corrida real documentada en docs/NORMALIZACION.md |
| Cobertura de precios y escenario histórico | POC-02 | Implementado: mínimo de 3 estaciones recientes en el corredor, escenario congelado del 24/10 rotulado como histórico y reporte en docs/COBERTURA.md |
| Persistencia e ingesta mínimas | POC-06 | Implementado: esquema, migraciones e ingesta trazable, conectada a la normalización de POC-01 |
| Proveedor de rutas | POC-03 | Implementado, con prueba autenticada registrada en docs/evidencia/ |
| Motor determinístico | POC-04 | Implementado y probado; PR #26 integrado |
| Flujo de punta a punta | POC-05 | Implementado: consulta explicada, ranking, rutas reales guardadas y registro trazable; ver docs/POC-05.md |
| Levantar el sistema completo con contenedores | POC-07 | Implementado para la POC: migraciones y comando de consulta, con reproducción completa en CI |
| Diagnóstico estadístico con ML | MVP | Fuera del alcance de la POC |

## Consulta completa con datos reales (POC-05)

Después de instalar las dependencias, se puede reproducir el caso sin red ni clave:

```bash
DATABASE_URL=sqlite:////tmp/nafta2go-demo-entrega2.db python -m nafta2go.query \
  --origin=-34.6037,-58.3816 --destination=-34.5627,-58.4565 \
  --matrix-file docs/evidencia/poc-05-flujo-2026-10-26/matrix.json
```

Con una base nueva utiliza el escenario histórico rotulado del 24/10/2026 y las
rutas reales guardadas el 26/10. Para usar precios de la última ingesta y ORS en
vivo, ver [instrucciones y evidencia de POC-05](docs/POC-05.md).

## Proveedor de rutas (POC-03)

El adaptador de OpenRouteService y su prueba autenticada están documentados en [docs/RUTAS.md](docs/RUTAS.md). Para correrlos:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
pytest -v
cp .env.example .env   # completar ORS_API_KEY
python scripts/probe_openrouteservice.py
```

Los tests no usan red: reemplazan la API por una sesión HTTP simulada. Solo la prueba autenticada consulta OpenRouteService y necesita la API key.

## Video de la entrega

Pendiente de completar:

> **Video:** [Nafta2Go — Entrega 1: Diseño, PRD y Roadmap](https://youtu.be/zZpi70Od-EE)

## Entrega

- **Rama:** `main`
- **Repositorio:** https://github.com/estanislaomolina/nafta2go
- **Project:** https://github.com/users/estanislaomolina/projects/1
