# Preparación, entrenamiento y evaluación temporal de precios

El primer serving de referencias seleccionadas se describe en [API](API.md) y
[ADR-015](../adr/ADR-015-referencia-servida-y-abstencion-de-alertas.md): reutiliza
la preparación temporal, no carga el modelo no elegido y se abstiene de alertar
con otra selección o sin contexto. La selección auditada habilita ahora la regla
provisional de [ADR-021](../adr/ADR-021-ranking-conservador-por-desvio.md), sin
atribuirle detección de errores validada.

Fuente: precios en surtidor de Secretaría de Energía, CC BY 4.0;
[normalización y alcance](NORMALIZACION.md). Trabajo de #18 y #56; decisión propuesta en
[ADR-013](../adr/ADR-013-evaluacion-temporal-de-precios.md) y
[ADR-014](../adr/ADR-014-seleccion-de-modelo-de-precios.md). Entrena y compara modelos
offline y sirve sólo la referencia elegida, no un modelo. Ninguna referencia ni modelo
reemplaza el precio oficial ni altera el ranking general determinístico. La estimación de precios antiguos
de #57 está integrada aparte del ranking (ADR-020).

## Reproducir sin tocar la base operativa

Crear un directorio local y seleccionar una base separada; instalar las
[dependencias habituales](../README.md#levantar-con-docker) si falta el entorno.
El histórico completo es grande y los datos quedan ignorados por git:

```bash
mkdir -p data
export DATABASE_URL=sqlite:///data/ml-evaluation.db
python -m nafta2go.normalization --source historico --json
python -m nafta2go.ml --cutoff 2026-01-01T00:00:00-03:00 --output data/ml/evaluacion-1
python -m nafta2go.ml --cutoff 2026-01-01T00:00:00-03:00 --output data/ml/evaluacion-2
```

La preparación sólo lee la última ingesta histórica exitosa de esa base; no
migra ni modifica ingestas. La salida debe ser un directorio nuevo. Escribe
`examples.jsonl`, `manifest.json` y `baseline-report.json` mediante staging.
stdout contiene un resumen JSON y los errores no repiten valores ni conexiones.
Puede usarse un CSV histórico ya capturado con `normalization --file RUTA`.
Repetir exactamente requiere la captura original con el mismo hash: descargar
el recurso mutable otra vez puede dar otra versión.

## Datos y evaluación

Cada ejemplo contiene objetivo separado de features, fecha UTC, partición e
identificadores públicos de estación/fila. Excluye geometría fuera de CABA o
faltante y productos/franjas incompatibles. No usa alertas mensuales como
features ni para retirar precios atípicos del objetivo.

La mediana comparable usa observaciones anteriores dentro de treinta días,
producto/franja/zona y respaldo CABA; exige cinco observaciones o se abstiene.
Desde `price-temporal-v2` cada ejemplo también trae la mediana y cantidad de la
última semana para el mercado (producto/franja) y para la misma bandera, con las
mismas exclusiones del instante objetivo. Con la inflación del período, treinta
días quedan desactualizados.
Se informa MAE en ARS/L sobre ejemplos cubiertos, cobertura y abstenciones por
partición. Frecuencia de publicación puede dar mayor peso a algunas estaciones.

El corte separa objetivos por tiempo; observaciones simultáneas no se usan entre
sí. Durante validación se actualiza el contexto con precios ya observados,
sin reentrenar. Codificadores, imputadores y modelos futuros sólo se ajustarán
en train. El archivo usa vigencia como proxy de disponibilidad, sin evidencia
histórica de primera publicación/correcciones: no es un backtest de producción.

El manifiesto registra captura/hash/tamaño, normalización, hash de entradas y
dataset, código Python/requirements, entorno y parámetros. Git es metadato
adicional: puede faltar en la imagen Docker; el hash de archivos permanece.
No tiene aleatoriedad ni modelo aprendido; no se inventa una semilla de entrenamiento.

Faltan validar umbrales de diagnóstico, serving, actualización y monitoreo
(#19, #20). Las issues #18 y #56 siguen abiertas hasta que el equipo revise la
comparación de abajo. Las métricas no habilitan alertas ni prueban precisión de
precios actuales.

## Corrida real del 13/11/2026

[Evidencia](evidencia/ml-baseline-2026-11-13/manifest.json),
[reporte](evidencia/ml-baseline-2026-11-13/baseline-report.json) y
[verificación Docker](evidencia/ml-baseline-2026-11-13/docker-proof.json).
El commit `b20035c` de esa corrida queda preservado por el tag anotado
[`evidencia/ml-baseline-2026-11-13`](https://github.com/estanislaomolina/nafta2go/tree/evidencia/ml-baseline-2026-11-13),
independientemente de los rebases o la eliminación posterior de ramas.
La captura tiene 779.141.214 bytes; normalización conserva 80.056 filas y el
preparador excluye 84 por geometría. Con corte 01/01/2026 en hora Argentina,
ventana de treinta días y mínimo cinco, hay 73.396 ejemplos de train y 3.910
de validación. De 4.002 objetivos de validación, se abstiene en 92; cobertura
97,70 % y MAE del baseline 79,13 ARS/L sobre los cubiertos. Es una única
partición retrospectiva; no prueba disponibilidad real, calidad de un modelo,
alertas correctas ni estimación del precio actual de estaciones antiguas.

Dos ejecuciones locales produjeron ejemplos, manifiesto y reporte idénticos
byte a byte, desde el commit de código limpio registrado. Docker sin red y con
base de sólo lectura reprodujo hashes de entradas/dataset/código y las métricas,
aun con las versiones de entorno registradas por separado. No se commitean
archivo crudo, base ni ejemplos grandes; conservarlos localmente para repetir
con el mismo origen. No se modificó la base operativa ni se crearon recursos AWS.

## Comparación de modelos del 15/11/2026

[ADR-014](../adr/ADR-014-seleccion-de-modelo-de-precios.md) define el protocolo. Sobre
un dataset `price-temporal-v2`:

```bash
python -m nafta2go.ml.train --dataset data/ml/evaluacion-1 --output data/ml/modelos-1
```

El comando verifica el hash del dataset contra su manifiesto, entrena Ridge y árboles
potenciados con un solo hilo y semilla fija, elige el método con 2025 (dentro de train)
y recién después informa todos en la validación. Escribe `model.joblib` (el mejor
modelo, aunque no sea el elegido), `validation-predictions.jsonl`, `manifest.json` y
`model-report.json` con métricas y análisis de errores por segmento.

[Evidencia](evidencia/ml-modelos-2026-11-15/model-report.json) con la captura
`950f748f…28bb` (778.654.156 bytes, anterior a la de la corrida del 13/11, por eso
3.862 ejemplos de validación en lugar de 3.910), corte 01/01/2026 y código `f0e6c3f`.
Dos corridas completas, dataset y modelo, produjeron archivos idénticos byte a byte, y
recargar el artefacto reproduce sus predicciones.

**Corrección del 17/11/2026 (#119):** `market_change` comparaba medianas de ámbitos
distintos (zona contra CABA) cuando cambiaba el ámbito entre dos ejemplos de la misma
estación. Ahora queda vacío en ese caso. La tabla muestra la
[corrida corregida](evidencia/ml-modelos-2026-11-17/README.md), con el mismo dataset y
código `cef0c9a`. Las referencias no cambian, y la elección tampoco.

| Método | Selección 2025: MAE ARS/L | Error rel. | Validación 2026: MAE ARS/L | Error rel. |
|---|---|---|---|---|
| Mediana de 30 días (dataset) | 45,73 | 3,12 % | 79,72 | 3,89 % |
| Último precio de la estación | 25,40 | 1,73 % | 39,12 | 1,91 % |
| **Mediana de la bandera, última semana** | **20,62** | **1,42 %** | 41,21 | 2,01 % |
| Ridge | 35,30 | 2,49 % | **31,00** | **1,52 %** |
| Árboles potenciados | 24,24 | 1,70 % | 31,90 | 1,56 % |

Lectura:

- **El método elegido es una referencia, no un modelo**: la mediana de la bandera de la
  última semana gana en 2025. Según #56, el diagnóstico usaría esa referencia.
- En la validación 2026 los dos modelos superan a todas las referencias: erran entre
  un 18 % y un 21 % menos que el último precio, la mejor referencia de ese año.
  El resultado se informa pero no cambia la elección: hacerlo sería elegir con datos
  reservados. Un solo año de selección puede no representar al siguiente (ADR-014).
- Las features de la última semana mejoran a los modelos: con el dataset v1, los
  árboles daban 40,83 en validación y Ridge 35,35.
- Referencia y modelo fallan en casos opuestos (validación, MAE ARS/L): con último
  precio de hasta 7 días, la bandera da 53,7 y los árboles 24,0; con último precio de
  más de 30 días, la bandera da 23,7 y los árboles 56,0. Combinarlos es una mejora
  candidata, a evaluar con datos nuevos.
- YPF tiene solo 36 ejemplos en la validación 2026; sus métricas por bandera no son
  concluyentes.

El serving de ADR-015 usa la referencia elegida para #19. Evaluar otra selección
requiere un protocolo explícito y otro período de evaluación; no se cambia la
elección por las métricas de validación ya inspeccionadas.

## Evaluación de umbrales candidatos (MVP-05)

`python -m nafta2go.ml.evaluate_alerts --dataset DIR --model DIR --output DIR`
requiere además `--audit-start` (fecha ISO con zona) y `--quantile` (entre 0 y 1).
No hay cuantil ni corte predeterminados: fijarlos antes de examinar la auditoría.
La validación del dataset se divide en calibración anterior al corte y auditoría
posterior; el entrenamiento y selección previos no cambian. La porción usada para
calibrar deja de ser una validación independiente. No reajustar con la auditoría.

El reporte `alert-evaluation.json` conserva hashes y evalúa por producto/franja
la desviación relativa respecto de la referencia elegida, con el mismo fallback y
redondeo que la API. Usa cuantil empírico por rango superior y excedencia estricta;
`--min-examples` exige por defecto 30 ejemplos en cada período por segmento.
Sin soporte informa abstención; sin algún ejemplo en ambos períodos falla. La
salida debe ser nueva y se publica mediante staging/renombrado.

Es un reporte fuera de producción (`runtime_enabled=false`), sin ubicaciones,
filas individuales ni carga del pickle no elegido. La tasa de excedencias no es
precisión, recall ni probabilidad de error del precio. Una corrida sintética sólo
verifica el software. Falta evaluar el histórico real y revisar la política antes
de activar alertas o ranking conservador; [ADR-017](../adr/ADR-017-evaluacion-temporal-de-umbrales.md).

## Auditoría real del 17/11/2026

La [evidencia de auditoría](evidencia/alertas-precios-2026-11-17/README.md) conserva
el protocolo previo, manifiestos recibidos, reporte y reproducción exacta. Con
cuantil 0,95 se obtienen candidatos de 5,4244% para súper y 5,4570% para premium:
0 excedencias en 574 ejemplos auditados. No valida sensibilidad ni una política
para producción; las franjas contienen publicaciones relacionadas entre sí.
El ranking sigue siendo determinístico y `runtime_enabled=false`. #19/#20 siguen
abiertos. La comparación nominal/relativa del baseline v2 se documenta por separado
para responder al seguimiento de #100 sin confundir capturas v1 y v2.

## Precios de más de 30 días (#57)

`python -m nafta2go.ml.evaluate_stale --dataset DIR --output DIR --selection-start ISO`
evalúa estimaciones sobre **reingresos**: publicaciones cuyo precio previo propio
tiene más de 30 días. Elige el método con el período de selección dentro de train y
recién después reporta la validación por tramo de antigüedad; un tramo con menos de
`--min-examples` casos se informa sin métricas. Es un reporte offline
(`runtime_enabled=false`) que no carga modelos guardados ni cambia la API.

La [evidencia del 17/11/2026](evidencia/estimacion-antiguos-2026-11/README.md), con
protocolo previo y dos corridas idénticas, elige la mediana reciente de la bandera:
MAPE 1,14 % frente a 2,37 % de mostrar el precio viejo, sobre 768 reingresos de 2026.
La corrección de `market_change` (#119) no cambia la elección ni la adopción; ver la
[corrección](evidencia/estimacion-antiguos-2026-11/README.md#corrección-de-119).
[ADR-020](../adr/ADR-020-estimacion-de-precios-antiguos.md) propone una estimación
rotulada sólo para precios de 31 a 120 días, separada del precio oficial y fuera del
ranking normal. El proxy no observa estaciones cuyo precio no cambió; todavía no se
integró en la API ni en la web.


## Preparar el serving sin modificar la base operativa

Recibir `examples.jsonl` y los manifiestos no carga publicaciones en SQLite.
El diagnóstico requiere ingestas exitosas `historico` y `vigente` de la misma
base, reglas compatibles y el original histórico con el hash del modelo.
La comprobación del 21/11 encontró sólo `vigente` en la base operativa y recibió
503 seguros; no se ejecutó allí una carga histórica para obtener una medición.

Para preparar una base aislada con el original histórico ya capturado:

```bash
export DATABASE_URL=sqlite:///data/serving-ensayo.db
python -m nafta2go.normalization --source historico --file "$HISTORICAL_CSV" --json
python -m nafta2go.normalization --source vigente --file "$CURRENT_CSV" --json
export NAFTA2GO_PRICE_DATASET_DIR="$DATASET_DIR"
export NAFTA2GO_PRICE_MODEL_DIR="$MODEL_DIR"
```

Las rutas designan los originales y directorios recibidos; no se incluyen en Git.
Validar antes los hashes contra los manifiestos: descargar de nuevo una fuente
mutable puede dar otro histórico y no habilitará la política anterior. No cambiar
metadatos ni hashes para forzar compatibilidad. Sin el original adecuado, conservar
la abstención o preparar una nueva selección/auditoría versionada.

Verificar el diagnóstico autenticado sobre esa misma base antes de usarla en el
despliegue. La disponibilidad general de la API no implica disponibilidad de ML.
La carga histórica y los directorios deben incorporarse al procedimiento de #22/#59;
ninguno de estos pasos crea recursos AWS. La prueba de rendimiento sintética de
[VALIDACION](VALIDACION.md#costo-del-diagnóstico-activo-con-veinte-candidatas)
no sustituye esta preparación con datos reales.

## Registro de modelos y campeón (#161)

[ADR-030](../adr/ADR-030-registro-de-modelos-versionado.md). El registro es
[`nafta2go/ml/registry.json`](../nafta2go/ml/registry.json) y se versiona en Git.
Cada corrida se identifica por el SHA-256 de su manifiesto de modelo y guarda:

- parámetros y linaje: hashes del dataset y del histórico, y commit;
- el MAE de selección y de validación de cada candidato, marcado como `reference` o
  `model`;
- los hashes de `model.joblib` y de las predicciones;
- la política de alertas para la que fue auditada, si la hay.

```bash
python -m nafta2go.ml.registry show
python -m nafta2go.ml.registry register --manifest "$MODEL_DIR/manifest.json" \
  --report "$MODEL_DIR/report.json" \
  [--policy conservative-v1 --audit "$AUDIT_DIR/alert-evaluation.json"]
python -m nafta2go.ml.registry promote --run <sha256-del-manifiesto>
```

**Campeón y retadores.** El campeón actual es `bandera_reciente` de la corrida del
22/11 (`b65d2d54…`). Ridge y boosting de esa corrida son retadores: quedan
registrados con sus métricas, pero no se sirven.

**Promoción.** Gana el menor MAE de selección; la validación de 2026 nunca se usa
para elegir (ADR-014). Una promoción se rechaza sin tocar el archivo en estos casos:
- la corrida no conserva el reporte;
- el método elegido no es el ganador;
- la corrida no fue auditada para la política del método.

**Auditoría obligatoria.** Una corrida queda asociada a una política solo si se
registra con su `alert-evaluation.json`. El registro verifica que esa auditoría:
- corresponda al SHA de la corrida;
- use el método de la política;
- tenga los mismos umbrales por producto que sirve `domain/price_alert.py`.

Si la etiqueta de la política no viene acompañada de esa evidencia, la corrida se
rechaza. Por eso cambiar un alias no puede habilitar los umbrales de
`conservative-v1` para otro modelo. Para revertir se vuelve a promover la corrida
anterior.

**Serving.** El diagnóstico sirve solo la corrida del alias `champion`.
- **Dónde busca el manifiesto:** `NAFTA2GO_PRICE_MODEL_DIR` puede ser un almacén
  con una carpeta por versión (`<sha256>/manifest.json`), y entonces se usa la del
  campeón. Si no, se usa una carpeta simple, que tiene que contener exactamente el
  manifiesto del campeón. El dataset se resuelve igual, por el SHA de su manifiesto.
- **Si lo configurado no es el campeón:** el diagnóstico responde no disponible, en
  lugar de servir otra versión. Promover o revertir el alias cambia la versión
  servida sin tocar el código.
- **Alertas:** las emite `domain/price_alert.py` solo para las corridas con
  auditoría verificada, que hoy son `91cb07a3…` y `b65d2d54…`.

**Lo que no se conserva.** Está inventariado en el campo `missing` del registro:
- la corrida del 13/11 fue solo el baseline, sin manifiesto de modelo;
- la corrida auditada `91cb07a3…` no tiene el reporte de selección en el repositorio,
  así que está registrada pero no se puede promover;
- `model.joblib` y las predicciones de todas las corridas están fuera de Git;
- Ridge no guarda artefacto, porque solo se serializa el mejor modelo aprendido.

Nada de esto se reconstruyó.
