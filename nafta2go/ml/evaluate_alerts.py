"""Evaluar umbrales candidatos sin activar alertas; cortes y cuantil explícitos."""

import argparse
import json
import sys
from datetime import datetime
from decimal import InvalidOperation
from pathlib import Path

from nafta2go.application.price_alert_evaluation import evaluate_price_alerts


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        self.exit(2, "Argumentos inválidos; consultá --help.\n")


def main(argv=None):
    parser = Parser(prog="nafta2go.ml.evaluate_alerts", description=__doc__)
    for name in ("dataset", "model", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--audit-start", type=datetime.fromisoformat, required=True)
    parser.add_argument("--quantile", type=float, required=True)
    parser.add_argument("--min-examples", type=int, default=30)
    args = parser.parse_args(argv)
    try:
        report = evaluate_price_alerts(
            args.dataset,
            args.model,
            args.output,
            args.audit_start,
            args.quantile,
            args.min_examples,
        )
    except (ValueError, OSError, KeyError, TypeError, InvalidOperation, StopIteration):
        print("Evaluación fallida: revisar manifiestos, datos, cortes y salida.", file=sys.stderr)
        return 2
    print(json.dumps({"runtime_enabled": False, "segments": report["segments"]}, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
