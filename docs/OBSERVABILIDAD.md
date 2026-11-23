# Dashboards de negocio y funcionamiento

Requiere Docker Compose en Linux y las métricas protegidas de [API](API.md).
El perfil es opcional. No acredita supervisión 24/7 ni carga de combustible real.

1. Exportar `NAFTA2GO_API_TOKEN` y `NAFTA2GO_ADMIN_TOKEN`, distintos y privados.
2. Preparar secrets; la contraseña de Grafana se pide sin eco, o puede llegar por
   `NAFTA2GO_GRAFANA_PASSWORD` (no guardarla en Git ni argumentos):

   ```bash
   python scripts/prepare_observability_secrets.py
   docker compose --profile mvp --profile observabilidad up --build -d api grafana
   ```

3. Entrar en `http://localhost:3000` con usuario `admin` y la contraseña preparada.
   Los dashboards están en la carpeta **Nafta2Go**. Prometheus queda en
   `http://localhost:9090`; ninguno publica un puerto hacia otras máquinas.
4. En Funcionamiento, elegir el proyecto Compose de esta instalación (por defecto
   `nafta2go`), para que CPU/memoria no se sumen con otros proyectos del host.
5. Para detener sólo observabilidad: `docker compose stop grafana prometheus cadvisor`.
   No borrar el volumen de datos de la API para apagar los dashboards.

El directorio de secrets tiene permisos 0700 en el host; los archivos 0444 se
montan únicamente en el servicio que los necesita, para admitir los UID internos
de las imágenes. Las rutas pueden cambiarse con `NAFTA2GO_METRICS_TOKEN_FILE` y
`NAFTA2GO_GRAFANA_PASSWORD_FILE`. Rotar la contraseña con el procedimiento de
Grafana si ya existe su volumen: el password de bootstrap sólo actúa al crearlo.

Los JSON de dashboards, datasource y alertas se provisionan desde
[deploy/observability](../deploy/observability/prometheus.yml). Cada dashboard
tiene ocho paneles. Las alertas mantienen estado en Grafana para ingesta ausente,
fallida o atrasada, p95 > 5 s y errores HTTP > 5 %, con cinco minutos de
persistencia. No se configura SMTP ni contactos externos. Sin muestras, una
alerta queda `NoData`; no se interpreta como éxito.

Negocio muestra recomendaciones y litros/gasto **estimados**, no consumo ni ventas.
No se suman prioridades duplicadas ni se infiere bandera elegida. Los totales
persistidos se leen como gauges, mientras consultas/latencia HTTP tienen scope
por proceso. Una consulta sin cobertura no tiene registro histórico por usuario.
Los paneles con datos ausentes no se completan con valores inventados.

Funcionamiento combina API, estado persistido de ingesta y **cAdvisor** para CPU
(en núcleos) y memoria working set (bytes) del contenedor API. cAdvisor necesita
acceso privilegiado de lectura a cgroups/metadatos del host; sólo se inicia al
activar el perfil, no publica puertos y se conservan únicamente las etiquetas
Compose de servicio/proyecto. Prometheus descarta el resto de servicios/métricas.
No confundir estos valores con memoria de Python ni métricas de EC2 completas.

Prometheus limita retención a siete días/256 MB. Grafana usa otro volumen propio.
Medir consumo conjunto antes de habilitarlo en la t3.small. La validación local y
las capturas no prueban funcionamiento ni capacidad de AWS.

[Decisión y alternativas](../adr/ADR-027-observabilidad-con-prometheus-y-grafana.md).

## Reproducir evidencia sin servicios externos

```bash
npm ci --prefix tests/browser --ignore-scripts
tests/browser/node_modules/.bin/playwright install chromium
PYTHONPATH=. python tests/integration/observability_smoke.py \
  --evidence /tmp/nafta2go-observabilidad-evidencia-nueva --screenshots
```

El directorio de salida debe ser nuevo. El harness crea un proyecto con nombre y
puertos propios, tokens temporales, base vacía y API con rutas grabadas. Ejecuta
ocho consultas, espera scrapes y valida las consultas de cada panel y las tres
reglas. En `finally` elimina sólo ese proyecto, sus volúmenes y red.
[Evidencia guardada](evidencia/grafana-local-2026-11-22/README.md).
