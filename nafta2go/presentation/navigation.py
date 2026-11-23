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


def _label(brand: str | None, address: str | None, station_id: str) -> str:
    return f"Cómo llegar a {brand or 'la estación'} — {address or station_id}"


def present_recommendation(payload: dict) -> dict:
    hidden = {"navigation_destinations", "stale_navigation_destinations"}
    result = {key: value for key, value in payload.items() if key not in hidden}
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
                "label": _label(row["brand"], row["address"], station_id),
            }
        )
    stale = payload.get("stale_price_estimates")
    stale_destinations = payload.get("stale_navigation_destinations", {})
    if stale and stale.get("items"):
        items = []
        for item in stale["items"]:
            location = stale_destinations.get(item["station_id"])
            if location is not None:
                item = item | {
                    "navigation": {
                        "url": google_maps_url(location["lat"], location["lon"]),
                        "label": _label(item["brand"], item["address"], item["station_id"]),
                    }
                }
            items.append(item)
        result["stale_price_estimates"] = stale | {"items": items}
    shown_stale = (result.get("stale_price_estimates") or {}).get("items", [])
    has_links = links or any("navigation" in item for item in shown_stale)
    result.update(navigation=links, navigation_notice=NOTICE if has_links else None)
    return result
