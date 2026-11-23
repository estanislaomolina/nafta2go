# Evidencia reportada: red AWS del sandbox

Fecha: 11/11/2026. Fuente: salidas de CloudShell compartidas por el titular en
la sesión de trabajo. El asistente no ejecutó estos comandos contra AWS ni
consultó la cuenta directamente. Se omiten identificadores de cuenta, sesión,
change set y recursos; no se incluyen credenciales.

Plantilla: [network.json](../../../infra/aws/network.json), commit `945d6ca`.
Región `us-east-2`, stack `nafta2go-network`.

1. `validate-template`: devolvió `Parameters: []` y la descripción de la plantilla.
2. `deploy --no-execute-changeset`: informó creación exitosa del change set.
3. `describe-change-set`: mostró ocho acciones `Add`, para `Vpc`, `Subnet`,
   `InternetGateway`, `GatewayAttachment`, `RouteTable`, `InternetRoute`,
   `SubnetRoute` y `ApplicationSecurityGroup`. Coinciden con los tipos y recursos
   lógicos de la plantilla; no incluye cómputo ni almacenamiento de aplicación.
4. `execute-change-set`: terminó sin mensaje de error.
5. `wait stack-create-complete`: terminó sin mensaje de error.
6. `describe-stacks`: devolvió `Estado: CREATE_COMPLETE`, con las claves de
   outputs `VpcId`, `SecurityGroupId` y `SubnetId`.

Esta evidencia confirma la creación de la base de red reportada. No demuestra
funcionamiento de API, servidor, persistencia, ingesta ni CI/CD en AWS. No se
probó la eliminación del stack, ni se verificó facturación o permisos de otros
servicios. El titular eligió usar la futura aplicación solo en pruebas y demo;
el plan de cómputo y sus costos siguen pendientes en #59.
