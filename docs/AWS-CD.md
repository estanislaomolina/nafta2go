# Identidad y aprobación para CD de demo

El rol de [demo-cd.json](../infra/aws/demo-cd.json) sólo permite encender la EC2
indicada, enviar AWS-RunShellScript a esa instancia y consultar el estado.
El runner no recibe permiso de lectura de SecureString/KMS; lo mantiene el rol
del host. No se guardan access keys en GitHub.

Preparar el environment (administrador del repositorio):

```bash
python scripts/configure_demo_environment.py
```

La configuración versionada exige aprobación de Felipe, prohíbe autoaprobación y
bypass y admite sólo main o tags entrega-*. La confianza del rol no puede imponer
esas ramas mediante el subject: al usar environment, debe nombrar demo. GitHub
confirmó IDs inmutables; se usa
`repo:estanislaomolina@129418393/nafta2go@1375908771:environment:demo` con audiencia
`sts.amazonaws.com`. No reemplazarlo por un subject de rama ni por un wildcard.

Crear la plantilla revisada (sin cómputo adicional):

```bash
aws cloudformation deploy --profile nafta2go --region us-east-2 \
  --template-file infra/aws/demo-cd.json --stack-name nafta2go-demo-cd \
  --parameter-overrides InstanceId="$INSTANCE_ID" --capabilities CAPABILITY_IAM
```

Si ya existe un proveedor OIDC de GitHub en la cuenta, adaptar y revisar la
plantilla para reutilizarlo antes de crear uno duplicado. Guardar las referencias
como variables del environment: RoleArn → DEMO_ROLE_ARN, ID de instancia →
DEMO_INSTANCE_ID y nombre de SecureString → DEMO_RUNTIME_PARAMETER. Nunca su valor.

[Preparación](evidencia/oidc-demo-2026-11-22/README.md) y
[despliegue OIDC real exitoso](https://github.com/estanislaomolina/nafta2go/actions/runs/45290583089),
23/11/2026. El deploy por digest y el smoke terminaron correctamente.
La aprobación excepcional fue de Estanislao, con autorización explícita; después
se restauró Felipe como revisor y el bloqueo de autoaprobación.
[Alternativas](../adr/ADR-026-despliegue-con-oidc.md).
