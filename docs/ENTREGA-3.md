# Entrega 3 — MVP

Fecha de cierre documental: 24/11/2026. Integrantes: Estanislao Molina Abeniacar,
Felipe Sidiropulos y Santiago Bunge.

## Acceso al producto y video

- **Sitio web:** https://estanislaomolina.github.io/nafta2go/
- **Video:** [Nafta2Go — Entrega 3: MVP](https://youtu.be/Y3cV71ZnxuY), 7 min 26 s.
- **Operación:** https://estanislaomolina.github.io/nafta2go/operacion/
- **API:** https://nafta2go.18.216.94.147.sslip.io/
- **Grafana:** https://nafta2go.18.216.94.147.sslip.io/grafana/

Los códigos de conductor/administración son distintos. Grafana usa el usuario
`admin`; el equipo obtiene su contraseña del SecureString
`/nafta2go/demo/grafana-admin` en `us-east-2`. No se publican sus valores.

## Versión y reproducción

La entrega se identifica con el tag anotado
[entrega-3-mvp](https://github.com/estanislaomolina/nafta2go/tree/entrega-3-mvp),
creado sobre el commit de `main` integrado desde `dev` por PR y verificado en CI.
Para resolver el commit exacto después de obtener los tags:

```bash
git fetch origin --tags
git rev-parse 'entrega-3-mvp^{commit}'
git show --no-patch entrega-3-mvp
```

El [README](../README.md#desarrollo-local) documenta Python 3.12, dependencias,
migraciones y pytest; [Docker](../README.md#levantar-con-docker) permite repetir
el flujo sin depender de la instancia viva. Las pruebas usan fixtures y rutas
controladas. La [consigna](../res/%5BSHR%5D%5BS2%5D%20-%20Consigna%20TP%20I408.pdf)
requiere video de 5 a 12 minutos; la duración publicada del video entregado es 446 s.
Se comprobó disponibilidad y [metadatos del enlace](evidencia/entrega-3-video-2026-11-24.json); esto no es una revisión
independiente de todo el contenido audiovisual ni una defensa oral del equipo.

## Alcance y evidencia

El MVP incorpora web y API autenticadas, validaciones, hasta veinte candidatas
por API, rankings general y conservador, diagnóstico de precios y estimaciones
antiguas rotuladas. Incluye registro versionado de corridas con alias `champion`,
política auditada, ingesta automática trazable, métricas y dashboards.

La [validación integral](VALIDACION.md) y la
[evidencia operativa](evidencia/operacion-continua-2026-11-23/README.md) reúnen
pruebas en AWS, carga aislada, proveedor real, auditoría de persistencia,
publicación por digest, OIDC, smoke y rollback real. Las
[decisiones](../adr/README.md), [PRD](PRD.md), [SRD](SRD.md) y
[Roadmap](ROADMAP.md) conservan el alcance y sus recortes.

## Límites conservados al entregar

- Los litros y gastos son estimaciones de recomendaciones, no compras observadas.
- El campeón es una referencia estadística; no hay precisión medida para detectar
  errores reales de precios. Una alerta provisional no certifica precios.
- SQLite y caché por proceso; el histórico se satura bajo concurrencia. No se
  afirma p95 menor de cinco segundos con veinte usuarios simultáneos.
- La validación humana fue reemplazada por escenarios técnicos en ADR-023.
  La prueba física informada por el titular no acredita todos los navegadores,
  lector de pantalla ni una evaluación completa de accesibilidad.
- La adquisición usa un runner dedicado que requiere equipo encendido y red;
  usa OIDC y no una sesión SSO personal. La API/Grafana funcionan en EC2.
- El presupuesto autorizado es USD 17, con guardia de corte conservador de
  cómputo y reserva. Discos/IP/S3 pueden seguir facturando tras detener EC2;
  no hay límite duro garantizado ni saldo educativo auditado. Ver [HOSTING](HOSTING.md).
- El código puede revertirse por digest; una migración o los datos no se revierten
  automáticamente con la imagen.

El sitio estático puede seguir publicado cuando la API se detenga por presupuesto.
