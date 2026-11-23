# Revisión cruzada y protección de ramas — 17/11/2026

Responde a #54 y a la devolución de Entrega 2. La regla `Reglas` (25794035),
activa en `main` y `dev`, se consultó, actualizó y volvió a consultar mediante
la API de GitHub; no se alteraron workflows ni se omitieron checks.

## Configuración comprobada

Las capturas [antes](reglas-antes.json) y [después](reglas-despues.json) registran:

- Una aprobación requerida de otro integrante (antes: cero).
- Conversaciones de review resueltas (antes: no requerido).
- Aprobaciones invalidadas al subir cambios (antes: se conservaban).
- Seis checks: Docs y notebooks, Lint, Tests, Secretos, Contenedores y Web y accesibilidad.
  Los últimos dos se incorporaron a los cuatro ya requeridos, con la misma integración CI.
- Regla activa, sin actores con bypass; se conservan protección contra borrado,
  force push, condiciones de ramas y los demás parámetros.

La verificación fue por lectura de la configuración activa; no se intentó un
merge inválido ni se introdujeron fallos artificiales en ramas protegidas.

## Auditoría de las PRs integradas

[auditoria.json](auditoria.json) registra las 36 PRs hacia `dev`, desde #52 hasta
#120, posteriores a la Entrega 2 y presentes al consultar. Todas tienen una
aprobación ajena anterior al merge, checks exitosos terminados antes del merge
y ninguna conversación sin resolver al momento de esta auditoría. Incluye
número/URL, autor, revisores, fecha de merge, SHA de la rama y resultados de checks.

Ejemplos de trabajo y revisión entre los tres integrantes:
[#52](https://github.com/estanislaomolina/nafta2go/pull/52),
[#53](https://github.com/estanislaomolina/nafta2go/pull/53),
[#114](https://github.com/estanislaomolina/nafta2go/pull/114),
[#118](https://github.com/estanislaomolina/nafta2go/pull/118) y
[#120](https://github.com/estanislaomolina/nafta2go/pull/120).

La consulta usa `pullRequests` mergeadas (primeras 100 por actualización),
filtra `baseRefName=dev` y número >= 52, y lee autor, reviews, conversaciones y
los checks del último commit de cada PR. Esta captura termina en #120 y no se
actualiza automáticamente. Los checks anteriores a existir los seis jobs se
valoran según los jobs que realmente corrieron; no se les atribuyen seis checks.

La resolución de conversaciones es su estado actual, no una reconstrucción de
su estado exacto al merge. Una aprobación histórica no garantiza por sí sola que
se revisara el último push, porque antes no caducaban. Las reglas nuevas exigen
esa revisión para cambios futuros; esta auditoría no reescribe el historial.
