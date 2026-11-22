"""Preparar secrets locales sin valores en Compose, provisioning ni stdout."""

import getpass
import os
from pathlib import Path


def prepare(directory, token, password):
    if not token.strip() or len(password) < 12:
        raise ValueError(
            "Se requiere token administrativo y contraseña de al menos doce caracteres"
        )
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    for name, value in (("api_admin_token", token), ("grafana_admin_password", password)):
        temporary = directory / (name + ".next")
        temporary.write_text(value)
        # El directorio 0700 protege en el host; otros UID del contenedor leen el secret.
        temporary.chmod(0o444)
        temporary.replace(directory / name)


if __name__ == "__main__":
    prepare(
        Path("data/private/observability"),
        os.environ.get("NAFTA2GO_ADMIN_TOKEN", ""),
        os.environ.get("NAFTA2GO_GRAFANA_PASSWORD") or getpass.getpass("Contraseña de Grafana: "),
    )
