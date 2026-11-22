# Encendido de una sola vez para la demo

La [plantilla](../infra/aws/demo-start-once.json) agrega un grupo de EventBridge
Scheduler, una programación `at` y un rol limitado a `ec2:StartInstances` sobre la
instancia indicada. No crea otra instancia ni modifica su red. El rol sólo puede
ser asumido desde ese grupo y cuenta; no concede permisos para detener o terminar.

La zona se fija como `America/Argentina/Buenos_Aires`, con ventana flexible OFF.
El horario corresponde al envío de StartInstances: el arranque y el readiness de
la aplicación requieren tiempo adicional. Es una sola ejecución, no diaria.
Los reintentos se limitan a dos y una antigüedad máxima de cinco minutos.

```bash
aws cloudformation deploy --profile nafta2go --region us-east-2 \
  --stack-name nafta2go-start-once-FECHA \
  --template-file infra/aws/demo-start-once.json --capabilities CAPABILITY_IAM \
  --parameter-overrides InstanceId="$INSTANCE_ID" StartAtLocal="AAAA-MM-DDT10:00:00" \
  --no-execute-changeset
```

Revisar las tres altas antes de ejecutar el change set. La fecha debe ser futura.
Comprobar después con GetSchedule la fecha, zona, estado y destino reales; guardar
evidencia redactada sin IDs. CloudFormation no expone ActionAfterCompletion: tras
la prueba, eliminar este stack para limpiar programación, grupo y rol. La expresión
`at` no vuelve a ejecutarse aunque se conserve el recurso. No cambiar el parámetro
fecha de un stack completado para probar sin revisar el nuevo arranque y su costo.

El host conserva su timer habilitado `OnBootSec=2h`. Docker usa `unless-stopped`.
El encendido no depende de una computadora local ni de una sesión SSO abierta;
para usar `localhost:8001` hay que volver a abrir el túnel de [AWS-DEMO](AWS-DEMO.md).
Apagar conserva el disco y sus cargos; iniciar otra vez suma consumo de cómputo/IP.

## Observación del 21/11 de Argentina

Se programó un único encendido para el **22/11/2026 a las 10:00 de Argentina**
(13:00 UTC). Stack `CREATE_COMPLETE`; GetSchedule confirmó ENABLED, expresión at,
zona argentina, ventana OFF y destino EC2 StartInstances. La instancia se observó
`stopped` después de la primera demo. Antes del apagado, SSM confirmó timer enabled,
OnBootUSec=2h y reinicio unless-stopped del contenedor. Eso verifica configuración;
no acredita todavía que la invocación futura haya ocurrido ni readiness posterior.

[Tipos de programación](https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html),
[prevención de confused deputy](https://docs.aws.amazon.com/scheduler/latest/UserGuide/cross-service-confused-deputy-prevention.html).
