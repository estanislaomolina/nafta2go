"""Contrato de entrada HTTP; las restricciones físicas siguen en FuelRequest."""

from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nafta2go.adapters.routing import Point
from nafta2go.application.coverage_rules import MIN_RECENT_CANDIDATES
from nafta2go.application.recommendation import DEFAULT_CANDIDATE_LIMIT, MAX_CANDIDATES
from nafta2go.domain.engine import FuelRequest


class Coordinates(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    lat: float = Field(strict=True, ge=-90, le=90)
    lon: float = Field(strict=True, ge=-180, le=180)

    def point(self) -> Point:
        return Point(self.lat, self.lon)


class PlaceSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(strict=True, min_length=3, max_length=120)


class RecommendationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    origin: Coordinates
    destination: Coordinates | None = None
    fuel_type: Literal["super", "premium"]
    schedule_id: int = Field(default=2, strict=True, ge=2, le=3)
    max_candidates: int = Field(
        default=DEFAULT_CANDIDATE_LIMIT, strict=True, ge=MIN_RECENT_CANDIDATES, le=MAX_CANDIDATES
    )
    consumption_l_per_100km: Decimal
    tank_capacity_l: Decimal
    remaining_l: Decimal
    budget_ars: Decimal
    reserve_l: Decimal

    def fuel_request(self) -> FuelRequest:
        return FuelRequest(
            self.consumption_l_per_100km,
            self.tank_capacity_l,
            self.remaining_l,
            self.budget_ars,
            self.reserve_l,
        )

    @model_validator(mode="after")
    def validate_vehicle(self) -> Self:
        self.fuel_request()
        return self


class NavigationLink(BaseModel):
    station_id: str
    url: str
    label: str


class RecommendationOutput(BaseModel):
    status: Literal["ready", "historical_scenario", "insufficient_coverage"]
    outcome: Literal["recommended", "insufficient_coverage", "no_feasible_stations"]
    query: dict[str, Any]
    price_reference_at: str
    source: dict[str, Any]
    data_run_id: int | None
    scenario: dict[str, Any] | None
    current_eligible_count: int
    selected_eligible_count: int
    exclusions: dict[str, int]
    routing_provider: str
    engine_version: str
    routes: dict[str, Any] | None
    alternatives: list[dict[str, Any]]
    evaluations: list[dict[str, Any]]
    recommendation_id: int | None
    navigation: list[NavigationLink]
    navigation_notice: str | None
    stale_price_estimates: dict[str, Any] | None = None


class ErrorDetail(BaseModel):
    code: str
    errors: list[dict[str, str]] | None = None
    message: str | None = None


class PriceDiagnosticOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: Literal["published_price_retrospective"]
    status: Literal["reference_only", "unavailable"]
    station_id: int
    product_id: int
    schedule_id: int
    official_price_ars_per_l: str
    published_at: str
    reference_ars_per_l: str | None
    difference_ars_per_l: str | None
    alert_level: Literal["not_calibrated", "provisional_deviation", "provisional_within_threshold"]
    alert_policy_version: str | None = None
    relative_deviation: str | None = None
    alert_threshold: str | None = None
    alert_notice: str | None = None
    reason: Literal["alert_policy_not_validated", "context_unavailable", "provisional_policy"]
    method: Literal["mediana_previa", "ultimo_precio", "bandera_reciente"]
    version: str
    features_version: str
    data_run_id: int
    history_run_id: int
    history_sha256: str
    availability_assumption: str


class ErrorOutput(BaseModel):
    detail: ErrorDetail
