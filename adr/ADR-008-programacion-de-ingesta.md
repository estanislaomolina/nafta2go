---
status: Aceptado
date: 2026-11-09
decision-makers: Equipo Nafta2Go
consulted: PRD (RF08, RNF08), ADR-005, issue MVP-01
informed: Cátedra
---

# Programar la ingesta local con un temporizador de systemd

## Context and Problem Statement

La POC ingiere manualmente. RF08 exige hacerlo diariamente y RNF08 exige detectar
fallos. Necesitamos programar el comando existente conservando la base y los
originales en el mismo equipo; la frecuencia de descarga no cambia la vigencia
individual de cada precio.

## Decision Drivers

* Ejecución diaria sin superponer instancias de la misma tarea.
* Recuperación tras períodos sin servicio y registro de salida y fallos.
* Persistencia de detección y resolución de alertas, sin exportar errores sensibles.
* Instalación explícita y reversible, sin servicios externos adicionales.

## Considered Options

* Temporizador y servicio de usuario de systemd.
* Cron local.
* Bucle de programación dentro de la aplicación.

## Decision Outcome

Chosen option: **systemd**, porque permite recuperar una ejecución omitida,
limitar su duración y consultar su salida sin incorporar un proceso planificador.
Se programa el vigente diariamente a las 06:00 de Argentina. El histórico sigue
bajo demanda. Las unidades se entregan sin activarlas automáticamente.
`Persistent` recupera omisiones; no reintenta fallos de DNS o adquisición.
El comando implementa tres intentos de adquisición remota con esperas de 60 y
120 s, dentro de una sola ejecución trazable. Se prefiere esto a `Restart` del
servicio, que reiniciaría el ciclo completo y generaría otra ingesta. Solo se
repiten fallos transitorios de red/descarga o HTTP 502/503/504 sin `Retry-After`;
los demás errores fallan sin reintento. Normalización y persistencia se ejecutan
una vez. Ver [política y límites](../docs/INGESTA.md).

Se agrega un monitor horario, invocado también mediante `OnFailure`, que detecta
la última ingesta fallida, procesos en `running` por dos horas y ausencia diaria
tras dos horas de tolerancia. La tabla `ingestion_alerts` conserva detección,
seguimiento y resolución. Las alertas se exponen localmente en JSON y journal;
no se configura un receptor externo.

### Consequences

* Good, because usa el comando probado y conserva datos en el equipo operador.
* Good, because una unidad activa no se solapa consigo misma.
* Bad, because depende de Linux y de un gestor de usuario activo.
* Bad, because no impide ingestas manuales simultáneas ni entrega por sí solo
  notificaciones a una persona. Requiere supervisar el journal o conectar un colector.

### Confirmation

Validar las unidades con `systemd-analyze --user verify`, comprobar el calendario
y probar el registro de errores de adquisición y normalización sin red. Antes de
cerrar MVP-01, registrar evidencia de los temporizadores instalados y su supervisión.
Los tests con reloj controlado verifican las marcas de detección, la deduplicación,
la recuperación y el aislamiento entre fuentes.

La evidencia de [instalación y operación](../docs/INGESTA.md) incluye el ensayo
con fixture y la instalación del 09/11, fallos de DNS del 11 y 12/11 y recuperación
manual del 12/11. No demuestra disponibilidad continua ni éxito diario del timer.

## Pros and Cons of the Options

### Systemd

* Good, because conserva journal, estado, timeout y recuperación con `Persistent`.
* Bad, because requiere configurar el gestor de usuario en el equipo de operación.

### Cron

* Good, because es simple y ampliamente disponible en Unix.
* Bad, because requiere mecanismos extra para recuperar ejecuciones omitidas,
  impedir superposiciones y consultar el resultado de cada tarea.

### Bucle en la aplicación

* Good, because permite ejecutar en distintos sistemas operativos con Python.
* Bad, because obliga a implementar persistencia del calendario, supervisión y
  coordinación entre instancias, sin mejorar la normalización.

## More Information

* [Instalación y pendientes de MVP-01](../docs/INGESTA.md).
