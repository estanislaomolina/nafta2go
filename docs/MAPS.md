# Enlaces de navegación — primer incremento de MVP-03

La API y la CLI generan un enlace de Google Maps por alternativa elegida,
como preparación para la web y respuesta parcial a #58. Usan
[Maps URLs](https://developers.google.com/maps/documentation/urls/get-started),
sin API key, SDK ni llamadas a Google desde el servidor.

## Contrato de presentación

La respuesta agrega `navigation`, una lista con `station_id`, `url` y `label`.
Cada enlace corresponde a una entrada de `alternatives`; la etiqueta incluye
bandera y dirección, con identificador como respaldo si esos textos faltan.
`navigation_notice` aclara que Google recalcula su recorrido y puede diferir
del usado para recomendar. Sin alternativas, `navigation` es vacío y el aviso
es `null`. No se crean enlaces para estaciones descartadas.

La URL usa HTTPS, `api=1`, destino latitud/longitud codificado, modo `driving` y
`dir_action=navigate`. Solo contiene coordenadas públicas de la estación. No
incluye origen del conductor, destino de su viaje ni puntos intermedios. Google
puede pedir un origen o usar la ubicación del dispositivo según disponibilidad;
no se garantiza navegación paso a paso en todas las plataformas.

La aplicación transmite temporalmente las coordenadas de las estaciones elegidas
a la presentación **después** de persistir la recomendación. La presentación
construye los enlaces y omite ese campo interno de la salida HTTP/CLI. No guarda
URLs en la recomendación ni agrega coordenadas del conductor a los registros.
El motor, las métricas, el ranking y los campos previos de alternativas/evaluaciones
se conservan. Los escenarios históricos siguen rotulados; abrir Maps no convierte
sus precios en actuales ni verifica que la estación siga operando.

## Probar sin servicios externos

Con dependencias instaladas, ejecutar desde el repo y una base local de prueba:

```bash
python -m nafta2go.query --origin=-34.6037,-58.3816 --destination=-34.5627,-58.4565 \
  --matrix-file docs/evidencia/poc-05-flujo-2026-10-26/matrix.json --json
```

La matriz y precios de este ensayo son históricos. El JSON muestra los enlaces;
sin `--json`, la CLI los imprime junto a las alternativas y el aviso. El comando
no abre Maps ni transmite datos a Google. La misma información está en
`POST /api/v1/recommendations`, con la autenticación de [API](API.md).

## Pendiente de la interfaz (#58 y #17)

La [web local](WEB.md) presenta enlaces con texto descriptivo, aviso de recálculo
y vigencia. Abre otra pestaña con `rel="noopener noreferrer"` e inserta los textos
como texto, no HTML. Las pruebas automatizadas de teclado y navegador se entregan
en una PR dependiente; falta validar en un teléfono físico.
Los tests actuales cubren coordenadas, codificación, destino, conservación del
ranking, contrato HTTP/CLI y ausencia de enlaces en la persistencia, sin red.
