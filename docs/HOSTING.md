# Hosting continuo con presupuesto total

Decisión autorizada el 23/11: [ADR-032](../adr/ADR-032-pages-y-api-publica-con-presupuesto.md).
GitHub Pages sirve HTML/assets públicos. FastAPI, datos, ingesta y Grafana corren
en la instancia AWS existente. La web mantiene su publicación aunque se apague
la API; en ese caso informa que no pudo consultar, sin inventar recomendaciones.

`scripts/build_pages.py` fija `NAFTA2GO_PUBLIC_API_ORIGIN` del repositorio en la
publicación, con assets relativos al proyecto `/nafta2go/`. No admite una API
HTTP, rutas ni credenciales en esa configuración. `NAFTA2GO_WEB_ORIGIN` en el env
privado de AWS permite sólo el origen HTTPS de Pages; conserva Bearer y rechaza
preflight de terceros. El modo local sigue usando el mismo origen.

`infra/aws/public-api.json` agrega IP estable, entrada TCP/80 para ACME y
redirección, TCP/443 para API/Grafana y un guardia horario del presupuesto. No
habilita SSH, Prometheus ni cAdvisor públicos. `deploy/install-public-demo.sh`
instala Caddy y el perfil AWS de observabilidad sobre una release fijada.
Grafana usa usuario `admin` y contraseña SecureString
`/nafta2go/demo/grafana-admin`; no se publica en la web ni en Git.

El presupuesto `nafta2go-17-usd-total` es CUSTOM, acumulativo, con un período que
no reinicia al cambiar de mes. El sandbox bloquea Cost Explorer pero permite
Budgets. El guardia reserva USD 2 y estima el gasto no reportado a USD 0,05/h:
solicita apagado al alcanzar USD 15 o recibir información de más de 36 horas.
Marca la instancia para impedir que CD la reinicie automáticamente.

Apagar conserva datos y no elimina costos de EBS/IP/S3. No se promete un corte
exacto del proveedor a USD 17: la facturación tiene demora y la eliminación de
datos queda sujeta a la elección del titular. Deshabilitar el timer anterior de
dos horas requiere comprobar primero una invocación correcta del guardia.

La API se identifica por el digest probado y publicado en CI. La instalación de
ingesta y monitor sigue [INGESTA](INGESTA.md); los dashboards,
[OBSERVABILIDAD](OBSERVABILIDAD.md). Los agregados de negocio se cachean hasta
120 s para no recorrer toda la historia en cada scrape; los contadores HTTP
siguen siendo actuales. `business_snapshot_age_seconds` permite observar esa edad.


## Estado comprobado

[Operación del 23/11](evidencia/operacion-continua-2026-11-23/README.md):
Pages publicado, API y Grafana HTTPS accesibles, deploy OIDC y rollback reales
aprobados, guardia invocada y apagado a dos horas deshabilitado.
El [presupuesto observado](evidencia/operacion-continua-2026-11-23/budget.json)
es un control de gasto autorizado, no un saldo educativo auditado. El monto de
USD 17 fue informado por el titular; SCP impide verificar independientemente
créditos y vencimiento. La reserva y la detención de cómputo no eliminan costos
residuales de almacenamiento y dirección pública.
