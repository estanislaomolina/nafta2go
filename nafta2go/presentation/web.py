"""Pantalla local con assets propios, sin credenciales embebidas."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

WEB = Path(__file__).with_name("web")


def install_web(application: FastAPI) -> None:
    origin = os.environ.get("NAFTA2GO_WEB_ORIGIN", "").strip()
    if origin:
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("NAFTA2GO_WEB_ORIGIN debe ser un origen HTTPS sin ruta")
        application.add_middleware(
            CORSMiddleware,
            allow_origins=[origin],
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
            max_age=600,
        )
    application.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

    def page(name):
        return FileResponse(
            WEB / name,
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self'; style-src 'self'; "
                    "connect-src 'self'; base-uri 'none'; object-src 'none'; "
                    "frame-ancestors 'none'; form-action 'self'"
                ),
            },
        )

    @application.get("/", include_in_schema=False)
    def index():
        return page("index.html")

    @application.get("/operacion", include_in_schema=False)
    def operation():
        return page("operation.html")
