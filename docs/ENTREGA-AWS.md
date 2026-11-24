# Entrega de una release de demo por SSM

Requiere el host de [AWS-DEMO](AWS-DEMO.md), SSM Online y Docker activo.
El titular debe aprobar infraestructura y costos antes de crear el servidor.
Configurar un parámetro Standard SecureString bajo `/nafta2go/demo/` con
`DATABASE_URL=sqlite:////app/data/nafta2go.db`, `ORS_API_KEY` y tokens distintos
`NAFTA2GO_API_TOKEN` / `NAFTA2GO_ADMIN_TOKEN`. No poner valores en Git ni Run Command.

Desde un checkout revisado, con AWS CLI y sesión SSO válidos:

```bash
python scripts/aws_demo_command.py --profile nafta2go \
  --instance-id "$INSTANCE_ID" --commit "$REVIEWED_COMMIT" \
  --parameter /nafta2go/demo/runtime --image "$IMAGE_DIGEST"
```

El SHA debe ser completo y `IMAGE_DIGEST` debe ser la referencia
`ghcr.io/estanislaomolina/nafta2go@sha256:<64 caracteres hexadecimales>` del artefacto
`referencia-imagen` de una corrida CI exitosa para ese commit. No usar el tag como
entrada del despliegue. El comando devuelve un ID de SSM: consultar su estado
antes de repetir. El host descarga esa imagen y comprueba su etiqueta de revisión;
no descarga fuentes ni construye otra imagen.
Se conserva la imagen concreta, los datos fuera del contenedor y un respaldo
SQLite previo. El rollback recupera código con configuración actual, sin revertir
migraciones/datos; revisar compatibilidad del esquema antes de otra migración.

El despliegue no descarga ni importa capturas. La ingesta y el monitor se operan
por separado; un fallo de adquisición no obliga a reconstruir ni reinstalar.
`/ready` comprueba configuración, esquema y datos utilizables, y publica
`data_status=current`, `historical_scenario` o `unavailable`. El escenario histórico
está rotulado como tal y no acredita datos vigentes. Sin datos utilizables responde
503 y el despliegue no supera el smoke.

La API se liga a loopback. El smoke espera readiness y verifica `/health`, web,
`/operacion`, rechazo sin código, rechazo del código de conductor en operación y
una consulta autenticada con evaluaciones persistidas. En AWS usa una sola matriz
ORS de hasta diez candidatas; necesita cuota/servicio disponibles. En CI/pruebas
el mismo smoke se ejecuta con rutas grabadas, sin terceros. Sus consultas sintéticas
se persisten como las demás recomendaciones; no representan compras reales.

Si falla arranque/smoke, se intenta recuperar el digest anterior con configuración
actual: código de salida 4 si se recupera, 6 si también falla la recuperación.
La salida informa candidata/restaurada y etapa fallida sin exponer tokens. El
script usa un lock para impedir despliegues simultáneos y conserva la referencia
actual si falla la candidata. El smoke se transfiere por SSM y también comprueba
imágenes anteriores que no lo incluían. Los respaldos deben exportarse antes de
eliminar la instancia; el script no modifica el apagado de dos horas.

Rollback manual a una release instalada (digest conservado en
`/opt/nafta2go/releases/<sha>.image`):

```bash
python scripts/aws_demo_command.py --profile nafta2go \
  --instance-id "$INSTANCE_ID" --commit "$PREVIOUS_COMMIT" \
  --parameter /nafta2go/demo/runtime --image "$PREVIOUS_DIGEST" --mode rollback
```

Se verifica que SHA y digest correspondan a una release instalada. Este modo no
aplica migraciones ni ingesta. No restaura la base: antes de desplegar una
migración hay que revisar compatibilidad con la versión anterior y planificar
recuperación de datos. Un respaldo no sustituye esa revisión.

La prueba real de rollback y restauración en AWS terminó con ambos smoke tests
aprobados el 23/11: [evidencia](evidencia/operacion-continua-2026-11-23/rollback.json).
Los tests con dependencias falsas cubren además la recuperación automática fallida. [Alternativas y límites](../adr/ADR-025-imagen-verificada-por-digest.md).

## Publicación y lectura de la imagen

El job `Contenedores` construye una sola vez, ejecuta migraciones, consulta y smoke
sin APIs externas sobre esa imagen, y la conserva con `docker save`. Después de
aprobar todos los checks, `Publicar imagen verificada` carga ese mismo archivo y
lo publica con el tag del SHA completo. Sólo ocurre en push a `dev`/`main`; las PR
no publican ni reciben permiso de escritura sobre paquetes. El job comprueba que
el digest publicado resuelve al mismo ID de imagen probado, y exporta
`image-digest.txt` junto al resumen de Actions.

El paquete actual es público y se comprobó la descarga anónima por digest. En
una cuenta nueva, GHCR puede crear paquetes privados; el titular debe configurar el paquete
`nafta2go` como **público** tras la primera publicación y comprobar desde un cliente
sin sesión que `docker pull "$IMAGE_DIGEST"` funciona. El host no recibe un token
GitHub; un fallo de lectura conserva la API anterior. La publicación usa sólo
`GITHUB_TOKEN` con `packages: write` dentro del job, sin PAT persistente.

`current-image` y `releases/<sha>.image` conservan referencias por digest para
recuperar versiones instaladas. No eliminar esos digests del registro mientras
sean necesarios para recuperación. Una reconstrucción posterior del mismo commit
puede resolver otras dependencias: conservar el digest de la corrida elegida.
Los fixtures históricos recortados y la matriz de rutas forman parte de la prueba;
las capturas operativas, SQLite, modelos privados y secretos quedan fuera de la
imagen por las copias explícitas del Dockerfile.

La primera publicación corrió en `dev` el 23/11 (commit `683fe05`, digest
`sha256:6bf993df84ff3e18d851ebe0e94b9aec034f947ac835670939a54fdd90d4ee0f`). El
paquete es público: el 23/11, pedir ese manifiesto con un token anónimo de GHCR
devolvió 200. Una publicación no acredita un despliegue en AWS.
[Decisión y alternativas](../adr/ADR-025-imagen-verificada-por-digest.md).

Fuentes: [compartir la imagen entre jobs](https://docs.docker.com/build/ci/github-actions/share-image-jobs/)
y [acceso y visibilidad en GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

## Despliegue continuo y protecciones

`CI` publica tras todos los checks en push a dev/main o tags `entrega-*`. Sólo
main y esos tags pueden iniciar el job de despliegue. El job espera la aprobación
del environment `demo`, recibe el digest de esa corrida, asume el rol OIDC,
enciende la EC2, espera SSM y ejecuta el procedimiento. Un fallo de smoke, aun con
recuperación exitosa, hace fallar el workflow. Un push nuevo no cancela un
despliegue activo. No se despliega automáticamente desde dev.

La API de GitHub confirmó `use_immutable_subject=true` para este repositorio;
el subject es
`repo:estanislaomolina@129418393/nafta2go@1375908771:environment:demo`.
Se usa en [la plantilla del rol](../infra/aws/demo-cd.json) con audiencia
`sts.amazonaws.com`. Al usar environment no sirve el subject de rama. Las reglas
de `demo` restringen las ramas/tags y requieren aprobación de Felipe, con
`prevent_self_review=true` y `can_admins_bypass=false`.

Aplicación reproducible de las protecciones (requiere administración del repo):

```bash
python scripts/configure_demo_environment.py
```

Crear la infraestructura revisada una sola vez (sin cómputo adicional):

```bash
aws cloudformation deploy --profile nafta2go --region us-east-2 \
  --template-file infra/aws/demo-cd.json --stack-name nafta2go-demo-cd \
  --parameter-overrides InstanceId="$INSTANCE_ID" --capabilities CAPABILITY_IAM
```

Guardar en las variables del environment `demo` el output `RoleArn` como
`DEMO_ROLE_ARN`, la instancia como `DEMO_INSTANCE_ID` y el nombre de SecureString
como `DEMO_RUNTIME_PARAMETER`. No guardar su contenido ni access keys.
El runner no necesita acceso a Parameter Store/KMS: lo mantiene el rol de EC2.
Si la cuenta ya tiene un proveedor OIDC de GitHub, adaptar y revisar la plantilla
para reutilizarlo antes de crear otro. La activación se acredita con una corrida
real aprobada del workflow; la validación de plantillas no la sustituye.
[Alternativas](../adr/ADR-026-despliegue-con-oidc.md).
