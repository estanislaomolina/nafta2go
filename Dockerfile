# Imagen de la POC: migraciones, ingesta y consulta por comandos.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN useradd --create-home --uid 10001 app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY nafta2go ./nafta2go
COPY docs/evidencia/escenario-vigente-2026-10-24 ./docs/evidencia/escenario-vigente-2026-10-24
COPY docs/evidencia/poc-05-flujo-2026-10-26/matrix.json ./docs/evidencia/poc-05-flujo-2026-10-26/matrix.json

RUN mkdir -p /app/data && chown app:app /app/data
USER app

ENV DATABASE_URL=sqlite:////app/data/nafta2go.db
VOLUME ["/app/data"]

CMD ["alembic", "upgrade", "head"]
