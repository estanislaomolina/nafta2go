# Ingesta diaria y alertas locales — MVP-01

## Recibos de adquisición remota — parte de #160

La CLI admite `--source vigente --file CAPTURA.csv --receipt RECIBO.json`.
Comprueba tamaño, SHA-256, origen y fecha antes de normalizar: rechaza recibos de
más de 36 horas y fechas más de cinco minutos futuras. Conserva URL y adquisición
originales en lugar de la URI/mtime de la copia. El reporte guarda corrida de
Actions, commit y hash del recibo; la fecha de cada precio no cambia.

Un fallo de validación deja una ejecución fallida y conserva los precios
anteriores. El recibo no firma al proveedor HTTP: requiere un canal privado y
autenticado. El productor y receptor se incorporan como otro tramo de #160,
según [ADR-031](../adr/ADR-031-transferencia-verificada-de-capturas.md).
Pruebas de integridad, linaje y persistencia: `tests/adapters/test_capture_relay.py`.
#160 sigue abierto: este contrato no instala programación ni acredita autonomía.

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
En adquisición remota se conserva sólo el tipo de error, sin su mensaje original.
Otros fallos pueden conservar mensajes en la base; el JSON los omite para evitar
exportar URLs o credenciales contenidas en excepciones.

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

Estas unidades no reinician automáticamente el servicio. El comando realiza
los reintentos acotados de adquisición descritos abajo; si no se recupera, la
ejecución queda `failed`. `Persistent=true` recupera una ejecución
omitida, pero no reintenta una ejecución que falló. Tras comprobar conectividad,
el operador puede iniciar el servicio manualmente y luego consultar el monitor.
Los precios anteriores se conservan y su vigencia se evalúa por fecha original.
No se garantiza disponibilidad continua ni actualización exitosa diaria por
instalar los temporizadores. La evidencia fechada y sus límites se detallan abajo.

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

**Estado al 12/11 (histórico):** no hubo actualización automática exitosa los días del
fallo. Restan supervisión sostenida, instalar y observar los reintentos descritos
abajo y resolver la disponibilidad del equipo/catálogo; no hay notificaciones a un receptor externo.
No cambiar de rama ni mover el checkout operativo sin revisar sus servicios.

## Reintentos acotados de adquisición remota

Sin `--file`, cada invocación permite hasta **tres intentos** de adquisición del
catálogo y CSV, con esperas de **60 y 120 segundos**. Cada intento abre y cierra
su propia sesión y vuelve a consultar el catálogo. Se reintentan conexión/DNS,
timeouts, descarga interrumpida o incompleta y HTTP 502, 503 o 504 sin
`Retry-After`. El adaptador borra los archivos parciales antes del siguiente intento.
Con `--file` se usa el archivo local una sola vez.

No se reintentan TLS, proxy, errores permanentes de catálogo, HTTP distintos de
los anteriores, normalización ni persistencia. Si una respuesta HTTP trae
`Retry-After`, se detiene sin reintentar dentro de esa invocación: no se acorta ni
se ignora la espera indicada, aunque el valor esté mal formado. Tampoco se
reintenta HTTP 429. ORS y su política de cuota no se modifican.

Los intentos pertenecen al mismo `run_id`: permanece `running` hasta completar o
fallar, sin repetir precios ni crear ejecuciones por cada error transitorio.
Las nuevas ejecuciones conservan `report.acquisition_attempts`, tanto en éxito
como en fallo, y el JSON de la CLI lo expone dentro del reporte. Los eventos de
reintento incluyen origen, número de intento, tipo de error y próxima espera;
no incluyen URLs ni mensajes originales. En systemd se vinculan por invocación.
No se aplica una migración ni se infiere ese dato para las ejecuciones antiguas.

Al agotarse los intentos la ejecución queda `failed`, conserva la versión anterior
y el monitor puede alertar. Si la adquisición tiene éxito pero la normalización
falla, no vuelve a descargar. Las esperas adicionales suman como máximo 180 s;
los timeouts de red existentes y el límite de dos horas del servicio siguen
vigentes. Esto no garantiza una descarga exitosa ni disponibilidad del equipo.

Las pruebas simulan recuperación de DNS y corte de stream, agotamiento, errores
permanentes, cierre de sesiones y limpieza de parciales, sin red ni esperas reales.
La operación se actualizó a una copia fija de una versión revisada de `dev`;
la evidencia y las condiciones de conservación/rollback están al final de este documento.

La clasificación usa las [excepciones de Requests](https://requests.readthedocs.io/en/latest/user/quickstart/#errors-and-exceptions).

## Lectura administrativa por HTTP

La API local ofrece `GET /api/v1/operations/ingestion` con Bearer para consultar
el último intento, la última versión exitosa y sus conteos, captura y reglas.
Recalcula las condiciones del monitor sin escribir ni cambiar alertas; una
lectura no constituye una ejecución del monitor ni demuestra que el timer haya
corrido. No expone errores originales, URLs, archivos ni filas. Contrato y
límites en [API](API.md#estado-de-ingestas-para-operación).


## Actualización controlada de la operación — 19/11 local, 20/11 UTC

El servicio usaba `4325d79`, anterior a los reintentos de #76. Los intentos 13 y 14
fallaron por DNS. Se preparó una copia fija de `1622622` mediante `git archive` en
`.runtime/releases/<sha>`, con venv propio y dependencias registradas, sin cambiar
la rama ni los archivos versionados del checkout de trabajo.

Se respaldaron SQLite con su API de backup (integrity_check correcto) y el archivo
privado `ingestion.env`. El candidato se probó primero con una copia de la base y
un CSV existente: terminó correctamente sin alterar la base operativa. Se verificó
que los 249 archivos de la copia coinciden con el commit revisado.

Con servicios inactivos se pausaron los dos timers durante el cambio. Sólo se
actualizaron `NAFTA2GO_DIR` y `PYTHONDONTWRITEBYTECODE` en el EnvironmentFile; la URL
absoluta de base y las unidades se conservaron. La carpeta `data` de la release
es un enlace a los originales/base existentes. Los timers se reanudaron. Un timer
transitorio de diez segundos invocó **el servicio de ingesta real**: ejecución 15,
exit 0, éxito en 1,26 s y un intento de adquisición. El monitor posterior terminó
con exit 0 y cero alertas activas. No se provocó DNS fallido para esta medición.

La [evidencia](evidencia/ingesta-release-2026-11-20.json) conserva commit, hashes,
entorno, resultados y comprobación de que las ingestas/precios anteriores y todas
las recomendaciones permanecen iguales. Respaldos, configuración y datos quedan
fuera de Git, con permisos privados.

### Conservación y reversión

- Conservar la release y su enlace `data`: la captura de la ejecución 15 está en
  los originales compartidos, pero su ruta absoluta pasa por ese alias. No borrar
  releases usadas por capturas sin revisar sus referencias.
- No cambiar de rama dentro de una release ni mezclarla con código pendiente de
  review. Una actualización nueva empieza por otro commit revisado y otra copia.
- Antes de actualizar: comprobar servicios sin PID activo, pausar timers, respaldar
  SQLite/configuración y probar una copia. Si el candidato falla, conservar la
  configuración previa y reanudar los timers.
- Para revertir el código: pausar timers, comprobar que no hay trabajos activos y
  restaurar `ingestion.env` desde su respaldo privado con permisos 0600; después
  reanudar ambos timers y comprobar ingesta/monitor. No restaura la base por defecto:
  el esquema sigue en 0003 y la actualización no borró datos. Restaurar SQLite sólo
  ante un problema de datos, conservando antes la base actual y los originales.

**Estado al 20/11 UTC (histórico):** la ejecución del timer de prueba no es la diaria de las
06:00 ni acredita continuidad sostenida. Falta observar el próximo disparo diario
y su monitor; una computadora apagada no ejecuta tareas. No se agregó cómputo AWS
ni se enviaron notificaciones a un receptor externo.


## Verificación diaria y cierre funcional de MVP-01 — 21/11

La [evidencia diaria](evidencia/ingesta-diaria-2026-11-21.json) registra dos
adquisiciones reales posteriores a la actualización de la operación:

- Ejecución 16: 20/11 a las **09:05:31 de Argentina**, exitosa tras dos intentos
  (61,29 s). Ese día no se acredita puntualidad a las 06:00.
- Ejecución 17: 21/11 a las **06:00:51 de Argentina**, exitosa en un intento
  (1,83 s), coincidente con el disparo diario del timer a las 06:00:50.

Ambas validaron 732 filas de 184 estaciones, sin rechazos. Se contrastaron tamaño
(9.260.901 bytes) y SHA-256 de cada original contra sus metadatos persistidos.
La ejecución 17 identificó el mismo CSV de la 16 mediante `duplicate_of_run_id`.
Se conserva una versión de precios por ejecución; no se deduplican filas entre
ingestas distintas. La consulta selecciona una única ingesta exitosa.
Una descarga nueva no convierte los precios antiguos del catálogo en actuales.
Ingesta y monitor terminaron con estado exitoso; no había alertas activas y el
próximo disparo estaba programado para el 22/11 a las 06:00 de Argentina.

Esta evidencia completa la comprobación funcional de frecuencia local de
[#15](https://github.com/estanislaomolina/nafta2go/issues/15), junto con las
validaciones y trazabilidad ya verificadas. La ejecución 15 fue un timer de
prueba y se conserva separada en la evidencia anterior. Dos ejecuciones exitosas
no acreditan un SLA ni disponibilidad continua: la computadora apagada no ejecuta
tareas. El despliegue y la validación integral siguen en #22, #23 y #59.


## Productor y receptor de capturas — continuación de #160

`python -m scripts.publish_capture --bucket BUCKET_PRIVADO` se ejecuta en el runner
con `GITHUB_RUN_ID`, `GITHUB_SHA` e identidad AWS de máquina. Reutiliza los tres
intentos de adquisición; verifica integridad y calidad antes de publicar el CSV
por hash y después `vigente/latest.json`. Cada publicación limita AWS CLI a tres
intentos y 300 segundos. No recibe un perfil SSO personal.

El host usa `deploy/aws-ingestion-relay.sh` con `NAFTA2GO_CAPTURE_BUCKET` y el rol
EC2. Descarga una sola vez el recibo y el CSV de su hash, y ejecuta el importador
con la imagen de `current-image`. Comparte `private/deployment.lock` con el
procedimiento de despliegue; espera hasta 60 s y falla si continúa ocupado.
No adquiere nuevos precios durante un despliegue. Los originales quedan en
`data/imports/relay-*` desde que pueden ser referenciados por una transacción.
Una falla de descarga elimina el parcial y no ejecuta el importador; su ausencia
se detecta por antigüedad en el monitor.

Las pruebas ejecutan el receptor real con AWS/Docker sustituidos y comprueban
éxito, descarga fallida y corrupción. No representan una ejecución en AWS.
El contrato de recibos se revisa en #176 y el transporte en #177.
Estos ejecutables por sí solos no cierran el issue.

## Programación e identidad de máquina en AWS

`infra/aws/capture-relay.json` crea S3 privado, cifrado y versionado; una identidad
OIDC con permiso exclusivo de publicación bajo `vigente/`, y una política de sólo
lectura adjunta al rol EC2 existente. Reutiliza el proveedor OIDC de #164. La
confianza exige audiencia STS y el subject inmutable de este repositorio para
`main` o `dev`; no admite PRs, otras ramas ni `environment:demo`.

`.github/workflows/acquire-prices.yml` programa adquisición a las 09:17 UTC
(06:17 Argentina). No usa environment ni aprobación interactiva en cada corrida:
es una identidad distinta del despliegue de #156. Tanto el cron como el primer
disparo manual requieren que el archivo exista en la rama predeterminada,
actualmente `main`. Después se puede seleccionar `dev` al disparar manualmente;
integrarlo sólo a `dev` no habilita esa primera corrida. GitHub puede retrasar el
cron; [condiciones de los disparadores](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows).
Las variables de repositorio `NAFTA2GO_CAPTURE_BUCKET` y
`NAFTA2GO_CAPTURE_ROLE_ARN` son referencias públicas, no credenciales.

### Instalación sobre una release revisada

1. Aplicar el change set de `capture-relay.json` con `DemoRoleName` igual al rol
   EC2 existente; el proveedor OIDC debe existir. Usar sus outputs para las dos
   variables de repositorio. No crear access keys ni copiar sesiones SSO al host.
2. Integrar #176/#177 y la programación en `dev`, y entregar desde `dev` a `main`
   mediante PR para registrar el workflow. Activar una imagen que incluya
   `--receipt`. Mantener base/configuración privadas del host. El instalador
   verifica esa capacidad antes de habilitar los servicios.
3. Desde el directorio de esa release, ejecutar mediante SSM como root
   `bash deploy/install-aws-ingestion.sh BUCKET_PRIVADO`. Instala los dos scripts,
   `nafta2go-aws-ingestion.service/.timer` y `nafta2go-aws-monitor.service/.timer`;
   no cambia los servicios locales. El env sólo contiene el nombre del bucket.
4. Disparar la adquisición en Actions y observar la ingesta por timer en AWS.
   Contrastar el `workflow_run`, commit, hash y tamaño del reporte con la corrida
   y los originales. Revisar `systemctl list-timers 'nafta2go-aws-*'` y el journal.
   Un `systemctl start` manual no demuestra que el calendario diario haya corrido.

La ingesta del host está programada a las 06:45 de Argentina; el monitor, cada
hora y ante fallo del servicio. Ambos timers tienen `Persistent=true`: si el host
estaba apagado, recuperan un disparo omitido al arrancar, no cada día perdido.
Una captura de más de 36 horas se rechaza; no se transforma una descarga vieja
en datos actuales. No se despierta EC2 para adquirir ni se elimina su apagado
automático. Esto no ofrece operación 24/7 ni notificaciones a receptores externos.

El receptor limita su servicio a 30 minutos y cada llamada AWS a tres intentos.
El productor tiene un límite de 20 minutos y serializa corridas. Un fallo antes
de publicar el recibo conserva el puntero anterior; un timeout de la respuesta
del PUT del recibo puede dejar su resultado incierto y exige consultar S3.
No se borran originales locales referenciados. S3 expira transferencias a los 90
días y versiones previas a los siete; el bucket se conserva al borrar el stack.

### Reversión y evidencia

Para desactivar la programación, detener y deshabilitar ambos timers AWS, esperar
servicios sin PID activo y conservar configuración, originales y base. No restaura
SQLite ni revierte migraciones. Deshabilitar también el workflow si se abandona
la adquisición. Eliminar el stack retira sus políticas y rol de publicación,
pero conserva el bucket: revisar su contenido/costo antes de borrarlo aparte.

La infraestructura quedó creada el 23/11; [evidencia del canal](evidencia/ingesta-canal-2026-11-23/infra.json).
La creación de roles y S3 no acredita una corrida OIDC ni una ingesta automática.
El [preflight del host](evidencia/ingesta-canal-2026-11-23/preflight.json)
confirmó identidad EC2 renovable y que la imagen activa aún no admite `--receipt`;
no se habilitaron servicios incompatibles. El cierre de #160 requiere activar
una imagen compatible y observar el recorrido completo después de la revisión
e integración. Referencias: [OIDC de GitHub](https://docs.github.com/en/actions/reference/security/oidc)
y [S3 en CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-s3-bucket.html).


## Entorno de adquisición del canal AWS

`NAFTA2GO_ACQUISITION_RUNNER` permite seleccionar un runner de Actions con
conectividad comprobada al catálogo HTTP. Si no se configura, usa
`ubuntu-latest`. Un timeout del catálogo desde un runner no prueba ausencia de
publicación del proveedor. El flujo conserva OIDC, los reintentos acotados y
la validación del CSV; cambiar el runner no permite reutilizar capturas viejas
como si fueran descargas nuevas. La ingesta en EC2 conserva identidad de
instancia y timers persistentes, sin una sesión SSO personal.
