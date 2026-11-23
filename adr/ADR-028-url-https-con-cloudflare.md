---
status: Reemplazado por ADR-032
date: 2026-11-22
decision-makers: Equipo Nafta2Go
consulted: ADR-018, issue 155
informed: Cátedra
---

# URL HTTPS de demo mediante Cloudflare Tunnel

## Context and Problem Statement

Ya se probó una URL pública desde EC2 con Cloudflare. Falta repetirla desde un
procedimiento versionado, conservando SSM, autenticación de la API y apagado a las
dos horas, sin entrada pública al servidor.

## Considered Options

1. Quick Tunnel de Cloudflare para una URL temporal de demo.
2. Túnel administrado con dominio y credenciales persistentes.
3. Balanceador AWS con certificado.
4. Abrir 443 directamente en EC2 y administrar TLS.
5. ngrok.

## Decision Outcome

Se propone Quick Tunnel para esta etapa. No requiere cuenta, dominio ni token
persistente. La URL cambia en cada arranque y no ofrece garantía de disponibilidad.
Se fija cloudflared por versión/hash, se ejecuta como servicio sin privilegios y
se fuerza HTTP/2. La red permite únicamente TCP 7844 hacia los veinte IPv4/32
publicados de las dos regiones globales de Cloudflare; no se agrega entrada.
La condición de CloudFormation está desactivada por defecto y se habilita para
el host de demo. Revisar la lista si cambia la documentación del proveedor.

### Consequences and Confirmation

- El código de conductor sigue siendo necesario; operación conserva otro código.
- Quick no tiene token de túnel. El modo administrado sí requiere credenciales
  recuperadas de SecureString, sin valor en UserData, argumentos ni Run Command.
- Cloudflare Access o la autenticación por email de Quick son alternativas para
  la página; añadirlas cambia la prueba con clientes no interactivos. No se
  configura email ni se envían OTP desde esta implementación.
- HTTPS permite pedir geolocalización en el teléfono; permisos, señal y sistema
  pueden impedir obtener posición. La prueba física sigue siendo necesaria.
- Las reglas temporales existentes deben reconciliarse con la plantilla antes
  de activar CloudFormation, evitando reglas duplicadas. SSM usa 443 y no se corta.

## Pros and Cons of the Options

- **Quick:** gratuito y reproducible sin credenciales; URL cambiante y servicio
  para pruebas, con límites de concurrencia y sin garantía de uptime.
- **Administrado:** hostname estable y políticas Access; requiere dominio/cuenta
  y custodia/rotación de credenciales.
- **Balanceador:** TLS administrado e integración AWS; costos fijos y recursos
  extra para una instancia que vive sólo durante la demo.
- **443 en EC2:** control del endpoint; añade entrada pública y gestión de TLS,
  contrarios al acceso saliente elegido.
- **ngrok:** preparación rápida y controles de acceso; añade cuenta/dependencia
  y restricciones de su plan sin aprovechar la prueba Cloudflare ya realizada.

## More Information

[Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/),
[destinos y puertos](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/tunnel-with-firewall/).
