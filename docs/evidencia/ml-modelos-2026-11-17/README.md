# Comparación de modelos corregida — 17/11/2026

Repite la [comparación del 15/11](../ml-modelos-2026-11-15/model-report.json) con el
mismo dataset y el arreglo de #119. Antes, `market_change` comparaba la mediana actual
con la del ejemplo anterior de la estación aunque una fuera de la zona y la otra de
CABA. Ahora queda vacío cuando cambia el ámbito.

- Dataset: el mismo `price-temporal-v2` (`dataset_sha256` `ea952f51…a6f25e`), con
  su [manifiesto](../ml-modelos-2026-11-15/dataset-manifest.json).
- Código: commit `cef0c9a`, árbol limpio.
- Comando: `python -m nafta2go.ml.train --dataset DIR --output DIR`, con la selección
  por defecto desde el 01/01/2025.
- Dos corridas en Linux produjeron `model.joblib`, manifiesto, reporte y predicciones
  idénticos byte a byte (`artifact_sha256` `30326745…87f35`).

El protocolo de ADR-014 no cambia, y el método elegido sigue siendo
`bandera_reciente`. Las referencias no usan `market_change`, así que sus métricas son
las mismas. Cambian sólo Ridge y los árboles potenciados (MAE en ARS/L):

| Modelo | Selección 2025 antes → ahora | Validación 2026 antes → ahora |
|---|---|---|
| Ridge | 35,37 → 35,30 | 31,24 → 31,00 |
| Árboles potenciados | 22,69 → 24,24 | 31,39 → 31,90 |

Los árboles empeoran un poco; no se investigó qué parte de su resultado anterior
venía del cambio de ámbito. Este resultado no se usa para reelegir nada: es la
corrección de un error de cálculo, evaluada sobre una validación ya inspeccionada.
