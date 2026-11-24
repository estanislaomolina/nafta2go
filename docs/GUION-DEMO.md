# Video y guion de referencia — Entrega 3

Video entregado: [Nafta2Go — TP Integrador I408 | Entrega 3: MVP](https://youtu.be/Y3cV71ZnxuY),
7 min 26 s. Sitio: https://estanislaomolina.github.io/nafta2go/.
Versión y reproducción: [ENTREGA-3](ENTREGA-3.md).

## Guion de preparación

Se propuso un recorrido de ocho minutos, dividido en 2:40 por integrante.
Los rangos siguientes son el plan de preparación, no capítulos comprobados
ni una transcripción del video final:

- Estanislao, 0:00–2:40: presentación, web pública, consulta con destino,
  prioridades de combustible neto/desvío/equilibrio, retorno al origen,
  validaciones, privacidad y ranking conservador provisional.
- Felipe, 2:40–5:20: selección temporal de referencias/modelos, campeón
  `bandera_reciente`, registro JSON versionado, compatibilidad de política
  auditada, adquisición Actions/OIDC → S3 → EC2 y pruebas de estrés aisladas.
- Santiago, 5:20–8:00: infraestructura AWS, dashboards de negocio/funcionamiento,
  seis checks CI, imagen por digest, despliegue OIDC, smoke/rollback y límites
  de presupuesto, disponibilidad y validación técnica.

## Evidencia y precisiones

Preparar sesiones antes de grabar, sin mostrar códigos, contraseñas, `.env`,
claves de ORS ni identificadores privados de cuenta. Mostrar las corridas
verificadas para explicar despliegue y recuperación; distinguirlas del uso en vivo.

- [Registro y campeón](ML.md): referencia estadística seleccionada en 2025;
  no elegir con validación 2026 ni afirmar precisión para errores reales.
- [Rankings y privacidad](WEB.md): no reemplazar el precio oficial, no duplicar
  estaciones por prioridades ni confirmar compras desde recomendaciones.
- [Operación AWS/Grafana](HOSTING.md) y [validación](VALIDACION.md): reportar
  alcance de cada medición, saturación y diferencias entre proveedor/red/API.
- [Recortes](ENTREGA-3.md#límites-conservados-al-entregar): no presentar emulación
  como teléfono físico, simulación como utilidad humana ni corte de cómputo
  como eliminación de todos los cargos.

El video se vincula desde el README. El tag anotado `entrega-3-mvp` identifica
el commit de `main` una vez completada la integración y verificación de entrega.
