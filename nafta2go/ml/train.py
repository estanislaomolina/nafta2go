"""Entrenar y comparar modelos sobre un dataset de `python -m nafta2go.ml`.

Uso: python -m nafta2go.ml.train --dataset DIR --output DIR. No modifica la base ni el
recomendador; escribe artefacto, manifiesto, predicciones y reporte en un directorio nuevo.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from nafta2go.application.price_model import train_price_models

DEFAULT_SELECTION_START = "2025-01-01T00:00:00-03:00"


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        self.exit(2, "Argumentos inválidos; consultá --help.\n")


def main(argv=None):
    parser = Parser(prog="nafta2go.ml.train", description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--selection-start",
        type=datetime.fromisoformat,
        default=datetime.fromisoformat(DEFAULT_SELECTION_START),
    )
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        result = train_price_models(args.dataset, args.output, args.selection_start, args.seed)
    except (ValueError, OSError, KeyError):
        print(
            "Entrenamiento fallido: revisar dataset, corte de selección y salida.", file=sys.stderr
        )
        return 2
    report = result["report"]
    summary = {
        "chosen_method": report["chosen_method"],
        "chosen_is_model": report["chosen_is_model"],
        "best_model": report["best_model"],
        "selection_mae_ars_per_l": {
            name: scores["mae_ars_per_l"] for name, scores in report["selection"].items()
        },
        "validation_mae_ars_per_l": {
            name: scores["mae_ars_per_l"] for name, scores in report["validation"].items()
        },
        "artifact_sha256": result["manifest"]["artifact_sha256"],
    }
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
