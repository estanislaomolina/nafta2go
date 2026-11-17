# Estimación para precios de más de 30 días — 17/11/2026

Responde a #57: ¿sirve mostrar una estimación rotulada del precio actual de una
estación cuyo último precio oficial tiene más de 30 días?

El precio actual de una estación que no volvió a publicar no es observable. El proxy
son los **reingresos**: publicaciones cuyo precio previo de la misma estación,
producto y franja tiene más de 30 días. Sobre esos casos se mide qué tan bien cada
método habría estimado el precio nuevo.

## Entradas y protocolo

- Dataset `price-temporal-v2` del paquete `ml-precios-v2-2026-11-15.tar.gz` de
  Felipe. El SHA-256 del archivo, del manifiesto y de `examples.jsonl` coincide con
  la [recepción de #110](../alertas-precios-2026-11-17/recepcion.json). Los datos
  quedan locales y fuera de Git. No se cargó ningún modelo del paquete.
- El [protocolo](protocolo.json) se commiteó en `e4bbf40` y su estado se actualizó en
  `3447783`, antes de la corrida. Fija los métodos, la selección con 2025, el mínimo
  de 30 casos y la regla de adopción. Los umbrales los fijó Santiago Bunge; Felipe y
  Estanislao no los confirmaron explícitamente antes de correr.
- La selección usa 2.052 reingresos de 2025 (dentro de train). La validación 2026
  tiene 768 reingresos: 540 de 31 a 60 días, 180 de 61 a 120 y 48 de más de 120.

## Reproducción

Desde el tag `evidencia/estimacion-antiguos-2026-11` (commit `3447783`, árbol limpio):

```bash
python -m nafta2go.ml.evaluate_stale \
  --dataset "$DATASET_DIR" --output "$OUTPUT_DIR" \
  --selection-start 2025-01-01T00:00:00-03:00
```

Dos corridas en salidas nuevas dieron bytes idénticos; ver [reproducción](reproduccion.json).
El [reporte](stale-evaluation.json) registra hashes, parámetros y procedencia del código.

## Resultados

Método elegido con 2025: **mediana reciente de la bandera** (`bandera_reciente`),
con MAPE 1,69 %. En 2025, "mostrar el precio viejo" (`ultimo_precio`) da 2,34 %.

Validación 2026, error relativo medio (MAPE) y percentil 90 del error relativo:

| Antigüedad | Casos | Bandera reciente | Precio viejo | Mejor método del tramo |
|---|---|---|---|---|
| Total | 768 | 1,14 % / p90 2,16 % | 2,37 % / p90 3,58 % | bandera reciente |
| 31 a 60 días | 540 | 1,09 % / p90 2,16 % | 1,64 % / p90 2,17 % | bandera reciente |
| 61 a 120 días | 180 | 0,80 % / p90 1,56 % | 2,89 % / p90 5,93 % | bandera reciente |
| Más de 120 días | 48 | 2,91 % / p90 3,10 % | 8,76 % / p90 23,42 % | Ridge (2,07 %) |

El chequeo del protocolo da `adopt=true`: MAPE ≤ 3 %, p90 ≤ 8 % y mejor que el
precio viejo en los tres tramos.

Lectura:

- La diferencia frente al precio viejo crece con la antigüedad: con más de 120 días,
  el precio viejo se equivoca en promedio un 8,76 %.
- En el tramo de más de 120 días, Ridge rinde mejor que el método elegido. No se
  reelige: hacerlo sería elegir con la validación.
- El "último precio ajustado por el mercado" rinde mal en 2026 (MAPE 4,80 %), aunque
  en 2025 estaba cerca del precio viejo. No se investigó la causa en esta corrida.

## Límites

- **Sesgo del proxy:** un reingreso existe porque la estación publicó un precio nuevo.
  Si una estación no cambió su precio, no aparece; el proxy favorece a los métodos que
  estiman cambios frente a mostrar el precio viejo.
- **Antigüedad cubierta:** los reingresos de más de 120 días tienen mediana de 129
  días y máximo de 391. La evidencia no cubre los precios de cientos de días que el
  PRD observó en el conjunto vigente.
- La vigencia se usa como proxy de disponibilidad (ADR-013), y 2026 ya tenía métricas
  globales publicadas (ADR-014, #110): no es una prueba prospectiva ni ciega.
- Es una evaluación retrospectiva (`runtime_enabled=false`); no habilita nada en la
  API ni en la web. La decisión está en
  [ADR-020](../../../adr/ADR-020-estimacion-de-precios-antiguos.md).
