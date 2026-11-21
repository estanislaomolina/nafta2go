# Validación integral del MVP (MVP-09)

Matriz de trazabilidad entre los requisitos del [PRD](PRD.md) y su evidencia, con las
mediciones del 18/11/2026 sobre `dev` (`98d46a2` más los commits de esta rama). Cada
fila indica qué la respalda y qué falta. No reemplaza a [INTEGRACION](INTEGRACION.md),
que describe la prueba entre componentes.

Estados: **Cumple** (prueba automatizada o medición que alcanza el criterio),
**Parcial** (cubierto en parte; se indica qué falta) y **Pendiente** (sin evidencia).

## Mediciones del 18/11/2026

Todas se reproducen sin red ni credenciales, desde un árbol limpio:

```bash
python scripts/measure_query_latency.py --requests 120 --output latencia.json
DATABASE_URL=sqlite:///ruta/a/la/base.db python -m nafta2go.audit
```

**Rendimiento (RNF01).** 120 consultas UC01 válidas contra la API HTTP en el mismo
proceso, que pasan por autenticación, validación, lectura de precios, motor,
guardado y telemetría. ORS se reemplaza por la matriz real capturada en POC-05. Dos
corridas, en Linux x86_64 con Python 3.12.3 y el código `ed5540d` (tag
`evidencia/validacion-2026-11-18`):

| Corrida | Respuestas | p50 | p95 | Máximo |
|---|---|---|---|---|
| [1](evidencia/validacion-2026-11-18/latencia-api-1.json) | 120 × 200 | 26,6 ms | 38,7 ms | 78,0 ms |
| [2](evidencia/validacion-2026-11-18/latencia-api-2.json) | 120 × 200 | 28,2 ms | 39,9 ms | 73,1 ms |

La matriz de ORS se midió aparte: p95 1,24 s en 5 llamadas de 22 ubicaciones
([RUTAS](RUTAS.md#límites-y-latencia)). Sumando el peor p95 de cada parte, la
consulta completa quedaría cerca de **1,28 s**, debajo del objetivo de 5 s. Es una
**estimación compuesta**, no una medición de punta a punta: la muestra de ORS es
chica, no incluye la red del cliente y UC02 (sin destino) no tiene matriz guardada.
El lote real UC01/UC02 del 21/11 se registra al final; la composición anterior
se conserva como medición histórica separada.

**Trazabilidad, frescura y privacidad.** `python -m nafta2go.audit` revisa lo que
quedó guardado en `recommendations`, no lo que el código intentó guardar:

- *Trazabilidad:* un único origen (ingesta exitosa o escenario con ID, fecha y
  hashes), el mismo origen en las columnas y en el resultado, motor y proveedor
  coherentes, vigencia guardada entre 1 y 30 días, fila de origen en cada precio y
  hash de la matriz reproducida. Una fila sin los campos esperados falla con su id
  sin cortar la auditoría.
- *Frescura:* cada precio evaluado está dentro de la vigencia de su consulta respecto
  de la fecha de referencia de precios. Una vigencia guardada mayor a 30 días no la
  amplía.
- *Privacidad:* ninguna clave de ubicación (origen, destino, `lat`, `lon` y similares),
  ningún par de números dentro de CABA, en lista o en texto, ni enlaces de mapas en la
  consulta, el resultado o el escenario.

Sobre las 123 recomendaciones guardadas en cada medición (120 más 3 de
calentamiento, todas del escenario histórico): trazabilidad 123/123, frescura
1.230/1.230 precios evaluados y privacidad 123/123. La prueba integral
(`tests/integration/test_local_mvp.py`) audita además tres recomendaciones de
ingestas vigentes hechas por HTTP, con 100 % en los tres criterios. Todas son
recomendaciones generadas para la validación: la auditoría todavía no corrió sobre la
base de un despliegue real (#22). Los resultados se midieron con
`recommendation-audit-v1`; con la versión 2 (#126), que suma los controles de arriba,
una corrida nueva de 120 consultas dio los mismos 123/123, 1.230/1.230 y 123/123.

## Requisitos funcionales

| ID | Estado | Evidencia | Falta |
|---|---|---|---|
| RF01 Validar la consulta | Cumple | `tests/presentation/test_http.py` (422 sin repetir valores), `tests/test_query_cli.py`, `tests/test_engine.py` | — |
| RF02 CABA y nafta compatible | Cumple | `tests/application/test_stored_query.py`, `tests/normalization/test_validation.py` | — |
| RF03 Hasta veinte candidatas | Cumple | `tests/integration/test_local_mvp.py` (más de diez y hasta veinte por HTTP), `tests/presentation/test_http.py` | — |
| RF04 Cálculos determinísticos | Cumple | `tests/test_engine.py`, `tests/test_engine_precision.py`, reproducción exacta en [POC-05](POC-05.md) | — |
| RF05 Descartes con motivo | Cumple | `tests/test_engine.py`, recorrido UC06 en `tests/browser/web.test.cjs` | — |
| RF06 Tres alternativas | Cumple | `tests/test_ranking.py`, `tests/application/test_recommendation.py` | — |
| RF07 Explicar cada resultado | Cumple | `tests/application/test_query.py`, `tests/browser/web.test.cjs`, [WEB](WEB.md) | Prueba de comprensión con usuarios (ver criterios) |
| RF08 Ingesta diaria | Cumple | `tests/services/test_ingestion.py`, `tests/normalization/`, [INGESTA](INGESTA.md), [ADR-008](../adr/ADR-008-programacion-de-ingesta.md) | Operación continua: ver criterio de ingesta |
| RF09 Vigencia configurable | Cumple | `tests/application/test_coverage_rules.py`, frescura 100 % en la auditoría de las recomendaciones generadas en la medición y la prueba integral | — |
| RF10 Diagnóstico del precio | Parcial | `tests/presentation/test_price_diagnostic.py`, [ADR-015](../adr/ADR-015-referencia-servida-y-abstencion-de-alertas.md) | Sirve la referencia y su versión, pero Regla provisional de [ADR-021](../adr/ADR-021-ranking-conservador-por-desvio.md); tests de fronteras y selección versionada (#140), pendiente de integrar |
| RF11 Ranking conservador | Parcial | API/web y tests integrados de la comparación en #141 | Integrar #140/#141 con revisión; regla provisional sin precisión/sensibilidad medidas |
| RF12 Autenticación administrativa | Cumple | `tests/presentation/test_ingestion_status.py`, `tests/presentation/test_http.py`, [ADR-016](../adr/ADR-016-acceso-administrativo-separado.md) | — |
| RF13 Configuración sin código | Parcial | Vigencia por variable de entorno (#96), parámetros de caché y cupo en Compose | No hay auditoría de cambios de configuración |
| RF14 Estado operativo | Cumple | Panel `/operacion`, métricas de ingesta/consultas/rutas/diagnóstico, `tests/presentation/test_price_diagnostic.py` y prueba móvil del panel | — |
| RF15 Escenarios históricos | Cumple | `tests/application/test_scenario.py`, rótulo `historical_scenario` en las respuestas | — |

## Requisitos no funcionales

| ID | Estado | Evidencia | Falta |
|---|---|---|---|
| RNF01 Rendimiento | Parcial | Medición en proceso y composición con ORS (arriba) | Ampliar muestra y medir red del cliente/despliegue; ver lote real del 21/11 |
| RNF02 Disponibilidad | Cumple | `tests/adapters/test_openrouteservice.py` (401/403/429/5xx, timeout, matriz inválida) | — |
| RNF03 Privacidad | Cumple | Auditoría 100 % sobre las recomendaciones generadas en la medición y la prueba integral, `tests/integration/test_local_mvp.py`, `tests/presentation/test_telemetry.py` | Auditar la base del despliegue (#22) |
| RNF04 Seguridad | Cumple | Check Secretos del CI, pruebas de acceso administrativo, [CALIDAD](CALIDAD.md) | — |
| RNF05 Trazabilidad | Cumple | Auditoría 100 % sobre las recomendaciones generadas en la medición y la prueba integral, restricción `ck_recommendations_data_origin`, `tests/persistence/test_repository.py` | Auditar la base del despliegue (#22) |
| RNF06 Calidad | Cumple | Cobertura 98 %, seis checks requeridos en `main` y `dev` (#121) | — |
| RNF07 Portabilidad | Cumple | Check Contenedores (build, migración y consulta sin red), README | Readiness del despliegue en AWS (#22) |
| RNF08 Observabilidad | Parcial | Eventos JSON de API y CLI (`tests/test_query_telemetry.py`), monitor de ingesta | Supervisión continua fuera de la máquina local |
| RNF09 Accesibilidad | Parcial | Teclado y axe en `tests/browser/web.test.cjs`, [WEB](WEB.md) | Teléfono físico, otros navegadores y lector de pantalla |
| RNF10 Reproducibilidad ML | Cumple | Corridas idénticas en [ML](ML.md) y en la evidencia de ADR-014, #118 y #120 | — |

## Criterios de éxito del PRD

| Dimensión | Objetivo | Resultado | Estado |
|---|---|---|---|
| Utilidad | ≥ 80 % elige y explica una opción, con ≥ 10 conductores | Sin participantes; diez casos técnicos por decisión de alcance (ADR-023) | No acreditado: recorte |
| Comprensión | ≥ 80 % interpreta precio, desvío y combustible neto | Sin participantes; diez casos técnicos por decisión de alcance (ADR-023) | No acreditado: recorte |
| Factibilidad | 100 % de recomendaciones respeta las restricciones | Suite del motor y del ranking, sin fallas | Cumple |
| Explicabilidad | 100 % de resultados y descartes con motivo trazable | Pruebas de contrato del motor y de la API | Cumple |
| Rendimiento | p95 ≤ 5 s | ≈ 1,28 s estimado por composición | Parcial |
| Ingesta | ≥ 95 % completada o alertada en 24 h | 3 de 3 corridas observadas (2 fallas alertadas en segundos y 1 recuperación), en [la evidencia del 12/11](evidencia/mvp-01-operacion-2026-11-12.json) | Parcial: muestra chica, sin operación continua |
| Frescura | 100 % de precios dentro del umbral | 1.230 de 1.230 en la auditoría de la medición | Cumple |
| ML | Mejora material o adopción explícita del modelo simple | Se adoptó una referencia simple con protocolo previo ([ADR-014](../adr/ADR-014-seleccion-de-modelo-de-precios.md)) | Cumple |
| Privacidad | 100 % sin ubicación persistida | 123 de 123 en la auditoría de la medición, más la prueba integral | Cumple |

## Recortes e incumplimientos

- **Utilidad y comprensión:** se reemplazó el estudio por simulación técnica por
  decisión del 21/11 ([ADR-023](../adr/ADR-023-validacion-tecnica-sin-participantes.md)).
  No hay participantes ni métricas humanas; esos objetivos no están acreditados.
- **Ranking conservador (RF11):** implementación API/web en #141, dependiente de
  #140 y pendiente de integrar. La regla provisional no mide sensibilidad ni precisión.
- **Rendimiento:** el lote del 21/11 incluye ORS real, pero sólo cinco solicitudes
  por caso de uso y HTTP en proceso. Falta medir la red del cliente y el despliegue.
- **Accesibilidad y operación:** faltan la verificación en un teléfono físico y la
  supervisión continua de la ingesta fuera de la máquina local.


## Diez escenarios técnicos — 21/11/2026

La actividad de utilidad/comprensión se recorta según ADR-023. No se simulan
participantes: `real_participants=0`. El ejecutable comprueba cinco casos UC01 y
cinco UC02, con diferentes productos, horarios, consumos, presupuestos y límites
de candidatas; incluye presupuesto nulo. Audita las recomendaciones guardadas en
una base temporal. El histórico mantiene su fecha y rótulo; no altera la ingesta.

```bash
python scripts/validate_simulated_scenarios.py --output simulacion.json
# Opcional: requiere ORS_API_KEY y consume hasta diez matrices reales.
python scripts/validate_simulated_scenarios.py --live-routes --output rutas-reales.json
```

La primera modalidad usa distancias sintéticas constantes; la segunda mide la
API en proceso con ORS real. Ninguna mide comprensión, utilidad, red del cliente,
tráfico o un teléfono físico. El ranking conservador se abstiene en este histórico;
la integración con publicaciones vigentes se comprueba en los tests de #141.


Resultados con código limpio `ca4e55c` (procedencia completa en los JSON):

- [Simulación técnica](evidencia/validacion-2026-11-21/simulacion-tecnica.json):
  10/10 casos cumplen las comprobaciones técnicas; p95 UC01 0,044 s y UC02 0,028 s.
- [API con ORS real](evidencia/validacion-2026-11-21/api-ors-real.json):
  10/10 casos cumplen; p95 UC01 **1,503 s** y UC02 **1,036 s** (cinco consultas
  por caso de uso). Son latencias observadas de la API en proceso incluyendo ORS,
  por debajo de 5 s en este lote, no una garantía de percentiles poblacionales.
- En cada corrida: trazabilidad 10/10 recomendaciones, privacidad 10/10 y
  frescura 106/106 precios respecto de la referencia histórica; cero fallos de
  auditoría. Ninguna corrida acredita precios actuales, usuarios reales o AWS.
- [Comprobación del diagnóstico operativo](evidencia/validacion-2026-11-21/diagnostico-operativo.json):
  cinco estaciones recibieron 503 seguro porque la base local todavía no contiene
  una ingesta histórica exitosa. No se presenta su latencia como inferencia exitosa.
  El serving necesita ingesta `historico` y manifiestos compatibles, además de
  `vigente`; no alcanza con haber recibido el dataset de entrenamiento.
  La preparación de la base del despliegue se mantiene en #22/#59.

Los JSON se guardan compactos sin alterar valores; se pueden inspeccionar con
`python -m json.tool archivo.json`. La simulación y el lote ORS se reproducen con
los comandos anteriores. Usar el commit indicado para comparar la procedencia;
las latencias cambian entre ejecuciones. No se publican claves ni la base local.


### Costo del diagnóstico activo con veinte candidatas

La observación de Felipe en #141 es correcta: el lote histórico anterior no
incluye veinte diagnósticos activos. Se agrega un ensayo independiente:

```bash
python scripts/measure_active_diagnostics.py --output diagnostico-activo.json
```

El ensayo construye veinte estaciones y 1.200 publicaciones históricas sintéticas,
con manifiestos sintéticos compatibles entre sí. Sólo dentro del ensayo sustituye
la selección admitida por la política por el hash del manifiesto sintético; restaura
la configuración al terminar. Usa rutas sintéticas y ejecuta el código real de
lectura, preparación temporal, referencia, política, ranking y persistencia por HTTP.
No es una carga del histórico real ni una habilitación de esos datos en producción.

La [corrida versionada](evidencia/validacion-2026-11-21/diagnostico-activo-20.json)
completó cinco consultas con veinte diagnósticos activos cada una, p95 **0,677 s**,
con código limpio `1275047` y 1.200 filas históricas de QA. No se suma
su p95 al del lote ORS para anunciar una latencia completa: siguen siendo muestras
y condiciones diferentes. La latencia con el histórico real queda sin acreditar.
