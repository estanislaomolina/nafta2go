# API local del recomendador — primer incremento de MVP-02

La presentación HTTP usa FastAPI ([ADR-009](../adr/ADR-009-api-http-con-fastapi.md))
y prepara la entrada a la capa de aplicación. Requiere Python 3.12 y las dependencias
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

Esta base expone `GET /health` para comprobar que el proceso responde y
`GET /ready` para verificar token configurado, conexión y revisión esperada del
esquema. Readiness devuelve 503 si falta una condición; nunca aplica migraciones.
Ambos controles son públicos y solo devuelven estado, sin datos ni credenciales.
OpenAPI está disponible en `http://127.0.0.1:8000/docs`.

La consulta autenticada `POST /api/v1/recommendations`, su contrato y sus pruebas
se incorporan en una PR dependiente de esta base (#62). Todavía no hay consultas
HTTP ni interfaz web. No se despliegan recursos en AWS. El token local prepara la
configuración del siguiente incremento y no debe incrustarse en JavaScript
público; autenticación de usuarios y HTTPS siguen pendientes para uso público.
Las pruebas usan bases temporales y no realizan solicitudes externas.
