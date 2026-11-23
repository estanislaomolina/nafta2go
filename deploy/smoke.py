"""Smoke reutilizable. Lee el código del entorno y nunca lo escribe en la salida."""

import json
import os

import requests

QUERY = {
    "origin": {"lat": -34.6037, "lon": -58.3816},
    "destination": {"lat": -34.5627, "lon": -58.4565},
    "fuel_type": "super",
    "consumption_l_per_100km": "10",
    "tank_capacity_l": "50",
    "remaining_l": "10",
    "budget_ars": "12000",
    "reserve_l": "2",
    "max_candidates": 10,
}


class SmokeFailure(RuntimeError):
    """El contrato de activación no se cumple; mensaje sin datos privados."""


def smoke(base, token, client=None):
    client = client or requests.Session()
    auth = {"Authorization": "Bearer " + token}
    for path in ("/health", "/ready", "/", "/operacion"):
        if client.get(base + path, timeout=10).status_code != 200:
            raise SmokeFailure("fallo en " + path)
    if client.post(base + "/api/v1/recommendations", json=QUERY, timeout=10).status_code != 401:
        raise SmokeFailure("consulta sin autorización no rechazada")
    if client.get(base + "/api/v1/operations", headers=auth, timeout=10).status_code != 401:
        raise SmokeFailure("separación de permisos inválida")
    result = client.post(base + "/api/v1/recommendations", headers=auth, json=QUERY, timeout=30)
    if result.status_code != 200:
        raise SmokeFailure("consulta autenticada fallida")
    body = result.json()
    if not body.get("evaluations") or body.get("recommendation_id") is None:
        raise SmokeFailure("consulta sin evaluaciones persistidas")
    return {
        "smoke": "passed",
        "price_status": body["status"],
        "evaluations": len(body["evaluations"]),
    }


def main():
    try:
        result = smoke(
            os.environ.get("NAFTA2GO_SMOKE_URL", "http://127.0.0.1:8000"),
            os.environ["NAFTA2GO_API_TOKEN"],
        )
    except (SmokeFailure, requests.RequestException, KeyError, ValueError):
        print(json.dumps({"smoke": "failed", "reason": "contrato de activación incumplido"}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
