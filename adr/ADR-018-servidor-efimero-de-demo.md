---
status: Reemplazado por ADR-032 para la operación continua
date: 2026-11-16
decision-makers: Equipo Nafta2Go
consulted: ADR-005, ADR-011, ADR-016, issues 22 y 59
informed: Cátedra
---

# Servidor efímero de demo con acceso por Session Manager

## Context and Problem Statement

El sandbox tiene USD 17 totales y el titular eligió pruebas/demo, sin servicio
permanente. Existe una red, pero faltan cómputo, entrega de la imagen, datos y
readiness cloud. No se asume Free Tier ni permisos de IAM por tener una VPC.

## Considered Options

* EC2 única con SQLite y túnel SSM: conserva contenedores/persistencia actuales y
  evita puertos públicos; requiere operar disco, respaldos y horas encendidas.
* Fargate y almacenamiento administrado: reduce operación del host, pero agrega
  servicios, permisos y costos para persistir SQLite o migrar la base.
* Lambda/API Gateway: permite consumo por invocación, pero exige adaptar ASGI,
  procesos de datos y persistencia; no resuelve por sí sola la arquitectura actual.
* Sólo local: facilita corrección sin costos, pero deja readiness cloud sin probar.

## Decision Outcome

Se propone EC2 para demo privada: `t3.small`, AMI AL2023 x86_64 fijada como
parámetro, disco gp3 cifrado de 16 GiB, IMDSv2 y rol de núcleo SSM. Sin claves SSH,
entrada de red, NAT, EIP, balanceador ni permisos de publicación de imágenes.
Una IPv4 pública permite salida HTTPS; no significa que la aplicación sea pública.
La imagen debe ejecutarse ligada a loopback y el acceso requiere IAM/SSO y túnel.

Créditos CPU en modo standard y sin métricas detalladas. Un timer local apaga el
host a las dos horas de cada arranque, incluso antes de instalar Docker. No es
un límite de gasto acumulado: cada arranque suma horas y el disco cobra detenido.
Eliminar el stack termina la instancia y borra el disco; antes se exige respaldo.

### Consequences and Confirmation

La plantilla prepara Docker, no despliega la app, secretos, datos ni ML. Deben
revisarse costo completo, IAM y cuota antes de ejecutar el change set. Transferir
imagen, migrar/restaurar datos, programar ingesta y verificar readiness son el
siguiente incremento de #22. No se promete capacidad con datos reales todavía.
Tests sin AWS y cfn-lint verifican plantilla, exposición, identidad, disco y timer;
`CREATE_COMPLETE` no demuestra bootstrap exitoso ni aplicación lista.
