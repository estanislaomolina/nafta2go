# Aplicación web local — MVP-03

La pantalla está en `/` del servidor descrito en [API](API.md). Levantar el
mismo servicio con `uvicorn nafta2go.presentation.http:app --host 127.0.0.1 --port 8000 --no-access-log --log-config deploy/logging.json`
o `docker compose --profile mvp up --build api`, después de configurar el código
`NAFTA2GO_API_TOKEN` y migrar la base. Abrir `http://127.0.0.1:8000/` y usar ese
código en «Acceso a la demo». La API y la web comparten origen; decisión propuesta
en [ADR-012](../adr/ADR-012-web-local-con-assets-propios.md).

El formulario recibe coordenadas manuales o ubicación solicitada mediante un
botón, destino opcional (volver al origen), vehículo, nafta, horario y presupuesto.
La geolocalización depende de permisos y del contexto seguro del navegador;
si no está disponible, permite ingresar coordenadas. No se consulta al cargar.
Los importes/litros viajan como cadenas decimales; solo la presentación redondea.
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
El diagnóstico ML, ranking conservador, perfiles y autenticación pública siguen
pendientes en sus respectivos issues. La web usa el valor predeterminado de diez candidatas; la API permite configurar
un máximo entre 3 y 20. Esto no completa por sí solo MVP-03.

## Panel local de operación

Abrir `http://127.0.0.1:8000/operacion` en el mismo servicio. El HTML de acceso
es público y no contiene datos ni código; las dos lecturas de [API](API.md)
requieren el Bearer local existente. No hay roles separados de usuario/operador:
esta interfaz no habilita uso público. Elegir fuente, ingresar el código y pulsar
«Actualizar estado»; no hace polling ni consultas antes de esa acción.

Presenta contadores de consultas HTTP y caché de rutas, condiciones del monitor
y último intento separado de la última versión exitosa, con fechas, duración,
conteos, reglas y captura. No genera ingestas ni escribe/resuelve alertas.
Explica que contadores son por proceso, que la CLI queda fuera y que ausencia
de condiciones no garantiza frescura, cobertura ni disponibilidad. ML queda
rotulado como pendiente; no se inventan métricas.

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
