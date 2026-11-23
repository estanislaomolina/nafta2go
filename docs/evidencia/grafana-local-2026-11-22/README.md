# Grafana local con ocho consultas de QA

Capturas reales de los dos dashboards provisionados y verificación de todas sus
consultas PromQL. Se ejecutaron ocho consultas HTTP con rutas grabadas en una base
nueva y aislada. CPU/memoria provienen de cAdvisor sobre ese contenedor API.
No son mediciones de capacidad, latencia pública ni AWS; tampoco compras reales.

No se ingirieron datos operativos ni se configuró diagnóstico en esta pasada:
los paneles conservan datos ausentes y el indicador de ausencia de observaciones.
La verificación incluye las tres reglas de alerta y confirma que se eliminaron
contenedores, volúmenes y red del proyecto de QA. Los secretos no se conservan.

Reproducción: seguir [OBSERVABILIDAD](../../OBSERVABILIDAD.md) y ejecutar el harness
versionado con un directorio de evidencia nuevo y `--screenshots`.
