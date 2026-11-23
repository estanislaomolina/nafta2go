# API local del recomendador — primer incremento de MVP-02

## Diagnóstico retrospectivo de precios (incremento de MVP-05)

`GET /api/v1/price-diagnostics/{station_id}?product_id=2&schedule_id=2` requiere
el mismo Bearer de las consultas. Producto/franja aceptan 2 o 3. Selecciona la
última publicación no futura en la última ingesta vigente exitosa; el cliente
no puede enviar precio, fecha, features ni rutas de artefactos.

Configurar `NAFTA2GO_PRICE_DATASET_DIR` y `NAFTA2GO_PRICE_MODEL_DIR` con los
directorios generados según [ML](ML.md). Se leen sus `manifest.json`: deben
coincidir hashes, features, captura histórica y reglas de normalización. Ventana
y mínimo de historia proceden del dataset. Solo se sirve la corrida del alias
`champion` del [registro de modelos](ML.md#registro-de-modelos-y-campeón-161).
Cualquier otra versión deja el diagnóstico no disponible. En despliegue, usar directorios de
confianza de sólo lectura; Docker requiere mounts y rutas del contenedor.

El método servido es `chosen_method` si es una referencia admitida; no se carga
pickle ni se sustituye por `artifact_model`. Devuelve precio oficial, fecha,
referencia, diferencia (oficial menos referencia), método, versión e ingestas,
con `Cache-Control: no-store`. Usa la misma preparación temporal que entrenamiento
y publicaciones estrictamente anteriores al objetivo. El supuesto de disponibilidad
histórica se declara en la respuesta; no equivale a disponibilidad verificada.

`scope=published_price_retrospective` diagnostica la publicación, no el precio
actual. `reference_only` conserva el alcance retrospectivo y nunca afirma error. La selección
auditada habilita niveles provisionales de ADR-021; otra selección conserva
`alert_level=not_calibrated`. Sin contexto devuelve 200/`unavailable`, referencia/diferencia
nulas; sin publicación, 404; sin datos/configuración compatibles, 503 seguro.
La referencia no modifica motor, precio oficial, ranking ni vigencia.

Las lecturas filtran en SQL la última publicación no futura de la estación y el
histórico del mismo producto/franja estrictamente anterior al objetivo más reciente
del lote. La preparación ordenada excluye el mismo instante y el futuro para cada
publicación individual. Sólo
materializan los campos de preparación temporal. El histórico conserva precios
antiguos del grupo: el último precio propio puede ser anterior a la ventana de
medianas y sigue siendo necesario para el fallback. Esto reduce lecturas ajenas
al diagnóstico; no acredita p95 ni un límite de memoria para un grupo grande.

Es optativo: sin estas variables, la consulta habitual sigue funcionando y
readiness no exige diagnóstico. La regla provisional se describe al final de este documento; no acredita
calibración para detectar errores ni exige servir un modelo aprendido no seleccionado. La [web](WEB.md#referencia-histórica-de-una-publicación) permite consultar esta referencia bajo pedido. Alternativas en
[ADR-015](../adr/ADR-015-referencia-servida-y-abstencion-de-alertas.md).

La presentación HTTP usa FastAPI ([ADR-009](../adr/ADR-009-api-http-con-fastapi.md))
y llama al mismo caso de uso que la CLI. Requiere Python 3.12 y las dependencias
de `requirements-dev.txt` para correr los tests. Para iniciar desde el repositorio:

```bash
python -m pip install -r requirements-dev.txt
alembic upgrade head
export NAFTA2GO_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uvicorn nafta2go.presentation.http:app --host 127.0.0.1 --port 8000 --no-access-log --log-config deploy/logging.json
```

La API no carga `.env` automáticamente ni expone la clave de ORS al cliente.
`DATABASE_URL` selecciona la base; `ORS_API_KEY` habilita rutas en vivo cuando hay
cobertura. Con Docker: `docker compose --profile mvp up --build api`. Compose lee
las variables y publica solo `127.0.0.1:8000`; el token debe estar configurado.
Compose espera el esquema migrado y comprueba `/ready` mediante healthcheck.
Para detenerla: `docker compose --profile mvp stop api`.

Abrir `http://127.0.0.1:8000/docs`, usar **Authorize** con el token del entorno
y ejecutar `POST /api/v1/recommendations`. Ejemplo de cuerpo:

```json
{
  "origin": {"lat": -34.6037, "lon": -58.3816},
  "destination": {"lat": -34.5627, "lon": -58.4565},
  "fuel_type": "super",
  "schedule_id": 2,
  "consumption_l_per_100km": "10",
  "tank_capacity_l": "50",
  "remaining_l": "10",
  "budget_ars": "12000",
  "reserve_l": "2"
}
```

Los importes y litros pueden enviarse como cadenas decimales para preservar su
precisión. `destination` es opcional: sin ella se evalúa volver al origen. No se
aceptan campos extra, fechas de referencia ni rutas de archivos del cliente.
La fecha de referencia la establece el servidor. El control geográfico mantiene
el rectángulo de CABA del caso de uso existente.

La respuesta conserva el [contrato explicado de POC-05](POC-05.md): alternativas,
descartes, métricas, fuente, vigencia y origen de datos. La falta de cobertura o de
alternativas viables devuelve 200 con `outcome` explícito, sin inventar ganadoras.
El escenario histórico sigue rotulado. Los errores usan `detail.code`: 401 sin
autorización, 422 por entradas inválidas, 502 por rutas fallidas, 504 por timeout
y 503 por configuración, cuota o datos no disponibles. No incluyen mensajes
originales de excepciones ni repiten el cuerpo enviado. La operación se confirma
en la base antes de responder; un fallo de dependencia revierte la transacción.

`GET /health` comprueba que el proceso responde. `GET /ready` exige token de
servidor configurado, conexión y esquema en la revisión esperada; si no, devuelve
503 sin aplicar migraciones. Además comprueba datos utilizables y expone
`data_status`: `current`, `historical_scenario` (fallback histórico rotulado) o
`unavailable`; este último impide readiness aunque el esquema esté migrado.
Ambos controles y OpenAPI son públicos y no exponen
precios, ubicaciones ni credenciales. La consulta requiere `Authorization: Bearer`.

La API acepta `max_candidates` como entero estricto entre 3 y 20. Si se omite,
usa 10, igual que la CLI y el caso de uso. El límite se propaga a la selección y
queda registrado en la consulta persistida; puede haber menos evaluaciones si
la cobertura disponible es menor. La web local omite el campo y mantiene 10.
La caché y cuota por proceso están descritas en [RUTAS](RUTAS.md). Antes del uso
público faltan coordinación entre réplicas, HTTPS,
autenticación apropiada para usuarios y observabilidad completa (#21). El token
local no debe incrustarse en JavaScript público. La [web local](WEB.md) se sirve en `/` del mismo proceso. AWS y el despliegue
público siguen pendientes. Los tests usan bases temporales y rutas grabadas, sin red.

La presentación agrega `navigation` (enlaces por estación elegida con ID, URL y
etiqueta) y `navigation_notice`. No incluye el origen del conductor ni persiste
los enlaces. Contrato y límites en [MAPS](MAPS.md); la [web local](WEB.md) presenta estos enlaces; las pruebas de navegador se
entregan en una PR dependiente.

## Estimación de precios desactualizados (#117)

La respuesta de `POST /api/v1/recommendations` incluye `stale_price_estimates`,
aparte de `alternatives` y `evaluations`. Lista estaciones del corredor cuyo último
precio oficial en la ingesta vigente tiene más de `min_age_days` (el mayor entre 30
y la vigencia configurada) y hasta `max_age_days` (120) días, como propone
[ADR-020](../adr/ADR-020-estimacion-de-precios-antiguos.md).

Cada ítem conserva en campos separados el precio oficial
(`official_price_ars_per_l`), su fecha y antigüedad, la estimación
(`estimate_ars_per_l`), la ventana de referencia (`reference_from_local` a
`reference_to_local`) y la cantidad de precios usados. El bloque declara método
(`bandera_reciente`), versión (`stale-estimate-v1`), evidencia y `notice`.

La estimación es la mediana de los precios de la misma bandera, producto y franja
publicados en CABA durante los 7 días anteriores a la consulta, igual que la
feature `brand_recent_median` evaluada en
[la evidencia](evidencia/estimacion-antiguos-2026-11/README.md). Sin precios
recientes de la bandera se abstiene: la estación no aparece. A diferencia de la
evaluación, usa la ingesta vigente, que guarda la última publicación de cada
estación, en lugar de todas las publicaciones del histórico.

Cada ítem trae además `navigation` (URL de Google Maps y etiqueta), armada en la
presentación como la de las alternativas: las coordenadas de la estación se agregan
después de persistir y la recomendación guardada no las incluye.

No requiere `NAFTA2GO_PRICE_*`: es una regla determinística sin artefactos. Las
estaciones estimadas nunca se enrutan, no entran al ranking, no cuentan para la
cobertura y no renuevan la vigencia del precio oficial. Sin ingesta vigente, el
bloque informa `status=no_current_data` y una lista vacía. Se persiste con la
recomendación, sin ubicaciones del conductor.

## Telemetría local de consultas

Cada POST de recomendaciones devuelve `X-Request-ID` generado por el servidor;
el identificador del cliente se ignora. Al finalizar se emite un evento JSON
`query_completed` con ese ID, fecha UTC de inicio, duración monotónica en ms,
estado HTTP y resultado acotado. En fallos inesperados agrega
`error_type`, sin mensaje ni traza. Incluye rechazos 401, validaciones 422 y fallos;
un error inesperado anterior a la respuesta devuelve 500 con `internal_error`,
sin propagar el mensaje original al servidor. Una transmisión interrumpida se
registra como fallo y sólo propaga un mensaje fijo.

`GET /api/v1/operations` exige `NAFTA2GO_ADMIN_TOKEN`, distinto del token de conductor y devuelve conteos
por estado/resultado, suma de duraciones y contadores de caché/rutas. No consulta
ORS ni lee datos del conductor. La configuración inválida de caché devuelve el
error seguro de dependencia. El proceso genera sus propios IDs; no se guardan
requests ni una lista por ID en memoria. Contadores/duración de consultas están
aislados por aplicación y protegidos ante concurrencia; los contadores de rutas
pertenecen a la caché compartida por proceso y sólo reflejan el proveedor en vivo
que la utiliza. Proveedores de pruebas/grabados no incrementan esos contadores.

El arranque documentado y Compose usan `deploy/logging.json` y desactivan el
access log de Uvicorn: una URL arbitraria puede contener datos privados. Los
eventos no incluyen URL, headers, cuerpo, mensajes de excepción ni ubicaciones.
Otros servidores/proxies deben aplicar la misma política antes de exponerlos.
Los contadores se reinician al reiniciar la aplicación/caché, no se agregan entre
réplicas ni constituyen p95 o disponibilidad sostenida. La ingesta se consulta en el endpoint siguiente. El diagnóstico agrega sus propias métricas operativas; no se mide precisión ni deriva en línea.

El token administrativo ausente o igual al del conductor produce
503/`admin_not_configured`; el código del conductor no autoriza operación.
Las respuestas operativas usan `Cache-Control: no-store`. Readiness y las
recomendaciones siguen dependiendo sólo del token de conductor. Propuesta y
límites en [ADR-016](../adr/ADR-016-acceso-administrativo-separado.md).

El [panel local](WEB.md#panel-local-de-operación) presenta estas lecturas.

## Estado de ingestas para operación

`GET /api/v1/operations/ingestion?source=vigente` requiere el Bearer administrativo;
`source` sólo acepta `vigente` (predeterminado) o `historico`. Responde con
`Cache-Control: no-store` y hora UTC del servidor. Separa `latest_attempt` de
`latest_successful`: un fallo posterior no oculta la última versión exitosa.
Incluye ID, estado, fechas UTC, duración en segundos, reglas, hash/tamaño de
captura y conteos de filas normalizadas, estaciones distintas y rechazos. Si no
hay captura o versión exitosa, sus campos son nulos; un intento running muestra
duración transcurrida. No se exportan mensajes de error, reportes arbitrarios,
URLs, rutas locales, filas, precios ni coordenadas.

`conditions` recalcula las reglas existentes del monitor (falta diaria, fallo
terminado o running de dos horas), hasta veinte condiciones ordenadas por clave;
`condition_count` y `conditions_truncated` explicitan el total y el recorte.
`healthy` sólo significa que no se detectaron esas condiciones al leer: no
garantiza disponibilidad, cobertura ni precios actuales. `historico` aplica las
mismas reglas si se selecciona, sin implicar que esa fuente esté programada.

La lectura usa la capa de aplicación y proyecciones SQL explícitas, sin leer los
campos privados ni escribir en la base. No ejecuta ingestas ni sincroniza alertas: las
marcas persistidas de detección/resolución siguen siendo tarea del monitor
programado. Una lectura saludable no resuelve una alerta previa. Base/esquema no
disponibles producen 503 seguro. El [panel local](WEB.md#panel-local-de-operación) consume esta lectura; no reemplaza supervisión sostenida.

## Telemetría CLI

La CLI emite eventos seguros separados del resultado; contrato y límites en
[POC-05](POC-05.md#telemetría-cli-agregada-en-mvp). Sus eventos no se agregan
a los contadores HTTP.

La vigencia se configura con `NAFTA2GO_MAX_PRICE_AGE_DAYS` (1–30, predeterminado
30); ver [COBERTURA](COBERTURA.md#vigencia-configurable-en-mvp). El cliente no
puede enviarla en el cuerpo. La respuesta registra `query.max_price_age_days`;
configuración inválida produce 503/`coverage_not_configured` y readiness 503.


## Buscar una dirección o lugar

`POST /api/v1/places`, con el mismo Bearer de conductor y cuerpo
`{"text":"Corrientes 1234"}`, devuelve hasta tres `items` con `label`, `lat`, `lon`
y `source=USIG · GCBA`. No recibe texto en query params. El cliente elige un
resultado antes de recomendar. Código 429 pide reintentar, 503 indica dependencia
no disponible y 422 rechaza texto inválido. Las respuestas exitosas son no-store.
No persiste búsquedas ni crea recomendaciones. El texto se envía al proveedor sólo
por acción del usuario; no reenviar credenciales. Los logs de proxies deben omitir
cuerpos, como los de la aplicación.

Caché volátil y cupo por proceso, límites y alternativas en
[ADR-022](../adr/ADR-022-busqueda-de-direcciones-y-lugares.md).
`NAFTA2GO_PLACE_SEARCH_ENABLED=0` deshabilita el proveedor sin cambiar el motor.
La interfaz se incorpora separadamente en #130.


## Métricas del diagnóstico de precios

La lectura administrativa `/api/v1/operations` agrega `price_diagnostics`, aislado
por aplicación/proceso: conteos HTTP y por resultado, duración acumulada, fecha de
última solicitud y última referencia válida observada (método, versión y fecha).
`not_observed` significa que todavía no se observó una lectura válida; `degraded`
indica fallo operativo en la última lectura, y `observed` una lectura sin fallo.
Rechazos de autenticación/validación se cuentan sin confirmar recuperación. Una
referencia antigua puede seguir informada después de un fallo nuevo, con su fecha.

Cada GET de diagnóstico genera `X-Request-ID` y un evento JSON
`price_diagnostic_completed`. No registra estación, URL, parámetros, coordenadas,
precios, credenciales ni mensajes originales de excepciones. Un error inesperado
produce 500 seguro; una respuesta interrumpida se registra sin propagar su causa.

El [panel](WEB.md#panel-local-de-operación) presenta estas lecturas, sin polling ni
escrituras. El método elegido hoy es una referencia simple: estos contadores no
calibran alertas, miden error predictivo o detectan deriva. Se reinician con el
proceso; no se agregan entre réplicas ni constituyen disponibilidad sostenida.


La telemetría de consultas generales incluye también `status` por proceso:
`not_observed`, `observed` o `degraded` tras la última consulta completada con fallo
operativo. Un 401/422 no confirma recuperación. El panel avisa la degradación de
consultas y diagnóstico por separado de las alertas persistidas de ingesta; no
implica una notificación externa ni un control de disponibilidad sostenida.


## Política provisional de desvío — ADR-021

Con la selección auditada identificada en [ADR-021](../adr/ADR-021-ranking-conservador-por-desvio.md),
el diagnóstico conserva `status=reference_only` (referencia retrospectiva), pero
`alert_level` distingue `provisional_deviation` y `provisional_within_threshold`.
Devuelve `alert_policy_version=conservative-v1`, `relative_deviation`,
`alert_threshold` y un aviso explícito de limitaciones. La comparación es estricta:
`abs(publicado-referencia) > umbral * referencia`. Los umbrales por producto son
0,05424409844299347 y 0,054570259208731244 para súper y premium respectivamente.
No se interpreta la ausencia de excedencia como certificación del precio.

Otra selección/modelo conserva `not_calibrated` y política nula; sin contexto
se mantiene `unavailable`. No cambia el precio oficial ni la preparación temporal.
El resultado de la auditoría histórica sigue teniendo `runtime_enabled=false`:
es una fotografía del experimento, no la configuración actual del servicio.
La regla no tiene precisión ni sensibilidad medidas para detectar errores reales.

## Comparación conservadora (RF11)

`POST /api/v1/recommendations` agrega `conservative_ranking` sin modificar las
`alternatives` generales ni sus precios. Con precios vigentes y la selección de
ADR-021, `status=available` devuelve sus propias `alternatives`,
`excluded_station_ids`, `without_reference_station_ids` y `diagnostics` trazables
(ingestas, publicación, versión del modelo y política). Sólo evalúa candidatas
viables ya enrutadas: no hace llamadas adicionales a ORS. Las estaciones sin
referencia se conservan y se listan aparte. Puede quedar vacío si todas exceden.

Ante escenario histórico, diagnóstico/configuración incompatible o publicación
que no coincide con la recomendación, informa `unavailable` con motivo y sin
copiar el general. El bloque se persiste junto al resultado, sin coordenadas del
conductor. La web muestra ambas comparaciones y el carácter provisional.


### Histórico actualizado para el despliegue — 22/11/2026

La repetición de [la selección y auditoría](evidencia/actualizacion-precios-2026-11-22/README.md)
propone admitir además el manifiesto `b65d2d54ff3229486c495a35d89985b42981648dd02d576bf6a02b6f539aaf83`,
ligado al nuevo original `5a03269876a0facd38290938fcc580d6cf03fdae30264e5549affde22e3a1e70`.
Los umbrales y el método no cambian: la política sigue `conservative-v1`, con el
hash del manifiesto como versión de selección separada. Se conserva la selección
anterior; cualquier otro manifiesto se abstiene. El diagnóstico aún comprueba que
el hash del histórico sea el del modelo: no permite mezclar las dos capturas.
No se cambia el precio oficial ni se carga el artefacto aprendido descartado.
La habilitación en AWS requiere revisión e integración de esta actualización.


### Preparación compartida del contexto de diagnóstico

El recomendador agrupa hasta veinte publicaciones viables del mismo producto/franja
para leer la selección y el histórico una vez. Se calculan sus referencias en una
sola pasada cronológica: las publicaciones consultadas no se incorporan como contexto
de otras consultas. Se conservan el precio oficial, referencia, corte temporal,
abstención y metadatos por publicación. El endpoint individual usa el mismo camino
con un solo objetivo. No agrega llamadas de rutas ni expone un endpoint masivo.

La preparación de entrenamiento por defecto conserva sus bytes; el modo de consulta
emite sólo objetivos adicionales sin alterar el contexto histórico. Los tests
comparan el lote contra preparaciones individuales, incluso con publicaciones
históricas del mismo instante, objetivos intercalados y precios de consulta enormes.
La medición real del histórico en [la evidencia de rendimiento](evidencia/diagnostico-lote-2026-11-22/README.md)
se mantiene separada del lote con ORS y de la validación en AWS.
