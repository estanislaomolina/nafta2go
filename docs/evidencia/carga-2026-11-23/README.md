# Carga y estrés de la API — 23/11/2026

Refs #158, [ADR-029](../../../adr/ADR-029-pruebas-de-carga-con-locust.md). Las tres
corridas de línea de base usan el commit `ac67b8c` con el árbol limpio (`git_dirty: false` en cada
reporte), Linux x86_64, Python 3.12.3, Intel Core Ultra 9 285H (16 CPU) y uvicorn
con **un proceso**. Locust y el servidor corren en la misma máquina.

Alcance: la API real (autenticación, validación, lectura de precios, motor, guardado
y telemetría) sobre una base temporal con el escenario histórico. ORS se reemplaza
por la matriz grabada de POC-05, así que **no incluye la latencia de ORS ni la red
del cliente**. No es una medición del despliegue en AWS.

**Escenario medido.** Cada consulta responde así:
- `status=historical_scenario`, con la captura congelada del 24/10;
- **diez evaluaciones**, porque `max_candidates` queda en el valor por defecto;
- `conservative_ranking` no disponible (`historical_or_insufficient_coverage`), porque
  la base no tiene histórico real ni una selección de modelo configurada.

Por eso estas tres corridas **no ejercitan el cuello de botella que pide #158**:
miden la API sin diagnóstico. Quedan como línea de base y como verificación del
arnés, el cupo y la persistencia. El escenario de #158 está más abajo, en la sección
"Histórico real con diagnóstico activo".

```bash
pip install -r requirements-load.txt
python scripts/run_load_test.py --profile sostenida --output sostenida.json
python scripts/run_load_test.py --profile estres --output estres.json
python scripts/run_load_test.py --profile cupo --output cupo.json
```

## Sostenida — 10 usuarios con 1 s de pausa, 120 s

[sostenida.json](sostenida.json): 987 solicitudes, 8,2 por segundo, p50 0,12 s, p95
**0,47 s**, p99 5,01 s, máximo 8,5 s. CPU media 51 %, memoria máxima 159 MB.

Hubo **9 respuestas 503 `data_unavailable` (0,91 %)**, debajo del umbral de 1 % del
reporte. La API devuelve ese código cuando falla el acceso a la base. El p99 de
5,01 s coincide con el tiempo de espera por defecto de SQLite ante un bloqueo de
escritura, que es la hipótesis más probable, pero **no está confirmada**: una
repetición con el mismo perfil (1055 solicitudes) y otra con 20 clientes sin pausa
(1200 solicitudes) no dieron errores. Las 979 respuestas exitosas quedaron
guardadas y la auditoría no encontró fallas.

#173 confirmó la causa y está integrado: un test reproduce el bloqueo (un commit
espera a las lecturas abiertas hasta el timeout) y el arreglo activa WAL en SQLite.

## Estrés — escalones de 1 a 80 usuarios sin pausa, 30 s cada uno

[estres.json](estres.json): 2924 solicitudes, **0 errores**.

| Usuarios | Solicitudes/s | p50 | p95 | CPU media |
|---|---|---|---|---|
| 1 | 33,0 | 0,03 s | 0,04 s | 78 % |
| 5 | 14,2 | 0,34 s | 0,47 s | 112 % |
| 10 | 12,9 | 0,76 s | 0,98 s | 116 % |
| 20 | 12,6 | 1,55 s | 2,02 s | 117 % |
| 40 | 12,5 | 3,08 s | **4,89 s** | 117 % |
| 80 | 12,0 | 6,09 s | **8,17 s** | 117 % |

El rendimiento deja de crecer desde 5 usuarios: el proceso queda limitado por CPU
(el GIL de Python permite poco más de un núcleo) y las consultas hacen cola en vez
de fallar. El p95 cumple RNF01 (≤ 5 s) hasta 40 usuarios simultáneos sin pausa y lo
supera con 80. La memoria sube de 135 a 245 MB. Se guardaron 3004 recomendaciones
para 2924 respuestas registradas: 80 consultas terminaron mientras Locust se
detenía. Ninguna respuesta exitosa quedó sin guardar.

## Cupo — 10 usuarios sin pausa contra 30 matrices por minuto, 90 s

[cupo.json](cupo.json): 1229 solicitudes. Solo **60 llegaron al proveedor de
rutas**, el máximo permitido en dos ventanas de un minuto. Las otras 1169 se
cortaron con 503 `routes_quota_exceeded` antes de pedir una matriz. Bajo carga, el
cupo de ADR-010 bloquea en vez de agotar la cuota diaria de ORS.

## Histórico real con diagnóstico activo — escalones de 1 a 20 usuarios, 30 s cada uno

Este es el escenario que pide #158. [historico.json](historico.json) usa el commit
`8d25ba8` con el árbol limpio, que ya incluye #152 (diagnóstico por lote) y #173
(WAL). El servidor copia en modo lectura una base local que no se versiona
(SHA-256 `6225fd7f…`), con la ingesta histórica del 24/10 y la vigente del 19/11.
Fija el reloj en `2026-11-19T16:00:00Z` y usa rutas sintéticas de distancia
constante, como `measure_real_history_diagnostics`. Cada consulta pide veinte
candidatas y la prueba se aborta ante la primera respuesta 200 que no traiga los
veinte diagnósticos disponibles.

El modelo servido es la corrida auditada `91cb07a3…` del 17/11, con la misma
política (`conservative-v1`) y el mismo método que el campeón. Se elige con
`--model-run`, porque los artefactos del campeón `b65d2d54…` no están en esta
máquina. No es una medición con el artefacto del campeón.

```bash
NAFTA2GO_PRICE_MODEL_DIR=... NAFTA2GO_PRICE_DATASET_DIR=... \
python scripts/run_load_test.py --profile historico --source-database "$SQLITE_FILE" \
  --reference-at 2026-11-19T16:00:00+00:00 --model-run 91cb07a3... --output historico.json
```

Se obtuvieron 147 respuestas, **todas con los veinte diagnósticos disponibles**, y
**0 errores**.

| Usuarios | Respuestas | Solicitudes/s | p50 | p95 | CPU media | Memoria máx. |
|---|---|---|---|---|---|---|
| 1 | 67 | 2,23 | 0,44 s | 0,56 s | 94 % | 151 MB |
| 2 | 53 | 1,77 | 1,05 s | 1,97 s | 117 % | 171 MB |
| 5 | 16 | 0,53 | 8,08 s | **9,57 s** | 171 % | 217 MB |
| 10 | 5 | — | 20,5 s | 22,7 s | 138 % | 245 MB |
| 20 | 6 | — | 42,3 s | 48,0 s | 151 % | 322 MB |

- **El diagnóstico domina el costo.** Con un usuario, una consulta tarda 0,44 s
  contra 0,03 s sin diagnóstico, y el rendimiento cae de 33 a 2,2 consultas por
  segundo.
- **La saturación está entre 2 y 5 usuarios simultáneos sin pausa.** Con 2, el p95
  es 1,97 s. Con 5 llega a 9,57 s y supera RNF01.
- **El rendimiento baja en lugar de quedar estable.** Pasa de 2,2 a 0,5 consultas por
  segundo con 5 usuarios. Una cola pura sobre un núcleo lo mantendría constante, así
  que hay contención entre diagnósticos concurrentes. La causa no se investigó.
- **Los escalones de 10 y 20 usuarios no se leen como rendimiento.** Ahí las
  latencias superan los 30 s del escalón, así que casi ninguna consulta termina
  dentro de su ventana.
- **No se perdieron recomendaciones.** Se guardaron 155 recomendaciones para 147
  respuestas registradas: 8 consultas terminaron mientras Locust se detenía. La
  auditoría no encontró fallas.

## Conclusión y pendientes

Sin diagnóstico activo, un proceso de la API cumple RNF01 con holgura hasta unos 40
usuarios simultáneos sin pausa. **Con el diagnóstico activo sobre el histórico real
y veinte candidatas, sólo lo cumple hasta 2 consultas simultáneas sin pausa.** El
cuello de botella es la preparación de diagnósticos dentro de un único proceso.
Agregar workers de uvicorn exigiría compartir la caché y el cupo de rutas entre
procesos (ADR-010), y precalcular diagnósticos fuera de la consulta es otra
decisión de diseño. Ninguna de las dos se toma en esta etapa.

Pendiente para cerrar #158: medir contra la instancia `t3.small` de AWS. Para la
línea de base alcanza `--target`. Para el perfil histórico hace falta correr el
servidor de carga en la instancia, con los artefactos del campeón. Las tres
corridas de línea de base no se repitieron con WAL; el arreglo se verificó en #174.
