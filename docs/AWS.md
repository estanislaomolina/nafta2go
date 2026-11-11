# AWS: preparación del sandbox y base de red

## Estado verificado por el titular

El 11/11/2026 el titular reportó un lease activo de **USD 17 totales**, con
2976 horas de duración, acceso SSO y una sesión válida mediante
`aws sts get-caller-identity`. Las consultas no devolvieron instancias ni VPCs en
Ohio, ni VPCs en Virginia del Norte. `CreateVpc --dry-run` devolvió
`DryRunOperation`: confirma permiso para esa operación, sin crear la VPC.
No confirma permisos de CloudFormation, subredes, rutas, EC2, IAM ni facturación.
No se guardan identificadores de cuenta, sesiones ni credenciales en el repo.

## Alcance de este incremento

[Plantilla CloudFormation](../infra/aws/network.json), propuesta en
[ADR-011](../adr/ADR-011-base-de-red-con-cloudformation.md): VPC `10.20.0.0/24`,
subred `10.20.0.0/26`, internet gateway, tabla/ruta y security group sin entrada,
con salida TCP 443. Región operativa prevista: Ohio (`us-east-2`).
La subred no asigna IPv4 pública automáticamente; la ruta no proporciona por sí
sola internet a una futura instancia. Tampoco abre SSH ni publica la API.
No incluye servidor, discos, direcciones públicas, NAT, balanceador ni secretos.
Los recursos etiquetables identifican proyecto, stack y gestión por CloudFormation.

La plantilla todavía **no fue validada por AWS ni desplegada**. Las pruebas
locales revisan JSON e invariantes de exposición, CIDR, topología y recursos
permitidos; no sustituyen la validación del servicio ni el despliegue real.
La API local se prepara en #67 y #68; esta base no depende de integrarlas.

## Validar desde CloudShell sin crear recursos

Desde un checkout de esta rama en CloudShell, ubicado en la raíz del repo:

```bash
aws cloudformation validate-template --region us-east-2 \
  --template-body file://infra/aws/network.json
```

Guardar la salida redactada como evidencia cuando se ejecute. Si devuelve
`AccessDenied`, solicitar el permiso indicado al administrador; la consola del
sandbox y la del servicio pueden tener permisos distintos. Validar la plantilla
no comprueba autorización ni cuotas para desplegar todos sus recursos.

## Crear y comprobar la red después de revisar la PR

Estos comandos **sí crean recursos**. Se documentan para una ejecución posterior;
no se ejecutaron durante la preparación. Revisar cuenta y región en CloudShell:

```bash
aws sts get-caller-identity
aws cloudformation deploy --region us-east-2 \
  --stack-name nafta2go-network \
  --template-file infra/aws/network.json
aws cloudformation describe-stacks --region us-east-2 \
  --stack-name nafta2go-network --query 'Stacks[0].Outputs'
```

No modificar a mano los recursos del stack. Si hay fallos, revisar los eventos de
CloudFormation y sus permisos antes de reintentar; no deshabilitar el rollback.
Los CIDR fijos deben revisarse antes de conectar esta red a otra.

## Eliminar la base de red

Para una red de prueba sin cargas conectadas:

```bash
aws cloudformation delete-stack --region us-east-2 --stack-name nafta2go-network
aws cloudformation wait stack-delete-complete --region us-east-2 \
  --stack-name nafta2go-network
```

Eliminar el stack borra sus recursos. Antes de añadir cómputo o almacenamiento
hay que definir backup/restauración, orden de eliminación y retención de datos;
no conectar recursos manuales que impidan borrar esta red.

## Presupuesto y trabajo pendiente (#59 y #22)

AWS publica USD 0,005 por hora de IPv4 pública: 2976 horas equivalen a **USD 14,88
solo de dirección**, sin servidor, discos, transferencia ni otros servicios.
[Tarifa oficial](https://aws.amazon.com/vpc/pricing/), consultada el 11/11/2026.
No se presupone Free Tier. Esto justifica planificar sesiones acotadas de prueba.
Apagar EC2 no elimina todos los costos: EBS continúa facturando mientras exista;
ver [ciclo de vida](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html).

Falta comparar cómputo y persistencia, presupuestar horas activas y almacenamiento,
verificar restricciones del sandbox y alertas, accesos del equipo, permisos de
provisión, backups, secretos, HTTPS, ingesta, observabilidad y CI/CD. El lease no
prueba que todos los servicios estén habilitados ni que haya créditos adicionales.
La elección del servidor y el costo completo se revisan antes de provisionarlo.

[Validación de plantillas](https://docs.aws.amazon.com/cli/latest/reference/cloudformation/validate-template.html).
