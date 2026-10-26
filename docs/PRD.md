# Nafta2Go PRD (Product Requirements Document)

## Problema

Actualmente, cuando una persona se encuentra conduciendo y necesita cargar combustible, debe dirigirse a una estación de servicio. En este contexto, surge una decisión frecuente: determinar a qué estación de servicio acudir. La elección del conductor puede estar condicionada por diversos factores, entre ellos, la proximidad de la estación y el precio del combustible. Estos factores pueden variar en importancia según las necesidades y preferencias de cada conductor.

Elegir la estación con el menor precio publicado no garantiza la mejor decisión. El conductor necesita saber si puede llegar con una reserva segura, cuánto combustible podrá comprar, cuánto consumirá durante el desvío y cómo quedará su autonomía al completar el recorrido.

Hoy esos factores se evalúan de manera fragmentada. Además, la vigencia, cobertura y continuidad de los precios públicos pueden variar. El producto debe evitar una falsa precisión: cuando no haya datos suficientes o una ruta no pueda calcularse, deberá comunicarlo de forma explícita.

## Contexto

La exploración de este apartado corresponde a la Entrega 1, del 18/09/2026.
La actualización de datos y verificaciones de la POC está en la sección
«Respuesta a la devolución de la Entrega 1». Los conteos siempre se interpretan
con su fecha y fuente.

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

Cada requisito define una métrica, un umbral y cómo comprobarlo. Los objetivos de
MVP siguen siendo compromisos de aceptación, no resultados ya obtenidos. La POC
tiene interfaz de comandos y hasta diez candidatas; no incluye API pública, web
ni ML. Una prueba del adaptador de rutas no acredita el rendimiento del sistema
completo. Los límites externos se observan por cuenta y fecha.

| ID | Métrica y umbral de aceptación | Medición | Etapa y estado |
|---|---|---|---|
| RNF01 Rendimiento | p95 ≤ 5 s para consultas válidas con hasta veinte candidatas y proveedor disponible. Reportar también errores y dependencias degradadas. | Lote de ≥ 100 consultas UC01/UC02; medir desde entrada hasta respuesta, incluida la llamada de rutas, con datos y entorno identificados. | MVP: pendiente la medición completa. POC: diez candidatas; solo se midió la latencia del adaptador ORS, no este p95. |
| RNF02 Disponibilidad | El 100% de los casos de credencial inválida, cuota, timeout y respuesta de proveedor inválida produce un error explícito; 0 recomendaciones presentadas como válidas a partir de rutas inventadas o parciales. Timeout de conexión 5 s y lectura 15 s. | Pruebas de contrato con respuestas 401/403/429/5xx, timeout y matrices inválidas; el código propaga el error o descarta la candidata sin ruta. | POC: implementado y probado; no equivale a un SLA de disponibilidad de Internet o del proveedor. |
| RNF03 Privacidad | 0 coordenadas de origen o destino del usuario en el historial persistido por defecto; el 100% de recomendaciones respeta esa regla. | Auditar request/result guardados y pruebas de campos prohibidos. Las matrices guardadas requieren una opción explícita y quedan fuera de ese historial. | POC: implementado. MVP: aplicar también a telemetría, exportaciones y métricas de uso. |
| RNF04 Seguridad | 0 secretos nuevos detectados por gitleaks; el 100% de entradas inválidas de los casos de prueba se rechaza. En MVP, el 100% de accesos administrativos sin credencial válida se rechaza con 401/403. | Check Secretos en cada PR y push; pruebas de validación. Para MVP, pruebas de autenticación/autorización de cada función administrativa. | POC: secretos y validación operativos; no hay interfaces administrativas expuestas. Autenticación: pendiente para MVP. |
| RNF05 Trazabilidad | El 100% de recomendaciones persistidas tiene exactamente un origen: ingesta exitosa o escenario con ID, fecha y hashes. Incluye versión del motor, proveedor de rutas y parámetros; los precios conservan su fila de origen. | Restricción CHECK, validación del repositorio y pruebas de ambos orígenes. Versiones y reporte de normalización en la ingesta; referencia de la matriz en el resultado cuando se captura/reproduce. | POC: implementado. MVP: añadir versión del diagnóstico ML al usarlo. |
| RNF06 Calidad | Cobertura de líneas de nafta2go ≥ 90%; 0 pruebas fallidas. Job Tests completo ≤ 5 min en GitHub Actions Ubuntu/Python 3.12, incluida instalación. Para entregar: 5/5 checks exitosos; el ruleset exige automáticamente 4. | pytest-cov con --cov-fail-under=90; timeout-minutes: 5 en Tests; revisar Lint, Docs y notebooks, Tests, Secretos y Contenedores. | POC: control automático en CI. El porcentaje mide líneas, no cobertura de ramas ni ausencia de defectos. |
| RNF07 Portabilidad | El procedimiento documentado termina con código 0 en instalación local Python 3.12 y en la imagen Docker: esquema en head y consulta reproducida con diez evaluaciones y recomendación persistida. 0 credenciales embebidas en la imagen. | README desde entorno limpio; check Contenedores construye, migra, verifica head y ejecuta la consulta sin red ni clave. | POC: local y CI verificados. Readiness de los servicios de producción: MVP, todavía pendiente. |
| RNF08 Observabilidad | En MVP, el 100% de consultas e ingestas que terminan normalmente registra identificador, fecha, duración y estado; 0 secretos o ubicaciones del usuario en logs. Detectar un fallo de ingesta diaria en ≤ 24 h. | Pruebas de captura de logs, consulta de registros y simulación de fallo con marca de detección; revisar también ejecuciones interrumpidas. | POC: estados y reportes de ingesta persistidos. Telemetría completa, métricas y alertas: pendientes para MVP. |
| RNF09 Accesibilidad | En MVP, el 100% de los pasos de UC01, UC02 y UC06 se completa con teclado; el 100% de campos tiene etiqueta; 0 errores críticos en el análisis automatizado elegido. | Checklist manual de esos recorridos y reporte automatizado sobre la web entregada, con herramienta y versión identificadas. | MVP: pendiente; no se presenta una CLI como evidencia de accesibilidad de una web inexistente. |
| RNF10 Reproducibilidad ML | En MVP, el 100% de entrenamientos registra hashes de datos, código, parámetros y semilla. Dos repeticiones con el mismo entorno/entradas difieren ≤ 1e-6 en la métrica declarada; cargar el mismo artefacto reproduce predicciones con tolerancia ≤ 1e-6. | Comparar manifiestos, métricas y predicciones sobre un conjunto fijo; documentar el entorno y cualquier fuente de no determinismo. | MVP: pendiente. No se diseña aún entrenamiento, serving ni monitoreo en el SRD de la POC. |

### Respuesta a la devolución de la Entrega 1

La devolución aprobó el diseño y pidió precisar requisitos que no tenían umbral
de medición. La tabla anterior sustituye las descripciones generales por
criterios de aceptación y distingue lo construido de los objetivos de MVP.

Como línea de base, en el código 8ae8ab0 se midieron 353 pruebas y 148 subtests,
con 1.249 de 1.307 líneas ejecutables de nafta2go cubiertas: **95,56%**. La
corrida local con cobertura duró 38,99 s; ese tiempo no se presenta como tiempo
de CI. El mínimo exigido es **90%** y el límite del job de CI es **5 min**.
La cobertura excluye las pruebas como objeto de medición y no es cobertura de
ramas. La medición se reproduce con el comando de [CALIDAD](CALIDAD.md).

La observación sobre datos se responde usando el CSV oficial completo en lugar
del DataStore parcial y validando fechas con formato fijo. El histórico actual
normalizado tiene 80.008 filas válidas de CABA y nafta sobre 80.025 leídas; se
rechazan seis fechas inválidas, una futura y diez precios no positivos. Las 84
fechas futuras observadas en la Entrega 1 no se pueden reconstruir exactamente
porque aquella consulta de DataStore ya no existe; sí se reprodujo el error de
interpretar mes y día al revés. La evidencia, formatos y límites están en
[NORMALIZACION](NORMALIZACION.md).

Los conteos del contexto y exploración inicial corresponden al 18/09/2026. En
la captura del 24/10 y con referencia al 26/10 se obtuvieron 30 estaciones de
súper diurna recientes en CABA y 16 dentro del corredor Obelisco–Cabildo; se
evaluaron diez. Esto no garantiza cobertura representativa de toda CABA. La
falta de cobertura activa un escenario congelado rotulado, como se demuestra
en [POC-05](POC-05.md). Cuota diaria de 500 y límite de 40 llamadas por minuto
se verificaron para la cuenta de ORS de la POC con evidencia fechada en
[RUTAS](RUTAS.md).


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
| La cobertura de precios recientes puede resultar suficiente para generar alternativas útiles. | En la exploración del 18/09 solo 2 de 184 estaciones cumplían el umbral; la captura de POC tiene cobertura variable y se mide por recorrido (ver COBERTURA.md). | Informar cobertura insuficiente y utilizar escenarios históricos claramente rotulados. |
| Las fechas de las fuentes vigente e histórica pueden normalizarse sin ambigüedad. | En la exploración inicial se detectaron 84 fechas posteriores a la ejecución; la POC confirmó día primero en el CSV histórico y conserva rechazos y originales (ver NORMALIZACION.md). | Confirmar el formato con la documentación, conservar el valor original y rechazar fechas inconsistentes. |
| Las coordenadas publicadas representan razonablemente la ubicación de acceso a la estación. | Sólo se validó que pertenezcan al área geográfica de CABA. | Verificar manualmente las estaciones usadas en los casos de prueba y demostración. |
| El usuario puede informar consumo, capacidad del tanque y combustible restante con precisión suficiente. | Todavía no fue validado con usuarios. | Validar rangos, ofrecer ayuda y comunicar que los resultados son estimaciones. |
| Un consumo promedio permite estimar autonomía y combustible utilizado con precisión útil. | No se consideran tránsito, pendiente, clima, carga ni estilo de conducción. | Aplicar una reserva configurable y evitar garantías de autonomía exacta. |
| La preselección de veinte estaciones permite encontrar alternativas relevantes. | Debe comprobarse durante la prueba de concepto. | Ajustar el radio o la cantidad máxima de candidatas. |
| El proveedor de rutas tendrá disponibilidad y cuota suficientes para el uso esperado. | Cuota diaria de 500 y límite de 40 por minuto verificados para la cuenta y fecha de POC; revisar de nuevo si cambia el plan o el proveedor (ver RUTAS.md). | Reducir candidatas, aplicar caché permitido o evaluar OSRM. |
| El histórico contiene señal suficiente para construir una referencia estadística de precios. | Existe volumen suficiente, pero todavía no se entrenó ni evaluó ningún modelo. | Ampliar el entrenamiento a datos nacionales y mantener una evaluación separada sobre CABA. |
| El modelo podrá mejorar o complementar un baseline simple. | No existe evidencia de mejora en este momento. | Utilizar el modelo más simple evaluado y evitar alertas accionables si su desempeño no es adecuado. |
| Los conductores aceptarán ingresar los datos requeridos a cambio de una recomendación explicada. | Debe validarse mediante pruebas con usuarios. | Reducir entradas y ofrecer valores predeterminados u orientativos. |
| La disponibilidad real del equipo coincide con las horas estimadas. | El cálculo actual deja sólo dos horas de margen. | Priorizar requisitos imprescindibles y postergar funcionalidades de menor prioridad. |

## Limitaciones

La principal limitación observada es la vigencia de los precios. En la exploración del 18/09, solo 8 registros de 2 estaciones tenían vigencia dentro de los 30 días anteriores a esa ejecución. La antigüedad mediana superaba los 400 días para ambos tipos de nafta. En consecuencia, la frecuencia de actualización del archivo no garantiza que cada precio individual sea reciente. El sistema deberá informar la fecha de vigencia y abstenerse de presentar una recomendación como actual cuando no exista cobertura suficiente.

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
