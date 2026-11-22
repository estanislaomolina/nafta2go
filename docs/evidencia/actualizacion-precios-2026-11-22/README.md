# Actualización del histórico disponible — 22/11/2026

Para preparar AWS se descargó el recurso histórico oficial actual. Sus 779.141.214
bytes tienen SHA-256 `5a03269876a0facd38290938fcc580d6cf03fdae30264e5549affde22e3a1e70`.
No coincide con la captura del 24/10 recibida de Felipe (778.654.156 bytes,
`950f748f881c95ea5bf9511a0c0ea120d6fc9a28345052ad46c8fc5d41f528bb`). No se
modificaron los manifiestos originales ni se declara que sea la misma captura.
La normalización en una copia aislada pasó: 80.056 filas válidas, 17 rechazadas.

## Protocolo y reproducción

[Protocolo](protocolo.json) fijado en af00cab antes de ajustar modelos/evaluar los
umbrales nuevos. Ya se habían observado preparación/baseline y resultados de 2026
anteriores; no es una validación ciega ni prospectiva. Se mantuvieron cortes,
semilla, candidatos y cuantil del protocolo anterior. Los archivos grandes y la
base están fuera de Git. Con el original identificado y una base aislada:

```bash
python -m nafta2go.normalization --source historico --file "$HISTORICAL_CSV" --json
python -m nafta2go.ml --cutoff 2026-01-01T00:00:00-03:00 --output "$DATASET_DIR"
python -m nafta2go.ml.train --dataset "$DATASET_DIR" --output "$MODEL_DIR" \
  --selection-start 2025-01-01T00:00:00-03:00 --seed 0
python -m nafta2go.ml.evaluate_alerts --dataset "$DATASET_DIR" --model "$MODEL_DIR" \
  --output "$AUDIT_DIR" --audit-start 2026-07-01T00:00:00-03:00 \
  --quantile 0.95 --min-examples 30
```

Usar un directorio de salida nuevo en cada corrida. Repetir el entrenamiento y la
auditoría. [Reproducción](reproduccion.json): manifiestos, reporte, artefacto,
predicciones y auditoría dieron hashes idénticos; la preparación produjo los mismos
bytes de ejemplos. La procedencia completa está en los manifiestos.

## Resultado

[Dataset](dataset-manifest.json): 73.396 ejemplos de entrenamiento y 3.910 de
validación. [Selección](model-manifest.json), [reporte](model-report.json): sigue
`bandera_reciente`, elegida sobre el período de selección de 2025. El MAE de
selección es 20,617 ARS/L frente a 24,243 del mejor modelo aprendido. No se cambia
la selección mirando el MAE de validación, donde otros métodos obtienen menor error.
El artefacto de boosting no se carga en serving ni sustituye el precio oficial.

[Auditoría](alert-evaluation.json): los umbrales coinciden exactamente con los
anteriores. Hay seis excedencias entre 622 observaciones (tres por franja premium),
con franjas correlacionadas. No hay etiquetas de errores: no se mide precisión,
sensibilidad ni normalidad. `runtime_enabled=false` describe el experimento.

Se propone admitir el hash exacto del manifiesto nuevo además del anterior,
conservando `conservative-v1` porque no cambian método/umbrales. Sigue siendo
obligatoria la coincidencia entre la captura y su propio modelo; cualquier otra
selección se abstiene. Esta propuesta requiere review antes de usarla en AWS.

## Rendimiento y pendientes

[Prueba inicial](latencia-inicial.json) sobre la base real aislada, API en proceso
y rutas sintéticas: veinte evaluaciones y veinte diagnósticos disponibles, 14,292 s.
No es una medición de red, ORS, AWS ni p95. Supera el objetivo de cinco segundos:
se debe resolver el costo de construir veinte veces el contexto histórico antes de
activar esta combinación en el host chico. La base AWS sigue sin esta selección;
la programación de encendido es independiente y no se alteró por este experimento.
