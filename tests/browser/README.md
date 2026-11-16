# QA de la aplicación web

Requiere Python 3.12 con `requirements.txt`, Node 24, npm y las librerías del
sistema que necesita Chromium. Desde la raíz del repo:

```bash
npm ci --prefix tests/browser --ignore-scripts
tests/browser/node_modules/.bin/playwright install --with-deps chromium
npm test --prefix tests/browser
```

Si Python vive en un entorno virtual, indicar `WEB_TEST_PYTHON=/ruta/a/.venv/bin/python`.
Opcionalmente definir `PLAYWRIGHT_BROWSERS_PATH` para los ejecutables y
`WEB_TEST_ARTIFACTS` para los reportes. La ejecución inicia y detiene su propio
servidor en loopback/puerto libre y usa una base SQLite temporal. No reutiliza
sesiones del navegador del usuario ni consulta APIs de Google/ORS/Energía.

**Datos de QA:** escenario histórico versionado y distancias sintéticas de
`server.py`. El código de acceso es descartable, exclusivo de esa base temporal.
El servidor no se usa para una demo productiva ni para afirmar rutas reales.
Las otras respuestas interceptadas verifican estados de la presentación.

Doce pruebas cubren UC01/UC02 con teclado, descartes UC06, validación/corrección,
401, cuota, timeout, red, privacidad, geolocalización simulada/denegada, XSS y
layouts de 1440, 390 y 320 px. Playwright 1.65.0 usa Chromium 158.0.8127.18;
axe-core 4.14.0 revisa etiquetas WCAG 2/2.1 A-AA y 2.2 AA en siete estados.
El entorno exacto, violaciones e incompletos quedan en JSON junto a las capturas.
Cualquier violación automatizada falla la prueba; los incompletos se conservan
para revisión humana. No se declara conformidad universal con WCAG.

La corrida local del 13/11/2026 aprobó las doce pruebas, con cero violaciones e
incompletos en los siete análisis. Se corrigió un rol no permitido en el área de
resultados antes de registrar ese resultado. La vista móvil es emulación de
Chromium: falta prueba en teléfono físico, otros navegadores y lector de pantalla.
CI ejecuta la misma suite y conserva `web-qa` durante siete días.

La regresión de dirección ausente intercepta una respuesta de estaciones
descartadas y establece `address: null`: la interfaz debe explicar que la dirección
no está informada. Antes del arreglo mostraba literalmente `null`; la prueba
reproduce ese fallo y pasa con la corrección.
