# Validación local conjunta — primer incremento de MVP-09

Se reunieron los incrementos de ingesta/monitor/reintentos, límite de candidatas,
API, caché/cupo, Maps, web/QA y plantillas de red en una rama de validación.
[Fuentes](evidencia/integracion-local-2026-11-13/fuentes.json) registra los commits
de base; las pruebas y correcciones de integración están encima de esa base.
Esto no representa un merge aprobado en `dev` ni una entrega completa.

## Prueba entre componentes

`tests/integration/test_local_mvp.py` usa el CSV histórico versionado, un reloj
fijo del 26/10/2026, SQLite temporal, adquisición y HTTP de rutas simulados:

1. Recupera un fallo de DNS inyectado y conserva dos intentos en una única ingesta.
2. Normaliza el CSV y consulta por HTTP con tope de veinte; evalúa más de diez
   cuando la fixture lo permite y devuelve navegación de las alternativas.
3. Ingiere una captura **sintética**, derivada de la fixture aumentando 1 ARS cada
   precio. El archivo tiene su propio hash; no se presenta como precio oficial.
4. La consulta usa la nueva ingesta/precios y reutiliza la matriz previa.
5. Agota tres intentos de una adquisición fallida, conserva la versión exitosa y
   el monitor registra la alerta. Una tercera consulta sigue usando esa versión.
6. Las tres consultas hacen una sola petición simulada de matriz; el registro no
   incluye coordenadas del conductor ni enlaces de Maps.

La corrección #83 conecta `max_candidates` al contrato HTTP: antes devolvía 422,
aunque el motor soportaba veinte. Ahora valida entero estricto 3–20, propaga y
registra el límite; el predeterminado sigue siendo diez. Además se corrigió el
paso de las cuatro variables de caché/cupo a API y CLI en Compose: antes se
ignoraban las definidas en el host. CI comprueba configuración y valores reales
leídos dentro de un contenedor.

## Reproducir

```bash
pytest -q --cov=nafta2go --cov-precision=2 --cov-fail-under=90
npm ci --prefix tests/browser --ignore-scripts
# Instalar Chromium según tests/browser/README.md si no está disponible.
npm test --prefix tests/browser
docker compose build
python tests/integration/compose_smoke.py
```

El script Docker usa una imagen local ya construida, proyecto/volumen temporales,
sin puertos publicados ni ORS. Comprueba esquema/readiness, web/assets, rechazo
sin credencial, configuración de caché y consulta con la matriz real grabada de
POC-05. Elimina sus propios recursos al terminar. `--image` selecciona otra
imagen local; no publica imágenes ni despliega infraestructura AWS.

## Resultado local del 13/11/2026 y límites

519 tests Python y 148 subtests aprobados, cobertura de líneas 97,94 %; once
pruebas de navegador aprobadas. Ruff, formato, links, unidades systemd y calendario
válidos. Docker construyó y la consulta histórica produjo diez evaluaciones,
recomendación persistida y enlaces; API/web listas y límites configurados dentro
del contenedor. Los recursos temporales se retiraron.

No se midió p95 con ORS real, disponibilidad sostenida, frescura actual de toda
CABA ni utilidad con usuarios. La web se probó en Chromium y móvil emulado, no
en teléfono físico ni lector de pantalla. ML/ranking conservador, autenticación
de usuarios y despliegue público siguen pendientes. El checkout operativo de
las ingestas no se modificó. MVP-09 y la entrega final siguen abiertos.

## Validación de la corrección de concurrencia #98

Se incorporó en una rama aislada el commit `9500a38` de `felisl30`, conservando
su autoría. El conflicto en RUTAS.md se resolvió manteniendo la integración de
caché y sumando la coordinación por clave. No se modificó la rama de Felipe.

`tests/integration/test_concurrent_http.py` reproduce el bloqueo previo con dos
POST de rutas distintas. Con #98, ambos transportes sintéticos entran antes de
liberar el primero; consultas idénticas sólo hacen una llamada. Las dos
respuestas son exitosas y persisten recomendaciones distintas sin coordenadas
del conductor. El test falló antes del cambio y pasa con él.

Suite conjunta: 595 tests y 148 subtests, cobertura 98,33 %. Son pruebas con
matrices sintéticas, sin ORS real; no prueban p95 ni disponibilidad del proveedor.
La validación no reemplaza revisión ni integración individual de #65 y #98, ni
permite integrar primero toda la cadena acumulada mediante squash. La PR #86
se actualizará con dev después de integrar sus bases para conservar sólo su
incremento propio. El tag anotado de la evidencia de ingesta preserva `4325d79`.
