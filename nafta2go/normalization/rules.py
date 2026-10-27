"""Constantes de las reglas de normalización: alcance, formatos, umbrales y motivos.

Ver docs/NORMALIZACION.md para las reglas y la evidencia de normalización.
"""

SOURCES = ("vigente", "historico")
CABA_PROVINCE = "CAPITAL FEDERAL"
NAPHTHA_PRODUCTS = {2: "super", 3: "premium"}
# El histórico trae el día primero; leerlo con el mes primero generaba fechas futuras falsas.
DATE_FORMAT = {"vigente": "%Y-%m-%d %H:%M:%S", "historico": "%d/%m/%Y %H:%M"}
KEY = ["idempresa", "idproducto", "idtipohorario", "fecha_vigencia"]
CABA_BBOX = {"lat_min": -34.71, "lat_max": -34.52, "lon_min": -58.54, "lon_max": -58.33}
# Precio atípico: más de 3 veces o menos de un tercio de la mediana del grupo (mes, tipo_nafta).
OUTLIER_RATIO = 3.0
# Con menos observaciones la mediana del grupo no sostiene una alerta.
OUTLIER_MIN_GROUP = 5
LOCAL_TIMEZONE = "America/Argentina/Buenos_Aires"
RULES_VERSION = "1"

# Motivos de rechazo: la fila no pasa a las filas válidas.
INVALID_DATE = "fecha_invalida"
FUTURE_DATE = "fecha_futura"
INCONSISTENT_YEAR_MONTH = "fecha_inconsistente_anio_mes"
INVALID_PRICE = "precio_invalido"
NON_POSITIVE_PRICE = "precio_no_positivo"
CONFLICTING_DUPLICATE = "clave_duplicada_conflicto"

# Alertas: la fila sigue entre las válidas, marcada en la columna `alertas`.
OUTLIER_PRICE = "precio_atipico"
OUTSIDE_CABA = "fuera_de_caba"
MISSING_COORDINATES = "sin_coordenadas"
ALERT_SEPARATOR = ";"
