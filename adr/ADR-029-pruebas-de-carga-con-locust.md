---
status: Propuesto
date: 2026-11-22
decision-makers: Equipo Nafta2Go
consulted: PRD (RNF01), ADR-010, issue 158
informed: Cátedra
---

# Pruebas de carga y estrés con Locust sobre un servidor aislado

## Context and Problem Statement

RNF01 pide p95 ≤ 5 s para consultas válidas. Las mediciones existentes son
secuenciales (120 consultas de a una en #124) o chicas (cinco por caso de uso con ORS
real en #142): no dicen cuántas consultas simultáneas soporta la API, dónde se satura
ni si el cupo de rutas sigue protegiendo la cuota de ORS bajo carga. Se necesita una
herramienta de carga y un entorno que no consuma la cuota diaria de 500 matrices.

## Decision Drivers

* Medir latencia por escalón de concurrencia y encontrar el punto de saturación.
* No consumir la cuota de ORS por defecto; tope explícito si se usan rutas reales.
* Escenarios versionados, revisables y reproducibles por cualquier integrante.
* Poder verificar después lo que quedó guardado (persistencia y auditoría).
* No agregar dependencias a la imagen ni al CI.

## Considered Options

* Locust (Python).
* k6 (JavaScript, binario en Go).
* Apache JMeter (Java, planes XML).
* Script propio con hilos y `requests`.

## Decision Outcome

Chosen option: "Locust", porque los escenarios se escriben en Python como el resto
del proyecto, reutilizan las consultas de `measure_query_latency` y la verificación
posterior (persistencia y `recommendation_audit`) corre en el mismo lenguaje. Los
escalones se definen con `LoadTestShape` y cada solicitud se registra para calcular
percentiles exactos por escalón.

Por defecto la prueba levanta la API real con uvicorn sobre una base temporal, el
escenario histórico y la matriz grabada de POC-05. El perfil `cupo` hace pasar esas
rutas por la caché y el cupo reales de ADR-010, sin reutilizar matrices, para medir
si bajo carga el cupo bloquea en vez de agotar la cuota. Con `--target` se apunta a
un despliegue existente: las rutas son reales y se exige `--max-requests`.

Locust va en `requirements-load.txt`, fuera de la imagen y del CI. La lógica de
perfiles y análisis vive en `scripts/load_profile.py`, que se prueba sin Locust.

### Consequences

* Good, because los escenarios, el análisis y la evidencia quedan versionados y se
  repiten con un comando.
* Good, because la prueba local no usa red ni cuota y verifica lo persistido.
* Bad, because Locust agrega dependencias propias (gevent, Flask) que hay que instalar
  aparte.
* Bad, because el generador corre en la misma máquina que el servidor y compite por
  CPU; los resultados locales son una cota, no la capacidad del despliegue.
* Bad, because las rutas grabadas excluyen la latencia real de ORS y la red del
  cliente.

### Confirmation

`tests/scripts/test_load_test.py` verifica perfiles, análisis por escalón, detección de
saturación, el bloqueo del cupo con la API real y el chequeo de persistencia, sin
Locust ni red. La evidencia de cada perfil está en `docs/evidencia/carga-2026-11-23/`.
Los perfiles `sostenida`, `estres` y `cupo` miden el escenario histórico sin
diagnóstico activo. El perfil `historico` mide el diagnóstico activo sobre una copia
de la base real, con veinte candidatas, y aborta si alguna respuesta no trae los
veinte diagnósticos. La medición en la `t3.small` de AWS queda pendiente.

## Pros and Cons of the Options

### Locust

* Good, because escenarios en Python, reutilizando código y datos del proyecto.
* Good, because `LoadTestShape` permite escalones y el evento de solicitud da acceso a
  cada medición.
* Bad, because un proceso de Locust tiene un techo de solicitudes por segundo menor que
  k6; alcanza para la escala de la demo.

### k6

* Good, because es muy eficiente y tiene umbrales declarativos (`thresholds`).
* Bad, because los escenarios van en JavaScript y la verificación de persistencia y
  auditoría quedaría en otro lenguaje.
* Bad, because suma un binario externo al entorno de desarrollo.

### Apache JMeter

* Good, because es maduro y tiene interfaz gráfica para armar planes.
* Bad, because los planes en XML son difíciles de revisar en una PR y requiere Java.

### Script propio con hilos

* Good, because no agrega dependencias.
* Bad, because habría que reimplementar escalones, control de concurrencia y
  estadísticas que Locust ya resuelve, con más riesgo de medir mal.
