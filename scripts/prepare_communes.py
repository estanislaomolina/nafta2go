"""Reproducir polígonos públicos; rechazar cambios de la fuente sin revisión."""

import hashlib
import json
from pathlib import Path

import requests

SOURCE = "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/innovacion-transformacion-digital/comunas/comunas.geojson"
EXPECTED_SHA = "a4a7be8222a6a5c4a5a28c5e6e1b5ff5b0f6ba25f2788250f0ab3f9d6d59959f"
ROOT = Path(__file__).resolve().parents[1]


def transform(raw):
    if hashlib.sha256(raw).hexdigest() != EXPECTED_SHA:
        raise ValueError("La fuente cambió; revisar antes de actualizar la cartografía")

    def rounded(value):
        return [rounded(x) for x in value] if isinstance(value, list) else round(value, 6)

    return [
        {
            "commune": str(f["properties"]["comuna"]),
            "polygons": rounded(
                [f["geometry"]["coordinates"]]
                if f["geometry"]["type"] == "Polygon"
                else f["geometry"]["coordinates"]
            ),
        }
        for f in json.loads(raw)["features"]
    ]


if __name__ == "__main__":
    response = requests.get(SOURCE, timeout=30)
    response.raise_for_status()
    (ROOT / "nafta2go/resources/communes.json").write_text(
        json.dumps(transform(response.content), separators=(",", ":")) + "\n"
    )
