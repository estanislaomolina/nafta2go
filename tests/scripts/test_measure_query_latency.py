"""La medición usa la API real en proceso y rutas guardadas; no mide calidad del entorno."""

import json
import os

import pytest

from scripts.measure_query_latency import bodies, main, measure, percentile, response_outcome


def test_percentile_uses_the_nearest_observed_rank():
    values = [float(value) for value in range(1, 101)]
    assert percentile(values, 0.95) == 95
    assert percentile(values, 0.5) == 50
    assert percentile([3.0], 0.95) == 3


class FakeResponse:
    def __init__(self, body, content_type="application/json"):
        self.headers = {"content-type": content_type}
        self.body = body

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


def test_a_response_that_is_not_json_counts_as_an_error():
    assert response_outcome(FakeResponse("Internal Server Error", "text/plain")) == "error"
    assert response_outcome(FakeResponse(ValueError("cuerpo truncado"))) == "error"
    assert response_outcome(FakeResponse(["recommended"])) == "error"
    assert response_outcome(FakeResponse({"detail": "x"})) == "error"
    assert response_outcome(FakeResponse({"outcome": "recommended"})) == "recommended"


def test_bodies_are_valid_uc01_queries_that_vary_the_vehicle():
    requests = bodies(12)
    assert all(body["destination"] for body in requests)
    assert len({body["budget_ars"] for body in requests}) == 7


def test_measure_reports_every_request_through_the_api():
    report = measure(4, warmup=1)
    assert report["requests"] == 4 and report["statuses"] == {"200": 4}
    assert sum(report["outcomes"].values()) == 4
    assert (
        0 < report["latency_s"]["p50"] <= report["latency_s"]["p95"] <= report["latency_s"]["max"]
    )
    assert "llamada real a OpenRouteService" in report["excludes"]
    assert report["audit"]["recommendations"] == 5
    assert not any(report["audit"]["fallas"].values())


def test_measure_restores_the_api_token(monkeypatch):
    monkeypatch.delenv("NAFTA2GO_API_TOKEN", raising=False)
    measure(1, warmup=0)
    assert "NAFTA2GO_API_TOKEN" not in os.environ
    monkeypatch.setenv("NAFTA2GO_API_TOKEN", "propio")
    measure(1, warmup=0)
    assert os.environ["NAFTA2GO_API_TOKEN"] == "propio"


def test_cli_writes_the_report_and_rejects_non_positive_counts(tmp_path, capsys):
    output = tmp_path / "latencia.json"
    assert main(["--requests", "2", "--output", str(output)]) == 0
    assert json.loads(output.read_text())["requests"] == 2
    capsys.readouterr()
    with pytest.raises(SystemExit):
        main(["--requests", "0"])
