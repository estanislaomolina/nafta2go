# Preparación y baseline temporal de precios — MVP-04 en progreso

Fuente: precios en surtidor de Secretaría de Energía, CC BY 4.0;
[normalización y alcance](NORMALIZACION.md). Trabajo de #18 y #56; decisión propuesta en
[ADR-013](../adr/ADR-013-evaluacion-temporal-de-precios.md). No entrena ni sirve
un modelo todavía. La mediana es baseline estadístico; no reemplaza precio
oficial, no altera el recomendador y no habilita estimaciones antiguas de #57.

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

Faltan entrenar y comparar modelos sobre estos mismos ejemplos, análisis de
errores, validación de umbrales y artefactos de inferencia/actualización/monitoreo.
Las issues #18, #19, #20 y #56 siguen abiertas. Las métricas de baseline no
habilitan alertas ni prueban mejora ML o precisión de precios actuales.

## Corrida real del 13/11/2026

[Evidencia](evidencia/ml-baseline-2026-11-13/manifest.json),
[reporte](evidencia/ml-baseline-2026-11-13/baseline-report.json) y
[verificación Docker](evidencia/ml-baseline-2026-11-13/docker-proof.json).
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
