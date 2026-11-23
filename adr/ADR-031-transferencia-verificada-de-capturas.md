---
status: Propuesto
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

Esta etapa implementa el contrato de importación, con pruebas sin AWS. No
provisiona S3/IAM, workflow ni timers; tampoco instala ni activa nada en AWS.
Esos componentes y una ejecución automática exitosa son condiciones pendientes
para cerrar #160. El rol del productor deberá tener escritura acotada; el de
EC2, lectura. No se usará una sesión SSO personal para tareas programadas.
