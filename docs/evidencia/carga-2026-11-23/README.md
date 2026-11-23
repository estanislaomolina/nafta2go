# Carga y estrés de la API — 23/11/2026

Issue #158, [ADR-029](../../../adr/ADR-029-pruebas-de-carga-con-locust.md). Las tres
corridas usan el commit `ac67b8c` con el árbol limpio (`git_dirty: false` en cada
reporte), Linux x86_64, Python 3.12.3, Intel Core Ultra 9 285H (16 CPU) y uvicorn
con **un proceso**. Locust y el servidor corren en la misma máquina.

Alcance: la API real (autenticación, validación, lectura de precios, motor, guardado
y telemetría) sobre una base temporal con el escenario histórico. ORS se reemplaza
por la matriz grabada de POC-05, así que **no incluye la latencia de ORS ni la red
del cliente**. No es una medición del despliegue en AWS.

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

Seguimiento en #173: un test reproduce el bloqueo (un commit espera a las lecturas
abiertas hasta el timeout) y el arreglo activa WAL en SQLite.

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

## Conclusión y pendientes

Un proceso de la API cumple RNF01 con holgura para el uso esperado de la demo y
hasta unos 40 usuarios simultáneos sin pausa. El cuello de botella es la CPU de un
único proceso. Agregar workers de uvicorn exigiría compartir la caché y el cupo de
rutas entre procesos (ADR-010), así que no se cambia en esta etapa.

Pendientes:

- medir con `--target` contra la instancia `t3.small` de AWS;
- repetir esta evidencia cuando #173 esté en `dev`.
