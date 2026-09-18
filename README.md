# Nafta2Go

Nafta2Go es un recomendador de estaciones de servicio para conductores de CABA. Combina precio publicado, presupuesto, autonomía, capacidad del tanque y desvío del recorrido para mostrar alternativas explicadas.

Este repositorio corresponde a la **Entrega 1: Diseño** del Trabajo Práctico Integrador. La entrega define el problema, documenta la evidencia disponible y organiza el trabajo futuro de la POC y el MVP. Todavía no contiene la implementación funcional del producto.

## Integrantes

Estanislao Molina Abeniacar

Felipe Sidiropulos

Santiago Bunge

## Accesos principales

- [PRD](docs/PRD.md): problema, usuarios, casos de uso, requisitos, criterios de éxito, supuestos y limitaciones.
- [Propuesta inicial](docs/Propuesta%20nafta2go.md): problema, solución de alto nivel, fuentes, viabilidad preliminar y alcance tentativo.
- [Notebook de exploración](notebooks/data_exploration.ipynb): descubrimiento de recursos oficiales, calidad, cobertura, histórico, riesgo de fechas, rutas y esfuerzo.
- [Roadmap](docs/ROADMAP.md): hitos, dependencias, orden de construcción y vínculo con GitHub Projects.
- [ADRs](adr/README.md): decisiones de diseño y comparación de alternativas.
- [Consigna del TP](res/%5BSHR%5D%5BS2%5D%20-%20Consigna%20TP%20I408.pdf): requisitos y formato de las entregas.
- [GitHub Project](https://github.com/users/estanislaomolina/projects/1): seguimiento operativo del roadmap.

## Evidencia y conclusión de viabilidad

La exploración del 18 de septiembre de 2026 utilizó el catálogo oficial de precios en surtidor de la Secretaría de Energía. Para el conjunto vigente se observaron 36.667 registros, 1.630 filas de CABA y 732 filas de nafta. Sólo 8 registros correspondientes a 2 estaciones tenían una antigüedad de hasta 30 días.

El histórico filtrado de nafta en CABA reunió 20.522 observaciones, 76 identificadores de estación y aproximadamente 142 meses de cobertura. Se detectaron 84 fechas posteriores a la ejecución, por lo que las reglas de normalización deben confirmarse antes de unir fuentes o entrenar modelos.

El proyecto es **viable con condiciones y/o recorte de alcance**. La POC debe validar fechas, cobertura y proveedor de rutas. Si no existe cobertura reciente suficiente, el sistema deberá informar la limitación o utilizar escenarios históricos claramente rotulados; nunca presentar precios antiguos como actuales.

## Reproducir la exploración

La notebook consulta recursos públicos y necesita conexión a Internet. No requiere credenciales para acceder al catálogo ni al DataStore de la Secretaría de Energía.

### Requisitos

- Python 3.10 o superior.
- JupyterLab o Jupyter Notebook.
- Conexión a Internet durante la ejecución.

### Instalación y ejecución

Desde la raíz del repositorio:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install jupyterlab pandas numpy requests matplotlib
jupyter lab
```

Luego abrir `notebooks/data_exploration.ipynb` y ejecutar todas las celdas en orden. La notebook descubre el recurso vigente desde el catálogo, descarga el CSV, consulta el histórico filtrado y muestra las tablas y gráficos usados para las conclusiones del PRD.

La ejecución puede tardar según la disponibilidad del catálogo oficial. Si se vuelve a ejecutar en otra fecha, los valores de cobertura y vigencia pueden cambiar; debe registrarse la fecha de ejecución y actualizarse la evidencia correspondiente.

## Decisiones de diseño

Los ADRs de la Entrega 1 documentan las alternativas evaluadas para:

- alcance en CABA y uso de datos actuales o históricos;
- recomendador determinístico y diagnóstico estadístico con ML separado;
- proveedor de rutas y alternativa OSRM;
- arquitectura modular por capas.

## Estado del desarrollo

La prioridad actual es la Entrega 1. Las tareas de POC y MVP están planificadas en GitHub Projects, pero su implementación se realizará en entregas posteriores.

## Video de la entrega

Pendiente de completar:

> **Video:** PEGAR_ACA_EL_LINK_PUBLICO_DEL_VIDEO

El video deberá durar entre 5 y 12 minutos y mostrar el razonamiento del proyecto, la evidencia del notebook, el PRD, los ADRs y el roadmap.

## Entrega

- **Rama:** `main`
- **Commit de entrega:** completar con el SHA final.
- **Repositorio:** https://github.com/estanislaomolina/nafta2go
- **Project:** https://github.com/users/estanislaomolina/projects/1
