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

Opcionalmente, `--capture-file /app/data/imports/<sha256>.csv` importa una captura
ya transferida y verificada. El archivo no se transfiere mediante este ejecutable.
Sin esa opción se intenta descargar del catálogo. Ambas modalidades usan el mismo
normalizador y registran la ingesta; una importación no acredita adquisición remota.

La API se liga a loopback. `/ready` sólo valida configuración/esquema: verificar
además autenticación y una consulta completa por el túnel de AWS-DEMO. El script
no cambia timers ni el apagado de dos horas. Los respaldos locales del host deben
exportarse antes de eliminarlo. [Alternativas y límites](../adr/ADR-024-entrega-por-ssm-y-configuracion-cifrada.md).

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

La primera publicación corrió en `dev` el 23/11 (commit `683fe05`, digest
`sha256:6bf993df84ff3e18d851ebe0e94b9aec034f947ac835670939a54fdd90d4ee0f`). El
paquete sigue privado: pedir ese manifiesto sin sesión devuelve 404. Falta que el
titular lo haga público y repetir la comprobación. Una publicación no acredita un
despliegue en AWS.
[Decisión y alternativas](../adr/ADR-025-imagen-verificada-por-digest.md).

Fuentes: [compartir la imagen entre jobs](https://docs.docker.com/build/ci/github-actions/share-image-jobs/)
y [acceso y visibilidad en GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
