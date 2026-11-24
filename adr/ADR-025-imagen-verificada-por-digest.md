---
status: Aceptado
date: 2026-11-22
decision-makers: Equipo Nafta2Go
consulted: ADR-024, issue 159
informed: Cátedra
---

# Imagen verificada en CI y entregada por digest

## Context and Problem Statement

Construir en EC2 con dependencias por rango no garantiza ejecutar la imagen que
probó el CI y consume recursos de la demo. Debemos entregar el mismo artefacto
verificado, con configuración y datos operativos externos.

## Considered Options

1. Conservar la imagen probada como artefacto de Actions y publicarla en GHCR.
2. Reconstruir en EC2 a partir del commit, como ADR-024.
3. Publicar en ECR e integrar autenticación AWS para publicación y descarga.

## Decision Outcome

Se propone la opción 1. Contenedores construye una sola imagen y la verifica con
migraciones, consulta y smoke sin red externa. Se transfiere mediante save/load a
un job que espera todos los checks. Sólo push a dev/main publica el tag SHA;
el despliegue acepta exclusivamente el digest y comprueba la etiqueta de revisión.
Se verifica que el digest publicado resuelva al ID de imagen probado.

### Consequences and Confirmation

- GHCR público permite lectura sin secretos adicionales en el host. El titular
  configura esa visibilidad tras la primera publicación y comprueba lectura anónima.
- Las PR no publican. Sólo el job de publicación recibe packages:write.
- Se conserva el digest de cada release instalada; un tag SHA puede cambiar tras
  reconstruir, por lo que no es una referencia admitida para despliegue.
- SSM, SecureString, respaldo SQLite y loopback de ADR-024 continúan vigentes.
- Volver a una imagen anterior no revierte migraciones ni datos. La compatibilidad
  de esquema debe revisarse antes de cada cambio estructural.
- Fixtures históricos pequeños se incluyen para pruebas reproducibles; secretos,
  capturas operativas y base persistente no se incorporan a la imagen.
- La publicación y activación reales requieren una corrida del cambio integrado;
  las pruebas con dependencias falsas no acreditan ejecución en GHCR o AWS.

## Pros and Cons of the Options

- **GHCR y artefacto:** entrega los bytes probados, evita construir en EC2 y usa
  GITHUB_TOKEN temporal; requiere transferencia de un tar y gestión de retención
  de digests. La visibilidad pública requiere configuración inicial del titular.
- **Construir en EC2:** usa únicamente el canal existente y no necesita registro;
  repite trabajo, consume CPU y permite resolver dependencias diferentes al CI.
- **ECR:** integra políticas y ciclo de vida AWS; añade permisos, autenticación y
  costos operativos de almacenamiento a esta demo temporal.

## More Information

[Procedimiento](../docs/ENTREGA-AWS.md),
[imagen entre jobs](https://docs.docker.com/build/ci/github-actions/share-image-jobs/),
[GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
