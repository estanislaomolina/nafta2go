"""Recorta una captura oficial para preparar el caso controlado de POC-05.

No descarga datos, no reemplaza el normalizador de POC-01 y no calcula rutas.
"""

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

RESOURCE_ID = "80ac25de-a44a-4445-9215-090cf55cfda5"
MAX_AGE_DAYS = 30
MAX_CANDIDATES = 10


def prepare_case(raw_csv: bytes, metadata: dict) -> tuple[dict, bytes]:
    """Selecciona registros verificables conservando los valores de la fuente."""
    if hashlib.sha256(raw_csv).hexdigest() != metadata["sha256"]:
        raise ValueError("La captura no coincide con el SHA-256 registrado")
    if metadata["resource_id"] != RESOURCE_ID or metadata["license_id"] != "CC-BY-4.0":
        raise ValueError("El recurso o su licencia no coincide con el caso acordado")
    captured_at = datetime.fromisoformat(metadata["retrieved_at_utc"])
    if captured_at.utcoffset() is None:
        raise ValueError("La fecha de captura debe incluir zona horaria")
    reference = captured_at.astimezone(UTC).date()
    reader = csv.DictReader(io.StringIO(raw_csv.decode("utf-8-sig")))
    fields = reader.fieldnames
    required = {
        "idempresa",
        "provincia",
        "idproducto",
        "idtipohorario",
        "precio",
        "fecha_vigencia",
        "latitud",
        "longitud",
        "direccion",
        "empresabandera",
    }
    if not fields or not required.issubset(fields):
        raise ValueError("Faltan columnas requeridas en el CSV")
    rows = list(reader)
    matching = [
        (line, row)
        for line, row in enumerate(rows, start=2)
        if row["provincia"] == "CAPITAL FEDERAL"
        and row["idproducto"] == "2"
        and row["idtipohorario"] == "2"
    ]
    keys = Counter(
        (row["idempresa"], row["idproducto"], row["idtipohorario"]) for _, row in matching
    )
    excluded = Counter()
    recent = []
    for line, row in matching:
        key = (row["idempresa"], row["idproducto"], row["idtipohorario"])
        if keys[key] != 1:
            excluded["duplicate_key"] += 1
            continue
        try:
            published = datetime.strptime(row["fecha_vigencia"], "%Y-%m-%d %H:%M:%S")
            price = Decimal(row["precio"])
            lat, lon = Decimal(row["latitud"]), Decimal(row["longitud"])
            if not isinstance(row["idempresa"], str) or not row["idempresa"].isdecimal():
                raise ValueError("Identificador inválido")
            if not all(value.is_finite() for value in (price, lat, lon)):
                raise ValueError("Valor no finito")
            if price <= 0 or not (Decimal("-34.71") <= lat <= Decimal("-34.52")):
                raise ValueError("Precio o latitud inválidos")
            if not Decimal("-58.54") <= lon <= Decimal("-58.33"):
                raise ValueError("Longitud inválida")
        except (ValueError, InvalidOperation, TypeError):
            excluded["invalid_record"] += 1
            continue
        age = (reference - published.date()).days
        if age < 0:
            excluded["future_date"] += 1
        elif age > MAX_AGE_DAYS:
            excluded["older_than_30_days"] += 1
        else:
            recent.append((line, row, published, age))

    # Fecha más reciente primero; empates por identificador numérico de estación.
    recent.sort(key=lambda item: int(item[1]["idempresa"]))
    recent.sort(key=lambda item: item[2], reverse=True)
    selected = recent[:MAX_CANDIDATES]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(row for _, row, _, _ in selected)
    subset = output.getvalue().encode("utf-8")
    report = {
        "schema_version": 1,
        "case_id": f"poc-05-obelisco-cabildo-{reference}",
        "status": "prices_prepared_routes_pending" if selected else "insufficient_price_coverage",
        "mode": "real_price_snapshot",
        "source": metadata,
        "query": {
            "origin": {"label": "Obelisco", "lat": "-34.6037", "lon": "-58.3816"},
            "destination": {"label": "Cabildo y Juramento", "lat": "-34.5627", "lon": "-58.4565"},
            "reference_date": reference.isoformat(),
            "product_id": "2",
            "schedule_id": "2",
            "consumption_l_per_100km": "10",
            "tank_capacity_l": "50",
            "remaining_l": "10",
            "budget_ars": "12000",
            "reserve_l": "2",
            "max_price_age_days": MAX_AGE_DAYS,
        },
        "coverage": {
            "source_rows": len(rows),
            "caba_super_daytime_rows": len(matching),
            "recent_stations": len(recent),
            "excluded_rows": dict(sorted(excluded.items())),
        },
        "selection": {
            "method": "latest_publication_then_numeric_station_id",
            "max_candidates": MAX_CANDIDATES,
            "age_rule": "calendar_days_between_capture_date_and_publication_date",
            "coordinate_check": "bounding_box_only_not_city_polygon_or_entrance_verification",
            "route_ranked": False,
        },
        "selected_prices": {"file": "prices.csv", "sha256": hashlib.sha256(subset).hexdigest()},
        "candidates": [
            {
                "station_id": row["idempresa"],
                "brand": row["empresabandera"],
                "address": row["direccion"],
                "lat": row["latitud"],
                "lon": row["longitud"],
                "price_ars_per_l": row["precio"],
                "price_effective_at_raw": row["fecha_vigencia"],
                "price_age_calendar_days": age,
                "source_record_number_including_header": line,
            }
            for line, row, _, age in selected
        ],
        "pending": [
            "confirm_normalization_contract_with_POC_01",
            "capture_complete_route_matrix_for_exact_candidate_coordinates",
            "evaluate_real_routes_and_prices_with_motor",
            "ranking_and_explained_recommendation",
        ],
    }
    return report, subset


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True, help="Captura original completa")
    parser.add_argument(
        "--metadata", type=Path, required=True, help="Metadatos y SHA-256 de captura"
    )
    parser.add_argument("--out", type=Path, required=True, help="Directorio de evidencia derivada")
    args = parser.parse_args()
    try:
        report, subset = prepare_case(
            args.csv.read_bytes(), json.loads(args.metadata.read_text(encoding="utf-8"))
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "prices.csv").write_bytes(subset)
    (args.out / "case.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Caso: {report['case_id']}; fecha de referencia: {report['query']['reference_date']}")
    print(f"Estaciones recientes: {report['coverage']['recent_stations']}")
    print(f"Candidatas preparadas: {len(report['candidates'])}; rutas y recomendación pendientes")
    return 0 if report["candidates"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
