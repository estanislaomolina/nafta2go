# Diagnóstico por lote con histórico real — 22/11/2026

La prueba inicial de #149 midió 14,292 s para veinte diagnósticos, con rutas
sintéticas. Se conservó después una salida individual completa de veinte
publicaciones: 12,594 s. La versión por lote conservó exactamente esos veinte
resultados y midió inicialmente 0,655 s en el mismo entorno local.

Se lee una vez el histórico del producto/franja y se recorre por instante. Los
objetivos no se agregan al contexto: una publicación actual no afecta a otra,
aunque sus fechas sean diferentes. Las publicaciones históricas del mismo instante
se incorporan sólo después de evaluar el grupo. La preparación de entrenamiento
por defecto produjo el mismo SHA de ejemplos que antes de la optimización:
`a6524b88d6fb900f69aed42c2001105ac3db32a332c2ac7029058cbcbf80ab58`.

La comparación utiliza el histórico real identificado por #149, la copia local
normalizada y veinte candidatas con todos sus diagnósticos disponibles. API en
proceso y rutas sintéticas: no mide ORS, red del cliente, AWS ni p95 poblacional.
Los originales, base y respuestas completas permanecen locales; el hash de los
veinte diagnósticos permite contrastar la igualdad sin publicar la base.

La [corrida con código fijado](comparacion.json) `017fd40` repitió cinco solicitudes
con igualdad exacta de los veinte diagnósticos; p95 observado por rango más cercano
0.300 s. Cinco observaciones no estiman un p95 poblacional. La instancia
AWS sigue con su versión anterior hasta review e integración de las dependencias.


Para reproducir, preparar una base aislada con las dos ingestas y configurar los
manifiestos indicados en #149. La herramienta copia SQLite usando modo de lectura;
no escribe en la base fuente y las solicitudes se guardan sólo en la copia temporal:

```bash
python scripts/measure_real_history_diagnostics.py --database "$SQLITE_FILE" \
  --reference-at 2026-11-22T02:20:21.931183+00:00 --output medicion.json
```

Usar la fecha exacta del reporte conservado para comparar sus veinte publicaciones.
Los datos y las latencias pueden cambiar con otros archivos, parámetros o equipo.
La herramienta informa fallo si no obtiene veinte diagnósticos disponibles; una
respuesta correcta sin histórico no cuenta como éxito del ensayo.
