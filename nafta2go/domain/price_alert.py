"""Política provisional auditada; un desvío no demuestra un precio incorrecto."""

from decimal import Context, Decimal, localcontext

POLICY_VERSION = "conservative-v1"
AUDITED_MODEL_VERSION = "91cb07a3ac0b99edd70e12b203318c1b498a1d06766011cbda5dd557852b5892"
THRESHOLDS = {
    2: Decimal("0.05424409844299347"),
    3: Decimal("0.054570259208731244"),
}
NOTICE = (
    "Regla provisional de desvío histórico: no demuestra que el precio sea incorrecto. "
    "No se midieron precisión ni sensibilidad para detectar errores reales."
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
        method != "bandera_reciente"
        or model_version != AUDITED_MODEL_VERSION
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
