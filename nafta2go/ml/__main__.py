"""Preparar dataset y baseline; no entrena modelos ni cambia el recomendador."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from nafta2go.application.price_dataset import prepare_price_dataset
from nafta2go.persistence.database import create_db_engine


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        self.exit(2, "Argumentos inválidos; consultá --help.\n")


def main(argv=None):
    parser = Parser(prog="nafta2go.ml", description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cutoff", type=datetime.fromisoformat, required=True)
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--min-history", type=int, default=5)
    args = parser.parse_args(argv)
    engine = None
    try:
        engine = create_db_engine()
        summary = prepare_price_dataset(
            engine,
            args.output,
            args.cutoff,
            window_days=args.window_days,
            min_history=args.min_history,
        )
    except (ValueError, OSError, SQLAlchemyError):
        print("Preparación fallida: revisar histórico, corte, salida y entorno.", file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
