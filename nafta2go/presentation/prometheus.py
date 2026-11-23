"""Métricas acotadas por aplicación; sin etiquetas derivadas de entradas privadas."""

from datetime import datetime
from threading import Lock
from time import monotonic

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily

from nafta2go.application.business_metrics import business_metrics
from nafta2go.application.ingestion_status import ingestion_status
from nafta2go.persistence.repository import open_ingestion_alert_count

ENDPOINTS = {
    "/",
    "/operacion",
    "/health",
    "/ready",
    "/metrics",
    "/api/v1/recommendations",
    "/api/v1/operations",
    "/api/v1/operations/ingestion",
    "/api/v1/places",
}


class Snapshot:
    def __init__(self, metric):
        self.metric = metric

    def collect(self):
        yield self.metric


class HTTPMetrics:
    def __init__(self):
        self._business = None
        self._business_at = 0.0
        self._business_lock = Lock()
        self.registry = CollectorRegistry()
        self.responses = Counter(
            "nafta2go_http_responses",
            "Respuestas HTTP por proceso",
            ["endpoint", "code"],
            registry=self.registry,
        )
        self.duration = Histogram(
            "nafta2go_http_duration_seconds",
            "Latencia HTTP por proceso",
            ["endpoint"],
            buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
            registry=self.registry,
        )
        self.queries = Counter(
            "nafta2go_queries",
            "Consultas HTTP por resultado, por proceso",
            ["outcome"],
            registry=self.registry,
        )

    def render(self, engine, routes, diagnostic, now):
        # Registro por scrape: los gauges persistidos no se acumulan al volver a leer.
        registry = CollectorRegistry()
        registry.register(self.responses)
        registry.register(self.duration)
        registry.register(self.queries)

        def gauge(name, help_text, values, label=None, counter=False):
            family = CounterMetricFamily if counter else GaugeMetricFamily
            metric = family("nafta2go_" + name, help_text, labels=[label] if label else [])
            for key, value in values.items() if label else [(None, values)]:
                metric.add_metric([str(key)] if label else [], value)
            registry.register(Snapshot(metric))

        # Los agregados persistidos pueden demorar hasta dos minutos en reflejar cambios.
        # Serializar la renovación evita recorrer la historia por cada scraper concurrente.
        with self._business_lock:
            captured_at = monotonic()
            if self._business is None or captured_at - self._business_at >= 120:
                self._business = business_metrics(engine)
                self._business_at = captured_at
            business = self._business
        gauge(
            "business_snapshot_age_seconds",
            "Edad del agregado persistido",
            captured_at - self._business_at,
        )
        for key, label in (
            ("stored", "outcome"),
            ("station", "station_id"),
            ("brand", "brand"),
            ("estimated_liters", "station_id"),
            ("estimated_spending_ars", "station_id"),
            ("commune_estimated_liters", "commune"),
            ("commune_estimated_spending_ars", "commune"),
        ):
            gauge(
                "recommendations_" + key,
                "Agregado persistido de recomendaciones; no compras",
                business[key],
                label,
            )
        for key in ("conservative_exclusions", "old_price_estimates", "station_overflow"):
            gauge(key, "Agregado persistido de recomendaciones", business[key])
        for key, value in routes.snapshot().items():
            gauge(
                "routes_" + key,
                "Estado local de rutas por proceso",
                value,
                counter=key != "entries",
            )
        for key, value in routes.quota_snapshot().items():
            gauge("routes_" + key, "Cupo local por proceso; no saldo real del proveedor", value)
        with engine.connect() as conn:
            gauge(
                "ingestion_open_alerts",
                "Alertas persistidas sin resolver",
                open_ingestion_alert_count(conn),
            )
        snapshot = diagnostic.snapshot()
        gauge("diagnostic_completed", "Diagnósticos HTTP por proceso", snapshot["completed"])
        gauge(
            "diagnostic_duration_seconds",
            "Duración acumulada de diagnósticos HTTP",
            snapshot["duration_ms_total"] / 1000,
            counter=True,
        )
        gauge(
            "diagnostic_degraded",
            "Último diagnóstico HTTP degradado",
            snapshot["status"] == "degraded",
        )
        for source in ("vigente", "historico"):
            status = ingestion_status(engine, source, now)
            attempt = status["latest_attempt"] or {}
            gauge(
                "ingestion_success_" + source,
                "Último intento exitoso; cero si ausente",
                attempt.get("status") == "succeeded",
            )
            gauge(
                "ingestion_duration_seconds_" + source,
                "Duración del último intento",
                attempt.get("duration_seconds", 0),
            )
            successful = status["latest_successful"] or {}
            timestamp = (
                datetime.fromisoformat(successful["finished_at"]).timestamp()
                if successful.get("finished_at")
                else 0
            )
            gauge(
                "ingestion_last_success_timestamp_seconds_" + source,
                "Última ingesta exitosa, Unix UTC",
                timestamp,
            )
            gauge(
                "ingestion_conditions_" + source,
                "Condiciones de alerta detectadas en este scrape",
                status["condition_count"],
            )
        return generate_latest(registry)


class MetricsMiddleware:
    def __init__(self, app, metrics):
        self.app, self.metrics = app, metrics

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        endpoint = (
            path
            if path in ENDPOINTS
            else (
                "/api/v1/price-diagnostics/{station_id}"
                if path.startswith("/api/v1/price-diagnostics/")
                else "other"
            )
        )
        if endpoint == "/metrics":
            return await self.app(scope, receive, send)
        status, start = 500, monotonic()

        async def observed(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, observed)
        finally:
            self.metrics.responses.labels(endpoint, str(status)).inc()
            self.metrics.duration.labels(endpoint).observe(max(0, monotonic() - start))
            if endpoint == "/api/v1/recommendations":
                result = scope.get("nafta2go.outcome") if status < 400 else "http_error"
                if result not in {
                    "recommended",
                    "no_feasible_stations",
                    "insufficient_coverage",
                    "http_error",
                }:
                    result = "other"
                self.metrics.queries.labels(result).inc()
