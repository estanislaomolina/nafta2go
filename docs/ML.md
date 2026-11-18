# Preparación, entrenamiento y evaluación temporal de precios

El primer serving de referencias seleccionadas se describe en [API](API.md) y
[ADR-015](../adr/ADR-015-referencia-servida-y-abstencion-de-alertas.md): reutiliza
la preparación temporal, no carga el modelo no elegido y se abstiene de alertar
hasta validar umbrales. Es un incremento parcial de #19.

Fuente: precios en surtidor de Secretaría de Energía, CC BY 4.0;
[normalización y alcance](NORMALIZACION.md). Trabajo de #18 y #56; decisión propuesta en
[ADR-013](../adr/ADR-013-evaluacion-temporal-de-precios.md) y
[ADR-014](../adr/ADR-014-seleccion-de-modelo-de-precios.md). Entrena y compara modelos
offline, pero todavía no sirve ninguno. Ninguna referencia ni modelo reemplaza el precio
oficial, altera el recomendador o habilita estimaciones antiguas de #57.

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

| Método | Selección 2025: MAE ARS/L | Error rel. | Validación 2026: MAE ARS/L | Error rel. |
|---|---|---|---|---|
| Mediana de 30 días (dataset) | 45,73 | 3,12 % | 79,72 | 3,89 % |
| Último precio de la estación | 25,40 | 1,73 % | 39,12 | 1,91 % |
| **Mediana de la bandera, última semana** | **20,62** | **1,42 %** | 41,21 | 2,01 % |
| Ridge | 35,37 | 2,49 % | **31,24** | **1,53 %** |
| Árboles potenciados | 22,69 | 1,59 % | 31,39 | 1,53 % |

Lectura:

- **El método elegido es una referencia, no un modelo**: la mediana de la bandera de la
  última semana gana en 2025. Según #56, el diagnóstico usaría esa referencia.
- En la validación 2026 los dos modelos superan por un 20 % a todas las referencias.
  El resultado se informa pero no cambia la elección: hacerlo sería elegir con datos
  reservados. Un solo año de selección puede no representar al siguiente (ADR-014).
- Las features de la última semana mejoran a los modelos: con el dataset v1, los
  árboles daban 40,83 en validación y Ridge 35,35.
- Referencia y modelo fallan en casos opuestos (validación, MAE ARS/L): con último
  precio de hasta 7 días, la bandera da 53,7 y los árboles 23,3; con último precio de
  más de 30 días, la bandera da 23,7 y los árboles 57,4. Combinarlos es una mejora
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
[ADR-020](../adr/ADR-020-estimacion-de-precios-antiguos.md) propone una estimación
rotulada sólo para precios de 31 a 120 días, separada del precio oficial y fuera del
ranking normal. El proxy no observa estaciones cuyo precio no cambió; todavía no se
integró en la API ni en la web.
