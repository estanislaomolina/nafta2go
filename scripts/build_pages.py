"""Publicar sólo HTML/assets propios, con API HTTPS fija y sin credenciales."""

import argparse
import html
import shutil
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "nafta2go/presentation/web"


def build(output: Path, api_origin: str):
    origin = urlsplit(api_origin)
    if (
        origin.scheme != "https"
        or not origin.hostname
        or origin.username
        or origin.password
        or origin.path
        or origin.query
        or origin.fragment
    ):
        raise ValueError("Se requiere un origen HTTPS de API, sin ruta ni credenciales")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(WEB / "assets", output / "assets", dirs_exist_ok=True)
    policy = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        f"connect-src 'self' {api_origin}; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; upgrade-insecure-requests"
    )
    metadata = (
        f'<meta name="nafta2go-api-origin" content="{html.escape(api_origin, quote=True)}">'
        f'<meta http-equiv="Content-Security-Policy" content="{html.escape(policy, quote=True)}">'
        '<meta name="referrer" content="no-referrer">'
    )
    for source, destination, prefix in (
        ("index.html", output / "index.html", "./"),
        ("operation.html", output / "operacion/index.html", "../"),
    ):
        content = (WEB / source).read_text().replace("</head>", metadata + "</head>")
        content = content.replace('"/assets/', '"' + prefix + "assets/")
        content = content.replace('href="/"', 'href="' + prefix + '"')
        content = content.replace('href="/operacion"', 'href="' + prefix + 'operacion/"')
        content = content.replace('action="/operacion"', 'action="./"')
        content = content.replace('action="/"', 'action="./"')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
    (output / ".nojekyll").touch()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--api-origin", required=True)
    args = parser.parse_args(argv)
    build(args.output, args.api_origin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
