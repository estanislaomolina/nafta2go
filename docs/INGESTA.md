# Ingesta diaria y alertas locales — MVP-01

RF08 requiere una ingesta diaria. El comando registra `running` **antes** de
consultar el catálogo: un fallo de catálogo, descarga, archivo local o normalización
queda en `failed`, con inicio, fin y error. La última versión exitosa sigue
disponible. Los precios, rechazos, captura y cierre se confirman juntos, como en
[PERSISTENCIA](PERSISTENCIA.md); los originales descargados quedan en `data/raw/`.

```bash
.venv/bin/python -m nafta2go.normalization --source vigente --json
```

El JSON expone `run_id`, origen, estado, fechas UTC, duración en segundos,
versión de reglas y reporte de calidad. El código de salida es 0 si termina
correctamente y 1 si falla la adquisición o ingesta. Los errores de configuración
o conexión a la base pueden impedir crear el registro y producen salida no cero.
Los mensajes completos de error quedan en la base; el JSON omite esos mensajes
para evitar exportar URLs o credenciales contenidas en excepciones.

## Programación en Linux con systemd

Se entregan unidades de usuario ([ADR-008](../adr/ADR-008-programacion-de-ingesta.md)).
Ejecutan el vigente a las 06:00 de Argentina, sin bajar diariamente el histórico.
Una misma unidad no se inicia de nuevo mientras sigue activa. El tiempo máximo
es dos horas: si se termina el proceso por timeout o interrupción puede quedar
`running`. El monitor lo alerta sin modificar ese estado.

Después de instalar las dependencias del README, ejecutar
`mkdir -p ~/.config/nafta2go` y crear `~/.config/nafta2go/ingestion.env`, con la
ruta absoluta de este repositorio:

```ini
NAFTA2GO_DIR="/ruta/absoluta/Nafta2Go"
# Opcional: DATABASE_URL. Por defecto usa data/nafta2go.db dentro del repositorio.
```

No se carga `.env` automáticamente. Conservar la base y `data/raw/` juntos;
ambos son necesarios para reconstruir versiones. Para instalar y activar:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/nafta2go-*.service deploy/nafta2go-*.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now nafta2go-ingestion.timer nafta2go-monitor.timer
systemctl --user start nafta2go-ingestion.service
systemctl --user list-timers 'nafta2go-*'
journalctl --user -u nafta2go-ingestion.service -n 20 --no-pager
journalctl --user -u nafta2go-monitor.service -n 20 --no-pager
```

`Persistent=true` recupera una ejecución omitida cuando el temporizador vuelve
a activarse. Sin un gestor de usuario activo, no corre; en una computadora
apagada se recupera al volver a iniciar sesión. Para mantener el gestor activo
sin una sesión abierta, habilitar `loginctl enable-linger "$USER"`; se puede
comprobar con `loginctl show-user "$USER" -p Linger`. Esto no evita la suspensión
ni permite ejecutar tareas con la computadora apagada. Para detener la programación:
`systemctl --user disable --now nafta2go-ingestion.timer nafta2go-monitor.timer`.

## Detección y seguimiento de alertas

Antes de activar el monitor, actualizar la base con `.venv/bin/alembic upgrade head`.
La migración `0003` agrega `ingestion_alerts` sin alterar las ingestas ni las
recomendaciones existentes. Para comprobar el estado manualmente:

```bash
.venv/bin/python -m nafta2go.monitor
```

El monitor usa la misma `DATABASE_URL` y vigila el vigente por defecto. Emite JSON
con estado, fecha UTC de comprobación y alertas activas. Cada alerta conserva
`detected_at` (primera detección), `last_seen_at` y `resolved_at` en la base.
Las comprobaciones repetidas no duplican la alerta ni reinician su detección.

- `failed`: la última ejecución terminada falló; se resuelve cuando una ejecución
  posterior termina correctamente, aunque haya un reintento en curso.
- `stalled`: una ejecución lleva al menos dos horas en `running`. Puede seguir
  activa; el monitor no la termina. Se resuelve cuando deja de estar excedida.
- `missing`: a las 08:00 de Argentina no hay ningún intento iniciado desde las
  06:00 de ese día. Antes de las 08:00 se comprueba la ventana del día anterior.
  Una ingesta fallida o excedida genera su propia alerta en lugar de `missing`.

El temporizador comprueba cada hora. `OnFailure` también lo ejecuta al fallar el
servicio de ingesta, incluidos errores de arranque. Con el gestor y la base
disponibles, un fallo registrado se detecta en la siguiente comprobación
(aproximadamente una hora), y una ingesta ausente desde las 06:00 se alerta a partir de las 08:00.
Si el equipo está apagado, se detecta al reactivarse el temporizador; no se puede
garantizar el límite de 24 h sin un equipo de operación encendido.

La salida es 0 sin alertas, 1 con alertas y 2 si el monitor no puede consultar o
registrar el estado. El código 1 deja el servicio en fallo y escribe un mensaje
de error en el journal; el JSON permite su consumo por herramientas operativas.
El código 2 también se registra en el journal, pero no se puede persistir la
detección si la base está caída. Los mensajes originales de error y las URLs de
conexión se omiten de la salida. Estas son **alertas locales**, sin envío a un
canal externo. El operador debe supervisar el journal o conectar su colector.

## Prueba reproducible sin red

En una base temporal, el monitor debe devolver 1 por ingesta ausente; luego de
ingerir la fixture real recortada, devuelve 0. Es un ensayo, no una ingesta actual
del catálogo ni evidencia de precios recientes:

```bash
(
  MONITOR_DEMO_DIR=$(mktemp -d)
  export DATABASE_URL="sqlite:///$MONITOR_DEMO_DIR/demo.db"
  .venv/bin/alembic upgrade head
  .venv/bin/python -m nafta2go.monitor
  .venv/bin/python -m nafta2go.normalization --source vigente --file tests/fixtures/vigente_sample.csv --json
  .venv/bin/python -m nafta2go.monitor
)
```

Los tests de `tests/application/test_ingestion_monitor.py` simulan fallos,
interrupciones, límites horarios y recuperación con marcas de detección, sin red.

La [evidencia del ensayo local del 09/11/2026](evidencia/mvp-01-monitor-2026-11-09.json)
registra dos ejecuciones transitorias reales con systemd: alerta por base vacía
(salida 1) y recuperación tras ingerir la fixture (salida 0). Incluye los IDs de
invocación del journal, el hash de la fixture y las marcas persistidas de la alerta.
No se activaron temporizadores permanentes durante esa prueba.

## Instalación local verificada el 09/11/2026

Se instalaron y activaron ambos temporizadores en el equipo de desarrollo, con
`Linger=yes`. Se respaldó la base antes de migrarla a `0003`. La primera ingesta
real mediante el servicio terminó como `succeeded` (ejecución 3) y el monitor
informó `healthy`, sin alertas. La [evidencia de instalación y ejecución real](evidencia/mvp-01-instalacion-local-2026-11-09.json)
incluye los estados, calendarios e IDs de invocación del journal, y comprueba que
las cuatro unidades instaladas coinciden con las del repositorio.

El CSV conservado tiene 9.260.911 bytes; su tamaño y SHA-256 coinciden con la
captura registrada. La normalización produjo 732 filas válidas de 184 estaciones,
sin rechazos. A la fecha del ensayo, 130 filas de 39 estaciones tenían hasta
30 días de antigüedad. Una ingesta exitosa no vuelve recientes todos los precios
ni demuestra cobertura suficiente para cualquier recorrido.

La observación registró el próximo monitor para el 09/11 a las 14:00 y la próxima
ingesta para el 10/11 a las 06:00 (Argentina). Son fechas del registro, no un
estado en vivo; consultar `systemctl --user list-timers 'nafta2go-*'` para el actual.
La configuración apunta a este checkout y a su entorno `.venv`: cambiar de rama
o moverlo puede alterar la ejecución; revisar los servicios después de hacerlo.

**MVP-01 sigue abierto:** resta observar ejecuciones programadas en régimen diario
y validar la supervisión sostenida. La instalación y el arranque manual correctos
no demuestran disponibilidad continua ni entrega de notificaciones a una persona.
