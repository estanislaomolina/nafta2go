---
status: Propuesto
date: 2026-11-19
decision-makers: Equipo Nafta2Go
consulted: ADR-004, ADR-009, issues 130 y 131
informed: Cátedra
---

# Búsqueda explícita de direcciones y lugares de CABA

## Context and Problem Statement

El conductor no conoce necesariamente las coordenadas de destino y el navegador
puede no obtener ubicación. Se requiere resolver una dirección o lugar sin cambiar
el contrato de coordenadas ni persistir la búsqueda en las recomendaciones.

## Considered Options

- Sólo coordenadas y GPS: no agrega dependencias, pero impide el uso a quien no
  conoce coordenadas y falla cuando el navegador no encuentra su ubicación.
- Nominatim público: cubre lugares amplios, pero exige condiciones de uso,
  identificación, caché, límite global y no admite autocompletado cliente.
- Servicios USIG/GCBA: direcciones y lugares de CABA sin una clave adicional;
  dependen de disponibilidad y cobertura del catálogo municipal.

## Decision Outcome

Se propone USIG, a través de un adaptador y un caso de uso propio. Primero se
normaliza una dirección; si no coincide, se consultan hasta tres lugares y se
geocodifica su dirección normalizada. Sólo se devuelven CABA y WGS84. La UI debe
pedir una elección explícita; no hay búsqueda automática mientras se escribe.

POST autenticado mantiene el texto fuera de la URL local. Las llamadas HTTPS al
proveedor sí incluyen el texto en sus parámetros; el conductor lo sabe antes de
buscar. No se envía el código de acceso al proveedor. Caché volátil de 64 entradas,
válidas diez minutos, y una búsqueda por segundo/proceso, sin consultas paralelas.
No se agregan búsquedas o coordenadas a la base ni a logs de la aplicación.

## Consequences and Confirmation

No es un índice completo de comercios ni garantiza disponibilidad. Cada consulta
puede hacer hasta ocho llamadas, con plazo de diez segundos comprobado antes de
cada llamada y durante lectura, timeouts de conexión/lectura y tope de 1 MiB.
La última operación de red puede terminar después del plazo por su timeout.
No hay reintentos remotos automáticos. El servicio puede deshabilitarse por entorno;
la recomendación conserva el ingreso manual. Para varias réplicas se requiere un
cupo/caché compartido. Tests reemplazan USIG; verificar dos ejemplos públicos reales
no acredita disponibilidad sostenida. La integración web se sigue en #130.

Fuentes: [API USIG](https://usig.buenosaires.gob.ar/apis/),
[EPOK](https://usig.buenosaires.gob.ar/apis/epok/epok.json),
[normalizador](https://servicios.usig.buenosaires.gob.ar/normalizar/) y
[política de Nominatim](https://operations.osmfoundation.org/policies/nominatim/).
ADR-021 está reservado para la propuesta de ranking de #20 en su rama de trabajo.
