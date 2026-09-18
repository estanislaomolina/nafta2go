# Propuesta 1: Recomendación de estaciones según presupuesto, autonomía y recorrido

## Problema a resolver

Un precio por litro menor puede no compensar el combustible y el tiempo del desvío. Se propone ayudar a conductores particulares y trabajadores que usan automóvil a elegir dónde cargar nafta en CABA.   
La solución considerará simultáneamente el precio publicado, el presupuesto disponible, la autonomía del vehículo, la capacidad del tanque y el costo adicional del recorrido hasta la estación.

## Usuarios/actores del sistema

El conductor aporta ubicación, destino opcional, presupuesto, tipo de nafta, consumo estimado, litros restantes y capacidad del tanque. El operador del sistema supervisa la ingesta, la calidad de los datos y los modelos.

## Solución propuesta a alto nivel

Una aplicación web comparará hasta 20 estaciones candidatas. El motor de recomendación será determinístico y calculará, para cada estación:

* Si puede alcanzarse conservando una reserva mínima configurable.  
* El combustible estimado necesario para llegar a la estación y completar el recorrido.  
* La capacidad disponible del tanque al momento de la carga.  
* Los litros que pueden comprarse de acuerdo con el presupuesto, el precio y la capacidad disponible.  
* La distancia y duración adicionales respecto del recorrido original.

Cuando el usuario indique un destino, se comparará el recorrido origen-estación-destino con el recorrido directo origen-destino. Cuando no indique destino, se evaluará el recorrido origen-estación-origen.  
El sistema descartará estaciones incompatibles por tipo de combustible, autonomía, presupuesto, capacidad del tanque, vigencia del precio o imposibilidad de calcular una ruta. Como resultado, mostrará hasta tres alternativas explicadas:

1. Mayor combustible neto al finalizar el recorrido.  
2. Menor distancia o tiempo adicional.  
3. Mejor equilibrio entre combustible neto y desvío, según la prioridad seleccionada por el usuario.

El recomendador no será un modelo de machine learning, sino un mecanismo de optimización basado en reglas, restricciones y cálculos reproducibles.  
El componente de machine learning tendrá una función diferente: estimará un precio de referencia y un nivel de confianza para cada precio publicado. Su objetivo será identificar cuándo una recomendación depende de un precio potencialmente atípico respecto de su contexto histórico, geográfico y comercial. El precio oficial no será sustituido por una predicción ni se afirmará que un valor señalado sea incorrecto.  
El diagnóstico del modelo tendrá un efecto visible en el producto. Las recomendaciones que dependan de precios de baja confianza mostrarán una advertencia, y el usuario podrá comparar el resultado general con un ranking conservador que excluya esas observaciones.  
Siempre se informarán la fuente, la fecha de vigencia, la fecha de consulta y las limitaciones de los datos.  
La solución utilizará una arquitectura por capas, con una aplicación web, una API, un motor de recomendación, un componente de diagnóstico de precios y adaptadores para las fuentes de datos y el proveedor de rutas. Un proceso programado realizará la ingesta diaria.  
PostgreSQL almacenará estaciones, productos, precios normalizados, ejecuciones de ingesta, resultados de calidad, consultas anonimizadas y metadatos de los modelos. Los archivos originales, conjuntos procesados y artefactos de modelos se conservarán en almacenamiento de objetos con versionado y trazabilidad.  
El proyecto integrará ingeniería de datos, calidad y trazabilidad, machine learning en producción y observabilidad. Contará con pruebas automatizadas, integración y despliegue continuos, contenedores, configuración externa y preparación para infraestructura cloud. También dispondrá de un procedimiento documentado de ejecución local.  
Las funciones administrativas requerirán autenticación. Las ubicaciones ingresadas por los usuarios no se conservarán por defecto. Se medirán, entre otros indicadores, la duración y los fallos de las consultas, la cobertura y antigüedad de los precios, el estado de las ingestas y el comportamiento del modelo.

## Fuentes de dato identificadas

[Precios y geolocalización](https://datos.energia.gob.ar/api/3/action/package_show?id=precios-en-surtidor): La Secretaría de Energía ofrece datos públicos mediante archivos CSV y una API CKAN, sin necesidad de credenciales. El catálogo declara una licencia CC BY 4.0.  
En la exploración inicial se descargó el CSV vigente completo, compuesto por 36.667 filas y aproximadamente 9,27 MB. La selección correspondiente a CABA contiene 1.630 filas y 221 valores diferentes de idempresa. Todas las filas analizadas presentan coordenadas dentro de un recuadro geográfico compatible con CABA. No se verificó individualmente el acceso físico a cada estación.  
En la selección analizada, la combinación idempresa \+ idproducto \+ idtipohorario no presenta duplicados. Antes de utilizarla como clave lógica se verificará documental y empíricamente qué entidad representa idempresa y si identifica de manera estable una estación física.  
La fuente incluye dirección, bandera, producto, franja horaria, precio y fecha de vigencia. En CABA se identificaron 732 filas correspondientes a nafta. La exploración inicial de la propuesta registró 96 filas, asociadas a 29 identificadores, con una fecha de vigencia dentro de los treinta días anteriores a ese relevamiento. En la ejecución reproducible del notebook del 18 de septiembre de 2026, que es la evidencia vigente para esta entrega, se observaron 8 registros correspondientes a 2 estaciones. La diferencia se explica por la fecha de consulta y la versión del recurso; para las decisiones actuales prevalecen los resultados del notebook y del PRD.
Según el catálogo oficial, el conjunto se actualiza cada hora y su campo accrualPeriodicity indica R/PT1H. Esto representa la frecuencia de publicación del conjunto, pero no implica que el precio de cada estación cambie o sea confirmado cada hora. Una fecha antigua no demuestra que un precio sea incorrecto, y una fecha reciente no garantiza stock ni disponibilidad del producto.  
Se aplicará inicialmente un umbral configurable de treinta días para considerar precios en las recomendaciones. Si no existen suficientes alternativas que cumplan ese criterio, el sistema informará cobertura insuficiente en lugar de presentar resultados con apariencia de actualidad.  
La consulta histórica inicial informaba 41.160 registros asociados con CABA sin el filtro final de producto. En la ejecución reproducible del notebook se filtraron los registros de nafta y se obtuvieron 20.522 observaciones, 76 identificadores de estación y aproximadamente 142 meses de cobertura. Durante ambas exploraciones se detectó una posible discrepancia en la interpretación de día y mes entre el CSV y la API. Por este motivo, la POC deberá confirmar los formatos y reglas de normalización antes de consolidar ambas fuentes.
La ingesta conservará las capturas originales, realizará validaciones de esquema, fechas, coordenadas, precios y duplicados, y registrará las transformaciones aplicadas. También preservará la atribución y las condiciones de licencia.  
Se propone [OpenRouteService Standard](https://account.heigit.org/info/plans) como proveedor principal de distancias, tiempos y matrices de rutas. Al momento del relevamiento, el plan gratuito documentaba límites de 2.000 consultas diarias para Directions y 500 para Matrix, con un máximo de 40 consultas por minuto. Estas cuotas deberán verificarse mediante una prueba autenticada antes de cerrar el diseño.  
Para reducir el consumo de la API, primero se realizará una preselección geográfica y posteriormente se solicitarán rutas únicamente para un máximo de veinte estaciones candidatas. Se respetarán las condiciones de uso y atribución del proveedor.  
Como alternativa ante indisponibilidad o restricciones incompatibles con la POC, se evaluará OSRM sobre un extracto regional de OpenStreetMap. El tráfico en tiempo real y la reconstrucción propia del grafo vial quedan fuera del alcance del MVP.

## Enfoque de Machine Learning

El componente de machine learning estimará un precio de referencia condicionado por el contexto disponible. Se compararán modelos de regresión regularizada y árboles potenciados utilizando variables como:

* Producto.  
* Bandera.  
* Ubicación o zona.  
* Franja horaria.  
* Antigüedad de la publicación.  
* Precios históricos anteriores de la misma estación.  
* Precios históricos anteriores de estaciones cercanas.  
* Medianas y dispersión por producto, zona y período.  
* Variables temporales disponibles al momento de la predicción.

El objetivo supervisado será el precio publicado observado. Las variables de cada registro se construirán exclusivamente con información disponible antes de su fecha para evitar fuga de información. No se utilizará el precio objetivo de una observación para construir sus propias variables históricas o agregadas.  
El resultado del modelo se comparará con el precio oficial publicado para obtener una diferencia o puntuación de atipicidad. A partir de esa diferencia y de la distribución de errores observada durante la validación, se asignará un nivel de confianza. Este resultado será un diagnóstico estadístico y no una afirmación de que el precio oficial sea incorrecto.  
La evaluación utilizará cortes temporales y agrupará registros repetidos para impedir que observaciones equivalentes aparezcan simultáneamente en entrenamiento y validación. Como baseline se utilizará una mediana comparable por producto, zona y período. La métrica principal será el error absoluto medio en pesos por litro. También se analizarán la estabilidad de las alertas, la cobertura y el efecto del diagnóstico sobre las recomendaciones.  
La POC deberá validar:

* La identidad y continuidad histórica de las estaciones.  
* La cantidad y variación de observaciones disponibles.  
* La posibilidad de construir variables sin información futura.  
* El desempeño de los modelos frente al baseline.  
* El efecto de las alertas sobre casos reales de recomendación.  
* El flujo completo desde la ingesta hasta una recomendación explicada.

Todavía no existe un modelo entrenado ni se ha demostrado una mejora respecto del baseline. El MVP incluirá entrenamiento reproducible, versionado de datos y modelos, serving y monitoreo del error, cobertura y cambios en la distribución de los datos.

## Variabilidad preliminar

El alcance permite dividir el trabajo entre tres áreas principales: datos y ML; API y motor de recomendación; e interfaz web, infraestructura y operación. La integración, las pruebas y la documentación serán responsabilidades compartidas.  
La POC utilizará un caso reducido, con una ubicación controlada, un tipo de combustible y hasta diez estaciones, para validar el flujo técnico de punta a punta. Posteriormente, el MVP ampliará la solución al alcance definido, incorporará la interfaz completa, la operación local y cloud, y el ciclo de vida del modelo.  
Las fuentes públicas, el volumen preliminar de información y las cuotas gratuitas documentadas son compatibles con el uso académico previsto. No obstante, esta viabilidad depende de confirmar la identidad de las estaciones, la profundidad del histórico y el funcionamiento autenticado del proveedor de rutas.

## Mayor riesgo técnico y Plan B

El principal riesgo técnico es que la calidad, vigencia, continuidad o cobertura de los datos sea insuficiente para generar recomendaciones útiles o entrenar un modelo con capacidad de generalización.  
Para las recomendaciones, si la cobertura reciente es insuficiente, el sistema informará la limitación y permitirá ejecutar escenarios históricos identificados expresamente como tales. No presentará precios antiguos como si fueran actuales. Para la demostración podrán utilizarse estaciones y capturas previamente verificadas, manteniendo la trazabilidad respecto de los datos reales de origen.  
Si los registros de CABA resultan insuficientes para entrenar el modelo, se evaluará ampliar el conjunto de entrenamiento con registros nacionales de la misma fuente, incorporando variables geográficas y manteniendo una evaluación específica sobre CABA. Si el modelo de árboles potenciados no mejora el baseline, se utilizará una regresión regularizada como alternativa más simple, interpretable y operable.  
El baseline estadístico permanecerá como referencia y respaldo del diagnóstico, pero no se presentará como un modelo de machine learning. Cualquier falta de mejora se documentará de manera transparente mediante métricas, limitaciones y análisis de errores.  
Si OpenRouteService no estuviera disponible o sus cuotas fueran incompatibles con el flujo previsto, se reducirá el número de estaciones evaluadas y se utilizará almacenamiento temporal de resultados compatibles con sus condiciones de uso. Si esto no fuera suficiente, se evaluará OSRM con un extracto regional como proveedor alternativo.

## Alcance tentativo del MVP

**Qué queda dentro**

* Ciudad Autónoma de Buenos Aires.  
* Nafta súper y premium.  
* Una única parada para cargar combustible.  
* Ubicación de origen y destino opcional.  
* Carga manual de características del vehículo y combustible disponible.  
* Presupuesto y prioridad de recomendación.  
* Preselección y evaluación de hasta veinte estaciones.  
* Ingesta diaria de datos.  
* Conservación de históricos y archivos originales.  
* Validaciones de calidad y trazabilidad.  
* Obtención de distancias y tiempos estimados.  
* Motor determinístico de recomendación.  
* Explicación de resultados y motivos de descarte.  
* Modelo de referencia de precios.  
* Advertencias de baja confianza.  
* Comparación entre ranking general y ranking conservador.  
* API y aplicación web.  
* Autenticación administrativa.  
* Pruebas, CI/CD, contenedores y configuración externa.  
* Observabilidad, ejecución local y preparación para cloud.

**Qué queda fuera**

* Compras o pagos de combustible.  
* Descuentos bancarios y promociones.  
* Información de stock o filas en tiempo real.  
* Tráfico en tiempo real.  
* Reconstrucción propia del grafo vial.  
* Lectura automática del tanque.  
* Navegación paso a paso.  
* Aplicación móvil nativa.  
* Múltiples cargas o paradas.  
* Aprendizaje de preferencias mediante comportamiento de usuarios.  
* Sustitución del precio publicado por una predicción.  
* Garantías de stock, ahorro, precio o autonomía exacta.
