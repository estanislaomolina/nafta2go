---
status: Aceptado
date: 2026-11-23
decision-makers: Estanislao Molina Abeniacar
consulted: ADR-018, ADR-028, ADR-031
informed: Equipo Nafta2Go
---

# Web estática en Pages y API pública con presupuesto total

## Context and Problem Statement

El titular pidió reemplazar Cloudflare por GitHub Pages y conservar API y Grafana
encendidos hasta agotar el presupuesto total de USD 17 o indicar su apagado.
Esto reemplaza el modo de demo de dos horas; Pages sólo aloja HTML y assets.

## Considered Options

* Pages para la web, IP estable en EC2 y HTTPS con Caddy y dirección gratuita.
* Cloudflare Quick Tunnel (ADR-028).
* Dominio propio y balanceador de AWS.
* Pages como único alojamiento.

## Decision Outcome

Se elige la primera opción. La web se construye sin secretos para Pages; su API
HTTPS se fija al publicar. La API admite únicamente el origen Pages configurado,
con autenticación Bearer y sin cookies entre orígenes. Caddy publica API y Grafana
por HTTPS; Prometheus, cAdvisor y la API directa siguen en loopback.

La IP estable permite una dirección `nafta2go.<ip>.sslip.io`. Caddy obtiene y
renueva certificados. Los datos, tokens y contraseñas quedan fuera de Pages/Git.
Grafana mantiene login propio y provisioning versionado, sin acceso anónimo.

### Consequences and Confirmation

El permiso de operación continua es explícito del titular. Antes de deshabilitar
el timer de dos horas se comprueba el guardia horario: usa un presupuesto CUSTOM
de USD 17 sin reinicio mensual, gasto bruto sin descontar créditos, margen para
demora contable y corte conservador a USD 15. Si la información supera 36 horas
se solicita apagado. El rol de CD no puede reiniciar una instancia marcada por
agotamiento. El guardia no borra datos: EBS/IP/almacenamiento retenidos pueden
seguir facturando, por lo que el margen no constituye un límite absoluto del
proveedor. La política de eliminación final requiere la elección del titular.

La validación incluye CORS, build de Pages, acceso autenticado, dashboards,
certificado público, timer/guardia e ingesta. Las capturas antiguas de Cloudflare
se conservan como evidencia histórica, sin atribuirles la nueva disponibilidad.

## Pros and Cons of the Options

### Pages, IP estable en EC2 y HTTPS con Caddy

* Bueno, porque conserva la aplicación completa y no requiere comprar un dominio.
* Bueno, porque la dirección `sslip.io` de la IP estable permite certificados gratuitos.
* Malo, porque abre la entrada 80/443 y exige CORS acotado y control de gastos.
* Malo, porque el DNS gratuito no ofrece SLA.

### Cloudflare Quick Tunnel

* Bueno, porque mantiene cerrada la entrada de la instancia.
* Malo, porque la URL cambia en cada arranque.
* Malo, porque no cumple la nueva elección del titular.

### Dominio propio y balanceador de AWS

* Bueno, porque da una dirección administrada.
* Malo, porque agrega costos y servicios injustificados para este presupuesto.

### Pages como único alojamiento

* Bueno, porque es gratuito para la web pública.
* Malo, porque no ejecuta FastAPI, la ingesta, SQLite ni Grafana.
