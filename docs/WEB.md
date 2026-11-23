# Aplicación web local — MVP-03

La pantalla está en `/` del servidor descrito en [API](API.md). Levantar el
mismo servicio con `uvicorn nafta2go.presentation.http:app --host 127.0.0.1 --port 8000`
o `docker compose --profile mvp up --build api`, después de configurar el código
`NAFTA2GO_API_TOKEN` y migrar la base. Abrir `http://127.0.0.1:8000/` y usar ese
código en «Acceso a la demo». La API y la web comparten origen; decisión propuesta
en [ADR-012](../adr/ADR-012-web-local-con-assets-propios.md).

El formulario permite buscar una dirección o lugar de CABA para origen y destino.
Primero se ingresa el código de demo y se pulsa Buscar; no consulta al escribir.
Muestra hasta tres opciones y exige seleccionar una. USIG/GCBA recibe el texto de
esa búsqueda, sin el código de acceso. Las coordenadas quedan en un desplegable
como alternativa; la recomendación sigue enviando sólo coordenadas.

Editar el texto invalida la ubicación anterior. Buscar o salir cancela lecturas y
una respuesta tardía no repone resultados. El retorno copia el origen y bloquea
la búsqueda de destino. Sin resultados, acceso, cupo, red o dependencia, se ofrecen
mensajes y reintento. No se agrega almacenamiento del navegador.

La ubicación automática es optativa: acepta una posición reciente de hasta un
minuto y reintenta una vez con mayor precisión si agota doce segundos (segundo
intento: veinte segundos). Puede cancelarse. Una posición tardía no pisa una
dirección editada. Se informa la precisión disponible y se pide confirmar el punto;
no garantiza GPS en una computadora ni ubicaciones dentro de CABA.

Los importes/litros viajan como cadenas decimales; sólo la presentación redondea.
La validación de negocio y el ranking permanecen en el servidor.

Muestra carga, errores, falta de cobertura, descartes y alternativas con precio,
litros, costo, consumo, reserva, autonomía, desvío, vigencia y fuente. Un escenario
histórico se rotula explícitamente. Los [enlaces de Maps](MAPS.md) abren otra
pestaña con `noopener noreferrer`; Google recalcula su recorrido.

La app no usa almacenamiento local, cookies ni parámetros de URL para guardar
el código o las coordenadas. El código queda en memoria y se vacía al abandonar
la página. Las respuestas de la pantalla llevan `no-store`, CSP de assets propios
y política de referrer. Los textos remotos se insertan como texto, no HTML.
El acceso por código es **local/demo**, no autenticación de usuarios para uso público.
No se desplegó en AWS ni se incorporó hosting externo.

Incluye etiquetas, enlace para saltar al formulario, foco visible y regiones de
estado/error. Las [pruebas de navegador](../tests/browser/README.md) verifican UC01/UC02 con
teclado y los descartes de UC06, errores, privacidad y layouts de escritorio/móvil
emulado. Axe-core registró cero violaciones e incompletos en doce estados de
la corrida local; no se declara conformidad completa con WCAG. Falta teléfono
físico, otros navegadores y lector de pantalla.
El diagnóstico ML y el ranking conservador están descritos más abajo; perfiles y
autenticación pública siguen pendientes. La web usa diez candidatas por defecto;
la API admite un límite de 3 a 20. No completa por sí sola MVP-03.

## Panel local de operación

Abrir `http://127.0.0.1:8000/operacion` en el mismo servicio. El HTML de acceso
es público y no contiene datos ni código; las dos lecturas de [API](API.md)
requieren el código administrativo, distinto del código de conductor
(ADR-016). Esta interfaz no habilita uso público. Elegir fuente, ingresar el código y pulsar
«Actualizar estado»; no hace polling ni consultas antes de esa acción.

Presenta contadores de consultas HTTP y caché de rutas, condiciones del monitor
y último intento separado de la última versión exitosa, con fechas, duración,
conteos, reglas y captura. No genera ingestas ni escribe/resuelve alertas.
Explica que contadores son por proceso, que la CLI queda fuera y que ausencia
de condiciones no garantiza frescura, cobertura ni disponibilidad. El diagnóstico presenta sólo solicitudes observadas y su última referencia, sin
afirmar precisión ni deriva.

Las lecturas usan `no-store` y mismo origen. La pantalla retira datos anteriores
al actualizar y sólo presenta el conjunto si ambas lecturas funcionan; ante
401, dependencia, red o espera de quince segundos muestra un mensaje seguro.
«Limpiar acceso y datos» o salir cancela la lectura y vacía credencial/resultados;
una respuesta tardía no los repone. Sin cookies, local/session storage ni código
en URL; sin servicios de terceros. Texto remoto se inserta con textContent.

QA cubre teclado, errores, cancelación, timeout, regreso a la página, XSS y
390/320 px emulados. Las capturas de operación son datos de prueba: el caso
de fallo posterior al éxito y su hash son sintéticos; no son evidencia de una
ingesta real. Falta validación con operador, teléfono físico y lector de pantalla.


El panel separa las alertas de ingesta del estado operativo del diagnóstico de
precios. Presenta conteos, tiempos y última referencia; sin lecturas informa que no
hay observaciones. Ante un fallo de dependencia/interno muestra degradación aunque
la consulta habitual pueda seguir disponible. No confunde falta de contexto con un
precio erróneo. La versión informada corresponde a la última referencia observada,
no a una confirmación de que la configuración actual siga siendo la misma.


## Atribución de rutas

El pie de la consulta identifica a openrouteservice by HeiGIT y a OpenStreetMap
contributors, con enlace al proveedor y a la página de copyright/licencia ODbL.
Los enlaces abren otra pestaña sin referrer ni acceso a la ventana original;
no cargan recursos externos ni consultan al proveedor al abrir la pantalla.
La regresión de navegador verifica que los créditos estén visibles y preserva
los recorridos de teclado, móvil emulado y análisis de accesibilidad existentes.


## Referencia histórica de una publicación

Para resultados de una ingesta vigente, cada alternativa ofrece «Consultar
referencia de precio». Sólo al pulsarlo consulta el diagnóstico autenticado;
no envía coordenadas y usa el producto/franja de la recomendación mostrada,
aunque se edite el formulario. Los escenarios históricos no ofrecen ese control:
el endpoint diagnostica la publicación de la última ingesta vigente.

La respuesta debe coincidir en ingesta, estación, producto, franja, precio y fecha;
si cambió la publicación se pide buscar de nuevo. La pantalla conserva el precio
oficial y muestra referencia, diferencia, fecha y trazabilidad por separado.
Explica que no estima el precio actual ni demuestra un error y que todavía no
hay una alerta validada. No modifica la factibilidad ni el ranking.

Falta de contexto, acceso, dependencia, red, respuesta inválida y timeout de quince
segundos tienen mensajes seguros. Una búsqueda nueva o salir cancela las lecturas
y retira referencias anteriores; el código sólo permanece en memoria de pestaña.
No se agrega almacenamiento, polling ni requests a terceros. QA usa respuestas de
referencia sintéticas; no acredita calidad del modelo ni disponibilidad real.

## Estaciones con precio desactualizado

Cuando la API devuelve `stale_price_estimates` con `status=available`, la web agrega
después de las alternativas una sección aparte, "Estaciones con precio
desactualizado". Cada tarjeta lleva el rótulo ESTIMADO y muestra en filas separadas
el precio oficial con su fecha y antigüedad, el precio estimado y la referencia
usada: cantidad de precios de la misma bandera y período. El aviso aclara que esas
estaciones no participan de la recomendación y que la estimación no es un precio
oficial ni garantiza el importe en el surtidor ([ADR-020](../adr/ADR-020-estimacion-de-precios-antiguos.md)).

La sección descarta ítems con precios no positivos o fechas mal formadas, inserta
todo texto remoto con `textContent` y no genera enlaces ni consultas adicionales.
Sin ingesta vigente o sin ítems válidos no aparece. La regresión de navegador
verifica rótulo, separación del ranking, XSS, ítems inválidos y ausencia de
desborde horizontal, con axe a 1440 y 320 px de ancho; los datos son sintéticos.


## Abrir el viaje en un mapa

Las alternativas ofrecen «Mapa del viaje y Waze»: Google Maps muestra origen,
estación intermedia y destino (o retorno al origen), mientras que Waze navega
hasta la estación. Se explica qué puntos se comparten al abrirlo. Los enlaces usan
la consulta original, viven en la presentación y no modifican el cálculo ni se
persisten. No se cargan mapas ni terceros automáticamente. Contrato y límites en
[MAPS](MAPS.md#mapa-del-viaje-y-waze).

## Ranking conservador provisional

La consulta muestra, además de las alternativas generales, una comparación
conservadora de las mismas candidatas viables y sus rutas ya calculadas. Excluye
las excedencias de la regla `conservative-v1`; las estaciones sin referencia se
mantienen y se identifican por separado. El precio oficial y el ranking general
conservan sus valores. Si todas exceden, se explica el resultado vacío.

La regla no prueba precios incorrectos ni certifica los restantes. No se presenta
una comparación disponible en el escenario histórico o sin diagnóstico compatible.
Consultar [ADR-021](../adr/ADR-021-ranking-conservador-por-desvio.md).
