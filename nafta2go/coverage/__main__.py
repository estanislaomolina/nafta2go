"""Reporte de cobertura: python -m nafta2go.coverage --origin=LAT,LON [--destination=LAT,LON].

Lee la última ingesta vigente de DATABASE_URL, cuenta las estaciones con precio
reciente en CABA y en el corredor del recorrido, y muestra si la consulta usaría
la captura actual, el escenario histórico o ninguno. No consulta rutas.

Las coordenadas van con "=" (--origin=-34.6037,-58.3816): si no, argparse toma
el signo negativo como el comienzo de otra opción.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from nafta2go.adapters.routing import Point
from nafta2go.application.coverage_report import coverage_report
from nafta2go.persistence.database import create_db_engine, database_url, upgrade_to_head


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.reference_at.utcoffset() is None:
        print("--reference-at: debe incluir zona horaria", file=sys.stderr)
        return 2

    url = database_url()
    upgrade_to_head(url)
    engine = create_db_engine(url)
    try:
        with engine.connect() as conn:
            report = coverage_report(
                conn,
                args.origin,
                args.destination,
                fuel_type=args.fuel,
                schedule_id=args.schedule,
                reference_at=args.reference_at,
            )
    finally:
        engine.dispose()

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


def _point(value: str) -> Point:
    try:
        lat, lon = (float(part) for part in value.split(","))
        return Point(lat, lon)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"se espera LAT,LON: {value!r}") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m nafta2go.coverage", description=__doc__)
    parser.add_argument("--origin", type=_point, required=True)
    parser.add_argument("--destination", type=_point)
    parser.add_argument("--fuel", choices=("super", "premium"), default="super")
    parser.add_argument("--schedule", type=int, choices=(2, 3), default=2)
    parser.add_argument(
        "--reference-at",
        type=datetime.fromisoformat,
        default=datetime.now(UTC),
        help="fecha ISO con zona; por defecto, ahora",
    )
    parser.add_argument("--output", type=Path, help="guarda también el reporte en JSON")
    return parser


if __name__ == "__main__":
    sys.exit(main())
