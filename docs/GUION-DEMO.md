# Guion de demo — Entrega 3 (MVP)

Guion para el video de 5 a 12 minutos que pide [#24](https://github.com/estanislaomolina/nafta2go/issues/24).
Todo lo que se muestra existe en el commit de entrega y se puede reproducir con el
[README](../README.md). Lo que no está terminado se dice en el bloque donde aparece,
no al final.

Duración objetivo: unos 10 minutos. Antes de grabar:

- Tener la base local con una ingesta reciente (`python -m nafta2go.normalization --source vigente`)
  o aceptar que la demo use el escenario histórico rotulado del 24/10.
- Exportar `NAFTA2GO_API_TOKEN` y `NAFTA2GO_ADMIN_TOKEN` ([API](API.md)) y levantar la
  API con `docker compose --profile mvp up --build api`.
- No mostrar en pantalla tokens, `.env`, la clave de ORS ni la consola de AWS con IDs de cuenta.

## 1. Problema y alcance — 1 min

- Qué resuelve: dónde cargar nafta en CABA en un viaje, comparando precio, desvío y
  autonomía con datos oficiales de la Secretaría de Energía.
- El dato que condiciona todo: la cobertura reciente de precios es baja
  ([ADR-001](../adr/ADR-001-alcance-y-estrategia-de-datos.md)). Por eso el sistema nunca
  presenta un precio viejo como actual: lo rotula o lo excluye.

## 2. Consulta de un conductor — 2 min

En `http://127.0.0.1:8000/` ([WEB](WEB.md)):

1. Ingresar el código de conductor, elegir origen y destino (búsqueda o ubicación) y
   los datos del vehículo.
2. Mostrar la recomendación y su explicación: costo, desvío, litros y por qué se
   descartaron otras estaciones.
3. Señalar el estado de los precios: actuales, histórico rotulado o estimación de 31
   a 120 días ([ADR-020](../adr/ADR-020-estimacion-de-precios-antiguos.md)), siempre fuera del
   ranking cuando no son vigentes.

Mensaje: el recomendador es determinístico
([ADR-002](../adr/ADR-002-recomendador-deterministico-y-diagnostico-ml.md)); el ML no decide
la recomendación.

## 3. Diagnóstico de precios y ranking conservador — 2 min

- Mostrar en el resultado la referencia de precio y la alerta provisional
  `conservative-v1`, y el ranking conservador que excluye las excedencias sin tocar el
  ranking general ([ADR-021](../adr/ADR-021-ranking-conservador-por-desvio.md)).
- Mostrar el registro de modelos: `python -m nafta2go.ml.registry show`. Explicar que la
  API sirve sólo el campeón y que una política exige una auditoría verificada de esa
  misma corrida ([ADR-030](../adr/ADR-030-registro-de-modelos-versionado.md), [ML](ML.md)).
- Decirlo tal cual: el método elegido es una referencia (mediana de la bandera de la
  última semana), no un modelo aprendido, porque ganó en el año de selección 2025. En
  la validación 2026 los modelos erraron menos, pero cambiar la elección con esos datos
  sería elegir con datos reservados
  ([ADR-014](../adr/ADR-014-seleccion-de-modelo-de-precios.md), [ML](ML.md)). Las alertas no
  tienen precisión medida para detectar errores reales.

## 4. Operación — 1 min

- Abrir `/operacion` con el código de administración: estado de ingestas, alertas y
  métricas de consultas, rutas y diagnóstico ([ADR-016](../adr/ADR-016-acceso-administrativo-separado.md)).
- Mostrar que el código de conductor no entra al panel.

## 5. Calidad y automatización — 2 min

- CI en GitHub Actions: links, lint, tests, secretos, contenedores y web; la imagen se
  publica por digest sólo si pasan los checks ([ADR-025](../adr/ADR-025-imagen-verificada-por-digest.md)).
- Una PR real: issue vinculada, review de otro integrante y CI en verde.
- Pruebas de carga ([ADR-029](../adr/ADR-029-pruebas-de-carga-con-locust.md),
  [evidencia](evidencia/carga-2026-11-23/README.md)): el cupo de rutas bloquea en vez de
  agotar la cuota de ORS y no se pierden recomendaciones. Si #179 está integrada,
  mostrar el hallazgo: con el diagnóstico activo un proceso cumple p95 ≤ 5 s sólo hasta
  dos consultas simultáneas.

## 6. Demo en AWS — 1 min

- Mostrar la instancia `t3.small` efímera, la entrega versionada y el acceso
  ([AWS-DEMO](AWS-DEMO.md)). Mostrar sólo lo que esté integrado en el commit de
  entrega: URL pública, despliegue desde el CI e ingesta autónoma (#155, #156, #160)
  dependen de PRs en revisión.

## 7. Limitaciones y cierre — 1 min

Repasar la sección "Partes simuladas, simplificadas o pendientes" del README:

- tokens de demo en vez de cuentas de usuario;
- SQLite y caché de rutas por proceso, sin réplicas;
- diagnóstico sin precisión medida y capacidad limitada con el diagnóstico activo;
- validación técnica sin participantes ([ADR-023](../adr/ADR-023-validacion-tecnica-sin-participantes.md))
  y sin prueba en un teléfono físico dentro de CABA.

Cerrar con el commit y el tag de entrega (`entrega-3-mvp`).
