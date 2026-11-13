# API local del recomendador — primer incremento de MVP-02

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
503 sin aplicar migraciones. Ambos controles y OpenAPI son públicos y no exponen
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

## Telemetría local de consultas

Cada POST de recomendaciones devuelve `X-Request-ID` generado por el servidor;
el identificador del cliente se ignora. Al finalizar se emite un evento JSON
`query_completed` con ese ID, fecha UTC de inicio, duración monotónica en ms,
estado HTTP y resultado acotado. En fallos inesperados agrega
`error_type`, sin mensaje ni traza. Incluye rechazos 401, validaciones 422 y fallos;
un error inesperado anterior a la respuesta devuelve 500 con `internal_error`,
sin propagar el mensaje original al servidor. Una transmisión interrumpida se
registra como fallo y sólo propaga un mensaje fijo.

`GET /api/v1/operations` exige el mismo Bearer administrativo y devuelve con `Cache-Control: no-store` conteos
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
réplicas ni constituyen p95 o disponibilidad sostenida. El resumen HTTP no incluye consultas CLI; su evento separado se describe en
[POC-05](POC-05.md#telemetría-cli-agregada-en-mvp). El [panel local](WEB.md#panel-local-de-operación) presenta estas lecturas.
Faltan métricas de modelo, alertas de consultas y supervisión sostenida (#21).

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

La vigencia se configura con `NAFTA2GO_MAX_PRICE_AGE_DAYS` (1–30, predeterminado
30); ver [COBERTURA](COBERTURA.md#vigencia-configurable-en-mvp). El cliente no
puede enviarla en el cuerpo. La respuesta registra `query.max_price_age_days`;
configuración inválida produce 503/`coverage_not_configured` y readiness 503.
