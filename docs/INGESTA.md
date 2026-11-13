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

## Límites de operación

Un fallo transitorio de DNS o de red queda registrado como `failed`; estas
unidades no reintentan automáticamente. `Persistent=true` recupera una ejecución
omitida, pero no reintenta una ejecución que falló. Tras comprobar conectividad,
el operador puede iniciar el servicio manualmente y luego consultar el monitor.
Los precios anteriores se conservan y su vigencia se evalúa por fecha original.
No se garantiza disponibilidad continua ni actualización exitosa diaria por
instalar los temporizadores. La evidencia de operación se incorpora por separado.

## Evidencia local y recuperación observada

El [ensayo del 09/11](evidencia/mvp-01-monitor-2026-11-09.json) conserva dos
invocaciones transitorias: alerta con base vacía y recuperación tras ingerir una
fixture. No prueba una descarga actual ni operación programada.
La [instalación del 09/11](evidencia/mvp-01-instalacion-local-2026-11-09.json)
registra timers habilitados, `Linger=yes`, ingesta real mediante el servicio y
monitor saludable. Los calendarios de ese archivo son históricos, no estado vivo.

La [observación del 12/11, hora de Argentina](evidencia/mvp-01-operacion-2026-11-12.json)
registra fallos de DNS en las ejecuciones 6 y 7 (11 y 12/11), sus alertas
persistidas y una **recuperación manual**: ejecución 8, iniciada el 12/11 a las
23:50 de Argentina (13/11 02:50 UTC). El monitor terminó después sin alertas activas.
El archivo original coincide con el SHA-256 y tamaño de su captura, y las cuatro
unidades instaladas coinciden con las versionadas. El checkout operativo observado
fue `4325d79`, conservado por el tag anotado
[`evidencia/mvp-01-operacion-2026-11-12`](https://github.com/estanislaomolina/nafta2go/tree/evidencia/mvp-01-operacion-2026-11-12).
El tag fija ese commit aunque posteriormente se elimine una rama de trabajo.
La rama mencionada en el JSON es la observada en aquella captura; no se reescribe
la evidencia histórica. El checkout operativo y sus servicios siguen sin cambios.

El último disparo observado del timer de ingesta coincide en horario con el
inicio de la ejecución 7. La base no registra el disparador de cada ejecución:
no se atribuyen todos los intentos al timer solo por sus fechas. La alerta del
fallo 6 se resolvió al aparecer un fallo posterior (7), reemplazada por su alerta;
no significa que se hubiese recuperado entonces la ingesta. La resolución del
fallo 7 y el monitor saludable sí fueron posteriores al éxito manual 8.

Para contrastar la evidencia, desde el checkout operativo y con la misma base:

```bash
systemctl --user list-timers 'nafta2go-*'
systemctl --user show nafta2go-ingestion.service nafta2go-monitor.service -p Result -p ExecMainStatus
journalctl --user -u nafta2go-ingestion.service -u nafta2go-monitor.service --since '2026-11-11' --no-pager
```

En SQLite, consultar `ingestion_runs` (IDs 6 a 8), `raw_captures` (`run_id=8`) e
`ingestion_alerts` (`run_id` 6 y 7); comparar el original con su SHA-256 y tamaño.
Las marcas de la base son UTC sin zona y el journal explicita su zona. La fecha
`observed_at` del archivo está en UTC; el nombre usa el día local de la observación.
La ruta del original se normalizó como relativa y se omitieron errores completos
y URLs. Los datos y el journal pueden cambiar o rotar después de esta captura.

**MVP-01 sigue abierto:** no hubo actualización automática exitosa los días del
fallo. Restan supervisión sostenida, política de reintentos acotados y resolver la
disponibilidad del equipo/catálogo; no hay notificaciones a un receptor externo.
No cambiar de rama ni mover el checkout operativo sin revisar sus servicios.
