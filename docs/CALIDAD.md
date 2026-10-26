# Calidad operativa

Implementa la tarea POC-07 (#12), correspondiente a RNF06 y RNF07 del
[PRD](PRD.md). Complementa las reglas de trabajo del equipo sobre ramas, PRs y
testing.

## Integración continua

El workflow [ci.yml](../.github/workflows/ci.yml) corre en cada push y PR hacia
`main` y `dev`. Un push nuevo cancela la corrida anterior de la misma rama.

| Check | Qué verifica | Falla si |
|---|---|---|
| `Docs y notebooks` | Links relativos de todos los `.md` y formato de las notebooks | Un link apunta a un archivo inexistente o una notebook no es válida |
| `Lint` | `ruff check .` y `ruff format --check .` con [ruff.toml](../ruff.toml) | Hay errores de estilo, imports sin usar o código sin formatear |
| `Tests` | `pytest` con pytest-cov sobre `nafta2go` y las dependencias de `requirements-dev.txt` | Falla un test, la cobertura de líneas es < 90% o el job supera 5 min |
| `Secretos` | [gitleaks](https://github.com/gitleaks/gitleaks) sobre los commits nuevos de cada push y PR | Aparece algo con forma de credencial (API keys, tokens, claves privadas) |
| `Contenedores` | Construye la imagen con `docker compose build`, corre las migraciones, verifica el esquema y reproduce la consulta completa con la matriz real guardada | El `Dockerfile` no construye, una migración falla dentro del contenedor, el esquema no llega a `head` o la consulta no produce un resultado histórico trazable |

`Docs y notebooks`, `Lint`, `Tests` y `Secretos` son **checks requeridos** en el
ruleset de `dev` y `main`: una PR con cualquiera en rojo no se puede mergear.
`Contenedores` corre en todas las PRs y falta sumarlo al ruleset. El ruleset
identifica los checks por el `name` de cada job. **Si se renombra un job, hay que actualizar el ruleset en el
mismo momento**; si no, el check requerido queda esperando un resultado que
nunca llega y bloquea todas las PRs.

Las notebooks quedan fuera del lint: son exploración, y la lógica reutilizable
vive en módulos con tests.

## Reproducir el CI localmente

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check .
pytest -v --strict-markers --cov=nafta2go --cov-report=term-missing --cov-precision=2 --cov-fail-under=90
python .github/scripts/check_links.py
```

`ruff format .` y `ruff check --fix .` corrigen la mayoría de los problemas de
estilo. Las dependencias se dividen en `requirements.txt` (lo que necesita la
aplicación para correr) y `requirements-dev.txt` (eso más tests y lint, con la
versión de ruff fijada para que local y CI den el mismo resultado).

## Umbrales de calidad

El job `Tests` mide cobertura de **líneas** del paquete `nafta2go` y falla por
debajo de **90%** con `--cov-fail-under=90`. No mide cobertura de ramas ni toma
los tests como código de producto. Mantiene el rechazo de pruebas fallidas y
marcadores inválidos. La opción [--cov-fail-under](https://pytest-cov.readthedocs.io/en/latest/config.html)
controla el mínimo. [timeout-minutes](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idtimeout-minutes)
limita el job completo a cinco minutos en el runner
Ubuntu/Python 3.12 de GitHub, incluidos preparación e instalación.

La línea de base local sobre 8ae8ab0 fue 95,56% (1.249/1.307 líneas), 353 pruebas
y 148 subtests en 38,99 s con cobertura. Es una medición local; el tiempo del
runner se consulta en Actions. Los umbrales de aceptación y la distinción entre
POC y MVP están en [PRD](PRD.md), RNF06.

`pytest -q tests/test_engine_precision.py` sigue siendo válido para un subconjunto:
la exigencia global de cobertura se aplica al comando completo del CI, no a
cada ejecución parcial.

## Credenciales y configuración sensible

- La configuración sensible se lee de variables de entorno. Localmente se cargan
  desde `.env`, que está en `.gitignore`; `.env.example` lista las claves sin valores.
- En CI no hay credenciales: los tests reemplazan los servicios externos por
  dobles de prueba. Si un job llegara a necesitar una, se guarda como
  *GitHub Secret* y nunca en el workflow.
- Si `Secretos` detecta una credencial real: se rota de inmediato en el
  proveedor; borrar el commit no alcanza porque el historial ya fue publicado.
- Si detecta un falso positivo, se agrega una excepción puntual (ruta y regla)
  en un `.gitleaks.toml`, explicando el motivo en la PR. Nunca se desactiva el job.

## Verificación de que el CI bloquea

La PR que incorporó estos checks incluyó, a propósito y revertidos después,
un test que falla y un token falso, para comprobar que `Tests` y `Secretos`
quedan en rojo. Los links a esas corridas están en la descripción de esa PR.
