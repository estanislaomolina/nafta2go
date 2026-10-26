# Cobertura de precios de la POC

Implementa la tarea POC-02 (#7), correspondiente a RF09 y RF15 del
[PRD](PRD.md). La decisión sobre el escenario histórico está en el
[ADR-006](../adr/ADR-006-escenario-historico-de-la-poc.md). La selección de
precios desde la base y su conexión con rutas y motor están en
[MOTOR.md](MOTOR.md).

| Módulo | Responsabilidad |
|---|---|
| `nafta2go/application/coverage_rules.py` | Parámetros de cobertura y del escenario histórico. **Se cambian acá y todo el código los toma** |
| `nafta2go/application/corridor.py` | Desvío estimado en línea recta respecto del recorrido |
| `nafta2go/application/stored_query.py` | Selección por vigencia, calidad y corredor; elección entre captura actual y escenario |
| `nafta2go/application/scenario.py` | Carga y verificación del escenario congelado |
| `nafta2go/application/coverage_report.py` | Reporte de cobertura de una consulta |
| `nafta2go/coverage/__main__.py` | Comando de reporte |
| `scripts/freeze_scenario.py` | Congela un escenario a partir de una captura vigente |

## Parámetros

| Constante | Valor | Qué define |
|---|---|---|
| `MAX_PRICE_AGE_DAYS` | 30 | Un precio es reciente si se publicó como máximo hace 30 × 24 horas, con el límite incluido. Igual para súper y premium |
| `MIN_RECENT_CANDIDATES` | 3 | Estaciones con precio reciente dentro del corredor necesarias para recomendar con datos actuales |
| `MAX_DETOUR_KM` | 5,0 | Desvío máximo en línea recta para que una estación cuente como cercana al recorrido |
| `HISTORICAL_SCENARIO_ID` | `vigente-2026-10-24` | Escenario que se usa cuando la cobertura actual no alcanza |
| `HISTORICAL_SCENARIO_REFERENCE_AT` | 24/10/2026 18:00, hora de Argentina | Fecha contra la que se mide la vigencia en el escenario |

Las funciones de consulta toman sus valores por defecto de estas constantes; un
test verifica que ninguna firma repita el número. Para el caso Obelisco →
Cabildo con la captura del 24/10, cambiar `MAX_DETOUR_KM` a 3 o a 10 km deja 12
o 26 estaciones en el corredor, en lugar de 16.

## Corredor del recorrido

La cobertura se mide **cerca del recorrido**, no en toda CABA: lo que importa
para quien va a cargar es si hay estaciones con precio reciente en su camino.

- Con destino, el desvío estimado de una estación es
  `d(origen, estación) + d(estación, destino) − d(origen, destino)`, con
  distancias en línea recta (haversine).
- Sin destino, es la distancia en línea recta desde el origen.
- Una estación con desvío estimado mayor a `MAX_DETOUR_KM` se excluye con el
  motivo `outside_corridor`. Ese motivo se evalúa después de los de producto,
  franja, vigencia, precio y coordenadas, así los demás conteos no cambian.

El corredor es una estimación sin consultar rutas. El desvío real lo calcula
después el motor con las distancias del proveedor. Dentro del corredor se
mantiene el orden de preselección de #37: recencia y después ID de estación.

## Estados de cobertura

`evaluate_with_coverage` (y `select_with_coverage`, que hace lo mismo sin
enrutar) decide así:

| Estado | Cuándo | Qué se usa | ¿Consulta rutas? |
|---|---|---|---|
| `ready` | La última ingesta vigente exitosa tiene al menos `MIN_RECENT_CANDIDATES` estaciones recientes en el corredor | Precios de esa ingesta, con su `data_run_id` | Sí |
| `historical_scenario` | La captura actual no alcanza o no hay ingesta exitosa, pero el escenario congelado sí alcanza | Precios del escenario, con `scenario` (ID, fecha de referencia y hashes) y sin `data_run_id` | Sí |
| `insufficient_coverage` | No alcanza ni la captura actual ni el escenario | Nada | No |

`no_successful_ingestion` sigue existiendo como estado de la selección actual
(`current`), pero la consulta no se detiene ahí: pasa al escenario.

El resultado conserva las dos selecciones (`current` e `historical`), así se
ve cuánta cobertura había en cada una.

## Garantía: nunca se presentan precios viejos como actuales

- En `historical_scenario` la vigencia se mide contra la **fecha de referencia
  del escenario**, no contra la fecha de la consulta, y la selección lleva el
  rótulo `scenario`. Ningún precio del escenario tiene `data_run_id` ni
  `price_id`.
- El escenario **no se ingiere en la base**. Si se guardara como `vigente`, la
  consulta actual lo tomaría como la última captura.
- Una captura actual sin precios recientes no se completa con datos de otra
  ingesta: o alcanza sola, o se usa el escenario rotulado.

## Escenario congelado

`docs/evidencia/escenario-vigente-2026-10-24/` contiene:

- `precios_caba_nafta.csv`: las 732 filas de CABA y nafta del vigente
  capturado el 24/10/2026 a las 17:57, con el encabezado y el orden del archivo
  original (200 KB).
- `escenario.json`: URL, SHA-256 y tamaño de la captura completa
  (`e22e8009d41b…`, 9.268.946 bytes), SHA-256 y cantidad de filas del recorte,
  regla de recorte, fecha de referencia y licencia CC BY 4.0.

`load_scenario` verifica el SHA-256 del recorte antes de usarlo y lo normaliza
con las reglas de POC-01 (ver [NORMALIZACION.md](NORMALIZACION.md)). Para
congelar otro escenario:

```bash
python scripts/freeze_scenario.py --file data/raw/vigente/<captura>.csv \
    --sha256 <sha256> --url <url> --fetched-at <AAAA-MM-DDTHH:MM:SS>
```

y actualizar `HISTORICAL_SCENARIO_ID` y `HISTORICAL_SCENARIO_REFERENCE_AT`.

## Reporte de cobertura

```bash
python -m nafta2go.coverage --origin=-34.6037,-58.3816 --destination=-34.5627,-58.4565 \
    [--fuel super|premium] [--schedule 2|3] [--reference-at ISO] [--output reporte.json]
```

Las coordenadas van con `=` porque empiezan con un signo negativo. El comando
lee la última ingesta vigente de `DATABASE_URL` y, sin consultar rutas, muestra:
las estaciones con precio de hasta 7, 30, 90 y 365 días en CABA y en el
corredor, las exclusiones, el estado que tomaría la consulta y sus candidatas.

## Evidencia

Caso Obelisco → Cabildo y Juramento, nafta súper diurna (8,23 km en línea
recta):

| Fecha de referencia | Captura | ≤ 30 días en CABA | ≤ 30 días en el corredor | Estado |
|---|---|---|---|---|
| 2026-10-25 21:18 | Vigente del 25/10 | 30 | 16 | `ready` |
| 2026-10-24 18:00 | Vigente del 25/10 | 31 | 16 | `ready` |
| 2026-11-15 12:00 | Vigente del 25/10 | 2 | 0 | `historical_scenario`, con 16 estaciones del escenario |

La primera fila está en
[poc-02-cobertura-obelisco-cabildo-2026-10-25.json](evidencia/poc-02-cobertura-obelisco-cabildo-2026-10-25.json).
La tercera muestra qué pasa si la fuente no se actualiza: con la misma captura,
tres semanas después ya no hay precios recientes en el corredor y la consulta
pasa sola al escenario rotulado.

## Pendiente

- Registrar recomendaciones hechas con el escenario en `recommendations`, que
  hoy exige una ejecución `succeeded` (POC-05).
- Configurar los parámetros sin modificar código (RF13, "Debería").
- Si se usara el CSV histórico como escenario, revisar la selección por estación
  comentada en #37: con muchas filas por estación, una exclusión de calidad
  podría dejar pasar un precio más viejo de la misma estación.
