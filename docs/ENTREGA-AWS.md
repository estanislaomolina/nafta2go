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
  --parameter /nafta2go/demo/runtime
```

El SHA debe ser completo. El comando devuelve un ID de SSM: consultar su estado
antes de repetir. La release se obtiene por SHA y se construye en el host; las
dependencias con rangos impiden garantizar bytes idénticos entre construcciones.
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
