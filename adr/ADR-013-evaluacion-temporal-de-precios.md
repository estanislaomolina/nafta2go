---
status: Propuesto
date: 2026-11-13
decision-makers: Equipo Nafta2Go (pendiente de revisión)
consulted: ADR-002, PRD RF10/RNF10, issues 18 y 56
informed: Equipo y cátedra
---

# Evaluación temporal retrospectiva de precios publicados

## Context and Problem Statement

El objetivo aprobado es diagnosticar un precio publicado, sin modificarlo ni
aprender el ranking. Para evaluar modelos hacen falta features y baseline con
el mismo contexto pasado. El histórico tiene fecha de vigencia, pero no conserva
cuándo cada fila se publicó por primera vez ni todas sus revisiones.

## Decision Drivers

* Excluir precio objetivo, observaciones simultáneas y futuras de las features.
* Mantener separado el diagnóstico de la factibilidad/ranking determinísticos.
* Poder reproducir cortes, abstenciones y comparaciones sin mejorar cifras ficticiamente.
* Explicitar qué demuestra una captura retrospectiva y qué no puede demostrar.

## Considered Options

* Partición aleatoria y agregados del mes completo.
* Corte temporal y features calculadas antes de cada instante de vigencia.
* Backtesting con capturas acumuladas y disponibilidad real por observación.

## Decision Outcome

Chosen option: **corte temporal retrospectivo para evaluación offline**, porque
permite comenzar con el histórico disponible sin mezclar objetivos y features.
Se asume que fecha de vigencia aproxima disponibilidad; no se afirma que eso se
haya verificado. La tercera opción es necesaria para contrastar esa limitación
con capturas futuras; no se sustituye su evidencia con el histórico descargado hoy.

La ventana comparable contiene observaciones de los 30 días anteriores, con el
borde inferior incluido y el instante objetivo excluido. El baseline es mediana
por producto/franja/zona de 0,02 grados; si faltan cinco observaciones se usa CABA
por producto/franja. Si tampoco alcanza, se abstiene y se contabiliza cobertura.
Son observaciones, no estaciones distintas: cambios frecuentes pueden pesar más.

Se preparan features para cada instante antes de incorporar cualquier precio de
ese instante. Entrenamiento termina estrictamente antes del corte; validación
usa observaciones posteriores. Sus features pueden usar publicaciones previas
de validación, simulando actualización de contexto sin reentrenar el modelo.
Imputación, codificación y ajuste de modelos deberán entrenarse sólo en train.

### Consequences

* Good, because se prueba causalidad temporal y se conserva la abstención.
* Good, because baseline y futuros modelos comparten ejemplos y features.
* Bad, because metadatos/precios del archivo podrían haberse corregido después.
* Bad, because un corte retrospectivo no demuestra rendimiento en producción.
* Bad, because zonas rectangulares no representan barrios ni acceso vial.

### Confirmation

Pruebas modifican objetivos/futuros sin cambiar features anteriores o simultáneas,
reordenan entrada, comprueban el corte, expiración y aislamiento de grupos. No se
usan las alertas mensuales de normalización como variables ni para eliminar
precios atípicos: dependen del mes completo. Sólo se excluye geometría/alcance.

## Pros and Cons of the Options

* **Aleatorio/mes completo:** simple; mezcla épocas e incorpora precio objetivo
  y datos posteriores. No permite validar el objetivo declarado.
* **Temporal por vigencia:** reproducible con el archivo existente y contexto
  anterior explícito; depende del supuesto de disponibilidad y posibles revisiones.
* **Capturas por disponibilidad:** representa mejor qué conocía el sistema;
  exige acumular evidencia que hoy no existe para todo el período histórico.

## More Information

La mediana es baseline estadístico, no ML. Esta decisión no habilita alertas,
serving, estimaciones actuales de datos antiguos (#57) ni cambia el recomendador.
Faltan comparar modelos, validar umbrales y revisar la política antes de servir.
