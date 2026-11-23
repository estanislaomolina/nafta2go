# Servidor temporal de demo AWS

La [plantilla](../infra/aws/demo-server.json) define un host con Docker sobre la
[red existente](AWS.md). Se creó el 21/11/2026 con autorización del titular; la
entrega de la aplicación se realiza por SSM y un commit revisado, como se describe
al final. Los apartados de propuesta se conservan como procedimiento reproducible.
[ADR-018](../adr/ADR-018-servidor-efimero-de-demo.md) compara alternativas.

## Diseño y permisos

Ohio, una `t3.small` Linux, disco gp3 cifrado de 16 GiB, AMI x86_64 fijada al revisar
el cambio, IMDSv2, rol `AmazonSSMManagedInstanceCore` y grupo sin entrada. Salida
HTTPS por defecto con IPv4 pública asignada a la instancia, sin EIP ni NAT.
Existe una excepción HTTP opcional y acotada para la fuente de Energía (abajo). La API continuará
ligada a loopback; el túnel de Session Manager exige autorización IAM/SSO.
La URL pública opcional se habilita con el [servicio HTTPS versionado](AWS-HTTPS.md);
no reemplaza la autenticación de conductor/administrador.

El administrador del sandbox debe permitir IAM/PassRole, instancia, disco, grupo
y SSM; el dry-run de VPC anterior no verifica esos permisos. La red/subred deben
corresponder a la misma VPC y tener la ruta a internet del stack de red.
Referencia de [AMI](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/finding-an-ami-parameter-store.html)
y [túnel SSM](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html).

## Costo revisado y autorizado para la primera prueba

El presupuesto es USD 17 **total**, no mensual. El titular confirmó saldo de
USD 17 y autorizó crear el servidor para la primera prueba el 21/11. La consulta
pública de EC2 de ese día mantiene USD 0,0208/h; la API Pricing del sandbox está
denegada por SCP. No se presume que todos los permisos estén habilitados.
Referencia de costos preparada el 16/11/2026:

* Linux On-Demand `t3.small` Ohio: USD 0,0208/h, 2 vCPU y 2 GiB según el
  [catálogo regional oficial](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/US%20East%20%28Ohio%29/Linux/index.json).
* IPv4: USD 0,005/h según [VPC](https://aws.amazon.com/vpc/pricing/).
* EBS se cobra también detenido. Como referencia general, AWS publica gp3 a
  USD 0,08/GiB-mes en [tipos de volumen](https://aws.amazon.com/ebs/volume-types/);
  confirmar tarifa de Ohio antes de aprobar. No se provisionan IOPS/throughput extra.

Dos horas de cómputo e IPv4 suman USD 0,0516 **sin disco ni transferencia**.
Si aplica la referencia de gp3, 16 GiB retenidos un mes agregan USD 1,28. Son
subtotales orientativos: falta revisar saldo/restricciones, horas acumuladas,
retención, transferencia, respaldos e impuestos. No se presupone crédito adicional,
franquicia de transferencia ni tope automático de facturación. El timer no limita
reinicios posteriores. Modo [CPU standard](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances-standard-mode.html)
evita créditos de CPU excedentes facturados, a cambio de reducir rendimiento.

## Validar y preparar revisión

Local/CI: `cfn-lint -r us-east-2 -t infra/aws/*.json` y `pytest tests/infra`.
No consultan ni crean recursos AWS. Con sesión del titular en CloudShell:

```bash
aws cloudformation validate-template --region us-east-2 \
  --template-body file://infra/aws/demo-server.json
```

Después de fijar VPC/subred de los outputs de `nafta2go-network` y una AMI AL2023
x86_64, el siguiente comando prepara un change set; **no lo ejecuta**:

```bash
aws cloudformation deploy --region us-east-2 --stack-name nafta2go-demo \
  --template-file infra/aws/demo-server.json --capabilities CAPABILITY_IAM \
  --parameter-overrides VpcId="${VPC_ID:?}" SubnetId="${SUBNET_ID:?}" ImageId="${AMI_ID:?}" \
  --no-execute-changeset
```

Revisar las cuatro altas (grupo, rol, profile e instancia), AMI, costo completo y
permisos con el titular antes de ejecutar. No se incluyen secretos en parámetros
ni UserData. Resolver una AMI actual no equivale a probarla: registrar su ID en la
evidencia privada. No subir IDs de cuenta, sesiones ni credenciales al repo.

## Excepción opcional para la ingesta pública

El 17/11/2026 se verificó que el [catálogo oficial de precios](http://datos.energia.gob.ar/api/3/action/package_show?id=precios-en-surtidor)
redirige HTTPS a HTTP y publica los CSV vigente e histórico en HTTP, en
`datos.energia.gob.ar`. El [adaptador](../nafta2go/adapters/energy_source.py)
usa ese contrato. Con la salida predeterminada sólo por 443, la ingesta desde el
host queda bloqueada. La plantilla no descarga datos durante el bootstrap.

`EnergyHttpCidr` queda vacío por defecto: no habilita el puerto 80. Para permitir
la ingesta en una futura demo se debe verificar la IPv4 actual del catálogo,
los CSV y sus redirecciones, y fijar **una única IPv4/32**. Por ejemplo, resolver
el host desde el entorno de despliegue con `getent ahostsv4 datos.energia.gob.ar`
y comprobar los destinos de las URLs devueltas por el catálogo. Si aparecen
varias IP o cambia el host, revisar el alcance antes de preparar el cambio.
No copiar una IP histórica sin verificarla ni ampliar a una subred o a internet.

Una vez verificado el destino, agregar al comando anterior de preparación del
change set `EnergyHttpCidr="${ENERGY_HTTP_CIDR:?}"`, junto con los otros parámetros.
Revisar en el change set la salida TCP/80 hacia esa /32. El security group filtra
IP, no nombres: un cambio de DNS puede requerir actualizar el parámetro. La
excepción sólo permite salida; no abre entrada ni instala la aplicación.

HTTP no autentica el origen ni cifra estos datos públicos. Los hashes registran
contenido, pero no reemplazan TLS. No enviar credenciales por esta excepción:
ORS conserva HTTPS y el acceso a la app sigue por SSM. También se puede conservar
el valor vacío y transferir capturas verificadas desde otro entorno; esa
transferencia todavía requiere implementación. [ADR-019](../adr/ADR-019-salida-http-acotada-de-energia.md)
compara las alternativas. No se ejecutó ningún cambio en AWS para esta corrección.

## Verificación posterior y apagado

Tras una futura creación aprobada, verificar SSM online, Docker y el timer desde
la sesión del host: `docker info` y `systemctl list-timers nafta2go-demo-stop.timer`.
`CREATE_COMPLETE` no espera la instalación de Docker. El host se apaga a las dos
horas de cada boot; si se termina o borra el stack, el disco también se elimina.
Detenerlo conserva el disco y sus cargos; no se crean snapshots automáticos.

Una vez desplegada la API, el túnel se inicia en **la computadora local** con
AWS CLI, plugin Session Manager y SSO; localhost de CloudShell no es el del equipo:

```bash
aws ssm start-session --region us-east-2 --target "${INSTANCE_ID:?}" \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8000"],"localPortNumber":["8000"]}'
```

Antes de terminar/eliminar, exportar y verificar respaldo fuera del host. Esa
restauración, la entrega por imagen versionada, secretos, ingesta y prueba real
de readiness/rollback siguen pendientes en #22/#59. Esta propuesta no cierra esos
issues ni acredita un despliegue; no usar el host como única copia de los datos.


## Entrega versionada por SSM — 21/11/2026

Se verificaron directamente sesión SSO, red `CREATE_COMPLETE`, ausencia de
instancias/discos anteriores, AMI AL2023 x86_64 disponible y permiso RunInstances
por dry-run. Se revisaron cuatro altas y se ejecutó el change set autorizado:
instancia, rol SSM, instance profile y security group. El stack terminó
`CREATE_COMPLETE`, SSM informó `Online` y Docker terminó de instalarse. El timer de
apagado quedó activo a las dos horas desde el arranque. No se publican IDs privados.

El titular autorizó también la excepción de salida HTTP del catálogo. Se verificó
una sola IPv4 para el host del catálogo y sus CSV; el change set modificó sólo el
grupo de seguridad, sin reemplazo y sin entrada. La IP puede cambiar: verificarla
antes de cada actualización. El rol de la instancia permite recuperar la
configuración desde un parámetro Standard `SecureString`; no se envían secretos
como argumentos de Run Command, UserData ni archivos versionados.

La [guía breve de entrega](ENTREGA-AWS.md) reúne los prerrequisitos.
El [ejecutable local](../scripts/aws_demo_command.py) envía el
[procedimiento remoto](../deploy/aws-demo-release.sh) por `AWS-RunShellScript`:

```bash
python scripts/aws_demo_command.py --profile nafta2go \
  --instance-id "$INSTANCE_ID" --commit "$REVIEWED_COMMIT" \
  --parameter /nafta2go/demo/runtime --image "$IMAGE_DIGEST"
```

Usa un SHA completo, valida instancia/parámetro y devuelve el ID del comando.
Consultar su estado; no reenviarlo mientras siga ejecutándose. La aplicación se
descarga de GHCR por el digest del artefacto `referencia-imagen` del CI y se verifica
su etiqueta de commit; no se construye en EC2. El paquete debe permitir lectura
anónima. Conservar el digest de la corrida elegida; reconstruir un commit con
dependencias con rangos puede producir otra imagen. Ver [entrega](ENTREGA-AWS.md).

El parámetro privado contiene `DATABASE_URL=sqlite:////app/data/nafta2go.db`,
`ORS_API_KEY`, tokens distintos de conductor/administrador y límites de vigencia,
caché y cuota. Se recupera sólo en el host a un env con permisos 0600, fuera de la
release. El puerto se liga a `127.0.0.1:8000`; las credenciales no se imprimen.

Antes de activar se aplican migraciones sobre almacenamiento
persistente; la adquisición se ejecuta por separado; si ya hay base, se respalda usando la API SQLite y se comprueba
integridad. El servicio anterior continúa mientras se descarga la imagen y se
preparan los datos. Después se sustituye el contenedor y se ejecuta el smoke de [entrega](ENTREGA-AWS.md);
si falla, se intenta recuperar la imagen anterior. El rollback es de código,
con la configuración actual: no revierte migraciones ni restaura datos. El esquema
0003 es compatible entre las primeras releases; una migración futura debe revisar
esa premisa. La base y originales del host no son todavía un backup externo.

Las pruebas aisladas ejecutan el script con dependencias falsas para verificar
fallo de descarga o discrepancia de revisión, recuperación ante readiness fallido, conservación de la
imagen anterior y ausencia de valores privados en la salida. La validación del
transporte rechaza inyección y referencias fuera del prefijo permitido. No se
confunden estas pruebas con un rollback provocado en AWS.

Para la primera prueba se utiliza el túnel SSM con puerto local 8001, evitando
interferir con una preview local en 8000:

```bash
aws ssm start-session --profile nafta2go --region us-east-2 \
  --target "$INSTANCE_ID" --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8000"],"localPortNumber":["8001"]}'
```

Abrir `http://localhost:8001/` con el código privado de conductor. Es acceso por
SSO/túnel, no una URL pública compartible. Cerrar el túnel no detiene la instancia.
El apagado conserva el disco facturable; respaldar fuera del host y eliminar el
stack cuando termine su uso, como se indica arriba.

La actualización programada, respaldo externo/restauración, histórico compatible
y validación final se siguen en #22/#23/#59. No se declara disponible el diagnóstico
sólo por configurar manifiestos: necesita también la ingesta histórica compatible.


### Captura transferida cuando el catálogo no responde desde AWS

En la primera prueba, la descarga directa desde Ohio terminó con ConnectTimeout
tras tres intentos; el DNS resolvía la IPv4 permitida y la regla de salida estaba
aplicada. Una comprobación HTTP independiente también agotó el timeout. No se
atribuye el bloqueo a una causa no demostrada ni se amplía el grupo de seguridad.

Se descargó el CSV vigente con el adaptador habitual desde el entorno local y se
transfirió comprimido por SSM en partes separadas. Antes de descomprimir/importar,
se contrastaron hash del gzip, cantidad de partes, tamaño y SHA-256 del original.
El archivo público queda en `data/imports/<sha256>.csv`, con permisos para el UID de
la aplicación. No se transfieren tokens mediante ese mecanismo.

El procedimiento original (anterior a #157) admitía `--capture-file /app/data/imports/<sha256>.csv`.
Sólo acepta esa ruta con nombre de hash completo; ejecuta el mismo normalizador
con `--file`. Es una importación explícita, no una descarga exitosa desde AWS.
La captura ya cargada no elimina la necesidad de resolver la adquisición
programada ni prueba frescura futura. No se instalan timers que oculten ese bloqueo.


## Resultado de la primera demo

[Evidencia redactada](evidencia/aws-demo-2026-11-21.json): aplicación `de1d98d`,
imagen identificada por SHA-256, `/health` y `/ready` 200; sin token 401, conductor
sin acceso a operaciones (401) y administrador con acceso (200). Una consulta de
prueba con origen/destino sintéticos obtuvo `ready/recommended`, diez evaluaciones,
una alternativa y rutas reales de ORS en 0,816 s sobre el túnel. Es una observación,
no una medición de p95. Había 27 estaciones elegibles con precios recientes.

Chromium mostró la alternativa sin rótulo de escenario histórico. Axe no encontró
violaciones ni incompletos en ese estado. La interfaz mantuvo el diagnóstico y el
ranking conservador como no disponibles por falta de configuración/histórico.
No se atribuyen resultados predictivos ni participantes humanos.

La repetición de la entrega terminó con la misma imagen y readiness 200. Las
importaciones 2 y 3 identifican la misma captura mediante `duplicate_of_run_id`;
cada ejecución conserva su versión de precios (732 filas por ejecución). Eso no
supone deduplicar filas entre ejecuciones.

Se exportó un snapshot SQLite por SSM fuera del host; su copia local pasó
`integrity_check=ok`. Se verificaron los originales contra sus hashes y tamaños,
y la auditoría sobre la base restaurada dio trazabilidad/privacidad 2/2 y frescura
20/20 precios evaluados. Las dos recomendaciones son consultas de prueba. Datos,
originales y configuración quedan fuera de Git. La exportación inicial se realizó
por fragmentos; resta automatizar su retención y recuperación operativa.

El primer apagado está programado para el 21/11 a las 23:51 UTC (20:51 de Argentina).
Después del apagado la URL local requiere volver a iniciar la instancia y el túnel;
no confundir cerrar CloudShell o el túnel con detener el servidor.

La prueba temporal de Cloudflare se convirtió en un [procedimiento HTTPS](AWS-HTTPS.md)
con servicio, versión/hash fijados y salida opcional de CloudFormation. Quick no
requiere token; el modo administrado sí gestiona credenciales. La prueba desde
un teléfono físico sigue siendo un criterio distinto del smoke HTTP automatizado.
