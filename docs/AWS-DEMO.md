# Servidor de demo AWS — propuesta, sin provisionar

La [plantilla](../infra/aws/demo-server.json) prepara un host con Docker sobre la
[red existente](AWS.md). No se ejecutó en AWS ni instala la aplicación o sus datos.
[ADR-018](../adr/ADR-018-servidor-efimero-de-demo.md) compara alternativas.

## Diseño y permisos

Ohio, una `t3.small` Linux, disco gp3 cifrado de 16 GiB, AMI x86_64 fijada al revisar
el cambio, IMDSv2, rol `AmazonSSMManagedInstanceCore` y grupo sin entrada. Salida
HTTPS con IPv4 pública asignada a la instancia, sin EIP ni NAT. La API continuará
ligada a loopback; el túnel de Session Manager exige autorización IAM/SSO.
No entrega una URL pública ni reemplaza la autenticación de conductor/administrador.

El administrador del sandbox debe permitir IAM/PassRole, instancia, disco, grupo
y SSM; el dry-run de VPC anterior no verifica esos permisos. La red/subred deben
corresponder a la misma VPC y tener la ruta a internet del stack de red.
Referencia de [AMI](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/finding-an-ami-parameter-store.html)
y [túnel SSM](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html).

## Costo pendiente de aprobar

El presupuesto es USD 17 **total**, no mensual. Consulta del 16/11/2026:

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
