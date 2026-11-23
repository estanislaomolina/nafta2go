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
