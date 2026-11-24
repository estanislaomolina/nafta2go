---
status: Aceptado
date: 2026-11-17
decision-makers: Equipo Nafta2Go
consulted: ADR-018, issues 22 y 59
informed: Cátedra
---

# Salida HTTP opcional acotada para la fuente de Energía

## Context and Problem Statement

La demo propuesta permite salida HTTPS. Sin embargo, el 17/11/2026 el catálogo
oficial redirige a HTTP y los CSV vigente e histórico también se publican por
HTTP en el mismo host. El adaptador ya usa ese contrato. La ingesta en el host
no funcionaría con la regla predeterminada; aún no se provisionó la demo.

## Considered Options

* Habilitar TCP/80 hacia internet: tolera cambios de IP, pero permite más destinos
  de los necesarios y amplía el alcance del tráfico sin cifrar.
* Mantener sólo HTTPS y transferir capturas desde otro entorno: conserva la red
  cerrada por defecto, pero requiere implementar transferencia, integridad y
  programación fuera del host antes de demostrar ingesta cloud.
* Excepción opcional hacia una IPv4/32 verificada: permite el contrato actual
  sin abrir HTTP general; exige revisar DNS, destinos y redirecciones, y puede
  fallar si el proveedor cambia IP o necesita varios destinos.

## Decision Outcome

Se propone la tercera opción mediante `EnergyHttpCidr`, vacío por defecto. La
condición de CloudFormation añade TCP/80 sólo al recibir una IPv4/32 válida.
No se fija una IP del proveedor en código ni se amplía automáticamente la regla.
La documentación exige verificar el destino antes del change set. Con el valor
vacío se conserva la segunda opción como restricción de red, sin dar por resuelta
la transferencia de capturas.

Complementa ADR-018: conserva su topología y su salida predeterminada HTTPS;
no reemplaza la decisión de servidor ni activa la excepción en el sandbox.
No cambia entrada, rol, disco, apagado o cantidad de recursos facturables.

### Consequences and Confirmation

El security group controla IP, no hostname. Un cambio de DNS exige revisar el
parámetro y la ingesta puede fallar hasta entonces. No se promete autenticidad
TLS para la fuente: HTTP no autentica ni cifra; SHA-256 identifica contenido,
pero no evita suplantación del origen. Sólo se reciben datos públicos sin claves.
ORS sigue en HTTPS y la API se accede por SSM, con su autenticación habitual.

Tests cubren ambas ramas de la condición, rechazo de CIDR amplios y conservación
de entrada cerrada. cfn-lint valida la plantilla sin AWS. No se ejecutó un change
set ni se acredita conectividad cloud: continúa pendiente en #22/#59.
