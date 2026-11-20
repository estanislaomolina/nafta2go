"""Direcciones y lugares de USIG/GCBA; nunca registra el texto de búsqueda."""

import json
import os
from time import monotonic

import requests

from nafta2go.domain.places import Place, PlaceUnavailable
from nafta2go.normalization.rules import CABA_BBOX


class USIGPlaces:
    def __call__(self, text):
        if os.environ.get("NAFTA2GO_PLACE_SEARCH_ENABLED", "1") != "1":
            raise PlaceUnavailable()
        deadline = monotonic() + 10
        normalizer = "https://servicios.usig.buenosaires.gob.ar/normalizar/"
        epok = "https://epok.buenosaires.gob.ar/"
        with requests.Session() as session:
            session.headers["User-Agent"] = "Nafta2Go/1.0 (github.com/estanislaomolina/nafta2go)"

            def get(url, params):
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise PlaceUnavailable()
                try:
                    with session.get(
                        url,
                        params=params,
                        timeout=(2, min(3, remaining)),
                        allow_redirects=False,
                        stream=True,
                    ) as response:
                        if response.status_code != 200:
                            raise PlaceUnavailable()
                        raw = bytearray()
                        for chunk in response.iter_content(8192):
                            raw.extend(chunk)
                            if len(raw) > 1_048_576 or monotonic() > deadline:
                                raise PlaceUnavailable()
                        return json.loads(raw)
                except (requests.RequestException, ValueError, TypeError) as exc:
                    raise PlaceUnavailable() from exc

            def addresses(value):
                data = get(normalizer, {"direccion": value, "geocodificar": "True"})
                if not isinstance(data, dict) or not isinstance(
                    data.get("direccionesNormalizadas"), list
                ):
                    raise PlaceUnavailable()
                places = []
                for row in data["direccionesNormalizadas"][:20]:
                    try:
                        point = row["coordenadas"]
                        lat, lon = float(point["y"]), float(point["x"])
                        if row.get("cod_partido") != "caba" or point.get("srid") != 4326:
                            continue
                        if not (
                            CABA_BBOX["lat_min"] <= lat <= CABA_BBOX["lat_max"]
                            and CABA_BBOX["lon_min"] <= lon <= CABA_BBOX["lon_max"]
                        ):
                            continue
                        label = row["direccion"]
                        if isinstance(label, str) and label.strip():
                            places.append(Place(label[:240], lat, lon))
                    except (KeyError, TypeError, ValueError, OverflowError):
                        continue
                return places[:3]

            result = addresses(text)
            if result:
                return result
            data = get(epok + "buscar/", {"texto": text, "limit": 3})
            if not isinstance(data, dict) or not isinstance(data.get("instancias"), list):
                raise PlaceUnavailable()
            for row in data["instancias"][:3]:
                if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                    continue
                content = get(epok + "getObjectContent/", {"id": row["id"]})
                if not isinstance(content, dict):
                    raise PlaceUnavailable()
                address = content.get("direccionNormalizada")
                name = row.get("nombre")
                if isinstance(address, str) and address and isinstance(name, str):
                    points = addresses(address)
                    if points:
                        point = points[0]
                        result.append(
                            Place((name + " — " + point.label)[:240], point.lat, point.lon)
                        )
            return result
