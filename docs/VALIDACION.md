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
La medición real con ORS necesita la clave y consume cuota; queda pendiente.

**Trazabilidad, frescura y privacidad.** `python -m nafta2go.audit` revisa lo que
quedó guardado en `recommendations`, no lo que el código intentó guardar:

- *Trazabilidad:* un único origen (ingesta exitosa o escenario con ID, fecha y
  hashes), motor y proveedor coherentes, fila de origen en cada precio y hash de la
  matriz reproducida.
- *Frescura:* cada precio evaluado está dentro de la vigencia de su consulta respecto
  de la fecha de referencia de precios.
- *Privacidad:* ninguna clave de origen o destino ni enlaces de mapas en la consulta,
  el resultado o el escenario.

Sobre las 123 recomendaciones guardadas en cada medición (120 más 3 de
calentamiento, todas del escenario histórico): trazabilidad 123/123, frescura
1.230/1.230 precios evaluados y privacidad 123/123. La prueba integral
(`tests/integration/test_local_mvp.py`) audita además tres recomendaciones de
ingestas vigentes hechas por HTTP, con 100 % en los tres criterios. Todas son
recomendaciones generadas para la validación: la auditoría todavía no corrió sobre la
base de un despliegue real (#22).

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
| RF10 Diagnóstico del precio | Parcial | `tests/presentation/test_price_diagnostic.py`, [ADR-015](../adr/ADR-015-referencia-servida-y-abstencion-de-alertas.md) | Sirve la referencia y su versión, pero `alert_level` sigue en `not_calibrated`: falta una política de alertas aprobada (#19) |
| RF11 Ranking conservador | Pendiente | Auditoría de umbrales en [ML](ML.md#auditoría-real-del-17112026) | Depende de la política de alertas (#20) |
| RF12 Autenticación administrativa | Cumple | `tests/presentation/test_ingestion_status.py`, `tests/presentation/test_http.py`, [ADR-016](../adr/ADR-016-acceso-administrativo-separado.md) | — |
| RF13 Configuración sin código | Parcial | Vigencia por variable de entorno (#96), parámetros de caché y cupo en Compose | No hay auditoría de cambios de configuración |
| RF14 Estado operativo | Parcial | Panel `/operacion` y API de estado (`tests/browser/web.test.cjs`, `tests/presentation/test_ingestion_status.py`) | Métricas del modelo en el panel |
| RF15 Escenarios históricos | Cumple | `tests/application/test_scenario.py`, rótulo `historical_scenario` en las respuestas | — |

## Requisitos no funcionales

| ID | Estado | Evidencia | Falta |
|---|---|---|---|
| RNF01 Rendimiento | Parcial | Medición en proceso y composición con ORS (arriba) | Lote real de punta a punta con ORS, UC01 y UC02 |
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
| Utilidad | ≥ 80 % elige y explica una opción, con ≥ 10 conductores | No se realizó la prueba con usuarios | Pendiente |
| Comprensión | ≥ 80 % interpreta precio, desvío y combustible neto | No se realizó la prueba con usuarios | Pendiente |
| Factibilidad | 100 % de recomendaciones respeta las restricciones | Suite del motor y del ranking, sin fallas | Cumple |
| Explicabilidad | 100 % de resultados y descartes con motivo trazable | Pruebas de contrato del motor y de la API | Cumple |
| Rendimiento | p95 ≤ 5 s | ≈ 1,28 s estimado por composición | Parcial |
| Ingesta | ≥ 95 % completada o alertada en 24 h | 3 de 3 corridas observadas (2 fallas alertadas en segundos y 1 recuperación), en [la evidencia del 12/11](evidencia/mvp-01-operacion-2026-11-12.json) | Parcial: muestra chica, sin operación continua |
| Frescura | 100 % de precios dentro del umbral | 1.230 de 1.230 en la auditoría de la medición | Cumple |
| ML | Mejora material o adopción explícita del modelo simple | Se adoptó una referencia simple con protocolo previo ([ADR-014](../adr/ADR-014-seleccion-de-modelo-de-precios.md)) | Cumple |
| Privacidad | 100 % sin ubicación persistida | 123 de 123 en la auditoría de la medición, más la prueba integral | Cumple |

## Recortes e incumplimientos

- **Pruebas con usuarios (utilidad y comprensión):** no se hicieron. Requieren al
  menos diez conductores y un guion moderado; sin ellas, esos criterios no pueden
  darse por cumplidos.
- **Ranking conservador (RF11):** no está implementado porque no hay una política de
  alertas validada. La auditoría de umbrales no mide sensibilidad (#20).
- **Rendimiento de punta a punta:** la medición separa la aplicación de ORS. Falta un
  lote real con la clave, que consume cuota del plan gratuito (500 matrices por día).
- **Accesibilidad y operación:** faltan la verificación en un teléfono físico y la
  supervisión continua de la ingesta fuera de la máquina local.
