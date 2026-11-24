---
status: Aceptado
date: 2026-11-22
decision-makers: Equipo Nafta2Go
consulted: issues 153 y 154, ADR-016
informed: Cátedra
---

# Observabilidad con métricas acotadas y dashboards versionados

## Context and Problem Statement

La operación expone JSON por proceso. Necesitamos conservar series, distinguir
funcionamiento y negocio, y evitar afirmar compras/consumo que no observamos.

## Considered Options

1. Prometheus y Grafana propios, provisionados en un perfil opcional de Compose.
2. Grafana Cloud con envío de métricas y dashboards administrados.
3. CloudWatch con agentes/exportación y dashboards en AWS.

## Decision Outcome

Se propone Prometheus/Grafana propios para la demo. La API expone métricas sólo
con código administrativo; la instalación guarda las credenciales fuera de Git.
Los contadores HTTP son por proceso y los agregados de recomendaciones guardadas
son gauges reconstruibles desde SQLite. La falta de cobertura se cuenta por
proceso porque esas consultas no se persisten. Nada acredita compras reales.

Cada estación se cuenta una vez por consulta, sin multiplicar por prioridades.
Se limita la cardinalidad por dimensión y se evita cruzarlas. Comuna se calcula
únicamente para coordenadas públicas de estaciones con cartografía GCBA versionada.
Los precios antiguos continúan rotulados; sus estimaciones no renuevan vigencia.

### Consequences and Confirmation

- Los dashboards de negocio usan nombres de recomendación y estimación, no venta,
  elección de bandera ni consumo efectivo. No hay barrio de origen del conductor.
- CPU/memoria del contenedor necesitan un exporter independiente; no se infieren
  de los histogramas HTTP. El perfil no es supervisión permanente ni envía mensajes.
- La lectura de resultados persistidos crece con la historia: medir el costo de
  scrape y separar pruebas de carga de la base de demo.
- Pruebas sin red comprueban protección, privacidad, deduplicación y sumas por
  estación/comuna. La validación de provisioning no equivale a dashboards vivos.
- Las capas conservan acceso a datos en repository y agregación en application;
  la exportación Prometheus y el middleware pertenecen a presentation.

## Pros and Cons of the Options

- **Prometheus/Grafana propios:** reproducibles localmente y fáciles de mostrar;
  suman memoria/volúmenes a la demo y requieren retención y protección de secretos.
- **Grafana Cloud:** facilita retención y alertas administradas; exige otra cuenta,
  credenciales de envío, límites de plan y egreso de métricas hacia un tercero.
- **CloudWatch:** integra IAM y métricas AWS; cuesta reproducirlo sin nube y añade
  agentes, costos de series y configuración específica del proveedor.

## More Information

[Contrato de métricas](../docs/API.md),
[cardinalidad Prometheus](https://prometheus.io/docs/practices/instrumentation/),
[fuente pública GCBA](https://data.buenosaires.gob.ar/dataset/comunas).
