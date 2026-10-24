# Proveedor de rutas de la POC

Implementa la tarea POC-03 (#8), correspondiente a RF03, RNF01 y RNF02 del
[PRD](PRD.md), y aporta la evidencia que pide la confirmación del
[ADR-003](../adr/ADR-003-proveedor-de-rutas.md).

El código vive en la capa de adaptadores definida en el
[ADR-004](../adr/ADR-004-arquitectura-por-capas.md):

| Módulo | Responsabilidad |
|---|---|
| `nafta2go/adapters/routing.py` | Contrato neutral: `Point`, `DistanceMatrix`, errores, `RoutingProvider` y `trip_matrix` |
| `nafta2go/adapters/openrouteservice.py` | Cliente de OpenRouteService Matrix V2 que cumple ese contrato |
| `scripts/probe_openrouteservice.py` | Prueba autenticada que mide contrato, errores, límites y latencia |

El dominio no importa nada de OpenRouteService. Cambiar de proveedor implica
escribir otro adaptador con el método `matrix(sources, destinations)`.

## Configuración

1. Crear una cuenta gratuita en [openrouteservice.org](https://openrouteservice.org/dev/#/signup) y generar una API key del plan Standard.
2. Copiar `.env.example` a `.env` y completar `ORS_API_KEY`. El archivo `.env` está en `.gitignore`.
3. Correr los tests (no usan red ni la key):

```bash
python -m pip install -r requirements.txt
pytest -v
```

4. Correr la prueba autenticada (usa 8 solicitudes de la cuota diaria con los valores por defecto):

```bash
python scripts/probe_openrouteservice.py --runs 5 --stations 20
```

El script imprime la evidencia y la guarda en `docs/evidencia/poc-03-ors-AAAA-MM-DD.json`.
Nunca escribe la API key.

## Contrato con OpenRouteService

`POST https://api.openrouteservice.org/v2/matrix/driving-car` con el header
`Authorization: <API key>` y este cuerpo:

```json
{
  "locations": [[-58.3816, -34.6037], [-58.389601, -34.640861], [-58.4565, -34.5627]],
  "sources": [0, 1],
  "destinations": [1, 2],
  "metrics": ["duration", "distance"],
  "units": "m"
}
```

- Las coordenadas van como **`[longitud, latitud]`**, al revés que en el dataset. `Point` siempre se construye con `lat` y `lon` nombrados y el adaptador hace la inversión.
- La respuesta trae `durations` (segundos) y `distances` (metros) como matrices `sources × destinations`. Un par sin ruta viene como `null` y el adaptador lo entrega como `None`.
- Si la respuesta tiene status 200 pero no tiene esa forma (falta una matriz, filas o columnas de largo distinto, valores no numéricos), se trata como proveedor no disponible y no se usa.

## Una matriz por recomendación

`trip_matrix(provider, origin, stations, destination)` pide en una sola
solicitud todos los tramos que necesita el motor:

| | estación 1 … estación N | destino (u origen) |
|---|---|---|
| **origen** | origen → estación | origen → destino (ruta de referencia) |
| **estación i** | no se usa | estación → destino |

Con 20 candidatas son 22 ubicaciones y 21 × 21 = 441 elementos en **una**
solicitud. Sin destino, la última columna es la vuelta al origen y el origen no
se repite en `locations`. El adaptador rechaza más de 22 ubicaciones
(`MAX_LOCATIONS`) sin llamar a la API.

Para usarla con el motor de POC-04, la integración (POC-05) convierte metros a
kilómetros y segundos a minutos, arma `Route` con `to_station` = fila 0,
`after_station` = fila de la estación y `direct` = fila 0 última columna, y pasa
`route=None` cuando alguno de esos valores es `None`.

## Errores y timeouts

| Situación | Excepción | Qué hace la aplicación |
|---|---|---|
| Falta `ORS_API_KEY`, o respuesta 401/403 | `InvalidCredentials` | Error de configuración; no reintentar |
| 429 | `QuotaExceeded` | Degradar: informar que no hay rutas disponibles (RNF02) |
| 400, 404, 413 y otros 4xx (con `error.code` 6000–6099 en `provider_code`) | `InvalidRequest` | Revisar la solicitud; 6010 = punto sin red vial cercana |
| 5xx, error de conexión o 200 con formato inesperado | `ProviderUnavailable` | Degradar y registrar |
| Sin respuesta en 5 s de conexión o 15 s de lectura | `ProviderTimeout` | Degradar y registrar |

Los mensajes de error no incluyen el cuerpo de la respuesta, los headers ni la
API key. Los headers `x-ratelimit-limit`, `x-ratelimit-remaining` y
`x-ratelimit-reset` de la última respuesta quedan en `client.last_rate_limit`
para observabilidad.

## Límites y latencia

| Dato | Publicado (plan Standard) | Observado |
|---|---|---|
| Solicitudes Matrix por día | 500 | Pendiente de la prueba autenticada |
| Solicitudes Matrix por minuto | 40 | Pendiente de la prueba autenticada |
| Latencia de una matriz de 22 ubicaciones | No publicada | Pendiente de la prueba autenticada (p50/p95 de 5 corridas) |
| Respuesta a una key inválida | 401/403 (no documentado) | Pendiente de la prueba autenticada |
| Punto sin red vial | 404 con código 6010 | Pendiente de la prueba autenticada |

Los valores publicados salen de [openrouteservice.org/plans](https://openrouteservice.org/plans/).
La cuota cuenta solicitudes, no elementos de la matriz. Con una solicitud por
recomendación y el supuesto del PRD de 40 consultas diarias, el uso esperado es
del 8 % de la cuota diaria.

## Plan alternativo

Si la prueba autenticada no confirma cuota, latencia o disponibilidad:

1. **Menos candidatas.** Preseleccionar por distancia en línea recta y bajar de 20 a 10 estaciones (12 ubicaciones, 121 elementos). La POC ya pide hasta diez.
2. **Caché de matrices.** Solo si las condiciones de uso de OpenRouteService lo permiten (pendiente de verificar), con clave por coordenadas redondeadas y vencimiento corto.
3. **OSRM propio.** Levantar `osrm-backend` en Docker con el extracto de Argentina de Geofabrik e implementar otro `RoutingProvider` con su servicio `table`. El motor no cambia.
4. **Sin proveedor disponible.** Nunca reemplazar la ruta por la distancia en línea recta sin avisarlo: la recomendación se descarta como `route_unavailable` y la interfaz lo explica.
