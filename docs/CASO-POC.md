# Caso controlado: Obelisco → Cabildo y Juramento

Preparación de POC-05 (#10), con una captura real de precios del **24/10/2026**.
La ficha está lista para conectar datos y rutas; todavía no constituye una
recomendación de punta a punta.

| Entrada | Valor |
|---|---|
| Origen | Obelisco: latitud -34.6037, longitud -58.3816 |
| Destino | Cabildo y Juramento: latitud -34.5627, longitud -58.4565 |
| Producto y franja | Nafta súper (`idproducto=2`), diurno (`idtipohorario=2`) |
| Consumo supuesto | 10 L/100 km |
| Capacidad e inventario inicial | 50 L y 10 L |
| Presupuesto y reserva | ARS 12.000 y 2 L |
| Fecha de referencia congelada | 24/10/2026 |
| Antigüedad máxima del precio | 30 días calendario |
| Cantidad de candidatas | 10 |

Los parámetros del vehículo son supuestos del caso; las estaciones, coordenadas,
precios y fechas provienen de la captura oficial. Las coordenadas de origen y
destino coinciden con las de la prueba de rutas de POC-03.

## Captura y evidencia

- [Ficha y candidatas, case.json](evidencia/poc-05-obelisco-cabildo-2026-10-24/case.json).
- [Recorte de registros originales, prices.csv](evidencia/poc-05-obelisco-cabildo-2026-10-24/prices.csv).
- Fuente: [Precios en Surtidor — Secretaría de Energía](https://datos.energia.gob.ar/dataset/precios-en-surtidor), recurso `80ac25de-a44a-4445-9215-090cf55cfda5`, licencia CC BY 4.0.
- Captura: `2026-10-24T20:31:11.071132+00:00`. La ficha conserva URL solicitada,
  URL final, licencia, tamaño y SHA-256 del archivo completo y del recorte.

El archivo completo contiene 36.645 registros. Para CABA, nafta súper y franja
diurna hay 184 registros con claves distintas. **31 estaciones** tienen fecha de
publicación dentro de los 30 días calendario anteriores o iguales a la fecha de
captura; 153 registros quedan fuera por antigüedad. Esto permite preparar este
caso con diez precios recientes, sin activar un escenario histórico.

Se seleccionan los diez registros más recientes, desempatando por identificador
numérico de estación. No se los presenta como las estaciones más cercanas ni
como las mejores alternativas: todavía no se calcularon sus desvíos. El recorte
conserva los textos originales, incluidos decimales y fechas, y la ficha identifica
el número de registro en el CSV de origen, contando la cabecera como primero.

La comprobación de fechas exige el formato exacto `AAAA-MM-DD HH:MM:SS`; calcula
antigüedad por fecha calendario, sin atribuir una zona horaria a la publicación.
El normalizador de POC-01 debe confirmar ese contrato y su política definitiva
de vigencia. La ubicación se filtra por provincia y un rectángulo de coordenadas;
no se verificó el polígono de CABA ni el acceso físico a las estaciones. La
publicación reciente no confirma stock ni precio efectivo al cargar.

## Reproducir el recorte

El original de 9,27 MB se conserva localmente en `data/raw/poc-05-2026-10-24/`,
fuera de Git. Desde la raíz:

```bash
python scripts/prepare_poc_case.py \
  --csv data/raw/poc-05-2026-10-24/prices.csv \
  --metadata data/raw/poc-05-2026-10-24/capture.json \
  --out /tmp/nafta2go-caso-reproducido
pytest -q tests/scripts/test_prepare_poc_case.py
```

Para reproducir exactamente los conteos globales se necesita el original con el
SHA-256 registrado; el CSV público cambia y una descarga futura puede diferir.
Los archivos pequeños de evidencia permiten inspeccionar y verificar sin red los
diez registros seleccionados. El script no descarga, ingiere ni persiste precios
en la base de datos y no reemplaza el normalizador de Felipe.

El caso sigue referenciado al 24/10/2026: no se deben presentar estos precios
como actuales en otra ejecución sin volver a comprobar la vigencia y cobertura.

## Trabajo para completar la consulta

1. **Datos (Felipe):** confirmar el contrato de normalización, las claves de
   estación/producto/franja, el formato de fechas y los filtros de cobertura;
   contrastar el resultado con las diez filas originales. La persistencia del
   PR #29 todavía recibe un normalizador inyectado.
2. **Rutas (Santiago):** capturar la matriz completa para el origen, destino y
   coordenadas exactas de `case.json`, conservando el orden de sus candidatas.
   El PR #32 aporta evidencia autenticada del proveedor, pero su JSON resume la
   prueba y no incluye los tramos necesarios para evaluar estas estaciones.
3. **Integración (Estanislao):** pasar esos precios y rutas al servicio del
   PR #31, comprobar los descartes y construir el ranking explicado.

La matriz solicitada por `trip_matrix` debe tener 11 filas y 11 columnas:
`sources=[origen, *candidatas]`, `destinations=[*candidatas, destino]`. La captura
de rutas debe conservar `distances_m`, `durations_s`, coordenadas de ambas listas,
identificadores de estación en el mismo orden, proveedor, endpoint, fecha de
consulta y referencia al identificador y hash de esta ficha. Los pares sin ruta
se conservan como `null`; no se rellenan con distancias en línea recta.

Hasta disponer de esa matriz no se calcula combustible final ni se elige una
estación. Este documento no cierra POC-01, POC-02, POC-03 ni POC-05.
