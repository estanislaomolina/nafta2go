"""Evaluar estimaciones para precios de más de 30 días con reingresos, sin servirlas (#57)."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from nafta2go.application.stale_price_evaluation import evaluate_stale_estimates


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        self.exit(2, "Argumentos inválidos; consultá --help.\n")


def main(argv=None):
    parser = Parser(prog="nafta2go.ml.evaluate_stale", description=__doc__)
    for name in ("dataset", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--selection-start", type=datetime.fromisoformat, required=True)
    parser.add_argument("--min-gap-days", type=int, default=30)
    parser.add_argument("--min-examples", type=int, default=30)
    args = parser.parse_args(argv)
    try:
        report = evaluate_stale_estimates(
            args.dataset,
            args.output,
            args.selection_start,
            min_gap_days=args.min_gap_days,
            min_examples=args.min_examples,
        )
    except (ValueError, OSError, KeyError, TypeError):
        print("Evaluación fallida: revisar dataset, fechas y salida.", file=sys.stderr)
        return 2
    summary = {
        "runtime_enabled": False,
        "chosen_method": report["chosen_method"],
        "adoption_check": report["adoption_check"],
    }
    print(json.dumps(summary, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
