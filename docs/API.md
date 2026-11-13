# API local del recomendador — primer incremento de MVP-02

La presentación HTTP usa FastAPI ([ADR-009](../adr/ADR-009-api-http-con-fastapi.md))
y llama al mismo caso de uso que la CLI. Requiere Python 3.12 y las dependencias
de `requirements-dev.txt` para correr los tests. Para iniciar desde el repositorio:

```bash
python -m pip install -r requirements-dev.txt
alembic upgrade head
export NAFTA2GO_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uvicorn nafta2go.presentation.http:app --host 127.0.0.1 --port 8000
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

Esta rama independiente conserva diez candidatas, como `dev`. La ampliación a
veinte está en `feat/16-limite-candidatas` y se incorporará tras integrar ambos
incrementos. Antes del uso público faltan caché y control de cuota (#55), HTTPS,
autenticación apropiada para usuarios y observabilidad completa (#21). El token
local no debe incrustarse en JavaScript público. La [web local](WEB.md) se sirve en `/` del mismo proceso. AWS y el despliegue
público siguen pendientes. Los tests usan bases temporales y rutas grabadas, sin red.

La presentación agrega `navigation` (enlaces por estación elegida con ID, URL y
etiqueta) y `navigation_notice`. No incluye el origen del conductor ni persiste
los enlaces. Contrato y límites en [MAPS](MAPS.md); la [web local](WEB.md) presenta estos enlaces; las pruebas de navegador se
entregan en una PR dependiente.
