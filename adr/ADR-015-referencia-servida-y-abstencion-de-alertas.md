---
status: Aceptado
date: 2026-11-16
decision-makers: Equipo Nafta2Go
consulted: ADR-013, ADR-014, MVP-05, issues 19 y 56
informed: Cátedra
---

# Referencia servida y abstención de alertas

## Context and Problem Statement

La evaluación de #102 elige `bandera_reciente`, pero conserva boosting como
artefacto para comparación. No hay umbrales de alerta validados: una diferencia
respecto de una referencia no demuestra un error de la fuente.

## Considered Options

* Servir `artifact_model`: aprovecha el pipeline entrenado, pero puede publicar
  un método que perdió la selección temporal y requiere cargar el pickle.
* Servir la referencia elegida, absteniéndose de alertar: respeta la selección,
  permite probar paridad y evita conclusiones sin calibración; deja alertas y
  serving de modelos aprendidos pendientes.
* Desactivar todo diagnóstico hasta calibrar: evita conclusiones prematuras,
  pero también oculta una referencia descriptiva trazable.

## Decision Outcome

Se propone la segunda opción como incremento parcial de #19. Se admiten las
tres referencias de #102; una selección de modelo aprendido se rechaza hasta
validar su inferencia. No se carga `model.joblib` ni se sustituye la selección.
Manifiestos enlazados por hash fijan features, ventana y mínimo de historia;
captura histórica y reglas deben coincidir con los datos usados.

El objetivo es la publicación de la última ingesta vigente exitosa. Se reutiliza
la preparación de entrenamiento con observaciones estrictamente anteriores.
Su disponibilidad sigue siendo el supuesto retrospectivo de ADR-013, no evidencia
de qué conocía el sistema entonces. No estima el precio actual de datos antiguos.

### Consequences and Confirmation

* Precio, fecha, referencia, diferencia y versión permanecen separados.
* `not_calibrated` no significa normal ni anómalo. No cambia ranking ni vigencia.
* Tests de paridad con entrenamiento, fallback de bandera, causalidad, datos
  ausentes, manifiestos incompatibles, acceso y ausencia de escrituras.
* Las lecturas proyectan campos y filtran producto/franja/tiempo en SQL; no
  recortan el precio previo por antigüedad. Aún no acreditan p95 ni capacidad
  bajo carga. Faltan
  calibración, serving aprendido, métricas e integración visual; #19 sigue abierta.
