# Motor determinístico de la POC

Implementa la tarea POC-04 (#9), correspondiente a RF04 y RF05 del
[PRD](PRD.md). Es un módulo Python sin dependencias externas. Requiere Python
3.12, como el CI y las convenciones del repositorio.

Desde la raíz del repositorio:

```bash
python -m unittest discover -s tests -v
```

El CI también descubre estos casos mediante `pytest`.

Ejemplo ejecutable desde la raíz, con valores sintéticos:

```python
from nafta2go.domain.engine import FuelRequest, Route, evaluate_candidate

request = FuelRequest(
    consumption_l_per_100km=10,
    tank_capacity_l=50,
    remaining_l=10,
    budget_ars=12000,
    reserve_l=2,
)
route = Route(
    to_station_km=10,
    after_station_km=20,
    to_station_min=15,
    after_station_min=25,
    direct_km=25,
    direct_min=30,
)
result = evaluate_candidate(request, price_ars_per_l=1200, route=route)
print(result.feasible)  # True
print(result.metrics.final_l)  # 17.0: litros al terminar el recorrido
```

## Contrato para integrar datos y rutas

`nafta2go.domain.engine.evaluate_candidate(request, price_ars_per_l, route)`
recibe una `FuelRequest`, un precio en pesos por litro y una `Route` o `None`.
Las entradas numéricas admiten enteros, floats finitos, cadenas decimales y
`Decimal`; se convierten usando su representación decimal. Los booleanos se
rechazan. Las entradas inválidas generan `ValueError` con el nombre del campo.
Como protección numérica, los valores distintos de cero deben tener una magnitud
de al menos `1e-12` y menor que `1e13`. Este límite técnico evita exponentes que
desborden la aritmética; las restricciones físicas de cada campo se aplican además.
Cada entrada admite como máximo 28 dígitos significativos, contando los ceros
finales del coeficiente decimal. El exceso se rechaza con `ValueError` y el
nombre del campo; no se redondea silenciosamente. El cero se canonicaliza como 0.

| Objeto | Campo | Unidad y restricción |
|---|---|---|
| FuelRequest | consumption_l_per_100km | Litros cada 100 km, mayor que cero |
| FuelRequest | tank_capacity_l | Litros, mayor que cero |
| FuelRequest | remaining_l | Litros iniciales, entre cero y capacidad |
| FuelRequest | budget_ars | Pesos disponibles, no negativo |
| FuelRequest | reserve_l | Litros mínimos, entre cero y capacidad |
| Route | to_station_km / after_station_km | Kilómetros antes y después de cargar, no negativos |
| Route | to_station_min / after_station_min | Minutos antes y después de cargar, no negativos |
| Route | direct_km / direct_min | Recorrido de referencia, no negativo |

Con destino, el segundo tramo es estación-destino y la referencia es
origen-destino. Sin destino, el segundo tramo es estación-origen y la referencia
es cero. No se presupone que ida y vuelta sean simétricas. El adaptador de rutas
debe convertir metros a kilómetros y segundos a minutos antes de llamar al motor.
Si no puede obtener una ruta completa, debe pasar `None`.

El servicio de integración debe filtrar previamente CABA, producto compatible,
vigencia del precio y cobertura, y conservar identificadores de estación, fuente,
fechas y versiones de datos/rutas. Este motor no certifica esos atributos: evalúa
una sola candidata normalizada. La selección de hasta diez estaciones y el ranking
se implementan en la capa de aplicación de [POC-05](POC-05.md), con evidencia real.

## Cálculos y decisiones de negocio

Para consumo `c` en litros cada 100 km:

```text
consumo_ida = km_hasta_estacion * c / 100
litros_llegada = litros_iniciales - consumo_ida
capacidad_libre = capacidad_tanque - litros_llegada
litros_comprados = min(presupuesto / precio, capacidad_libre)
consumo_salida = km_despues_estacion * c / 100
litros_finales = litros_llegada + litros_comprados - consumo_salida
ganancia_neta = litros_finales - litros_iniciales
autonomia_final_km = max(0, litros_finales) * 100 / c
desvio_km = max(0, km_hasta_estacion + km_despues_estacion - km_directos)
tiempo_extra_min = max(0, min_hasta_estacion + min_despues_estacion - min_directos)
```

La reserva debe conservarse al llegar a la estación si la consulta empieza con
esa cantidad disponible. Si ya se empieza por debajo, no se permite consumir
más antes de cargar: el mínimo de llegada es `min(reserva, litros_iniciales)`.
Esto permite cargar cuando el vehículo ya está en la estación, sin habilitar un
viaje que profundice el déficit de reserva. Al terminar el recorrido siempre se
exige la reserva completa; la igualdad es admisible. Una estación inalcanzable o
que compromete el mínimo de llegada se descarta antes de calcular una carga. La
capacidad libre se calcula al llegar, porque el viaje ya consumió combustible.
Presupuesto cero y ausencia de espacio para cargar son descartes aunque el
recorrido pudiera completarse sin cargar. Una ganancia neta negativa por sí sola
no es un descarte: el combustible final debe respetar la reserva.

Las restricciones de llegada, reserva y capacidad se comparan con fracciones
exactas de las entradas decimales admitidas (`fractions.Fraction`, biblioteca
estándar). La compra máxima es el menor entre presupuesto/precio y capacidad
libre exacta. Se convierte a `Decimal` con 28 dígitos redondeando hacia abajo,
por lo que los litros comprados no exceden ninguna de esas cotas. La reserva
final se comprueba con esos litros y los consumos exactos, antes del redondeo de
las métricas. Así se corrige el caso del issue #34 y también los límites que un
producto de dos entradas de 28 dígitos podría redondear favorablemente.

Las métricas conservan el contexto local `Decimal` de 28 dígitos, independiente
del contexto del llamador. No se redondean a centavos ni a litros de surtidor;
son estimaciones y la terminal solo redondea para mostrar. Una métrica final
que se muestra igual a la reserva no implica factibilidad si el cálculo exacto
queda por debajo: el motivo de descarte es el que determina la viabilidad.
La autonomía final incluye la reserva; no equivale a distancia segura disponible
antes de consumirla.

## Resultado y descartes

`Evaluation.feasible` indica si no hay motivos de descarte. `metrics` contiene
consumos, litros de llegada, espacio libre, compra, costo, combustible final,
ganancia neta, autonomía y desvíos. Puede contener un combustible final negativo
en una alternativa inviable; no debe mostrarse como recomendación.

| Motivo | Significado |
|---|---|
| route_unavailable | No se obtuvo la ruta completa |
| station_unreachable | El combustible no alcanza para llegar |
| reserve_at_station | Llegar consumiría parte de la reserva |
| no_budget | No hay presupuesto para cargar |
| no_tank_space | No hay capacidad disponible al llegar |
| insufficient_fuel_for_trip | La carga posible no permite terminar con reserva |

Los tres primeros devuelven `metrics=None`. Los restantes conservan los cálculos
para explicar la inviabilidad y pueden combinarse. Un precio no positivo o no
finito es un error del contrato (`ValueError`), que debe corregir el adaptador.

Los tests usan escenarios sintéticos con resultados calculables a mano, límites
de reserva, presupuesto y tanque, ida y vuelta, fallos de ruta, entradas inválidas
y restricciones físicas/económicas sobre combinaciones de precios y presupuestos.
No constituyen evidencia de cobertura ni validación de un proveedor externo.

## Conexión con la matriz de rutas

`nafta2go.application.recommendation.evaluate_stations` recibe la consulta del
motor, hasta diez `Candidate` (identificador, ubicación y precio ya validado),
origen, destino opcional y un `RoutingProvider`. Pide una única matriz usando
`trip_matrix` y devuelve un `StationEvaluation` por candidata, en el mismo orden.
Cada resultado conserva la candidata y su evaluación explicada por el motor.
Esta función conserva las evaluaciones; `application.query.recommend` agrega el ranking y el registro.

`route_from_matrix` toma la fila cero para el tramo origen-estación y la fila de
esa estación para el tramo estación-destino (u origen). Convierte metros a
kilómetros y segundos a minutos usando `Decimal`. Con destino usa la ruta directa
como referencia; sin destino la referencia es cero y admite una vuelta distinta
de la ida. Un tramo necesario `None` se convierte en `route_unavailable`; los
pares ajenos a ese recorrido no afectan la evaluación. Una matriz inconsistente
o un fallo global del proveedor se propaga como error, sin simular una consulta
vacía exitosa. Sin candidatas no se consulta al proveedor.

Las pruebas de conexión están en `tests/application/test_recommendation.py` y usan
matrices sintéticas, sin red ni credenciales. La consulta completa conecta la
ingesta, los filtros, el ranking y el registro; su evidencia real está en
[POC-05](POC-05.md).

## Consulta desde la base de datos

`nafta2go.application.stored_query.select_stored_candidates` recibe una conexión,
`fuel_type` (`super` o `premium`), `schedule_id` (2 diurno, 3 nocturno) y
`reference_at` con zona horaria. Lee exclusivamente la última ingesta `vigente`
exitosa; no mezcla versiones ni recurre al histórico o a una ingesta anterior si
la última no ofrece cobertura. Consume las filas guardadas por el normalizador
de POC-01, ya integrado, y reutiliza sus constantes de producto, zona y alertas.

La fecha de publicación guardada se interpreta como hora argentina sin zona,
según el contrato de normalización/persistencia. Se le asigna la zona
`America/Argentina/Buenos_Aires` y se compara con la referencia en UTC. Se excluyen fechas futuras y precios con más de
`max_age_days` de antigüedad exacta (por defecto `MAX_PRICE_AGE_DAYS` = 30 × 24 horas,
límite incluido).
`tzdata` permite resolver esa zona también en sistemas sin base IANA instalada,
según el mecanismo de respaldo de [ZoneInfo](https://docs.python.org/3/library/zoneinfo.html#data-sources).
La referencia sirve para validar la vigencia, no para reconstruir qué captura
existía en una fecha pasada: no es una consulta histórica ni una evaluación temporal.

También se filtran producto y franja, precios no positivos o no finitos,
coordenadas ausentes/no finitas, el rectángulo de CABA acordado en POC-01 y las
alertas `fuera_de_caba`/`sin_coordenadas`. La provincia no está en el esquema de
precios: se exige que la ingesta haya filtrado CABA previamente. El rectángulo no
reemplaza un polígono ni verifica la entrada física de la estación.

Entre las publicaciones utilizables de cada estación se conserva la más reciente.
La preselección ordena por fecha descendente e identificador numérico ascendente
y devuelve hasta diez estaciones distintas. No es un ranking de conveniencia. Si se
pasa `origin`, solo cuentan las estaciones dentro del corredor del recorrido
(`MAX_DETOUR_KM` en línea recta; motivo `outside_corridor`), como se explica en
[COBERTURA.md](COBERTURA.md). Las alertas `precio_atipico` se conservan sin cambiar ni excluir por
sí solas el precio oficial.

`CandidateSelection` informa `data_run_id`, fecha de referencia, precios elegidos
con sus IDs/filas/fechas/alertas, cantidad de estaciones elegibles y motivos
normalizados de exclusión con sus conteos. Sus estados son `ready`,
`no_successful_ingestion` e `insufficient_coverage`. El mínimo requerido se fija
con `minimum_candidates` (por defecto `MIN_RECENT_CANDIDATES` = 3); debe estar entre
uno y el límite elegido. Los dos valores por defecto se definen una sola vez en
`nafta2go/application/coverage_rules.py`. No certifica cobertura representativa de toda CABA.

`evaluate_with_coverage` agrega el escenario histórico: si la captura actual no
alcanza el mínimo en el corredor, usa la captura congelada con el estado
`historical_scenario` y su rótulo, y si tampoco alcanza no consulta rutas. Los
estados y la garantía de no presentar precios viejos como actuales están en
[COBERTURA.md](COBERTURA.md).

`evaluate_from_database` conecta esa selección con `evaluate_stations`, utilizando
el `RoutingProvider` recibido. Si no se alcanza el mínimo no llama al proveedor y
devuelve la falta de cobertura sin evaluaciones. Los errores de base y rutas se
propagan; no se presentan como una búsqueda vacía exitosa. No escribe consultas,
ubicaciones ni recomendaciones en la base.

Las pruebas de `tests/application/test_stored_query.py` usan un SQLite temporal
con migraciones reales, escenarios normalizados ficticios, la fixture CSV del
normalizador real y un proveedor sin red. Verifican el recorrido normalización →
ingesta → base → selección → rutas → motor y sus límites.
Para ejecutarlas:

```bash
python -m pip install -r requirements-dev.txt
pytest -q tests/application/test_stored_query.py
```

La matriz real, las alternativas y la ejecución completa están documentadas en
[POC-05](POC-05.md). La evidencia del flujo definitivo incluye normalización e
ingesta reales, rutas autenticadas y recomendación persistida con su origen de datos.
