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
    to_station_km=10, after_station_km=20,
    to_station_min=15, after_station_min=25,
    direct_km=25, direct_min=30,
)
result = evaluate_candidate(request, price_ars_per_l=1200, route=route)
print(result.feasible)         # True
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
se integrarán en POC-05. Todavía no existe una POC con datos reales de punta a punta.

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

Se usa aritmética `Decimal` con un contexto local propio de 28 dígitos, independiente
de la precisión y los límites de exponentes del llamador. La división para
calcular la compra redondea hacia abajo para no superar el presupuesto. No se
redondea a centavos ni a litros de surtidor: son estimaciones, y el formato de
presentación se resolverá en la interfaz. La autonomía final incluye la reserva;
no equivale a distancia segura disponible antes de consumirla.

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

## Conexión con la matriz de rutas (inicio de POC-05)

`nafta2go.application.recommendation.evaluate_stations` recibe la consulta del
motor, hasta diez `Candidate` (identificador, ubicación y precio ya validado),
origen, destino opcional y un `RoutingProvider`. Pide una única matriz usando
`trip_matrix` y devuelve un `StationEvaluation` por candidata, en el mismo orden.
Cada resultado conserva la candidata y su evaluación explicada por el motor.
Todavía no selecciona una ganadora ni produce un ranking.

`route_from_matrix` toma la fila cero para el tramo origen-estación y la fila de
esa estación para el tramo estación-destino (u origen). Convierte metros a
kilómetros y segundos a minutos usando `Decimal`. Con destino usa la ruta directa
como referencia; sin destino la referencia es cero y admite una vuelta distinta
de la ida. Un tramo necesario `None` se convierte en `route_unavailable`; los
pares ajenos a ese recorrido no afectan la evaluación. Una matriz inconsistente
o un fallo global del proveedor se propaga como error, sin simular una consulta
vacía exitosa. Sin candidatas no se consulta al proveedor.

Las pruebas de conexión están en `tests/application/test_recommendation.py` y usan
matrices sintéticas, sin red ni credenciales. Quedan pendientes la ingesta y los
filtros de datos reales, la validación autenticada de rutas, el ranking y la demo
completa. Esta conexión por sí sola no cierra la tarea #10.

Para inspeccionar ese recorrido en la terminal, ejecutar desde la raíz:

```bash
python -m nafta2go.demo
python -m nafta2go.demo --presupuesto 6000 --sin-destino
python -m nafta2go.demo --litros-iniciales 0
```

El proveedor ficticio de la demo devuelve dos recorridos evaluables y una estación
sin ruta completa. Los precios, coordenadas y distancias de ese ejemplo son
sintéticos y se rotulan al ejecutarlo. La salida conserva el orden de entrada,
sin elegir una estación ganadora. Se puede consultar `--help` para modificar las
entradas. La salida del proceso es 0 si hay candidatas viables, 1 si ninguna lo es
y 2 si los parámetros son inválidos. La ejecución no consulta la API ni necesita
instalar dependencias externas; las pruebas completas sí requieren los paquetes
de `requirements.txt`.
