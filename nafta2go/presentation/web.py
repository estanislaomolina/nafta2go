"""Pantalla local con assets propios, sin credenciales embebidas."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

WEB = Path(__file__).with_name("web")


def install_web(application: FastAPI) -> None:
    application.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

    @application.get("/", include_in_schema=False)
    def index():
        return FileResponse(
            WEB / "index.html",
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
