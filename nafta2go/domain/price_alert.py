"""Política provisional auditada; un desvío no demuestra un precio incorrecto."""

from decimal import Context, Decimal, localcontext

from nafta2go.ml.registry import audited_versions

POLICY_VERSION = "conservative-v1"
POLICY_METHOD = "bandera_reciente"
# Corridas auditadas para esta política según el registro de modelos (#161).
AUDITED_MODEL_VERSIONS = audited_versions(POLICY_VERSION, POLICY_METHOD)
THRESHOLDS = {
    2: Decimal("0.05424409844299347"),
    3: Decimal("0.054570259208731244"),
}
NOTICE = (
    "Regla provisional de desvío histórico: no demuestra que el precio sea incorrecto. "
    "No se midieron precisión ni sensibilidad para detectar errores reales."
)


def policy_compatible(method, model_version):
    return (
        method == POLICY_METHOD
        and isinstance(model_version, str)
        and model_version in AUDITED_MODEL_VERSIONS
    )


def provisional_alert(published, reference, product_id, method, model_version):
    """Se abstiene ante otra selección, producto o referencia no válida."""
    result = {
        "alert_level": "not_calibrated",
        "alert_policy_version": None,
        "relative_deviation": None,
        "alert_threshold": None,
        "alert_notice": NOTICE,
    }
    if (
        not policy_compatible(method, model_version)
        or type(product_id) is not int
        or product_id not in THRESHOLDS
    ):
        return result
    if any(
        not isinstance(value, Decimal) or not value.is_finite() or value <= 0
        for value in (published, reference)
    ):
        return result
    with localcontext(Context(prec=28)):
        # Comparar por multiplicación evita redondear el cociente en el empate.
        difference = abs(published - reference)
        exceeds = difference > THRESHOLDS[product_id] * reference
        deviation = difference / reference
    return result | {
        "alert_level": "provisional_deviation" if exceeds else "provisional_within_threshold",
        "alert_policy_version": POLICY_VERSION,
        "relative_deviation": str(deviation),
        "alert_threshold": str(THRESHOLDS[product_id]),
    }
