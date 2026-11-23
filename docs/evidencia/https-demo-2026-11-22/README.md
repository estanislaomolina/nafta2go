# HTTPS real en EC2 y pruebas de acceso

El servicio Quick Tunnel se instaló por SSM con binario 2026.11.1 verificado por
SHA-256. La red se actualizó con un change set que sólo modificó el grupo de
seguridad sin reemplazo: veinte IPv4/32 TCP 7844 y ninguna regla de entrada.
`verificacion.json` conserva el smoke por HTTPS con tres candidatas, rechazo de
acceso anónimo/administrativo y timer de apagado activo. La URL es temporal.

El usuario reportó acceso y uso de ubicación escrita satisfactorios con iPhone 13
desde fuera de CABA. También reportó geolocalización correcta en una computadora
dentro de CABA. No se registraron coordenadas personales, iOS ni navegador; no se
atribuye a esta evidencia una obtención de GPS móvil dentro del área.

`energia-red.json` conserva el diagnóstico separado del catálogo: DNS coincide
con el /32 habilitado, pero TCP 80/443 y HTTP/HTTPS dieron timeout desde la EC2.
No demuestra la causa última ni acredita adquisición autónoma; corresponde a #160.

[Reproducción HTTPS](../../AWS-HTTPS.md).
