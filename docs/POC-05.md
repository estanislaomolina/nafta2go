# POC-05: consulta explicada de punta a punta

Implementa [#10](https://github.com/estanislaomolina/nafta2go/issues/10):
normalización → ingesta → SQLite → cobertura → rutas → motor → alternativas →
registro. La interfaz de la POC es un comando; la web y la API quedan para el MVP.

## Ejecutar sin red ni credenciales

Desde la raíz, con Python 3.12 y `requirements-dev.txt` instalado:

```bash
DATABASE_URL=sqlite:////tmp/nafta2go-demo-entrega2.db python -m nafta2go.query \
  --origin=-34.6037,-58.3816 --destination=-34.5627,-58.4565 \
  --matrix-file docs/evidencia/poc-05-flujo-2026-10-26/matrix.json
```

Usar una base nueva en ese comando activa el **escenario histórico de precios del
24/10/2026**, rotulado en la salida. La matriz fue obtenida de ORS el 26/10/2026:
son rutas reales guardadas, no una simulación del tránsito del 24/10. La vigencia
se mide contra la fecha fija del escenario. No se ingiere ese escenario como una
captura vigente. La matriz solo sirve para esas coordenadas y ese orden de
candidatas; cualquier diferencia falla explícitamente.

La reproducción también está automatizada en el check `Contenedores`:

```bash
docker compose build
docker compose run --rm query \
  --origin=-34.6037,-58.3816 --destination=-34.5627,-58.4565 \
  --matrix-file docs/evidencia/poc-05-flujo-2026-10-26/matrix.json
```

El volumen conserva la base. Una ingesta actual con cobertura puede elegir otras
estaciones; en ese caso hay que usar rutas en vivo o una matriz de esa selección.

## Ejecutar con captura y rutas en vivo

```bash
python -m nafta2go.normalization --source vigente
# Completar ORS_API_KEY en .env, que está ignorado por Git.
set -a
source .env
set +a
python -m nafta2go.query \
  --origin=-34.6037,-58.3816 --destination=-34.5627,-58.4565
```

La consulta no descarga precios: utiliza la última ingesta vigente exitosa. Si
no alcanza la cobertura, aplica el respaldo de [COBERTURA](COBERTURA.md). Solo
llama a ORS cuando hay candidatas suficientes; sin cobertura no necesita clave.
Los errores de credencial, cuota, timeout, matriz o base se informan como errores,
sin inventar recomendaciones. No hay reintentos automáticos que consuman cuota.

Opciones: `--presupuesto`, `--consumo`, `--capacidad`, `--litros-iniciales`,
`--reserva`, `--fuel-type super|premium`, `--schedule-id 2|3`, `--reference-at`
(ISO con zona), `--json` y `--save-matrix RUTA`. Sin destino, se evalúa la vuelta
al origen. Guardar una matriz conserva las coordenadas de esa consulta: la opción
es explícita y no se usa para registrar ubicaciones en el historial de usuarios.

El código de salida es 0 para una consulta procesada, incluso si explica falta
de cobertura o de estaciones factibles, y 2 para entradas o servicios fallidos.

## Prioridades y explicación

Solo participan candidatas factibles. El ranking de la POC es determinístico:

1. **Combustible neto:** mayor ganancia neta en litros; desempata por menor
   desvío en km, menor tiempo extra e identificador de estación.
2. **Menor desvío:** menor distancia extra, luego menor tiempo extra, mayor
   ganancia neta e identificador.
3. **Equilibrio:** normaliza a [0, 1] la ganancia neta y los km extra entre las
   candidatas factibles, y maximiza `ganancia_normalizada - desvio_normalizado`.
   Esto da el mismo peso a ambos objetivos. Un rango constante aporta cero;
   desempata como combustible neto. Es una regla de la POC, no un modelo de ML.

Si una estación gana varias prioridades, aparece una sola vez con sus etiquetas.
Así se devuelven hasta tres alternativas, sin forzar ganadoras diferentes. La
salida incluye dirección, bandera, precio publicado, fecha, litros comprados,
costo, consumo, ganancia neta, combustible final, reserva, desvío, alertas y fuente.
El JSON conserva la precisión de cálculo y todas las evaluaciones y descartes;
la terminal redondea solo para mostrar.

`application.query.recommend` registra también el resultado y la versión del
motor. Con precios vigentes conserva `data_run_id`; con escenario conserva su
identificador, fecha y hashes, sin inventar una ingesta. La migración `0002`
exige exactamente uno de esos orígenes. No guarda origen ni destino del usuario.

## Evidencia real del 26/10/2026

- [Matriz real completa](evidencia/poc-05-flujo-2026-10-26/matrix.json): una
  solicitud autenticada, 11 × 11, sin pares ausentes; coordenadas, unidades,
  endpoint y fecha conservados. No contiene la credencial.
- [Resultado histórico](evidencia/poc-05-flujo-2026-10-26/historical-result.json):
  base temporal nueva, respaldo de precios rotulado y rutas consultadas en vivo.
- [Normalización e ingesta real](evidencia/poc-05-flujo-2026-10-26/ingestion.json):
  CSV oficial completo del 24/10, SHA-256 verificado, normalización real y
  escritura en otra base temporal migrada.
- [Resultado desde esa ingesta](evidencia/poc-05-flujo-2026-10-26/current-result.json):
  16 estaciones recientes dentro del corredor al momento de la consulta, diez
  evaluadas con la matriz real guardada y recomendación persistida verificada.
  Los IDs de ejecución y recomendación pertenecen a esas bases temporales.

En ambos casos gana la estación **3765, Shell, Av. Córdoba 3710** para las tres
prioridades: precio publicado ARS 2189/L, compra estimada 5,482 L, consumo del
recorrido 1,064 L, combustible final 14,418 L y desvío de 0,409 km. Son resultados
del caso y fechas registrados; no acreditan precio ni stock para otra fecha.

## Verificación y límites

```bash
pytest -q
ruff check .
ruff format --check .
```

Las pruebas no usan red: cubren las tres prioridades, agrupación y desempates,
ingesta, persistencia, falta de cobertura, rutas ausentes, timeout, entradas
inválidas y reproducción exacta de las evaluaciones reales guardadas. También
prueban que la migración conserva recomendaciones anteriores y que el registro
no contiene las ubicaciones del conductor.

Persisten las simplificaciones declaradas: diez candidatas, prefiltro geográfico
en línea recta, rectángulo de CABA, ingesta manual, escenario fijo, sin ML ni web.
El límite numérico de más de 28 cifras significativas sigue registrado en
[#34](https://github.com/estanislaomolina/nafta2go/issues/34).
