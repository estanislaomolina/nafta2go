---
status: Reemplazado por ADR-025
date: 2026-11-21
decision-makers: Equipo Nafta2Go
consulted: ADR-018, ADR-019, issues 22 y 59
informed: Cátedra
---

# Entrega de demo por SSM y configuración cifrada

Reemplazado por [ADR-025](ADR-025-imagen-verificada-por-digest.md). Se conserva el
registro de la entrega original; SSM y SecureString continúan en el procedimiento.

## Context and Problem Statement

El host temporal de ADR-018 no tiene puertos de entrada. Debemos entregar una
release y su configuración sin incluir secretos en Git, UserData o Run Command,
conservando el presupuesto total de USD 17 y evidencia verificable.

## Considered Options

1. SSM Run Command para el procedimiento, repositorio público por SHA completo,
   construcción local y Parameter Store SecureString para el env privado.
2. Publicar imagen en un registro y artefactos en almacenamiento de objetos.
3. Enviar el env directamente como argumento de Run Command o abrir SSH.

## Decision Outcome

Se propone la opción 1 para esta demo: usa el acceso SSO/SSM ya previsto y evita
agregar registro, bucket o entrada de red. Run Command sólo recibe el nombre del
parámetro; el host recupera su valor cifrado y lo guarda con permisos 0600. Tokens
distintos de conductor/administrador y la clave ORS quedan fuera de Git y logs.
Se registra el commit y el ID de imagen construido. La construcción con rangos de
dependencias no garantiza bytes idénticos; el ID concreto es parte de la evidencia.

### Consequences and Confirmation

- SSM y su rol son prerrequisitos; probar permisos reales, no inferirlos del dry-run.
- Datos/originales quedan fuera de la imagen. Antes de migrar una base existente,
  se respalda con SQLite y se comprueba integridad.
- El rollback recupera código con configuración actual; no revierte esquema/datos.
- La primera activación comprueba readiness y una consulta autenticada aparte.
- Tests ejecutan fallos de build/readiness con dependencias falsas; no acreditan
  una restauración real en AWS. Hay que exportar respaldo fuera del host.

## Pros and Cons of the Options

- **SSM y SecureString:** aprovecha el canal existente y separa secretos del comando;
  depende de permisos SSM/KMS, descarga del repositorio y construcción en un host chico.
- **Registro y objetos:** permite promover artefactos ya construidos y facilita
  distribución; agrega IAM, almacenamiento y un ciclo de limpieza para esta demo.
- **Env en comando o SSH:** reduce preparación inicial; expone valores en historial
  o añade entrada de red, contrario al diseño de acceso elegido.

## More Information

[Procedimiento](../docs/ENTREGA-AWS.md),
[Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html).
