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

El reporte de la corrida con código fijado se incorpora por separado. La instancia
AWS sigue con su versión anterior hasta review e integración de las dependencias.
