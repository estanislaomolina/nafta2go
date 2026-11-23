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

La prueba de rollback real en AWS sigue pendiente: los tests con dependencias
falsas no la acreditan. [Alternativas y límites](../adr/ADR-025-imagen-verificada-por-digest.md).

## Publicación y lectura de la imagen

El job `Contenedores` construye una sola vez, ejecuta migraciones, consulta y smoke
sin APIs externas sobre esa imagen, y la conserva con `docker save`. Después de
aprobar todos los checks, `Publicar imagen verificada` carga ese mismo archivo y
lo publica con el tag del SHA completo. Sólo ocurre en push a `dev`/`main`; las PR
no publican ni reciben permiso de escritura sobre paquetes. El job comprueba que
el digest publicado resuelve al mismo ID de imagen probado, y exporta
`image-digest.txt` junto al resumen de Actions.

GHCR crea los paquetes privados por defecto. El titular debe configurar el paquete
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

La activación real y el acceso anónimo a GHCR quedan pendientes hasta publicar el
cambio; las pruebas locales no acreditan una publicación ni un despliegue en AWS.
[Decisión y alternativas](../adr/ADR-025-imagen-verificada-por-digest.md).

Fuentes: [compartir la imagen entre jobs](https://docs.docker.com/build/ci/github-actions/share-image-jobs/)
y [acceso y visibilidad en GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
