# Nafta2Go PRD (Product Requirements Document)

## Problema

Actualmente, cuando una persona se encuentra conduciendo y necesita cargar combustible, debe dirigirse a una estación de servicio. En este contexto, surge una decisión frecuente: determinar a qué estación de servicio acudir. La elección del conductor puede estar condicionada por diversos factores, entre ellos, la proximidad de la estación y el precio del combustible. Estos factores pueden variar en importancia según las necesidades y preferencias de cada conductor.

Elegir la estación con el menor precio publicado no garantiza la mejor decisión. El conductor necesita saber si puede llegar con una reserva segura, cuánto combustible podrá comprar, cuánto consumirá durante el desvío y cómo quedará su autonomía al completar el recorrido.

Hoy esos factores se evalúan de manera fragmentada. Además, la vigencia, cobertura y continuidad de los precios públicos pueden variar. El producto debe evitar una falsa precisión: cuando no haya datos suficientes o una ruta no pueda calcularse, deberá comunicarlo de forma explícita.

## Contexto

El producto utilizará como fuente principal el conjunto público de precios en surtidor de la Secretaría de Energía, publicado bajo licencia CC BY 4.0. En una exploración ejecutada el 18 de septiembre de 2026 se descargaron 36.667 registros, de los cuales 1.630 correspondían a CABA y 732 a nafta súper o premium. Estos últimos representaban 184 identificadores de estación. Las validaciones estructurales no detectaron faltantes en los campos requeridos, precios no positivos, coordenadas fuera del área esperada ni duplicados de la clave lógica candidata.

El histórico filtrado para nafta en CABA contiene 20.522 observaciones, 76 identificadores de estación y aproximadamente 142 meses de cobertura. Este volumen permite avanzar con una POC de diagnóstico estadístico de precios y validación temporal. No obstante, se detectaron 84 fechas posteriores a la ejecución, lo que exige confirmar la interpretación de día y mes antes de unir las fuentes o entrenar modelos. Tampoco se ha demostrado todavía que un modelo supervisado mejore un baseline basado en medianas comparables.

Aunque la estructura del conjunto vigente es adecuada, su cobertura reciente es insuficiente para sostener actualmente una recomendación representativa en toda CABA. Sólo 8 registros, correspondientes a 2 estaciones (YPF), tenían una antigüedad menor o igual a 30 días. Por lo tanto, la viabilidad del producto queda condicionada a la recuperación de la cobertura o a la utilización de escenarios históricos claramente identificados. El sistema no deberá presentar precios antiguos como actuales.

La evidencia permite avanzar, pero el dictamen actual es **viable con condiciones y/o recorte de alcance**. El mayor riesgo técnico es la baja cobertura de precios recientes, agravada por la ambigüedad detectada en algunas fechas históricas. Antes de unir fuentes o entrenar modelos se deberá confirmar el formato de fechas; para demostrar recomendaciones se exigirá cobertura reciente suficiente o se utilizará un escenario histórico reproducible y claramente rotulado.

Para el proveedor de rutas, la estimación preliminar contempla hasta 22 ubicaciones por matriz y 40 solicitudes diarias, equivalentes al 8 % de una cuota asumida de 500 solicitudes. El flujo resulta factible en papel, pero la cuota, los límites y la latencia deben validarse con una cuenta autenticada. Si esa prueba falla, se reducirá la cantidad de candidatas y se evaluará OSRM como alternativa.

La estimación de esfuerzo parte de la hipótesis de tres integrantes, doce semanas y seis horas semanales por persona: 216 horas disponibles frente a 214 planificadas. El margen de 2 horas (0,9 %) es insuficiente respecto del 10 % propuesto en la exploración. Por eso, la viabilidad temporal requiere priorizar los requisitos `Debe`, revisar semanalmente la capacidad real y postergar requisitos `Debería` o `Podría` si no se recupera margen.

## Usuarios

| Actor | Necesidad | Responsabilidad o interacción |
|---|---|---|
| Conductor | Elegir dónde cargar sin comprometer autonomía, presupuesto ni tiempo. | Ingresa origen, destino opcional, vehículo, combustible disponible, presupuesto, producto y prioridad; compara resultados. |
| Operador | Mantener el servicio y comprender fallos o degradaciones. | Supervisa ingestas, calidad de datos, cobertura, rutas, modelos y métricas operativas. |
| Administrador | Gestionar funciones sensibles. | Accede mediante autenticación a controles y vistas administrativas. |

## Casos de uso

- UC01 Buscar con destino. El conductor compara origen-estación-destino contra la ruta directa origen-destino.
- UC02 Buscar sin destino. El conductor evalúa origen-estación-origen para una carga de ida y vuelta.
- UC03 Comparar prioridades. El conductor alterna entre combustible neto, menor desvío y equilibrio.
- UC04 Entender una recomendación. El conductor consulta precio, litros comprables, consumo estimado, reserva, desvío, vigencia y fuente.
- UC05 Revisar precios de baja confianza. El conductor ve una advertencia y compara el ranking general con el conservador.
- UC06 Entender la falta de resultados. El conductor recibe motivos concretos: incompatibilidad, autonomía, presupuesto, tanque, antigüedad o ruta no disponible.
- UC07 Supervisar la operación. El operador revisa ingestas, calidad, cobertura, latencia, fallos y comportamiento del modelo.

## Requisitos funcionales priorizados

Prioridad MoSCoW: Debe = imprescindible para considerar completo el producto definido; Debería = importante, pero admite postergación justificada; Podría = mejora opcional.

| ID | Prioridad | Requisito | Criterio de aceptación |
|---|---|---|---|
| RF01 | Debe | Capturar y validar los datos de la consulta. | Rechaza valores faltantes, no numéricos o físicamente inconsistentes con un mensaje accionable. |
| RF02 | Debe | Filtrar por CABA y tipo de nafta compatible. | Ninguna estación incompatible aparece en los resultados. |
| RF03 | Debe | Preseleccionar y enrutar hasta veinte estaciones. | La evaluación nunca supera el máximo configurado y registra fallos de ruta. |
| RF04 | Debe | Calcular alcanzabilidad, reserva, consumo, capacidad, litros comprables y desvío. | Los cálculos son determinísticos y reproducibles para la misma entrada y versión de datos. |
| RF05 | Debe | Descartar alternativas inviables. | Cada descarte conserva al menos un motivo normalizado y visible cuando no haya resultados. |
| RF06 | Debe | Mostrar hasta tres alternativas diferenciadas. | Incluye combustible neto, menor desvío y equilibrio; evita duplicar una estación sin explicarlo. |
| RF07 | Debe | Explicar cada resultado. | Muestra precio, litros, consumo, reserva estimada, desvío, fuente, vigencia y consulta. |
| RF08 | Debe | Ingerir y normalizar precios diariamente. | Registra ejecución, archivo original, validaciones, transformaciones y resultado. |
| RF09 | Debe | Aplicar umbral configurable de vigencia. | Si la cobertura es insuficiente, informa la limitación y no presenta datos antiguos como actuales. |
| RF10 | Debe | Emitir diagnóstico de confianza del precio. | El diagnóstico no modifica el precio oficial y expone nivel de confianza y versión del modelo. |
| RF11 | Debe | Comparar ranking general y conservador. | El conservador excluye precios de baja confianza y muestra diferencias de forma comprensible. |
| RF12 | Debe | Autenticar funciones administrativas. | Una persona no autenticada no puede acceder a funciones administrativas. |
| RF13 | Debería | Permitir configurar reserva, vigencia y parámetros operativos. | Los cambios quedan auditados y no requieren modificar código. |
| RF14 | Debería | Presentar estado operativo al administrador. | Muestra ingestas, cobertura, errores de rutas y métricas del modelo. |
| RF15 | Podría | Ejecutar escenarios históricos de demostración. | Todo escenario se identifica como histórico y conserva su captura de datos. |


## Requisitos no funcionales

| ID | Definición verificable |
|---|---|
| RNF01 Rendimiento | Objetivo propuesto: p95 menor o igual a 5 s para una consulta con hasta veinte candidatas, salvo degradación declarada del proveedor externo. |
| RNF02 Disponibilidad | La interfaz informa dependencias degradadas y evita respuestas parcialmente válidas sin señalización. |
| RNF03 Privacidad | Las ubicaciones de usuarios no se conservan por defecto; las métricas de uso se anonimizan. |
| RNF04 Seguridad | Autenticación administrativa, secretos fuera del código, validación de entradas y mínimo privilegio. |
| RNF05 Trazabilidad | Toda recomendación puede vincularse con versiones de datos, reglas, rutas y modelo utilizadas. |
| RNF06 Calidad | Pruebas unitarias, integración, contrato y flujo de punta a punta en CI. |
| RNF07 Portabilidad | Contenedores, configuración externa, ejecución local documentada y preparación para cloud. |
| RNF08 Observabilidad | Métricas, logs estructurados y alertas para consultas, ingestas, cobertura y modelo. |
| RNF09 Accesibilidad | Interfaz navegable por teclado, etiquetas de formulario y mensajes que no dependan solo del color. |
| RNF10 Reproducibilidad ML | Datos, features, código, parámetros y artefactos versionados; entrenamiento y serving repetibles. |


## Criterios de éxito medibles

Los valores siguientes son objetivos propuestos para validar con el equipo antes de congelar el alcance. Las métricas de impacto requieren una prueba con usuarios; las técnicas pueden medirse desde la POC.

| Dimensión | Métrica | Objetivo | Medición |
|---|---|---|---|
| Utilidad | % de participantes que identifica una opción preferida y explica el motivo | ≥ 80% en prueba moderada | Prueba con ≥ 10 conductores |
| Comprensión | % que interpreta correctamente precio, desvío y combustible neto | ≥ 80% | Preguntas posteriores a la tarea |
| Factibilidad | % de recomendaciones que respeta todas las restricciones en casos de prueba | 100% | Suite automatizada |
| Explicabilidad | % de resultados y descartes con motivo trazable | 100% | Logs y pruebas de contrato |
| Rendimiento | Latencia de consulta p95 | ≤ 5 s | Telemetría de API |
| Ingesta | % de ejecuciones diarias completadas o alertadas dentro de 24 h | ≥ 95% | Monitoreo del pipeline |
| Frescura | % de precios usados dentro del umbral configurado | 100% | Auditoría de recomendaciones |
| ML | MAE frente al baseline en validación temporal | Mejora material acordada o adopción explícita del modelo simple | Reporte reproducible |
| Privacidad | % de consultas sin ubicación persistida por defecto | 100% | Prueba y revisión de almacenamiento |

## Supuestos

| Supuesto | Evidencia o validación pendiente | Plan alternativo |
|---|---|---|
| `idempresa` representa de manera suficientemente estable una estación física. | El histórico no mostró cambios de nombre o dirección, pero la semántica del identificador no está confirmada documentalmente. | Construir una clave canónica con dirección y coordenadas, y excluir casos ambiguos. |
| Un precio con hasta 30 días de antigüedad resulta aceptable para orientar una decisión académica. | El umbral es una decisión del proyecto y no garantiza el precio real en surtidor. | Hacerlo configurable y mostrar siempre fecha, fuente y antigüedad. |
| La cobertura de precios recientes puede resultar suficiente para generar alternativas útiles. | Actualmente sólo 2 de 184 estaciones cumplen el umbral. | Informar cobertura insuficiente y utilizar escenarios históricos claramente rotulados. |
| Las fechas de las fuentes vigente e histórica pueden normalizarse sin ambigüedad. | Se detectaron 84 fechas posteriores a la ejecución. | Confirmar el formato con la documentación, conservar el valor original y rechazar fechas inconsistentes. |
| Las coordenadas publicadas representan razonablemente la ubicación de acceso a la estación. | Sólo se validó que pertenezcan al área geográfica de CABA. | Verificar manualmente las estaciones usadas en los casos de prueba y demostración. |
| El usuario puede informar consumo, capacidad del tanque y combustible restante con precisión suficiente. | Todavía no fue validado con usuarios. | Validar rangos, ofrecer ayuda y comunicar que los resultados son estimaciones. |
| Un consumo promedio permite estimar autonomía y combustible utilizado con precisión útil. | No se consideran tránsito, pendiente, clima, carga ni estilo de conducción. | Aplicar una reserva configurable y evitar garantías de autonomía exacta. |
| La preselección de veinte estaciones permite encontrar alternativas relevantes. | Debe comprobarse durante la prueba de concepto. | Ajustar el radio o la cantidad máxima de candidatas. |
| El proveedor de rutas tendrá disponibilidad y cuota suficientes para el uso esperado. | La cuota todavía no fue comprobada mediante una cuenta autenticada. | Reducir candidatas, aplicar caché permitido o evaluar OSRM. |
| El histórico contiene señal suficiente para construir una referencia estadística de precios. | Existe volumen suficiente, pero todavía no se entrenó ni evaluó ningún modelo. | Ampliar el entrenamiento a datos nacionales y mantener una evaluación separada sobre CABA. |
| El modelo podrá mejorar o complementar un baseline simple. | No existe evidencia de mejora en este momento. | Utilizar el modelo más simple evaluado y evitar alertas accionables si su desempeño no es adecuado. |
| Los conductores aceptarán ingresar los datos requeridos a cambio de una recomendación explicada. | Debe validarse mediante pruebas con usuarios. | Reducir entradas y ofrecer valores predeterminados u orientativos. |
| La disponibilidad real del equipo coincide con las horas estimadas. | El cálculo actual deja sólo dos horas de margen. | Priorizar requisitos imprescindibles y postergar funcionalidades de menor prioridad. |

## Limitaciones

La principal limitación observada es la vigencia de los precios. Sólo 8 registros, correspondientes a 2 estaciones, tenían una fecha de vigencia dentro de los 30 días anteriores a la ejecución. La antigüedad mediana superaba los 400 días para ambos tipos de nafta. En consecuencia, la frecuencia de actualización del archivo no garantiza que cada precio individual sea reciente. El sistema deberá informar la fecha de vigencia y abstenerse de presentar una recomendación como actual cuando no exista cobertura suficiente.

  - Alcance geográfico limitado a CABA.
  - Sólo nafta súper y premium.
  - Una única estación por recorrido.
  - Sin información de stock, filas u horarios reales.
  - Sin promociones bancarias ni descuentos.
  - Sin tránsito en tiempo real.
  - Sin navegación paso a paso.
  - Los precios provienen de terceros y no se verifican físicamente.
  - La autonomía depende de los datos proporcionados por el usuario.
  - Las rutas, distancias y duraciones dependen de un proveedor externo.
  - El diagnóstico estadístico no determina que un precio sea verdadero o incorrecto.
