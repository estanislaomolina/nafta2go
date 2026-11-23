# Preparación real del CD

`estado.json` contiene lecturas de las APIs de GitHub y CloudFormation del 22/11.
El environment requiere aprobación de Felipe y no permite autoaprobación ni bypass.
La plantilla creó proveedor OIDC y rol para una sola instancia; las variables de
environment contienen referencias, nunca el env privado.

Esto acredita preparación, no asunción OIDC ni despliegue: falta integrar las
dependencias y ejecutar una corrida aprobada por otro integrante.
