# Operación continua y cierre operativo — 23/11/2026

Web: https://estanislaomolina.github.io/nafta2go/

API: https://nafta2go.18.216.94.147.sslip.io/

Grafana autenticado: https://nafta2go.18.216.94.147.sslip.io/grafana/

## Despliegue comprobado

[CI/CD exitoso](https://github.com/estanislaomolina/nafta2go/actions/runs/45290583089)
para `main`, commit `7a65b824e5618f10c765f32ac4ecec3630931180`.
Imagen probada y publicada sin reconstrucción:
`ghcr.io/estanislaomolina/nafta2go@sha256:66ed4cbfd9f07f60a4ad6fff45ee526e4cc00eb440e9d42d519e88c52a22544c`.
El job de despliegue autenticó por OIDC, esperó SSM y aprobó el smoke real.
Excepción autorizada: Estanislao aprobó su ejecución; después se restauró el
revisor Felipe y el bloqueo de autoaprobación. No se atribuye esa aprobación a Felipe.
[Pages exitoso](https://github.com/estanislaomolina/nafta2go/actions/runs/45290583174).

## Carga aislada en la EC2

Los reportes [histórico](historico-aws.json) y [sostenida](sostenida-aws.json)
proceden de una base de QA separada. La base productiva se abrió sólo para hacer
un backup consistente; la prueba no escribe recomendaciones en producción.
Se ejecutaron en t3.small, 2 vCPU, con la imagen CI de `b2b81f52` y fuentes del
archivo de `cbfdf67` (el hash de archivos está dentro de los reportes). El archivo
no contiene `.git`: no se infiere un commit desde el contenedor.

Histórico: 80.056 precios reales, referencia temporal fija, rutas sintéticas y
20 diagnósticos activos en cada una de las 128 respuestas medidas. Cero errores
HTTP; p95 con un usuario 0,8048 s. El rendimiento deja de crecer con dos usuarios:
a 20 usuarios el p95 llega a 29,0305 s. No demuestra cumplimiento de latencia bajo
esa concurrencia. Se persistieron 168 consultas: 40 terminaron después del cierre
de sus ventanas de medición y no se cuentan entre las 128 respuestas medidas.
Auditoría completa sin fallas de trazabilidad, frescura ni privacidad.

Sostenida: 1.069 respuestas 200 durante 120 s con diez usuarios, cero errores,
p95 0,3513 s. Rutas grabadas y sin diagnóstico histórico; no se extrapola ese
resultado al perfil histórico. La persistencia coincide con las 1.069 respuestas.
La prueba verifica la corrección WAL de #173 en una carga real de SQLite.
CPU/RSS provienen del proceso medido. No se usó esta carga para medir cuotas de
ORS ni latencia pública. Ver también el ensayo de cuota en
[la evidencia anterior](../carga-2026-11-23/README.md).

## Acceso público y observabilidad

[Smoke HTTPS](https-smoke.json): diez consultas reales por HTTPS con ORS,
alternando UC01 y UC02, todas 200. UC01 produce veinte diagnósticos y UC02
hasta diecisiete candidatas viables; no se inventan alternativas para llegar a veinte.
Muestra pequeña: no representa el p95 poblacional ni una prueba de estrés pública.

Las capturas [negocio](grafana-business.png) y
[funcionamiento](grafana-operations.png) se tomaron con login real en Grafana AWS.
Se comprobaron dos dashboards, datasource saludable y `up{job="nafta2go"}=1`.
No se exportan códigos, contraseñas ni tokens. Las métricas de litros/gasto son
estimaciones de recomendaciones y no acreditan compras confirmadas.

## Presupuesto y permanencia

El dueño autorizó operación continua. Se deshabilitaron el apagado a dos horas
y Cloudflare; API y observabilidad tienen reinicio automático. El guard horario
independiente limita la operación según el presupuesto acumulado de USD 17,
con corte conservador antes de USD 15 incluyendo proyección y reserva de USD 2.
No es un límite duro de facturación: detener EC2 conserva discos y dirección
pública, que pueden seguir generando cargos. No hay autorización para destruir
los datos. Cost Explorer está bloqueado por SCP; Budgets informa gasto, pero no
se afirma conocer el saldo exacto de créditos educativos.

## Recuperación y auditoría productiva

[Rollback real](rollback.json): se volvió de la imagen `66ed4cbf` a la release
previamente instalada `c0739705`, se aprobó el smoke y se restauró `66ed4cbf`,
también con smoke aprobado. Ambos pasos usaron modo rollback y digests guardados,
sin reconstrucción ni migración inversa. El esquema permanece en `0003`; una
migración futura requiere revisar compatibilidad antes de revertir código.

[Auditoría productiva](production-audit.json): 23/23 recomendaciones con
trazabilidad y privacidad, 308/308 precios con frescura; SQLite íntegro y WAL.
[Prueba en navegador sobre Pages](pages-browser.json): UC01 y UC02 reales 200,
geolocalización emulada dentro de CABA, cero errores de página y almacenamiento
local/session vacío. La emulación no se presenta como prueba de un teléfono físico.
El dueño probó previamente un iPhone 13 con ubicación manual fuera de CABA y una
computadora con geolocalización detectada dentro de CABA; no informó SO/navegador.

[Timers AWS habilitados](ingestion-timers.json): ingesta diaria 06:45 Argentina
y monitor horario, ambos con `Persistent=true`. Instalarlos no demuestra una
adquisición exitosa: esa evidencia se registra por separado.

## RNF01 en AWS con ORS real

[Medición aislada](live-api.json): copia consistente de la base desplegada,
mismo digest `66ed4cbf`, modelo y política vigentes, tres consultas de
calentamiento y cien medidas (50 UC01, 50 UC02). ORS real con caché, un usuario,
HTTP loopback; no incluye el transporte HTTPS público. p95 UC01 0,66478 s y
UC02 0,65488 s. Se guardaron las 103 consultas y la
[auditoría posterior](qa-live-audit.json) terminó sin fallas. Los tamaños de las
muestras y las condiciones no se extrapolan a veinte usuarios simultáneos.

## Canal autónomo completo

[Actions de adquisición](acquisition-run.json) terminó correctamente usando
OIDC y un runner dedicado con acceso al catálogo. [Resultado](acquisition.json):
9.258.843 bytes, SHA-256 `0ec9333f68f0ee2a7607b973bbaf2fb59ae3efb5f4bad3a37830bc1d44fecfbc`,
732 precios utilizables de CABA. No hubo transferencia manual del CSV ni uso de
SSO personal en el circuito. Linux y macOS alojados habían agotado los reintentos
de conexión; eso no demuestra que el proveedor no publique archivos.

La [prueba programada](autonomous-ingestion.json) y su
[verificación](ingestion-final.json) registran los runs 5 y 6 en AWS, ambos
exitosos, 732 precios por versión y 184 estaciones. El segundo está rotulado
como adquisición de contenido duplicado del run 5; no se presenta como una
publicación nueva del proveedor. Sus recomendaciones seleccionan una versión,
no suman las filas de ambas. Los dos conservan el linaje de Actions y el hash del
recibo. Monitor sin alertas abiertas; readiness 200.

Se disparó el servicio existente mediante timers transitorios para observarlo
ahora; no se atribuye la prueba al calendario diario de mañana. La instalación
diaria queda habilitada: Actions 06:17 y consumo EC2 06:45 de Argentina, monitor
horario y `Persistent=true`. La primera prueba usó la precisión predeterminada
del timer y el monitor consultado antes de dispararse indicó ausencia; al ejecutar
la ingesta, el monitor se resolvió correctamente.

Las capturas actuales de Grafana se renovaron después de esta recuperación.
Los precios conservan sus fechas originales: el máximo observado del conjunto
CABA es 17/11/2026 aunque se descargó el 23/11; no se rejuvenecen al copiarlo.
`fetched_at` de RawCapture usa hora de Argentina y las marcas de ejecución
son UTC, según el contrato de persistencia.

El runner oficial Linux x64 2.338.2 se verificó contra SHA-256
`baebf204307bac6193480852732f0aba2ae97b6c5597c244f4d5558390147c40`,
con Python 3.12 y AWS CLI 2.42.1. Su servicio de usuario está habilitado, con
reinicio y `Linger=yes`; usa credenciales de máquina de GitHub y OIDC de AWS.
Se instaló fuera del checkout. Necesita este equipo encendido y con red: no se
acredita disponibilidad 24/7 del origen de adquisición ni de sus proveedores.
La API y Grafana sí siguen en EC2 bajo el guardia de presupuesto.
