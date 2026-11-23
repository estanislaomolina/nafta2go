"""Perfiles y análisis de las pruebas de carga (#158); sin dependencia de Locust.

Separado del locustfile para poder probarlo en el CI sin instalar Locust.
"""

import math
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.measure_query_latency import bodies  # noqa: E402

# Objetivo de RNF01 y umbral de errores a partir del cual un escalón se considera saturado.
P95_TARGET_S = 5.0
MAX_ERROR_RATE = 0.01


@dataclass(frozen=True)
class Profile:
    users: tuple[int, ...]
    step_seconds: int
    think_seconds: float
    quota_per_minute: int | None = None
    # Copia de la base con histórico real: veinte candidatas con diagnóstico activo.
    real_history: bool = False


PROFILES = {
    # Corrida corta para verificar el arnés de punta a punta.
    "humo": Profile(users=(2, 4), step_seconds=5, think_seconds=0.0),
    # Uso esperado de la demo: pocos conductores con pausas entre consultas.
    "sostenida": Profile(users=(10,), step_seconds=120, think_seconds=1.0),
    # Escalones sin pausa hasta encontrar el punto de saturación.
    "estres": Profile(users=(1, 5, 10, 20, 40, 80), step_seconds=30, think_seconds=0.0),
    # Cupo real de rutas sin caché: cada consulta exitosa consume una matriz.
    "cupo": Profile(users=(10,), step_seconds=90, think_seconds=0.0, quota_per_minute=30),
    # Cuello de botella de #158: cada consulta prepara veinte diagnósticos del histórico real.
    "historico": Profile(
        users=(1, 2, 5, 10, 20), step_seconds=30, think_seconds=0.0, real_history=True
    ),
}

REQUIRED_DIAGNOSTICS = 20


def target_users(profile: Profile, elapsed: float) -> int | None:
    """Usuarios activos para el segundo `elapsed`; None termina la prueba."""
    step = int(elapsed // profile.step_seconds)
    return profile.users[step] if step < len(profile.users) else None


# Un ciclo completo de variaciones de vehículo y presupuesto de measure_query_latency.
BODIES = tuple(bodies(252))
# La consulta de measure_real_history_diagnostics (#152), con veinte candidatas.
HISTORY_BODY = bodies(1)[0] | {
    "max_candidates": REQUIRED_DIAGNOSTICS,
    "consumption_l_per_100km": "10",
    "tank_capacity_l": "50",
    "remaining_l": "10",
    "budget_ars": "12000",
}


def request_body(index: int, real_history: bool = False) -> dict:
    """Consultas UC01 válidas que coinciden con la matriz grabada de POC-05."""
    return HISTORY_BODY if real_history else BODIES[index % len(BODIES)]


def diagnostics_complete(result: dict) -> bool:
    """Una respuesta 200 sin los veinte diagnósticos disponibles no mide el cuello de botella."""
    block = result.get("conservative_ranking") or {}
    return (
        block.get("status") == "available"
        and len(block.get("diagnostics") or []) == REQUIRED_DIAGNOSTICS
    )


def percentile(values: list[float], share: float) -> float | None:
    """Percentil por rango más cercano, igual que measure_query_latency."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * share) - 1)]


def summarize(samples: list[dict], profile: Profile) -> list[dict]:
    """Métricas por escalón a partir de muestras {users, elapsed_s, latency_s, status, code}."""
    steps = []
    for index, users in enumerate(profile.users):
        start, end = index * profile.step_seconds, (index + 1) * profile.step_seconds
        rows = [s for s in samples if s["users"] == users and start <= s["elapsed_s"] < end]
        latencies = [row["latency_s"] for row in rows]
        failures = [row for row in rows if row["status"] != 200 or row.get("code")]
        statuses, codes = {}, {}
        for row in rows:
            statuses[str(row["status"])] = statuses.get(str(row["status"]), 0) + 1
            if row.get("code"):
                codes[row["code"]] = codes.get(row["code"], 0) + 1
        steps.append(
            {
                "users": users,
                "requests": len(rows),
                "requests_per_second": round(len(rows) / profile.step_seconds, 2),
                "latency_s": {
                    name: None if value is None else round(value, 4)
                    for name, value in (
                        ("p50", percentile(latencies, 0.5)),
                        ("p95", percentile(latencies, 0.95)),
                        ("p99", percentile(latencies, 0.99)),
                        ("max", max(latencies) if latencies else None),
                    )
                },
                "error_rate": round(len(failures) / len(rows), 4) if rows else None,
                "statuses": dict(sorted(statuses.items())),
                "error_codes": dict(sorted(codes.items())),
            }
        )
    return steps


def saturation(steps: list[dict]) -> dict:
    """Primer escalón que supera el objetivo de p95, los errores o deja de ganar rendimiento."""
    previous = None
    for step in steps:
        p95, errors = step["latency_s"]["p95"], step["error_rate"]
        reasons = []
        if p95 is not None and p95 > P95_TARGET_S:
            reasons.append("p95_supera_objetivo")
        if errors is not None and errors > MAX_ERROR_RATE:
            reasons.append("errores_superan_umbral")
        if previous and step["requests_per_second"] < previous["requests_per_second"] * 1.1:
            reasons.append("rendimiento_no_crece")
        if reasons:
            return {"users": step["users"], "reasons": reasons}
        previous = step
    return {"users": None, "reasons": []}
