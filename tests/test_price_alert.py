"""Casos sintéticos de frontera; no miden detección de errores reales."""

from decimal import Decimal, localcontext

import pytest

from nafta2go.domain.price_alert import (
    AUDITED_MODEL_VERSIONS,
    POLICY_VERSION,
    THRESHOLDS,
    provisional_alert,
)

AUDITED = min(AUDITED_MODEL_VERSIONS)


def alert(
    published,
    reference=Decimal(100),
    product=2,
    method="bandera_reciente",
    version=AUDITED,
):
    return provisional_alert(published, reference, product, method, version)


@pytest.mark.parametrize("product", [2, 3])
@pytest.mark.parametrize("sign", [-1, 1])
def test_strict_boundary_and_both_directions(product, sign):
    boundary = Decimal(100) * (1 + sign * THRESHOLDS[product])
    assert alert(boundary, product=product)["alert_level"] == "provisional_within_threshold"
    value = alert(boundary + sign * Decimal("0.000000000001"), product=product)
    assert value["alert_level"] == "provisional_deviation"
    assert value["alert_policy_version"] == POLICY_VERSION
    assert value["alert_threshold"] == str(THRESHOLDS[product])


@pytest.mark.parametrize(
    "published,reference",
    [
        (None, Decimal(100)),
        (Decimal("NaN"), Decimal(100)),
        (Decimal(100), Decimal(0)),
        (Decimal(-1), Decimal(100)),
        (True, Decimal(100)),
        (Decimal(100), Decimal("Infinity")),
    ],
)
def test_invalid_values_abstain(published, reference):
    result = alert(published, reference)
    assert result["alert_level"] == "not_calibrated"
    assert result["relative_deviation"] is None


@pytest.mark.parametrize(
    "options", [{"version": "otra"}, {"method": "ultimo_precio"}, {"product": 9}, {"product": True}]
)
def test_only_audited_selection_has_policy(options):
    assert alert(Decimal(100), **options)["alert_policy_version"] is None


def test_decimal_context_does_not_change_decision():
    with localcontext() as context:
        context.prec = 3
        assert alert(Decimal(110))["alert_level"] == "provisional_deviation"


def test_new_audited_manifest_matches_policy_and_preserves_old_selection():
    import hashlib
    import json
    from pathlib import Path

    folder = Path(__file__).resolve().parents[1] / "docs/evidencia/actualizacion-precios-2026-11-22"
    raw = (folder / "model-manifest.json").read_bytes()
    version = hashlib.sha256(raw).hexdigest()
    model = json.loads(raw)
    assert version in AUDITED_MODEL_VERSIONS
    assert model["chosen_method"] == "bandera_reciente"
    audit = json.loads((folder / "alert-evaluation.json").read_text())
    assert audit["model_manifest_sha256"] == version
    for product in [2, 3]:
        for schedule in [2, 3]:
            assert (
                Decimal(
                    str(audit["segments"][f"{product}:{schedule}"]["relative_deviation_threshold"])
                )
                == THRESHOLDS[product]
            )
        assert alert(Decimal(110), product=product, version=version) == alert(
            Decimal(110), product=product
        )
    assert (
        alert(Decimal(110), version=version, method="ultimo_precio")["alert_policy_version"] is None
    )
    assert alert(Decimal(110), version=version[:-1] + "0")["alert_policy_version"] is None
    assert alert(Decimal(110), version={})["alert_policy_version"] is None
