# Nafta2Go Roadmap

## Propósito

Este roadmap organiza el trabajo necesario para las entregas de Diseño, POC y MVP. El archivo documenta la estrategia, los hitos y el orden de construcción; el seguimiento operativo se realizará en un GitHub Project vinculado al repositorio.

- **Fuente de verdad del alcance:** `docs/PRD.md`.
- **Fuente de verdad del estado del trabajo:** [GitHub Project — Nafta2Go: Roadmap del producto](https://github.com/users/estanislaomolina/projects/1).
- **Unidad de trabajo:** GitHub Issue vinculada a un requisito, riesgo o entregable.
- **Evidencia de implementación:** Pull Request vinculada a la Issue correspondiente.

No se fijan fechas en este documento hasta contar con el calendario definitivo de la cátedra. Las fechas de inicio y objetivo deben cargarse en el Project y mantenerse actualizadas allí.

## Configuración del GitHub Project

Project: **[Nafta2Go — Roadmap del producto](https://github.com/users/estanislaomolina/projects/1)**.

### Configuración aplicada

Al 18 de septiembre de 2026, el Project está público, vinculado a `estanislaomolina/nafta2go` y contiene las 24 Issues definidas en este roadmap. Todas fueron creadas por `estanislaomolina` y tienen cargados `Delivery`, `Workstream`, `Priority`, `Risk`, `Effort` y `PRD reference`.

La Issue [E1-03](https://github.com/estanislaomolina/nafta2go/issues/3), correspondiente a esta configuración, está en `In progress` y asignada a la iteración vigente. Las restantes permanecen en `Backlog` hasta que el equipo acuerde responsables y seleccione el trabajo de la semana.

Se configuraron seis vistas, seis estados de trabajo y siete iteraciones semanales a partir del 14 de septiembre de 2026. Estas iteraciones son ciclos operativos y no representan fechas oficiales de entrega. `Start date` y `Target date` permanecen vacíos hasta recibir el calendario definitivo de la cátedra.

Los siguientes ajustes dependen de decisiones del equipo o de controles disponibles sólo en la interfaz de GitHub Projects:

1. asignar responsables y fechas oficiales;
2. validar las estimaciones iniciales de esfuerzo;
3. elegir `Start date` y `Target date` como ejes de la vista `Roadmap` y agruparla por `Delivery`;
4. ajustar agrupaciones y orden visual de las vistas de tabla;
5. activar el workflow de agregado automático para futuras Issues del repositorio.

### Campos

| Campo | Tipo | Valores o uso |
|---|---|---|
| Status | Selección | Backlog, Ready, In progress, In review, Blocked, Done |
| Delivery | Selección | Entrega 1, POC, MVP |
| Workstream | Selección | Product & Docs, Data, Backend, Frontend, ML, Platform, QA |
| Priority | Selección | P0, P1, P2 |
| Risk | Selección | High, Medium, Low |
| Effort | Número | Puntos Fibonacci: 1, 2, 3, 5 u 8 |
| Iteration | Iteración | Siete ciclos semanales iniciales; el primero comienza el 14/09/2026 |
| Start date | Fecha | Inicio planificado |
| Target date | Fecha | Fecha objetivo |
| PRD reference | Texto | Identificador relacionado, por ejemplo `RF04` o `RNF05` |

Siempre que esté disponible, se usarán los campos nativos **Parent issue**, **Sub-issue progress** y las dependencias entre Issues. Las etiquetas del repositorio se reservarán para clasificar el tipo de trabajo (`feature`, `bug`, `spike`, `documentation`) y no duplicarán los campos del Project.

### Vistas

| Vista | Layout | Configuración aplicada | Objetivo |
|---|---|---|---|
| Roadmap | Roadmap | Sin filtro; pendiente seleccionar ejes de fecha y agrupación desde la interfaz | Comunicar el plan completo y sus dependencias |
| Current iteration | Board | Filtro `iteration:@current`; campos de estado, iteración, entrega, área, riesgo y esfuerzo | Gestionar el trabajo semanal |
| Delivery backlog | Table | Filtro `-status:Done`; campos de entrega, prioridad, riesgo, área, esfuerzo, iteración y fecha objetivo | Refinar y priorizar el alcance |
| High risks | Table | Filtro `risk:High`; campos de estado, entrega, área, prioridad, fecha y responsable | Hacer visibles los riesgos que pueden cambiar el plan |
| Team workload | Table | Filtro `-status:Done`; campos de responsable, área, esfuerzo, iteración y entrega | Distribuir trabajo entre integrantes |
| PRD traceability | Table | Campos de referencia al PRD, entrega, estado, repositorio y Pull Requests vinculadas | Comprobar que diseño e implementación cuentan la misma historia |

### Reglas operativas y automatizaciones

Las transiciones se aplicarán manualmente hasta que el equipo active y valide los workflows equivalentes en GitHub Projects.

- Todo Issue agregado al Project comienza en `Backlog`.
- Al asignar una Iteration, el Issue pasa a `Ready` si no está bloqueado.
- Al comenzar el trabajo, la persona responsable mueve el Issue a `In progress`.
- Al abrir una Pull Request vinculada, el Issue pasa a `In review`.
- Al cerrar el Issue o fusionar la Pull Request que lo resuelve, pasa a `Done`.
- Un Issue en `Blocked` debe indicar la causa, el responsable de destrabarlo y la próxima fecha de revisión.

## Convenciones de trabajo

Las épicas se representarán como Issues padre y sus entregables como sub-issues. Los títulos usarán un resultado observable, por ejemplo `Validar formato de fechas del histórico`, en lugar de nombres genéricos como `Trabajar en datos`.

Cada Issue debe incluir:

- objetivo y justificación;
- criterio de aceptación verificable;
- requisito del PRD relacionado, cuando corresponda;
- dependencias o bloqueos;
- evidencia esperada: prueba, documento, métrica o demostración.

Un Issue puede pasar a `Done` cuando su criterio de aceptación está verificado, la documentación afectada está actualizada y el cambio se encuentra integrado a la rama principal. No se considerará terminado sólo porque el código fue escrito.

## Hitos y orden de construcción

### Entrega 1 — Diseño

**Objetivo:** definir un producto coherente, demostrar la viabilidad preliminar con datos reales y dejar trazado el camino hacia la POC y el MVP.

| ID | Épica o resultado | Dependencias | Criterio de salida |
|---|---|---|---|
| [E1-01](https://github.com/estanislaomolina/nafta2go/issues/1) | PRD revisado y consistente | Aprobación inicial del proyecto | Incluye problema, contexto, usuarios, casos de uso, requisitos priorizados, criterios de éxito, supuestos y limitaciones |
| [E1-02](https://github.com/estanislaomolina/nafta2go/issues/2) | Evidencia de datos y viabilidad reproducible | Fuente oficial disponible | El notebook identifica cobertura, calidad, estaciones, histórico, riesgos, esfuerzo y planes alternativos |
| [E1-03](https://github.com/estanislaomolina/nafta2go/issues/3) | Roadmap operativo en GitHub Projects | E1-01 | El Project contiene campos, vistas, hitos, responsables y fechas de la cátedra |
| [E1-04](https://github.com/estanislaomolina/nafta2go/issues/4) | Decisiones iniciales registradas | E1-01, E1-02 | Los ADRs comparan alternativas relevantes y justifican las decisiones adoptadas |
| [E1-05](https://github.com/estanislaomolina/nafta2go/issues/5) | Entrega verificable | E1-01 a E1-04 | README actualizado, commit de entrega identificado y video de 5 a 12 minutos disponible |

### Entrega 2 — POC y SRD

**Objetivo:** resolver el mayor riesgo técnico y demostrar un recorrido de punta a punta con datos reales y alcance controlado.

| ID | Épica o resultado | Dependencias | Criterio de salida |
|---|---|---|---|
| [POC-01](https://github.com/estanislaomolina/nafta2go/issues/6) | Normalización de datos validada | E1-02 | Fechas, claves, coordenadas, productos y precios tienen reglas documentadas y pruebas reproducibles |
| [POC-02](https://github.com/estanislaomolina/nafta2go/issues/7) | Riesgo de cobertura resuelto | POC-01 | Se demuestra una consulta actual con cobertura suficiente o se activa un escenario histórico claramente rotulado |
| [POC-03](https://github.com/estanislaomolina/nafta2go/issues/8) | Proveedor de rutas validado | E1-02 | Una prueba autenticada confirma contratos, errores, límites y consumo de cuota; el plan alternativo queda documentado |
| [POC-04](https://github.com/estanislaomolina/nafta2go/issues/9) | Motor determinístico probado | POC-01 | Los cálculos de autonomía, reserva, carga, consumo y desvío pasan casos normales y de borde |
| [POC-05](https://github.com/estanislaomolina/nafta2go/issues/10) | Flujo vertical de punta a punta | POC-02, POC-03, POC-04 | Una consulta controlada usa datos reales, evalúa hasta diez estaciones y devuelve una recomendación explicada o una falta de cobertura honesta |
| [POC-06](https://github.com/estanislaomolina/nafta2go/issues/11) | Persistencia e ingesta mínimas | POC-01 | Una ejecución conserva datos normalizados, metadatos de ingesta y resultados de calidad |
| [POC-07](https://github.com/estanislaomolina/nafta2go/issues/12) | Base de calidad operativa | POC-05, POC-06 | CI, pruebas automáticas y procedimiento local están operativos |
| [POC-08](https://github.com/estanislaomolina/nafta2go/issues/13) | SRD y ADRs de la POC | POC-01 a POC-07 | Arquitectura, stack, modelo de datos, contratos y estrategia de datos coinciden con la implementación |
| [POC-09](https://github.com/estanislaomolina/nafta2go/issues/14) | Entrega verificable | POC-05, POC-07, POC-08 | README actualizado, commit identificado y video funcional de 5 a 12 minutos disponible |

### Entrega 3 — MVP

**Objetivo:** completar el producto definido en el PRD, automatizar su ciclo de vida y demostrar que puede ejecutarse, observarse y mantenerse.

| ID | Épica o resultado | Dependencias | Criterio de salida |
|---|---|---|---|
| [MVP-01](https://github.com/estanislaomolina/nafta2go/issues/15) | Ingesta productiva y trazable | POC-01, POC-06 | La ingesta programada conserva originales, normalizados, validaciones y versiones |
| [MVP-02](https://github.com/estanislaomolina/nafta2go/issues/16) | Recomendador completo | POC-04, POC-05 | Los requisitos imprescindibles de cálculo, descarte, ranking y explicación están implementados |
| [MVP-03](https://github.com/estanislaomolina/nafta2go/issues/17) | Aplicación web integrada | MVP-02 | El conductor puede completar los casos de uso priorizados y comprender resultados y errores |
| [MVP-04](https://github.com/estanislaomolina/nafta2go/issues/18) | Entrenamiento y baseline reproducibles | POC-01 | Las features respetan el tiempo, la evaluación es temporal y los artefactos quedan versionados |
| [MVP-05](https://github.com/estanislaomolina/nafta2go/issues/19) | Diagnóstico estadístico servido | MVP-04 | La API expone el diagnóstico sin reemplazar el precio oficial y aplica el plan alternativo si el modelo no supera el baseline |
| [MVP-06](https://github.com/estanislaomolina/nafta2go/issues/20) | Ranking conservador integrado | MVP-02, MVP-05 | El usuario puede comparar el resultado general con alternativas que excluyen precios alertados |
| [MVP-07](https://github.com/estanislaomolina/nafta2go/issues/21) | Operación segura y observable | MVP-01 a MVP-06 | Autenticación administrativa, métricas, logs, alertas y manejo de secretos son verificables |
| [MVP-08](https://github.com/estanislaomolina/nafta2go/issues/22) | Entrega y despliegue automatizados | POC-07, MVP-07 | CI/CD, contenedores, configuración externa y readiness cloud están demostrados |
| [MVP-09](https://github.com/estanislaomolina/nafta2go/issues/23) | Validación integral | MVP-01 a MVP-08 | Pruebas de punta a punta y criterios de éxito del PRD tienen evidencia registrada |
| [MVP-10](https://github.com/estanislaomolina/nafta2go/issues/24) | Documentación final y defensa | MVP-09 | README, ADRs y SRD están actualizados; el sistema se levanta localmente; video y demo están preparados |

## Dependencias críticas

```text
Normalización de datos ─┬─> Cobertura verificable ──┐
                        └─> Features temporales ──┤
Proveedor de rutas ─────> Flujo POC ─────┤─> Recomendador completo ─> Validación integral
Motor determinístico ───> Flujo POC ─────┘
Features temporales ──────> Modelo ──> Diagnóstico y ranking conservador
```

## Puertas de decisión y planes alternativos

| Puerta | Momento | Condición para avanzar | Plan alternativo |
|---|---|---|---|
| G1 Fechas confiables | Inicio de POC | No existen fechas futuras injustificadas y el formato está documentado | No unir fuentes ni entrenar hasta corregir la normalización |
| G2 Cobertura utilizable | Antes del flujo POC | Existen suficientes estaciones recientes para el escenario seleccionado | Usar una captura histórica verificada y rotulada como tal |
| G3 Rutas operables | Antes de integrar el recomendador | Cuota, latencia y contratos fueron comprobados con credenciales reales | Reducir candidatas, aplicar caché permitido o evaluar OSRM |
| G4 Señal predictiva | Antes de servir el modelo | El modelo se compara mediante validación temporal con el baseline acordado | Usar el modelo más simple y evitar presentar alertas no validadas como confianza |
| G5 Alcance sostenible | En cada revisión semanal | El trabajo P0 cabe en la capacidad restante con margen | Postergar P1/P2 y documentar el recorte |

## Seguimiento

El equipo revisará el Project al menos una vez por semana para:

1. actualizar estados, fechas, esfuerzo y responsables;
2. revisar Issues bloqueados y riesgos altos;
3. comparar capacidad disponible con trabajo P0 pendiente;
4. confirmar que cada cambio continúa trazado al PRD, SRD o ADR correspondiente;
5. publicar una actualización breve del Project con avances, decisiones, riesgos y próximos pasos.

El roadmap puede cambiar a partir de evidencia obtenida durante la POC. Todo cambio de alcance debe quedar documentado y, si modifica el alcance aprobado, debe revalidarse con la cátedra.
