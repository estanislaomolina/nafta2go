---
status: Aceptado
date: 2026-11-22
decision-makers: Equipo Nafta2Go
consulted: ADR-025, issues 156 y 157
informed: Cátedra
---

# Despliegue de demo con OIDC y aprobación independiente

## Context and Problem Statement

La imagen verificada por digest debe llegar a la instancia sin una sesión SSO
personal ni claves AWS persistentes en GitHub. El despliegue necesita una
aprobación humana distinta de quien lo dispara.

## Considered Options

1. OIDC de GitHub con rol limitado y environment demo protegido.
2. Access keys de una identidad técnica guardadas como secrets de GitHub.
3. Continuar enviando cada despliegue manualmente con SSO/SSM.

## Decision Outcome

Se propone OIDC. El rol confía únicamente en audiencia sts.amazonaws.com y el
subject efectivo de este repositorio para el environment demo. Se verificó que
el repositorio usa IDs inmutables: owner 129418393 y repo 1375908771. Las reglas
del environment restringen main y tags entrega-*, requieren revisión de Felipe,
impiden autoaprobación y bypass administrativo. La confianza y las reglas se
necesitan juntas; un subject de rama no coincide con un job que usa environment.

La publicación espera todos los checks. El job demo recibe el digest de esa
misma corrida, se autentica tras la aprobación, enciende sólo la instancia
indicada y espera el resultado SSM, que incluye smoke y recuperación. No se
cancela un despliegue activo por un push nuevo. No se despliega desde dev.

### Consequences and Confirmation

- No hay access keys ni permiso del runner para leer el env privado; lo obtiene
  el rol de instancia. SendCommand queda limitado al documento y a esa EC2.
- GetCommandInvocation y acciones Describe requieren Resource '*'; no otorgan
  permiso de mutación sobre otras instancias. StartInstances usa un ARN exacto.
- La plantilla crea un proveedor OIDC de GitHub. Si ya existe en la cuenta, hay
  que reutilizarlo mediante una adaptación revisada, no crear un duplicado.
- Configurar DEMO_ROLE_ARN, DEMO_INSTANCE_ID y DEMO_RUNTIME_PARAMETER como
  variables del environment. El procedimiento sigue usando SecureString.
- Una plantilla válida no acredita una asunción OIDC ni un despliegue real:
  registrar la corrida aprobada después de integrar las dependencias.
- La revisión del environment no sustituye la revisión de código de la PR.

## Pros and Cons of the Options

- **OIDC:** credenciales temporales, confianza exacta y sin rotación de access keys;
  exige coordinar el subject, las protecciones y el rol de AWS.
- **Access keys:** integración directa con SDK/CLI; requiere custodia y rotación
  de un secreto duradero y aumenta el impacto de una filtración.
- **SSO manual:** ya funciona y conserva control humano; depende de la sesión
  personal y no automatiza el CD ni la espera del resultado.

## More Information

[Entrega](../docs/ENTREGA-AWS.md),
[OIDC en AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws),
[permisos SSM](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ssm.html).
