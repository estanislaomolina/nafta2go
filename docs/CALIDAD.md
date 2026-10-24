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
| `Tests` | `pytest -v --strict-markers` con las dependencias de `requirements-dev.txt` | Falla un test, falta `requirements-dev.txt` o no se encuentran tests |
| `Secretos` | [gitleaks](https://github.com/gitleaks/gitleaks) sobre todo el historial | Aparece algo con forma de credencial (API keys, tokens, claves privadas) |

Los cuatro son **checks requeridos** en el ruleset de `dev` y `main`: una PR con
cualquiera en rojo no se puede mergear. El ruleset identifica los checks por el
`name` de cada job. **Si se renombra un job, hay que actualizar el ruleset en el
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
pytest -v
python .github/scripts/check_links.py
```

`ruff format .` y `ruff check --fix .` corrigen la mayoría de los problemas de
estilo. Las dependencias se dividen en `requirements.txt` (lo que necesita la
aplicación para correr) y `requirements-dev.txt` (eso más tests y lint, con la
versión de ruff fijada para que local y CI den el mismo resultado).

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
