---
status: Aceptado
date: 2026-11-16
decision-makers: Equipo Nafta2Go
consulted: ADR-009, RF12, RNF04, issue 21
informed: Cátedra
---

# Acceso administrativo separado del código de conductor

## Context and Problem Statement

El código compartido para probar recomendaciones no debe habilitar lecturas de
operación. La revisión de #90/#94 señaló que ambos usos compartían una credencial.

## Considered Options

* Token único: simple, pero expone operación a toda persona que prueba la demo.
* Token administrativo independiente: separa privilegios con la infraestructura
  actual; requiere distribuir y rotar dos secretos y carece de identidad personal.
* Usuarios y roles con proveedor de identidad: permite auditoría individual y
  revocación por usuario, pero añade una integración y administración pendientes.

## Decision Outcome

Se propone el token independiente como control del MVP local. Recomendaciones
usa `NAFTA2GO_API_TOKEN`; operación usa `NAFTA2GO_ADMIN_TOKEN`. Si éste falta o
coincide con el de conductor, operación responde 503 sin aceptar el token público.
El token administrativo tampoco habilita la consulta del conductor. Las lecturas
no se cachean. Readiness del recomendador no depende de la configuración opcional
del administrador, para permitir diagnosticar configuración degradada.

### Consequences and Confirmation

Se conserva comparación en tiempo constante y configuración por entorno; ningún
token se inserta en HTML, logs ni storage del cliente. Tests reproducen el acceso
del conductor antes del arreglo y verifican rechazo cruzado, falta de configuración
y reutilización accidental. No equivale a autenticación personal, HTTPS, auditoría
de usuarios ni autorización para publicar el servicio; esos controles siguen en #21.
