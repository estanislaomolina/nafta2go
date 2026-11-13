"""Enlaces externos de presentación, sin origen del conductor ni llamadas a Maps."""

from decimal import Decimal
from urllib.parse import urlencode

NOTICE = "Google Maps recalcula el recorrido y puede diferir del usado para recomendar."


def google_maps_url(lat: float, lon: float) -> str:
    values = []
    for value, bound in ((lat, 90), (lon, 180)):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not -bound <= value <= bound
        ):
            raise ValueError("Coordenadas de estación inválidas")
        values.append(format(Decimal(str(value)), "f"))
    return "https://www.google.com/maps/dir/?" + urlencode(
        {
            "api": 1,
            "destination": ",".join(values),
            "travelmode": "driving",
            "dir_action": "navigate",
        }
    )


def present_recommendation(payload: dict) -> dict:
    result = {key: value for key, value in payload.items() if key != "navigation_destinations"}
    destinations = payload.get("navigation_destinations", {})
    rows = {row["station_id"]: row for row in payload["evaluations"]}
    links = []
    for choice in payload["alternatives"]:
        station_id = choice["station_id"]
        location = destinations.get(station_id)
        if location is None:
            continue
        row = rows[station_id]
        links.append(
            {
                "station_id": station_id,
                "url": google_maps_url(location["lat"], location["lon"]),
                "label": (
                    f"Cómo llegar a {row['brand'] or 'la estación'} — "
                    f"{row['address'] or station_id}"
                ),
            }
        )
    result.update(navigation=links, navigation_notice=NOTICE if links else None)
    return result
