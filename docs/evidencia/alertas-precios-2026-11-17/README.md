# Auditoría real de candidatos de alerta — 17/11/2026

Se recibió el paquete de Felipe `ml-precios-v2-2026-11-15.tar.gz`. Archivo,
`examples.jsonl`, modelo y predicciones permanecen locales y fuera de Git. Sus
hashes y la [recepción](recepcion.json) identifican las entradas sin modificarlas.
Los manifiestos recibidos figuran `git_dirty=true`, a diferencia de los publicados
el 15/11. El hash de archivos de código, datos, modelo y predicciones coincide;
la diferencia de metadata y del enlace entre manifiestos se conserva explícita.

## Protocolo y reproducción

[Protocolo](protocolo.json) fijado en b442de2 antes de calcular esta auditoría:
selección de método congelada, cuantil 0,95, corte local 01/07/2026 y mínimo 30.
El año 2026 ya había sido evaluado globalmente; no es una prueba prospectiva ni
una auditoría ciega nueva. No se modificaron los parámetros después del resultado.

Desde el tag `evidencia/alertas-precios-2026-11-17`, con las dependencias instaladas
y las carpetas originales recibidas, ejecutar dos veces en salidas nuevas:

```bash
python -m nafta2go.ml.evaluate_alerts \
  --dataset "$DATASET_DIR" --model "$MODEL_DIR" --output "$OUTPUT_DIR" \
  --audit-start 2026-07-01T00:00:00-03:00 --quantile 0.95 --min-examples 30
```

[Reproducción](reproduccion.json): ambas corridas produjeron bytes idénticos, SHA-256
`00e7168eb658f54851cb22ed1d6b6b1edeafc8cc639172b8fdf92ac046b15fd9`.
Comparar `alert-evaluation.json` con `cmp` y `sha256sum`. El tag conserva el commit
limpio exacto del reporte; ejecutar desde otro commit cambia su procedencia aunque
la lógica sea la misma. No se cargó el pickle ni se modificó la base operativa.

## Resultados y alcance

[Reporte del evaluador](alert-evaluation.json): 3.288 ejemplos de calibración
(70 estaciones) y 574 de auditoría (61 estaciones), hasta el 23/10/2026. Los cuatro
segmentos superan el mínimo. Para súper (producto 2), ambas franjas dan un umbral
relativo de 5,4244%; para premium (producto 3), 5,4570%. En cada franja se auditan
150 ejemplos de súper y 137 de premium. **No hay excedencias en la auditoría.**

Los ejemplos no son 574 observaciones independientes: hay 288 grupos distintos
estación/producto/instante, porque existen publicaciones en distintas franjas.
Los perfiles cuentan esos grupos sin franja y fechas UTC; no equivalen a una
corrección estadística por dependencia ni a intervalos de confianza.

El resultado no mide detección de errores: no hay etiquetas de precios erróneos
ni positivos auditados que permitan estimar sensibilidad. No se infiere precisión,
recall ni una garantía del 95%. Se mantiene `runtime_enabled=false`: #19 y #20
siguen pendientes de una política revisada e integración; no se excluyen estaciones.

## Brecha nominal del baseline

[Comparación](baseline-comparison.json) sobre el mismo dataset v2: la mediana previa
pasa de MAE 21,80 a 79,72 ARS/L entre train y validación, mientras el MAPE pasa de
5,39% a 3,89%. El precio publicado medio pasa de 454,18 a 2.048,86 ARS/L. La cobertura
es 96,61%/97,67%, con 2.574/92 abstenciones. El MAE de validación coincide con el
reporte original recibido. MAPE usa precio publicado como denominador; el score
del candidato usa la referencia. Son medidas distintas y no se intercambian.

El MAE nominal aislado no permite concluir peor error proporcional; hay cambios
de escala y composición entre períodos. Esto no demuestra que la inflación sea
la única causa. La captura v1 anterior tenía 3.910 ejemplos de validación y MAE
79,13: no se reemplaza aquel resultado por el v2 de 3.862 ejemplos.

Para repetir la comparación, agrupar `examples.jsonl` por `partition`, calcular
`abs(target_price_ars_per_l - features.prior_median)` y su cociente por el precio
publicado; promediar sobre ejemplos cubiertos. Cobertura/abstenciones proceden del
`baseline-report.json` recibido. No se entrenó ni seleccionó un método nuevo.
