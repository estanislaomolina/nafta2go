# POC-01: Normalización de datos validada — Plan de implementación

> Propuesta de plan para el issue POC-01 (#6), asignado a @felisl30. Es un punto de partida: los nombres, las reglas y los umbrales se pueden discutir en la PR antes de implementarlos.
>
> **Para asistentes de IA:** ejecutar tarea por tarea con TDD (test que falla → implementación → test que pasa). Los pasos usan casillas `- [ ]` para seguir el avance.

**Objetivo:** un pipeline reproducible que descarga los CSV oficiales (vigente e histórico), conserva el archivo original, filtra CABA + nafta y normaliza fechas, claves, productos, precios y coordenadas con reglas explícitas. Entrega filas válidas, rechazos con motivo y un reporte de calidad, en el formato que ya espera la persistencia de POC-06.

**Arquitectura:**
- `nafta2go/adapters/energy_source.py`: adaptador hacia la fuente (catálogo y descarga). Sigue el mismo patrón que `adapters/openrouteservice.py`.
- `nafta2go/normalization/`: las reglas, como funciones puras sobre `pandas.Series` y `DataFrame`. Se prueban con datos inline y con dos CSV de muestra que tienen el formato real.
- `normalize_capture(capture) -> NormalizationResult`: conecta todo con `ingest()` de POC-06, que guarda el resultado en la base.

**Stack:** Python 3.12, pandas, requests, pytest. Agregar `pandas` a `requirements.txt`.

**Spec:**
- Issue POC-01 (#6).
- `docs/PRD.md`: RF08, RF09, RNF05.
- `docs/ROADMAP.md`: puerta G1.
- `adr/ADR-001-alcance-y-estrategia-de-datos.md`.
- `docs/PERSISTENCIA.md` (PR #29): el contrato de filas que hay que respetar.

## Hallazgos que fijan las reglas (verificados el 2026-10-24)

- **Vigente:**
  - 36.645 filas, con `fecha_vigencia` siempre en formato `AAAA-MM-DD HH:MM:SS` y ninguna fecha futura.
  - CABA + nafta: 732 filas de 184 estaciones.
  - `precio` es un entero (por ejemplo `2354`).
- **Histórico:**
  - 3.381.083 filas y 778 MB.
  - `fecha_vigencia` siempre viene como `DD/MM/AAAA HH:MM` (día primero) y el archivo trae las columnas `anio` y `mes`. Leída con el día primero, la fecha coincide con `anio`/`mes` en el 99,99 % de las filas; leída con el mes primero, solo en el 3 %. **Las 84 "fechas futuras" de la Entrega 1 venían de leer día y mes al revés** (a través del DataStore).
  - CABA + nafta: 80.025 filas de 237 estaciones, de 2015 a 2026.
  - `precio` usa punto decimal (por ejemplo `45.67`).
- **Anomalías reales del histórico de CABA:**
  - 6 fechas con el año mal tipeado (`30/07/0025`, `07/02/6202`, `28/02/0026`).
  - 1 fecha futura (`01/01/2044`).
  - 10 precios `<= 0`.
  - Precios multiplicados por 10 o por 100 (por ejemplo `19320`, con una mediana mensual de `193.9`).
  - 6 filas sin coordenadas.
  - 1 estación (`8610`, "RUTA 3 K 21,5") con provincia CAPITAL FEDERAL pero ubicada fuera de CABA.
- **Claves:**
  - El histórico no tiene duplicados de `(idempresa, idproducto, idtipohorario, fecha_vigencia)`.
  - En el vigente, `(idempresa, idproducto, idtipohorario)` es única.
  - Ninguna estación cambió de dirección.
- **Productos:**
  - `idproducto` 2 = súper y 3 = premium, en ambos archivos.
  - `idtipohorario` 2 = diurno y 3 = nocturno.
- **Portal:**
  - El DataStore (`datastore_search_sql`) **ya no existe** en `datos.energia.gob.ar` y HTTPS redirige a HTTP. El histórico solo se obtiene bajando el CSV completo, y las URLs de descarga del catálogo son `http://`. **Esto rompe la notebook de exploración.**
- **Importa para el recomendador:**
  - ORS no rechaza coordenadas fuera de la red vial: las ajusta y devuelve rutas absurdas (ver `docs/RUTAS.md`). Por eso la alerta `fuera_de_caba` es importante.

## Restricciones globales

- Python 3.12; dependencias de ejecución en `requirements.txt` y de desarrollo en `requirements-dev.txt` (PR #28).
- Los tests **no usan red**: todo lo que toca HTTP recibe una sesión inyectada, igual que el adaptador de rutas.
- Nunca se modifica ni se borra el archivo crudo descargado. Los valores originales de `fecha_vigencia` y `precio` viajan en columnas `*_original`.
- Las reglas **no corrigen** datos (no "arreglan" años ni precios): rechazan con un motivo o marcan una alerta.
- Alcance: `provincia == "CAPITAL FEDERAL"` (sin distinguir mayúsculas) e `idproducto ∈ {2, 3}`.
- `fetched_at` y la comparación de "fecha futura" usan la hora local de Argentina (`America/Argentina/Buenos_Aires`) sin zona, porque las fechas de la fuente son locales y no traen zona.
- Los nombres de módulos y funciones van en inglés, como el resto del paquete. Las columnas conservan los nombres de la fuente (`idempresa`, `fecha_vigencia`, …) porque son el contrato con POC-06.
- `ruff check .` y `ruff format --check .` en verde (`ruff.toml`, PR #28).
- Rama `feat/6-normalizacion` desde `dev`, con PR contra `dev`. Commits convencionales en español, sin coautores.
- Si hace falta un ADR, es el **ADR-006**: el ADR-005 ya es la persistencia (PR #29).

## Puntos a revisar con cuidado

1. **"Ahora" con zona horaria:** una fila de hoy a las 23:00 hora local no debe rechazarse como futura si la ingesta corre a las 23:30 hora local (02:30 UTC del día siguiente). Test `test_future_uses_local_time`.
2. **Precio con coma decimal o con texto** (`"1.234,5"`, `"s/d"`): tiene que terminar en un rechazo `precio_invalido`, nunca en una excepción ni en un número equivocado.
3. **CSV con columnas faltantes o renombradas** por la fuente: tiene que fallar con un error que nombre las columnas faltantes, no con un `KeyError` en medio del pipeline. En la ingesta, eso deja la ejecución en `failed`.
4. **Descarga cortada** (bytes recibidos ≠ `size` del catálogo): no debe quedar en `data/raw/` una captura a medias que parezca válida.
5. **Grupo chico para calcular la mediana del precio atípico** (un mes con 1 a 4 observaciones): no debe marcar alertas apoyadas en una mediana sin sustento.

---

## Estructura de archivos

```
requirements.txt                               # + pandas
nafta2go/adapters/energy_source.py             # catálogo, descarga verificada -> RawCapture
nafta2go/normalization/__init__.py
nafta2go/normalization/rules.py                # constantes: alcance, formatos, bbox, motivos
nafta2go/normalization/dates.py                # parseo y motivos de rechazo de fechas
nafta2go/normalization/validation.py           # precio, coordenadas, alertas, duplicados
nafta2go/normalization/reading.py              # lectura por chunks + filtro + source_row
nafta2go/normalization/pipeline.py             # normalize(), normalize_capture()
tests/fixtures/vigente_sample.csv
tests/fixtures/historico_sample.csv
tests/normalization/test_dates.py
tests/normalization/test_validation.py
tests/normalization/test_reading.py
tests/normalization/test_pipeline.py
tests/adapters/test_energy_source.py
docs/NORMALIZACION.md
```

`rules.py` contiene solo constantes:

```python
SOURCES = ("vigente", "historico")
CABA_PROVINCE = "CAPITAL FEDERAL"
NAPHTHA_PRODUCTS = {2: "super", 3: "premium"}
DATE_FORMAT = {"vigente": "%Y-%m-%d %H:%M:%S", "historico": "%d/%m/%Y %H:%M"}
KEY = ["idempresa", "idproducto", "idtipohorario", "fecha_vigencia"]
CABA_BBOX = {"lat_min": -34.71, "lat_max": -34.52, "lon_min": -58.54, "lon_max": -58.33}
OUTLIER_RATIO = 3.0  # precio > 3x o < 1/3 de la mediana del grupo
OUTLIER_MIN_GROUP = 5  # tamaño mínimo del grupo (mes, tipo_nafta)
RULES_VERSION = "1"
```

**Motivos de rechazo.** La fila no pasa a las filas válidas y va a `rejections`:
- `fecha_invalida`
- `fecha_futura`
- `fecha_inconsistente_anio_mes`
- `precio_invalido`
- `precio_no_positivo`
- `clave_duplicada_conflicto`

**Alertas.** La fila sigue entre las válidas y se marcan en la columna `alertas`, separadas por `;`:
- `precio_atipico`
- `fuera_de_caba`
- `sin_coordenadas`

### Contrato de salida (lo que consume POC-06)

`normalize_capture(capture: RawCapture) -> NormalizationResult` (tipos de `nafta2go/persistence/models.py`):

- `rows`: una fila por precio válido, con las claves `fila_origen`, `idempresa`, `empresa`, `empresabandera`, `direccion`, `idproducto`, `tipo_nafta`, `idtipohorario`, `precio`, `fecha_vigencia`, `latitud`, `longitud`, `fecha_vigencia_original`, `precio_original` y `alertas`.
- `rejections`: todas las columnas crudas, más `fila_origen` y `motivo`.
- `report`: `filas_leidas`, `filas_validas`, `filas_rechazadas`, `duplicados_exactos`, `rechazos_por_motivo`, `alertas_por_tipo`, `estaciones`, `fecha_min` y `fecha_max`. Tiene que ser serializable a JSON. `ingest()` verifica que `filas_validas` y `filas_rechazadas` coincidan con lo que se entrega.
- `rules_version`: `RULES_VERSION`.

---

### Tarea 1: Reglas de fechas

**Archivos:** `nafta2go/normalization/{__init__,rules,dates}.py`, `tests/normalization/test_dates.py`

**Interfaces:**
- `parse_dates(raw: pd.Series, source: str) -> pd.Series`: devuelve `datetime64[ns]`, con `NaT` si el valor no respeta `DATE_FORMAT[source]` o si el año queda fuera del rango que maneja pandas. Si `source` no es válido, lanza `ValueError`.
- `date_reasons(dates: pd.Series, ingested_at: pd.Timestamp, anio: pd.Series | None = None, mes: pd.Series | None = None) -> pd.Series`: devuelve `None` si la fecha es aceptable. Si no, devuelve el primer motivo que aplique, en este orden:
  1. `fecha_invalida`: la fecha es `NaT`.
  2. `fecha_futura`: la fecha es posterior a `ingested_at`.
  3. `fecha_inconsistente_anio_mes`: el año o el mes no coinciden con `anio`/`mes` (solo se evalúa si se pasan).
- `local_now() -> pd.Timestamp`: hora actual en `America/Argentina/Buenos_Aires`, sin zona.

- [x] **Paso 1: escribir los tests que fallan**

```python
def test_vigente_iso_format():
    s = parse_dates(pd.Series(["2026-09-22 09:05:00"]), "vigente")
    assert s.iloc[0] == pd.Timestamp("2026-09-22 09:05:00")


def test_historico_is_day_first():
    s = parse_dates(pd.Series(["01/05/2026 12:43"]), "historico")
    assert s.iloc[0] == pd.Timestamp("2026-05-01 12:43")


def test_historico_mistyped_year_is_nat():
    s = parse_dates(pd.Series(["30/07/0025 14:15", "07/02/6202 06:00"]), "historico")
    assert s.isna().all()


def test_wrong_format_is_nat():
    assert parse_dates(pd.Series(["2026-05-01 12:43:00"]), "historico").isna().all()


def test_reasons_order_and_values():
    ingested = pd.Timestamp("2026-10-24 18:00")
    dates = pd.Series(
        pd.to_datetime(["2026-10-23 10:00", None, "2044-01-01 00:00", "2026-05-01 12:43"])
    )
    anio = pd.Series(["2026", "2026", "2044", "2026"])
    mes = pd.Series(["10", "1", "1", "6"])
    assert date_reasons(dates, ingested, anio, mes).tolist() == [
        None,
        "fecha_invalida",
        "fecha_futura",
        "fecha_inconsistente_anio_mes",
    ]


def test_future_uses_local_time():
    # 23:00 locales del 24/10 con ingesta a las 23:30 locales (02:30 UTC del 25/10): no es futura
    ingested = (
        pd.Timestamp("2026-10-25 02:30", tz="UTC")
        .tz_convert("America/Argentina/Buenos_Aires")
        .tz_localize(None)
    )
    assert date_reasons(pd.Series([pd.Timestamp("2026-10-24 23:00")]), ingested).tolist() == [None]
```

- [x] **Paso 2:** correr `pytest tests/normalization/test_dates.py -v`. Esperado: FAIL (import).
- [x] **Paso 3:** implementar. `parse_dates` usa `pd.to_datetime(raw, format=DATE_FORMAT[source], errors="coerce")`.
- [x] **Paso 4:** correr los tests. Esperado: 6 passed.
- [x] **Paso 5:** commit `feat(normalizacion): reglas de parseo y validacion de fechas por origen` (`Refs #6`).

### Tarea 2: Precio, coordenadas, duplicados y alertas

**Archivos:** `nafta2go/normalization/validation.py`, `tests/normalization/test_validation.py`

**Interfaces:**
- `parse_prices(raw: pd.Series) -> pd.Series`: devuelve `float64`. Solo acepta valores que cumplan `^\d+(\.\d+)?$` (punto decimal); el resto queda como `NaN`.
- `price_reasons(prices: pd.Series) -> pd.Series`: `precio_invalido` si es `NaN`, `precio_no_positivo` si es `<= 0`, y `None` en cualquier otro caso.
- `alerts(df: pd.DataFrame) -> pd.Series`: usa las columnas `precio`, `fecha_vigencia`, `tipo_nafta`, `latitud` y `longitud`, ya tipadas. Devuelve las alertas separadas por `;`, en el orden `precio_atipico;fuera_de_caba;sin_coordenadas`, o `""` si no hay ninguna.
- `resolve_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int]`: devuelve `(kept, rejected, exact_duplicates)`.
  - Filas idénticas en `KEY + ["precio"]`: se conserva la primera y las demás se descartan y se cuentan.
  - Misma `KEY` con precios distintos: todas pasan a `rejected` con `motivo = "clave_duplicada_conflicto"`.

- [x] **Paso 1: escribir los tests que fallan**

```python
def test_parse_prices_formats():
    assert parse_prices(pd.Series(["2354", "45.67"])).tolist() == [2354.0, 45.67]
    assert parse_prices(pd.Series(["1.234,5", "s/d", ""])).isna().all()


def test_price_reasons():
    assert price_reasons(pd.Series([2000.0, 0.0, -1.0, float("nan")])).tolist() == [
        None,
        "precio_no_positivo",
        "precio_no_positivo",
        "precio_invalido",
    ]


def test_outlier_x100_alert():
    df = _frame(prices=[190, 192, 193, 194, 196, 19320])  # mismo mes y tipo_nafta
    assert alerts(df).tolist()[-1] == "precio_atipico"
    assert alerts(df).tolist()[0] == ""


def test_no_outlier_alert_in_small_group():
    assert alerts(_frame(prices=[190, 192, 19320])).tolist() == ["", "", ""]


def test_outside_caba_and_missing_coordinates_alerts():
    df = _frame(prices=[200, 200], lat=[-34.70175, None], lon=[-58.58013, None])
    assert alerts(df).tolist() == ["fuera_de_caba", "sin_coordenadas"]


def test_exact_duplicate_keeps_one():
    kept, rejected, exact = resolve_duplicates(_dups(prices=[2000, 2000]))
    assert len(kept) == 1 and rejected.empty and exact == 1


def test_conflicting_duplicate_rejects_all():
    kept, rejected, _ = resolve_duplicates(_dups(prices=[2000, 2100]))
    assert kept.empty
    assert rejected["motivo"].tolist() == ["clave_duplicada_conflicto"] * 2
```

`_frame(...)` y `_dups(...)` son helpers del test que arman un `DataFrame` mínimo. Por defecto usan coordenadas dentro de CABA (`-34.60, -58.40`), el mismo mes y `tipo_nafta="super"`.

- [x] **Paso 2:** FAIL. **Paso 3:** implementar. Para los atípicos, calcular la mediana y el tamaño por `(fecha_vigencia.dt.to_period("M"), tipo_nafta)` con `groupby().transform`; marcar solo si el tamaño es `>= OUTLIER_MIN_GROUP`. **Paso 4:** 7 passed.
- [x] **Paso 5:** commit `feat(normalizacion): validaciones de precio, coordenadas, atipicos y duplicados` (`Refs #6`).

### Tarea 3: Lectura del CSV crudo con filtro de alcance

**Archivos:** `nafta2go/normalization/reading.py`, `tests/fixtures/{vigente,historico}_sample.csv`, `tests/normalization/test_reading.py`

**Interfaces:**
- `REQUIRED_COLUMNS: dict[str, list[str]]`:
  - Comunes a los dos orígenes: `idempresa, empresa, direccion, provincia, idproducto, producto, idtipohorario, precio, fecha_vigencia, empresabandera, latitud, longitud`.
  - `historico` agrega `anio` y `mes`.
- `class UnexpectedSchema(ValueError)`: el mensaje nombra las columnas faltantes.
- `read_raw(path: Path, source: str, chunksize: int = 500_000) -> pd.DataFrame`:
  - Lee con `dtype=str`, `encoding="utf-8-sig"`, `keep_default_na=False` y `usecols=REQUIRED_COLUMNS[source]`.
  - Filtra cada chunk por provincia CABA e `idproducto ∈ {"2", "3"}`.
  - Agrega `fila_origen`: el número de fila de datos en el archivo (1 = la primera fila después del encabezado), calculado **antes** de filtrar.
  - Valida las columnas leyendo solo el encabezado (`nrows=0`).

**Fixtures** (los encabezados tienen que ser exactamente los reales):
- `historico_sample.csv`, 9 filas:
  - 2 válidas de CABA (súper diurno y premium nocturno).
  - 1 de BUENOS AIRES con gas oil (se filtra).
  - 1 de CAPITAL FEDERAL con GNC, `idproducto=6` (se filtra).
  - 1 con fecha `30/07/0025 14:15`.
  - 1 con fecha `01/01/2044 00:00`.
  - 1 con precio `0`.
  - La estación `8610`, con coordenadas `-34.70175,-58.58013`.
  - 1 sin latitud ni longitud.
- `vigente_sample.csv`, 4 filas:
  - 2 válidas de CABA.
  - 1 de otra provincia.
  - 1 de CABA con gas oil.

- [x] **Paso 1: escribir los tests que fallan**
  - `test_historico_filters_scope_and_numbers_rows`: quedan 7 filas, `idproducto` solo `{"2","3"}`, y `fila_origen` conserva las posiciones del archivo.
  - `test_vigente_filters_scope`: quedan 2 filas.
  - `test_missing_columns_clear_error`: un CSV sin `fecha_vigencia` lanza `UnexpectedSchema` con un mensaje que contiene `fecha_vigencia`.
- [x] **Pasos 2 a 4:** FAIL → implementar → 3 passed.
- [x] **Paso 5:** commit `feat(normalizacion): lectura por chunks del CSV crudo con filtro CABA y nafta` (`Refs #6`).

### Tarea 4: Pipeline y contrato con POC-06

**Archivos:** `nafta2go/normalization/pipeline.py`, `tests/normalization/test_pipeline.py`

**Interfaces:**
- `normalize(raw: pd.DataFrame, source: str, ingested_at: pd.Timestamp) -> NormalizationResult`:
  - Orden: fechas → precio → duplicados (solo entre las filas sin motivo) → alertas.
  - Cada fila rechazada tiene exactamente un motivo, el primero que aplica.
  - `anio` y `mes` solo se pasan cuando `source == "historico"`.
  - Convierte a `list[dict]` con `to_dict("records")`. `NaN` → `None` en coordenadas; las fechas quedan como `datetime`.
- `normalize_capture(capture: RawCapture) -> NormalizationResult`: es `read_raw(Path(capture.stored_path), capture.source)` seguido de `normalize(..., ingested_at=capture.fetched_at)`. Es la función que se pasa como `normalize` a `ingest()`.

- [x] **Paso 1: escribir los tests que fallan**

```python
INGESTED = pd.Timestamp("2026-10-24 18:00")


def test_historico_sample_end_to_end():
    r = normalize(read_raw(FIX / "historico_sample.csv", "historico"), "historico", INGESTED)
    assert r.report["filas_leidas"] == 7
    assert r.report["rechazos_por_motivo"] == {
        "fecha_invalida": 1,
        "fecha_futura": 1,
        "precio_no_positivo": 1,
    }
    assert r.report["filas_validas"] == len(r.rows) == 4
    assert r.report["alertas_por_tipo"] == {"fuera_de_caba": 1, "sin_coordenadas": 1}


def test_rows_match_persistence_contract():
    r = normalize(read_raw(FIX / "historico_sample.csv", "historico"), "historico", INGESTED)
    assert set(r.rows[0]) == {
        "fila_origen",
        "idempresa",
        "empresa",
        "empresabandera",
        "direccion",
        "idproducto",
        "tipo_nafta",
        "idtipohorario",
        "precio",
        "fecha_vigencia",
        "latitud",
        "longitud",
        "fecha_vigencia_original",
        "precio_original",
        "alertas",
    }
    assert {"fila_origen", "motivo"} <= set(r.rejections[0])


def test_keeps_original_values(): ...  # fecha_vigencia_original y precio_original iguales al texto de la fixture


def test_report_is_json_serializable(): ...  # json.dumps(r.report)


def test_ingest_accepts_normalize_capture(engine, tmp_path):
    # fixture `engine` de tests/conftest.py (PR #29)
    ...  # copiar la fixture a tmp_path, armar un RawCapture, ingest(engine, capture, normalize_capture)
    ...  # la ejecución queda succeeded y prices_for_run devuelve 4 filas
```

- [x] **Pasos 2 a 4:** FAIL → implementar → toda la suite en verde.
- [x] **Paso 5:** commit `feat(normalizacion): pipeline con rechazos trazables y contrato con la ingesta` (`Refs #6`).

### Tarea 5: Descarga verificada de capturas

**Archivos:** `nafta2go/adapters/energy_source.py`, `tests/adapters/test_energy_source.py`

**Interfaces:**
- `CATALOG_URL = "http://datos.energia.gob.ar/api/3/action/package_show?id=precios-en-surtidor"`. Va por HTTP porque el portal redirige HTTPS a HTTP; la integridad se cubre con el tamaño y el SHA-256.
- `@dataclass(frozen=True) class Resource: id: str; name: str; url: str; last_modified: str | None; size: int | None`.
- `discover_resources(session) -> dict[str, Resource]`:
  - Claves: `"vigente"` (el nombre contiene "vigentes") e `"historico"` (el nombre, sin acentos, contiene "historicos").
  - Solo considera recursos con `format == "CSV"`.
  - Si falta alguno, lanza `LookupError`.
- `class IncompleteDownload(RuntimeError)`.
- `download(resource: Resource, source: str, root: Path, session) -> RawCapture`:
  - Descarga en streaming a `root/raw/<source>/.<tmp>.part` y calcula el SHA-256 sobre la marcha.
  - Si `size` no es `None`, verifica que los bytes coincidan. Si no coinciden, borra el `.part` y lanza `IncompleteDownload`.
  - Si coinciden, renombra el archivo a `root/raw/<source>/<AAAAMMDDTHHMMSSZ>_<sha256[:12]>.csv` y devuelve el `RawCapture`.

- [x] **Paso 1: escribir los tests que fallan**, con una `FakeSession` como la de `tests/adapters/test_openrouteservice.py`:
  - `test_discovers_vigente_and_historico`
  - `test_missing_resource_raises_lookup`
  - `test_download_stores_raw_and_returns_capture` (comprueba el SHA-256 y el contenido)
  - `test_incomplete_download_leaves_no_files`
- [x] **Pasos 2 a 4:** FAIL → implementar con `session.get(..., stream=True, timeout=(10, 300))` y chunks de 1 MiB → 4 passed.
- [x] **Paso 5:** commit `feat(ingesta): descubrimiento y descarga verificada de capturas crudas` (`Refs #6`).

### Tarea 6: Comando de ingesta, corrida real y documentación

**Archivos:** `nafta2go/normalization/__main__.py`, `docs/NORMALIZACION.md`, `README.md` y, si hace falta, `adr/ADR-006-reglas-de-normalizacion.md`

- `python -m nafta2go.normalization --source {vigente,historico} [--file RUTA]`:
  - Sin `--file`: descubre y descarga.
  - Con `--file`: arma el `RawCapture` desde ese archivo.
  - En los dos casos, después llama a `ingest(create_db_engine(), capture, normalize_capture)` e imprime el `run_id` y el reporte.

- [x] **Paso 1:** implementar el comando.
- [x] **Paso 2:** corrida real del vigente. Esperado: unas 732 filas leídas, casi sin rechazos y unas 184 estaciones. Anotar los números obtenidos, porque cambian con cada actualización de la fuente.
- [x] **Paso 3:** corrida real del histórico (~780 MB, conviene correrla en segundo plano). Esperado con la captura del 2026-10-24:
  - 80.025 filas leídas.
  - Rechazos: `fecha_invalida` = 6, `fecha_futura` = 1, `precio_no_positivo` ≈ 10, `fecha_inconsistente_anio_mes` = 0.
  - Alertas: `sin_coordenadas` = 6, y `fuera_de_caba` y `precio_atipico` mayores que 0.
  - Unas 237 estaciones.
- [x] **Paso 4:** escribir `docs/NORMALIZACION.md` con:
  - El formato real de fecha de cada origen, con un ejemplo.
  - La evidencia de que el histórico usa el día primero (coincide 99,99 % contra 3 %).
  - La explicación de las 84 fechas futuras.
  - La tabla de motivos y alertas con la regla exacta de cada uno.
  - La clave y la regla de duplicados.
  - Cómo correr el comando.
  - Los números de la corrida real.
- [ ] **Paso 5:** ADR-006, solo si el equipo lo considera una decisión estructural. Debe comparar tres alternativas: (a) corregir automáticamente, (b) rechazar o marcar sin corregir (la propuesta) y (c) descartar en silencio. También la decisión sobre la fuente: CSV por HTTP con SHA-256, frente al DataStore (ya no está disponible) y a HTTPS (redirige).
- [x] **Paso 6:** actualizar la tabla de estado del README. Correr `pytest -v`, `ruff check . && ruff format --check .` y `python .github/scripts/check_links.py`.
- [ ] **Paso 7:** abrir la PR contra `dev` con `Closes #6` y pegar en la descripción los reportes de las dos corridas reales.

## Cobertura de los criterios de aceptación

| Criterio | Dónde |
|---|---|
| El formato real de cada fecha está documentado | Tarea 1 (`DATE_FORMAT`) y `docs/NORMALIZACION.md` |
| No quedan fechas futuras injustificadas | Tarea 1 (`fecha_futura`) y Tarea 6, paso 3 (1 rechazada y explicada) |
| Claves candidatas y duplicados con regla explícita | Tarea 2 (`resolve_duplicates`) |
| Coordenadas, productos y precios validados con pruebas reproducibles | Tareas 2 a 4 (tests en CI, sin red) |
| Se conservan los valores originales | Tarea 5 (crudo intacto con SHA-256) y Tarea 4 (`*_original`, `fila_origen`, `rejections`), guardados por POC-06 |

## Dependencias y fuera de alcance

- **Depende de #29 (POC-06)** para `RawCapture`, `NormalizationResult` e `ingest()`. Las tareas 1 a 3 se pueden hacer antes de ese merge.
- Decidir si se recomienda con la cobertura actual o con un escenario histórico es POC-02.
- Arreglar la notebook de exploración, que usa el DataStore que ya no existe, queda para otro momento.
