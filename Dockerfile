# Imagen de la aplicación. Por ahora ejecuta las migraciones; el servicio de la
# API se agrega con el flujo de punta a punta (POC-05).
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

RUN mkdir -p /app/data && chown app:app /app/data
USER app

ENV DATABASE_URL=sqlite:////app/data/nafta2go.db
VOLUME ["/app/data"]

CMD ["alembic", "upgrade", "head"]
