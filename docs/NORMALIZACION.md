# Normalización de precios de la POC

Implementa la tarea POC-01 (#6), correspondiente a RF08, RF09 y RNF05 del
[PRD](PRD.md) y a la puerta G1 del [Roadmap](ROADMAP.md). El plan de trabajo
está en [planes/poc-01-normalizacion.md](planes/poc-01-normalizacion.md) y la
persistencia que recibe el resultado en [PERSISTENCIA.md](PERSISTENCIA.md).

| Módulo | Responsabilidad |
|---|---|
| `nafta2go/adapters/energy_source.py` | Catálogo de la Secretaría de Energía y descarga verificada de la captura cruda |
| `nafta2go/normalization/rules.py` | Constantes: alcance, formatos de fecha, umbrales, motivos y alertas |
| `nafta2go/normalization/reading.py` | Lectura por chunks del CSV crudo, filtro CABA + nafta y `fila_origen` |
| `nafta2go/normalization/dates.py` | Parseo de fechas por origen y motivos de rechazo de fechas |
| `nafta2go/normalization/validation.py` | Precio, coordenadas, precios atípicos y duplicados |
| `nafta2go/normalization/pipeline.py` | `normalize()` y `normalize_capture()`, el normalizador que recibe `ingest()` |
| `nafta2go/normalization/__main__.py` | Comando de ingesta |

## Uso

```bash
python -m nafta2go.normalization --source vigente
python -m nafta2go.normalization --source historico               # ~780 MB, unos 2 minutos
python -m nafta2go.normalization --source historico --file RUTA   # CSV ya descargado
```

Sin `--file`, el comando descubre el recurso en el catálogo y lo descarga a
`data/raw/<origen>/<AAAAMMDDTHHMMSSZ>_<sha256[:12]>.csv`. En los dos casos
aplica las migraciones, ingiere en la base de `DATABASE_URL` e imprime el
`run_id` y el reporte de calidad guardado en la ejecución. Si la ingesta falla,
la ejecución queda `failed` y el comando sale con código 1.

## Fuente y captura cruda

- El catálogo es
  `http://datos.energia.gob.ar/api/3/action/package_show?id=precios-en-surtidor`.
  Se toman los recursos CSV cuyo nombre contiene "vigentes" e "historicos" (sin
  acentos). Si falta alguno, se lanza `LookupError`.
- El portal redirige HTTPS a HTTP y el DataStore (`datastore_search_sql`) ya no
  existe, así que los CSV se bajan completos por HTTP. La integridad se cubre
  con el tamaño publicado en el catálogo y el SHA-256 de lo recibido.
- La descarga se escribe en un `.part`. Solo se renombra si los bytes coinciden
  con el tamaño del catálogo; si no, o si la conexión se corta, el `.part` se
  borra y no queda ninguna captura a medias.
- El archivo crudo nunca se modifica. `fetched_at` se guarda en hora local de
  Argentina sin zona, igual que las fechas de la fuente.

## Alcance

Se conservan las filas con `provincia == "CAPITAL FEDERAL"` (sin distinguir
mayúsculas) e `idproducto` 2 (súper) o 3 (premium). `fila_origen` es la
posición de la fila en el archivo, contada antes de filtrar (1 = la primera fila
después del encabezado), así que cada precio y cada rechazo apuntan a su fila
original.

Las columnas se leen como texto. Si la fuente quita o renombra una columna
necesaria, la lectura falla con `UnexpectedSchema` nombrando las columnas
faltantes, y la ingesta queda `failed`.

## Formato real de las fechas

| Origen | Formato | Ejemplo |
|---|---|---|
| Vigente | `AAAA-MM-DD HH:MM:SS` | `2026-07-06 12:04:00` |
| Histórico | `DD/MM/AAAA HH:MM` (día primero) | `01/03/2019 11:31` = 1 de marzo de 2019 |

Cada origen se parsea con un formato fijo, sin inferencia. Un valor que no
respeta el formato, o con un año fuera del rango que maneja pandas, queda como
fecha inválida.

**Evidencia de que el histórico usa el día primero.** El histórico trae las
columnas `anio` y `mes`. Sobre las 80.025 filas de CABA + nafta de la captura
del 2026-10-24:

| Lectura | Fechas que parsean | Coinciden con `anio`/`mes` |
|---|---|---|
| Día primero | 99,99 % | 99,99 % (80.019 filas) |
| Mes primero | 58,74 % | 2,98 % (2.388 filas) |

Las 6 filas que no coinciden con la lectura de día primero son las de año mal
tipeado (`30/07/0025`, `07/02/6202`, `28/02/0026`), que se rechazan como
`fecha_invalida`.

**Las 84 fechas futuras de la Entrega 1.** La notebook leía el histórico desde
el DataStore e interpretaba las fechas con el mes primero. Con esa lectura, una
fecha como `10/01/2026` (10 de enero) pasa a ser el 1 de octubre y aparece como
futura. El conteo exacto no se puede reproducir: el DataStore ya no existe y
aquella consulta trajo 20.522 filas, contra las 80.025 del CSV actual. El
mecanismo sí se reproduce: con las filas del CSV actual que ya existían el
2026-09-18, leer con el mes primero produce 314 fechas posteriores a ese día; con
el día primero, ninguna. Con la regla actual queda **una sola fecha futura**,
`01/01/2044 00:00`, que se rechaza.

## Rechazos

La fila no pasa a las filas válidas y se guarda en `rejected_rows` con todos sus
valores crudos y **un único motivo**: el primero que aplica, en este orden.

| Motivo | Regla |
|---|---|
| `fecha_invalida` | La fecha no respeta el formato del origen o el año queda fuera de rango |
| `fecha_futura` | La fecha es posterior a `fetched_at` de la captura |
| `fecha_inconsistente_anio_mes` | Solo histórico: el año o el mes no coinciden con `anio`/`mes` |
| `precio_invalido` | El precio no es un número con punto decimal (`^\d+(\.\d+)?$`): `1.234,5`, `s/d`, vacío |
| `precio_no_positivo` | El precio es `<= 0` |
| `clave_duplicada_conflicto` | Dos o más filas con la misma clave y precios distintos: se rechazan todas |

Las reglas **no corrigen datos**: un año mal tipeado o un precio multiplicado
por 100 no se arreglan, se rechazan o se marcan.

## Clave y duplicados

La clave es `(idempresa, idproducto, idtipohorario, fecha_vigencia)`. En la
captura del 2026-10-24 el histórico no tiene claves repetidas, y en el vigente
`(idempresa, idproducto, idtipohorario)` es única.

- Filas idénticas en la clave y el precio: se conserva la primera y las demás
  se cuentan en `duplicados_exactos`. No se guardan como rechazos.
- Misma clave con precios distintos: no hay forma de saber cuál es el correcto,
  así que todas se rechazan con `clave_duplicada_conflicto`.

La regla de duplicados se evalúa solo entre las filas que no tienen otro motivo.

## Alertas

La fila sigue entre las válidas y las alertas se guardan en `alerts`, separadas
por `;`, en este orden:

| Alerta | Regla |
|---|---|
| `precio_atipico` | El precio supera 3 veces o es menor a un tercio de la mediana del grupo (mes de `fecha_vigencia`, `tipo_nafta`). Solo se evalúa si el grupo tiene al menos 5 observaciones |
| `fuera_de_caba` | Las coordenadas existen pero caen fuera de la caja lat −34,71 a −34,52, lon −58,54 a −58,33 |
| `sin_coordenadas` | Falta la latitud o la longitud |

`fuera_de_caba` importa para el recomendador: OpenRouteService no rechaza
coordenadas fuera de la red vial, las ajusta y devuelve rutas absurdas (ver
[RUTAS.md](RUTAS.md)).

## Reporte de calidad

Cada ejecución guarda en `ingestion_runs.report`: `filas_leidas` (después del
filtro de alcance), `filas_validas`, `filas_rechazadas`, `duplicados_exactos`,
`rechazos_por_motivo`, `alertas_por_tipo`, `estaciones` (entre las filas
válidas), `fecha_min` y `fecha_max`. Se cumple
`filas_leidas = filas_validas + filas_rechazadas + duplicados_exactos`.

## Corrida real del 2026-10-24

| | Vigente | Histórico |
|---|---|---|
| Archivo | 9.268.946 bytes | 778.654.156 bytes |
| SHA-256 | `e22e8009d41b…` | `950f748f881c…` |
| Filas leídas (CABA + nafta) | 732 | 80.025 |
| Filas válidas | 732 | 80.008 |
| `fecha_invalida` | 0 | 6 |
| `fecha_futura` | 0 | 1 |
| `fecha_inconsistente_anio_mes` | — | 0 |
| `precio_no_positivo` | 0 | 10 |
| Duplicados exactos | 0 | 0 |
| `precio_atipico` | 0 | 106 |
| `fuera_de_caba` | 0 | 78 |
| `sin_coordenadas` | 0 | 6 |
| Estaciones | 184 | 237 |
| Fechas | 2023-08-16 a 2026-10-23 | 2015-07-01 a 2026-10-23 |
| Duración | 7 s | 1 min 44 s (630 MB de memoria máxima) |

- `fuera_de_caba` sale de dos estaciones cargadas como CAPITAL FEDERAL: la 8610
  ("RUTA 3 K 21,5", 36 filas) y la 8602 ("AV DEL LIBERTADOR 2376", lat −34,5086,
  al norte de la General Paz; 42 filas).
- `precio_atipico` marca precios divididos por 10 (por ejemplo `10.8` para
  premium en mayo de 2021) o multiplicados por 100 (`7945`, `19320`) en 65
  estaciones.
- El vigente no tiene rechazos, pero sus fechas van de 2023 a 2026: la
  normalización no decide si un precio es reciente. Eso lo resuelve POC-02.

Los números cambian con cada actualización de la fuente. Para repetir la corrida
basta con volver a ejecutar el comando y comparar el reporte.
