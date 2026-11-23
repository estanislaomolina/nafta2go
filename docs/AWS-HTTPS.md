# URL HTTPS reproducible de demo

Ya hubo una prueba temporal de Cloudflare desde EC2. Este procedimiento la
versiona como servicio; no implica disponibilidad permanente ni cambia el apagado
a las dos horas. Mantener separados los códigos de conductor y administrador.

## Red e instalación

La plantilla [demo-server.json](../infra/aws/demo-server.json) añade la condición
`EnableCloudflareTunnel=true`, desactivada por defecto: sólo TCP 7844 a los veinte
IPv4/32 globales publicados por Cloudflare. Se fuerza HTTP/2 e IPv4. No agrega
entrada, balanceador, dominio ni NAT. Revisar la lista si cambia el proveedor.

Crear un change set de la plantilla preservando VPC, subred, AMI y EnergyHttpCidr
existentes; debe mostrar sólo modificación de DemoSecurityGroup sin reemplazo.
Si quedan reglas de la prueba manual, exportarlas y reconciliarlas antes de
aplicar el change set para evitar duplicados; no quitar 443 ni la excepción de
Energía. Verificar después veinte destinos 7844 y cero reglas de entrada.

Con la EC2 existente encendida y SSM Online:

```bash
python scripts/aws_demo_tunnel.py --profile nafta2go \
  --instance-id "$INSTANCE_ID" --mode quick
```

El comando devuelve un ID de SSM. Consultar su estado antes de reintentar. El
instalador fija cloudflared 2026.11.1 y verifica SHA-256 del binario publicado;
instala un servicio con DynamicUser, sin privilegios, y desactiva autoupdate.
La URL `https://...trycloudflare.com` se consulta en el journal del servicio
`nafta2go-tunnel.service` filtrando únicamente esa URL. Cambia al reiniciar el túnel.
Parar/reanudar con `systemctl stop/start nafta2go-tunnel.service`; no afecta la API
por SSM. Al apagar la instancia la URL deja de responder.

Quick no necesita cuenta, dominio ni token persistente. El modo administrado es
opcional, requiere cuenta/dominio y un SecureString autorizado para el rol del host:

```bash
python scripts/aws_demo_tunnel.py --profile nafta2go \
  --instance-id "$INSTANCE_ID" --mode managed --parameter /nafta2go/demo/cloudflare
```

Sólo se envía el nombre del parámetro. El host obtiene el token, lo guarda 0600 y
systemd lo entrega como credencial al servicio; no viaja en UserData, argumentos
ni Run Command. Cloudflare Access puede proteger el hostname administrado. La
versión actual de Quick ofrece también `--allowed-mail`, pero requiere navegador
interactivo y cambia las pruebas de API; no se habilita por defecto ni se envían OTP.

## Verificación

Comprobar por la URL pública: `/health`, `/ready`, `/` y `/operacion` 200; consulta
sin código 401; código de conductor en operación 401; consulta autenticada con
evaluaciones. Usar coordenadas sintéticas de CABA y un máximo acotado de candidatas
para no consumir cupo innecesariamente. No publicar el código en la URL ni en logs.

En un **teléfono físico**, registrar modelo/SO/navegador y probar geolocalización y
búsqueda. HTTPS habilita contexto seguro, pero permisos denegados, señal o sistema
pueden impedir obtener posición; la UI debe conservar búsqueda/manual como salida.
La automatización de escritorio no acredita esta prueba física.

[Alternativas y límites](../adr/ADR-028-url-https-con-cloudflare.md).

[Evidencia real y pruebas reportadas](evidencia/https-demo-2026-11-22/README.md).
