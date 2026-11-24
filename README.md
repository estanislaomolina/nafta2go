# Nafta2Go

Nafta2Go es un recomendador de estaciones de servicio para conductores de CABA. Combina precio publicado, presupuesto, autonomía, capacidad del tanque y desvío del recorrido para mostrar alternativas explicadas.

Este repositorio contiene el diseño de la **Entrega 1**, la **Entrega 2: POC y SRD** y el **MVP de la Entrega 3** del Trabajo Práctico Integrador: ingesta programada, API HTTP, aplicación web, panel de operación y diagnóstico de precios con ML evaluado offline. Todo corre localmente con Python o Docker. La web está publicada en [GitHub Pages](https://estanislaomolina.github.io/nafta2go/) y la API en [AWS por HTTPS](https://nafta2go.18.216.94.147.sslip.io/), con despliegue OIDC por digest y [Grafana autenticado](https://nafta2go.18.216.94.147.sslip.io/grafana/). Lo que está simulado o recortado se lista en [Partes simuladas, simplificadas o pendientes](#partes-simuladas-simplificadas-o-pendientes).

## Entrega 3 — MVP publicado

- **Sitio web:** [https://estanislaomolina.github.io/nafta2go/](https://estanislaomolina.github.io/nafta2go/).
- **Video de Entrega 3:** [Demostración del MVP — 7 min 26 s](https://youtu.be/Y3cV71ZnxuY).
- **Versión de entrega:** [entrega-3-mvp](https://github.com/estanislaomolina/nafta2go/tree/entrega-3-mvp), tag anotado del commit final de `main`.
- **Documentación de entrega:** [alcance, reproducibilidad y límites](docs/ENTREGA-3.md).
- [Panel de operación](https://estanislaomolina.github.io/nafta2go/operacion/): requiere el código administrativo.
- [API HTTPS](https://nafta2go.18.216.94.147.sslip.io/), [salud](https://nafta2go.18.216.94.147.sslip.io/health) y [readiness](https://nafta2go.18.216.94.147.sslip.io/ready).
- [Grafana](https://nafta2go.18.216.94.147.sslip.io/grafana/): dashboards de [negocio](https://nafta2go.18.216.94.147.sslip.io/grafana/d/nafta2go-business) y [funcionamiento](https://nafta2go.18.216.94.147.sslip.io/grafana/d/nafta2go-operations).
- [CI y despliegues](https://github.com/estanislaomolina/nafta2go/actions).
- [Evidencia operativa y límites](docs/evidencia/operacion-continua-2026-11-23/README.md), [guion para grabar](docs/GUION-DEMO.md) y [cierre de la entrega](https://github.com/estanislaomolina/nafta2go/issues/24).

**Acceso a Grafana:** usuario `admin`. El equipo autorizado obtiene la contraseña
del parámetro **SecureString** `/nafta2go/demo/grafana-admin` en AWS Systems Manager
Parameter Store, región `us-east-2`. La contraseña y los códigos de acceso no se
publican en el repositorio. El login de Grafana es independiente del código del
conductor y del código administrativo de la aplicación.

Pages aloja la web estática; API y Grafana dependen de la EC2 y del presupuesto.
La adquisición automática requiere el equipo del runner encendido y conectado;
ver [operación y presupuesto](docs/HOSTING.md).

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
- [SRD](docs/SRD.md): especificación técnica de POC y MVP: arquitectura y diagramas, stack, modelo de datos, contratos y estrategia de datos.
- [Consulta completa de POC-05](docs/POC-05.md): ejecución, ranking, evidencia real y simplificaciones.
- [Ingesta diaria y monitor](docs/INGESTA.md): unidades systemd, alertas locales y evidencia de fallos/recuperación; [canal AWS automático y límites comprobados](docs/evidencia/operacion-continua-2026-11-23/README.md) (MVP-01).
- [Preparación AWS](docs/AWS.md): acceso del sandbox, plantilla de red, validación y límites.
- [Servidor de demo AWS](docs/AWS-DEMO.md): operación actual en `t3.small`, historial de la primera demo, entrega por SSM y respaldo de la base.
- [Hosting continuo](docs/HOSTING.md): web en GitHub Pages y API/Grafana por HTTPS en EC2 con guardia de presupuesto (ADR-032); [evidencia operativa](docs/evidencia/operacion-continua-2026-11-23/README.md).
- [Proveedor de rutas](docs/RUTAS.md): adaptador de OpenRouteService, contrato, errores, límites y prueba autenticada (POC-03).
- [Motor determinístico](docs/MOTOR.md): fórmulas, contrato de integración, motivos de descarte y ejemplo ejecutable (POC-04).
- [Enlaces de Google Maps](docs/MAPS.md): navegación por alternativa en API/CLI/web; pruebas en navegador y móvil emulado; no se acredita una prueba física específica de navegación externa.
- [Validación integral](docs/VALIDACION.md): matriz de requisitos y evidencia, latencia de la API y auditoría de trazabilidad, frescura y privacidad (MVP-09).
- [Guion de demo](docs/GUION-DEMO.md): recorrido del video de la Entrega 3, con lo que se muestra y las limitaciones que se dicen en cada bloque.
- [Validación conjunta local](docs/INTEGRACION.md): pruebas de ingesta, caché, API, web y Docker, complementadas por evidencia desplegada de MVP-09.
- [Aplicación web local](docs/WEB.md): formulario y resultados explicados sobre la API y panel local `/operacion`, con acceso por código.
- [API local](docs/API.md): consulta HTTP autenticada, OpenAPI, validaciones, errores y ejecución con Python o Docker (incremento de MVP-02).
- [Normalización de precios](docs/NORMALIZACION.md): formato real de las fechas, reglas de rechazo y alertas, duplicados y corrida real (POC-01).
- [Cobertura de precios](docs/COBERTURA.md): mínimo de cobertura en el corredor del recorrido, escenario histórico rotulado y reporte (POC-02).
- [ML de precios](docs/ML.md): preparación temporal, comparación de modelos, umbrales candidatos y estimación de precios antiguos (MVP-04 y MVP-05).
- [Calidad y CI](docs/CALIDAD.md): checks requeridos, protección de ramas, revisión cruzada y manejo de credenciales.
- [Consigna del TP](res/%5BSHR%5D%5BS2%5D%20-%20Consigna%20TP%20I408.pdf): requisitos y formato de las entregas.
- [GitHub Project](https://github.com/users/estanislaomolina/projects/1): seguimiento operativo del roadmap.

## Evidencia y conclusión de viabilidad de la Entrega 1

La exploración del 18 de septiembre de 2026 utilizó el catálogo oficial de precios en surtidor de la Secretaría de Energía. Para el conjunto vigente se observaron 36.667 registros, 1.630 filas de CABA y 732 filas de nafta. Sólo 8 registros correspondientes a 2 estaciones tenían una antigüedad de hasta 30 días.

El histórico filtrado de nafta en CABA reunió 20.522 observaciones, 76 identificadores de estación y aproximadamente 142 meses de cobertura. Se detectaron 84 fechas posteriores a la ejecución, por lo que las reglas de normalización deben confirmarse antes de unir fuentes o entrenar modelos. En la POC se confirmó que esas fechas salían de leer el histórico con el mes primero: con el día primero coincide con `anio`/`mes` en el 99,99 % de las filas y queda una sola fecha futura real (ver [docs/NORMALIZACION.md](docs/NORMALIZACION.md)).

La exploración concluyó que el proyecto era **viable con condiciones y/o recorte de alcance**. La POC debía validar fechas, cobertura y proveedor de rutas; sus verificaciones y el cierre MVP están vinculados en las secciones de entrega. Si no existe cobertura reciente suficiente, el sistema deberá informar la limitación o utilizar escenarios históricos claramente rotulados; nunca presentar precios antiguos como actuales.

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

Cada decisión estructural tiene un ADR con alternativas comparadas; el índice está en [adr/README.md](adr/README.md):

- **Entrega 1:** alcance en CABA, recomendador determinístico con diagnóstico ML separado, proveedor de rutas y arquitectura por capas (ADR-001 a ADR-004).
- **Entrega 2:** persistencia, escenario histórico y trazabilidad de recomendaciones (ADR-005 a ADR-007).
- **Entrega 3:**
  - ingesta programada, API, caché de rutas, web y acceso administrativo;
  - AWS: red y servidor de demo;
  - ML: evaluación y selección de modelos, referencia servida, umbrales y estimación de precios antiguos;
  - ranking conservador, búsqueda de direcciones, validación técnica y entrega por SSM;
  - imagen verificada en el CI y entregada por digest, despliegue con OIDC,
    observabilidad con Prometheus y Grafana, web en Pages y API HTTPS con Caddy/sslip.io, pruebas
    de carga con Locust, registro de modelos con alias de campeón y transferencia
    verificada de capturas.

  Abarca de ADR-008 a ADR-032.

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

Construye la imagen de la aplicación y corre las migraciones sobre una base SQLite guardada en el volumen `nafta2go-data`. El contenedor `migrate` termina cuando el esquema queda actualizado. Para borrar la base: `docker compose down --volumes`. La consulta completa se ejecuta con `docker compose run --rm query`; ver [POC-05](docs/POC-05.md). Para iniciar la API local, configurar el token y usar `docker compose --profile mvp up --build api`; ver [API](docs/API.md). La pantalla local se abre en `http://127.0.0.1:8000/`; ver [WEB](docs/WEB.md). La primera demo AWS se probó por túnel SSM; ver [servidor de demo](docs/AWS-DEMO.md) para acceso, costos e historial de la primera captura. La operación actual usa [Pages](https://estanislaomolina.github.io/nafta2go/) y [API HTTPS](https://nafta2go.18.216.94.147.sslip.io/), según [HOSTING](docs/HOSTING.md).

## Estado del desarrollo

La Entrega 2 (POC) incluye el flujo completo y su video de demostración; la Entrega 3 suma el MVP. Esta tabla declara qué partes existen, cuáles están simuladas y cuáles faltan; se actualiza en la misma PR que cambia el estado de un componente.

| Componente | Tarea | Estado |
|---|---|---|
| Integración continua: links, lint, tests y secretos | POC-07 | Implementado |
| Aplicación web local | MVP-03 | Formulario y resultados explicados con acceso de demo; flujos de teclado y navegador automatizados; prueba física de iPhone 13 informada por el dueño; otros navegadores y lector de pantalla sin acreditar; ver docs/WEB.md |
| API del recomendador | MVP-02 | Implementada localmente con token, caché por proceso y tests HTTP; despliegue público por HTTPS comprobado; ver docs/API.md |
| Normalización de precios | POC-01 | Implementado: descarga verificada, reglas con rechazos y alertas, y corrida real documentada en docs/NORMALIZACION.md |
| Cobertura de precios y escenario histórico | POC-02 | Implementado: mínimo de 3 estaciones recientes en el corredor, escenario congelado del 24/10 rotulado como histórico y reporte en docs/COBERTURA.md |
| Persistencia e ingesta mínimas | POC-06 | Implementado: esquema, migraciones e ingesta trazable, conectada a la normalización de POC-01 |
| Proveedor de rutas | POC-03 | Implementado, con prueba autenticada registrada en docs/evidencia/ |
| Caché y cupo de rutas | MVP-02 (#55) | Matrices en RAM con TTL y LRU, límites por proceso y credencial, y métricas sin ubicaciones; ver docs/RUTAS.md |
| Motor determinístico | POC-04 | Implementado y probado; PR #26 integrado |
| Flujo de punta a punta | POC-05 | Implementado: consulta explicada, ranking, rutas reales guardadas y registro trazable; ver docs/POC-05.md |
| Levantar el sistema completo con contenedores | POC-07, MVP-08 | Implementado: migraciones, consulta y API con web (perfil `mvp`); el CI construye una imagen, migra y consulta sin red; publica por digest tras aprobar los checks; el primer digest se publicó el 23/11 y el paquete de GHCR es público |
| Entrenamiento y selección de modelos | MVP-04 | Implementado offline y reproducible; el método elegido es una referencia (mediana de la bandera), no un modelo; ver docs/ML.md |
| Registro de modelos | MVP-04 (#161) | Implementado: registro versionado con alias de campeón; la API sirve sólo el campeón y la política exige una auditoría verificada (ADR-030); ver docs/ML.md |
| Pruebas de carga | MVP-09 (#158) | Locust local (ADR-029): sin diagnóstico activo, p95 ≤ 5 s hasta 40 usuarios simultáneos; con diagnóstico sobre histórico real y veinte candidatas, sólo hasta 2. Cupo y persistencia verificados bajo carga; medición en `t3.small` con veinte diagnósticos y saturación documentada desde dos usuarios; ver docs/VALIDACION.md |
| Diagnóstico estadístico servido | MVP-05 (#19) | Implementado: la API y la web sirven la referencia elegida y una alerta provisional `conservative-v1` solo para las selecciones auditadas (ADR-021). No tiene precisión medida para detectar errores reales; ver docs/API.md |
| Ranking conservador | MVP-06 (#20) | Implementado como comparación separada que excluye excedencias de `conservative-v1`, sin cambiar el ranking general ni el precio oficial (ADR-021); ver docs/WEB.md |
| Estimación de precios de 31 a 120 días | #117 | Implementada en API y web, rotulada y fuera del ranking (ADR-020) |
| Operación y acceso administrativo | MVP-07 | Panel `/operacion`, estado de ingestas y métricas de consultas/rutas/diagnóstico, con token administrativo separado (ADR-016), Prometheus/Grafana y cAdvisor; sin SLA de supervisión 24/7 |
| Despliegue en AWS | MVP-08 (#22) | Pages y API HTTPS publicados; despliegue OIDC desde CI, smoke y rollback real comprobados; ver docs/HOSTING.md |
| Recomendador completo | MVP-02 | CLI, caso de uso y API admiten hasta veinte candidatas (diez por defecto); ver docs/MOTOR.md |

### Partes simuladas, simplificadas o pendientes

- **Rutas en pruebas y en CI:** se reemplaza OpenRouteService por respuestas simuladas o por la matriz real guardada en POC-05. Sólo la prueba autenticada y el uso en vivo consultan la API real.
- **Escenario histórico:** cuando no hay cobertura reciente se usa la captura congelada del 24/10/2026, rotulada como histórica.
- **Acceso:** tokens de demo por variable de entorno (conductor y administración); no hay cuentas de usuario.
- **Base y caché:** SQLite local y caché de rutas en memoria por proceso, sin coordinación entre réplicas.
- **Diagnóstico ML:** sirve una referencia estadística (mediana de la bandera) con alertas provisionales cuya precisión no se midió. Los modelos aprendidos solo se evalúan offline. En la demo de AWS el diagnóstico queda no disponible si falta el histórico.
- **Demo AWS:** una sola instancia, operación continua autorizada y guardia de presupuesto; detener cómputo no elimina cargos de discos/IP. Ver docs/HOSTING.md.
- **Límites de validación y operación:** no se acredita un SLA 24/7 del productor de capturas, utilidad con participantes, otros navegadores ni lector de pantalla. La prueba física de iPhone 13 con ubicación manual fue informada por el titular. El recorte técnico está registrado en ADR-023.

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

## Videos de las entregas

- **Entrega 3 — MVP:** [Demostración del MVP](https://youtu.be/Y3cV71ZnxuY) (7 min 26 s).
- **Entrega 2 — POC y SRD:** [Demostración funcional de Nafta2Go](https://youtu.be/3hBFj-BQNzA) (9 min 57 s).
- **Entrega 1 — Diseño:** [PRD y Roadmap](https://youtu.be/zZpi70Od-EE).

El video de Entrega 2 muestra la prueba de concepto y el diseño técnico. El video
de Entrega 1 corresponde al problema, la exploración inicial y la planificación.
Las fechas y simplificaciones del caso reproducible se detallan en
[POC-05](docs/POC-05.md).

## Entrega 2

- **Rama de entrega:** `main`, integrada desde `dev` mediante PR.
- **Versión:** [entrega-2-poc](https://github.com/estanislaomolina/nafta2go/tree/entrega-2-poc), tag anotado del commit entregado.
- **Video:** [POC y SRD](https://youtu.be/3hBFj-BQNzA).
- **Diseño técnico:** [SRD](docs/SRD.md) y [ADRs](adr/README.md).
- **Ejecución y evidencia:** [Consulta completa de POC-05](docs/POC-05.md).
- **Repositorio:** https://github.com/estanislaomolina/nafta2go
- **Project:** https://github.com/users/estanislaomolina/projects/1

El repositorio se mantiene público por autorización de la cátedra, confirmada
por el equipo al cerrar esta entrega. La presentación se identifica con el
commit específico de `main` y la URL del video.

La observabilidad opcional de Prometheus/Grafana se levanta con la
[guía de dashboards](docs/OBSERVABILIDAD.md); sus métricas de negocio son
recomendaciones y estimaciones, no compras confirmadas.
La [web en Pages](https://estanislaomolina.github.io/nafta2go/) usa la API HTTPS
gratuita de sslip.io según [ADR-032](adr/ADR-032-pages-y-api-publica-con-presupuesto.md).
Cloudflare queda como alternativa histórica. Geolocalización depende de permisos
y dispositivo; la prueba física previa en iPhone 13 se conserva como evidencia
del alcance informado por el dueño, sin inventar navegador o sistema operativo.
