---
status: Aceptado
date: 2026-11-23
decision-makers: Equipo Nafta2Go
consulted: ADR-019, ADR-024, issue 160
informed: Cátedra
---

# Transferencia verificada de capturas para la ingesta cloud

## Context and Problem Statement

La ingesta directa desde Ohio sufrió timeout aun con la excepción de red del
catálogo. Importar un archivo a mano permite una demo, pero no satisface #160.
Además, el modo `--file` usa la fecha y URI locales: no representa correctamente
la adquisición efectuada en otro entorno.

## Considered Options

* Ingesta directa en EC2: menos componentes, pero depende de resolver la
  conectividad al catálogo HTTP; sigue siendo una alternativa si se recupera.
* Copia manual: simple para recuperar una demo, pero requiere una persona y no
  acredita actualización autónoma.
* Runner programado y S3 privado: separa adquisición de consumo, permite que el
  host esté apagado y usa identidades de máquina; agrega almacenamiento,
  permisos y programación que deben desplegarse y verificarse.
* Runner con SSM y contenido embebido: evita un bucket, pero los CSV exceden el
  tamaño práctico del comando; fragmentar la transferencia complica recuperación.

## Decision Outcome

Se prepara la tercera opción como alternativa de ADR-019. El productor reutiliza
los reintentos de adquisición, verifica calidad e integridad y publica primero el
CSV identificado por SHA-256, después un recibo `vigente/latest.json`. El receptor
descarga ese recibo una vez y el CSV de su hash, evitando mezclar adquisiciones.
Comprueba tamaño, hash, origen, fecha y linaje antes de normalizar y persistir.

El recibo conserva fecha real de adquisición, URL pública, modificación informada
por la fuente, intentos, corrida de Actions y commit. El reporte guarda linaje y
hash del recibo sin una migración. Copiar no renueva las fechas de los precios ni
la cobertura: readiness sigue aplicando la política existente.

### Consequences and Confirmation

La ventana de 36 horas limita recibos viejos; cinco minutos toleran desajuste de
reloj. No garantiza actualidad de cada precio. El SHA detecta corrupción entre
adquisición y consumo; no autentica al catálogo HTTP. El canal S3 debe ser privado
y autenticado. Una publicación fallida conserva el puntero anterior; el receptor
rechaza ese puntero si vence. Se conservan originales desde que el importador
puede referenciarlos, incluso si se interrumpe después de guardar.

La implementación se divide en contrato, transporte y programación. La plantilla
S3/IAM y el workflow usan una identidad distinta del despliegue: sin environment,
con subject inmutable de este repositorio para `main`/`dev`. El productor tiene
escritura acotada; EC2, lectura desde su rol renovable. Los servicios AWS corren
en contenedores con `current-image`, separados de los servicios locales. No se
copia una sesión SSO personal para tareas programadas.

La adquisición se programa antes del consumo; no enciende EC2. Timers persistentes
recuperan al arrancar un disparo omitido y rechazan recibos vencidos. Se mantienen
apagado automático y límites de duración. Las pruebas simulan transporte, fallos
y permisos; la evidencia de creación de infraestructura no reemplaza una corrida
OIDC ni una ingesta automática exitosa. Sin esa comprobación #160 sigue abierto.


## Verificación y entorno de adquisición

El 23/11 se comprobó el circuito Actions/OIDC → S3 → ingesta en EC2 con hash,
tamaño y linaje verificados. Los runners alojados Linux/macOS también dieron
timeout al catálogo: se eligió un runner dedicado en el entorno con conectividad
comprobada, con servicio persistente e identidad de máquina, sin SSO personal.
Conservar runners alojados evita operar un equipo propio, pero no resolvió el
acceso observado. Un runner dedicado permite adquirir, a cambio de mantenerlo
encendido, conectado y actualizado. No se declara disponibilidad 24/7 del
productor; el consumidor conserva las últimas versiones y el monitor detecta
la ausencia/fallo. [Prueba y límites](../docs/evidencia/operacion-continua-2026-11-23/README.md).
