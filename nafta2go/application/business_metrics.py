"""Agregados de resultados persistidos: recomendaciones, nunca compras observadas."""

from collections import Counter, defaultdict

from nafta2go.adapters.public_communes import station_commune
from nafta2go.application.scenario import load_scenario
from nafta2go.persistence import repository as repo

MAX_STATIONS, MAX_BRANDS = 512, 24


def business_metrics(engine):
    counts, station, brands = Counter(), Counter(), Counter()
    liters, spending = defaultdict(float), defaultdict(float)
    communes_l, communes_ars = defaultdict(float), defaultdict(float)
    exclusions = estimates = overflow = 0
    with engine.connect() as conn:
        run = repo.latest_successful_run(conn, "vigente")
        rows = repo.prices_for_run(conn, run) if run is not None else []
        locations = {
            str(row["station_id"]): (row["lat"], row["lon"]) for row in load_scenario().rows
        }
        locations.update({str(row["station_id"]): (row["lat"], row["lon"]) for row in rows})
        for body in repo.recommendation_results(conn):
            outcome = body.get("outcome")
            counts[outcome if outcome in {"recommended", "no_feasible_stations"} else "other"] += 1
            evaluations = {str(row["station_id"]): row for row in body.get("evaluations", [])}
            unique = {str(choice["station_id"]) for choice in body.get("alternatives", [])}
            for identifier in sorted(unique):
                row = evaluations.get(identifier, {})
                key = (
                    identifier if identifier in station or len(station) < MAX_STATIONS else "other"
                )
                overflow += key == "other"
                brand = str(row.get("brand") or "unknown")[:80]
                if brand not in brands and len(brands) >= MAX_BRANDS:
                    brand = "other"
                station[key] += 1
                brands[brand] += 1
                metrics = row.get("metrics") or {}
                value_l, value_ars = (
                    float(metrics.get("purchased_l", 0)),
                    float(metrics.get("cost_ars", 0)),
                )
                liters[key] += value_l
                spending[key] += value_ars
                commune = station_commune(*locations.get(identifier, (None, None)))
                communes_l[commune] += value_l
                communes_ars[commune] += value_ars
            exclusions += len(
                set((body.get("conservative_ranking") or {}).get("excluded_station_ids", []))
            )
            estimates += len(
                {
                    item["station_id"]
                    for item in (body.get("stale_price_estimates") or {}).get("items", [])
                }
            )
    return {
        "stored": counts,
        "station": station,
        "brand": brands,
        "estimated_liters": liters,
        "estimated_spending_ars": spending,
        "commune_estimated_liters": communes_l,
        "commune_estimated_spending_ars": communes_ars,
        "conservative_exclusions": exclusions,
        "old_price_estimates": estimates,
        "station_overflow": overflow,
    }
