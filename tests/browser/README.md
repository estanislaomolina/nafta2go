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

Diecisiete pruebas cubren UC01/UC02 con teclado, descartes UC06, validación/corrección,
401, cuota, timeout, red, privacidad, geolocalización simulada/denegada, XSS y
layouts de 1440, 390 y 320 px. Playwright 1.65.0 usa Chromium 158.0.8127.18;
axe-core 4.14.0 revisa etiquetas WCAG 2/2.1 A-AA y 2.2 AA en doce estados.
El entorno exacto, violaciones e incompletos quedan en JSON junto a las capturas.
Cualquier violación automatizada falla la prueba; los incompletos se conservan
para revisión humana. No se declara conformidad universal con WCAG.

La corrida local del 13/11/2026 aprobó las diecisiete pruebas, con cero violaciones e
incompletos en los doce análisis. Se corrigió un rol no permitido en el área de
resultados antes de registrar ese resultado. La vista móvil es emulación de
Chromium: falta prueba en teléfono físico, otros navegadores y lector de pantalla.
CI ejecuta la misma suite y conserva `web-qa` durante siete días.

Cinco casos adicionales cubren el panel `/operacion`: lectura de las APIs con
base temporal vacía, acceso por teclado, 401/dependencia/red, limpieza durante
carga, timeout, selección de fuente, regreso sin credenciales y móvil 390/320 px.
El caso visual de fallo posterior a éxito, reglas maliciosas y condiciones
truncadas usa respuestas sintéticas interceptadas. Capturas adicionales:
`operacion-escritorio.png` y `operacion-movil-emulado.png`; no son evidencia de
operación real ni de un teléfono físico.

El servidor de QA fija `NAFTA2GO_MAX_PRICE_AGE_DAYS=29` para comprobar una política
no predeterminada y su presentación; sigue usando rutas sintéticas explícitas.

La regresión de copia de código con espacios comprueba acceso y Bearer normalizado.
