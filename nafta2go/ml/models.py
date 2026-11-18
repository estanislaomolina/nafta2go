"""Modelos y referencias sobre los ejemplos temporales de precios (ADR-002, ADR-013).

Todo se expresa relativo a `prior_median`: el precio nominal cambia con la inflación y
no generaliza entre años. Los modelos aprenden una corrección sobre la referencia más
fuerte observada, el último precio propio, y nunca usan el precio objetivo como feature.
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
from threadpoolctl import threadpool_limits

# Un solo hilo: con varios, los árboles tardan decenas de veces más sobre estos tamaños
# y el orden de las sumas en paralelo deja de estar garantizado.
THREADS = 1
MAIN_BRANDS = ("YPF", "SHELL C.A.P.S.A.", "AXION")
OTHER_BRAND = "OTRA"
NUMERIC = (
    "previous_relative",
    "previous_age_days",
    "prior_iqr_relative",
    "prior_count",
    "market_change",
    "recent_relative",
    "recent_count",
    "brand_recent_relative",
    "brand_recent_count",
)
CATEGORICAL = ("brand_group", "product_id", "schedule_id", "baseline_scope")
REFERENCES = ("mediana_previa", "ultimo_precio", "bandera_reciente")
CANDIDATES = {
    "ridge": {"alpha": 1.0},
    "boosting": {
        "loss": "absolute_error",
        "max_leaf_nodes": 15,
        "learning_rate": 0.05,
        "max_iter": 300,
        "min_samples_leaf": 50,
    },
}


def examples_frame(examples: list[dict]) -> pd.DataFrame:
    """Ejemplos del dataset como tabla, con columnas relativas a la mediana previa."""
    frame = pd.json_normalize(examples)
    frame.columns = [column.removeprefix("features.") for column in frame.columns]
    frame["target_at"] = pd.to_datetime(frame.target_at_utc, utc=True)
    frame = frame.sort_values(["target_at", "source_row"]).reset_index(drop=True)
    for column in (
        "previous_station_price",
        "previous_station_age_days",
        "prior_iqr",
        "recent_median",
        "brand_recent_median",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    prior = frame.prior_median.astype(float)
    frame["target"] = np.log(frame.target_price_ars_per_l / prior)
    frame["previous_relative"] = np.log(frame.previous_station_price / prior)
    frame["previous_age_days"] = frame.previous_station_age_days
    frame["prior_iqr_relative"] = frame.prior_iqr / prior
    # Cuánto se movió la mediana desde el ejemplo anterior de la misma estación y franja.
    # Sólo entre medianas del mismo ámbito: zona contra CABA mide la diferencia entre
    # ámbitos, no un cambio del mercado.
    identity = frame.groupby(["station_id", "product_id", "schedule_id"], sort=False)
    same_scope = identity.baseline_scope.shift() == frame.baseline_scope
    frame["market_change"] = np.log(prior / identity.prior_median.shift()).where(same_scope)
    frame["recent_relative"] = np.log(frame.recent_median / prior)
    frame["brand_recent_relative"] = np.log(frame.brand_recent_median / prior)
    frame["brand_group"] = frame.brand.where(frame.brand.isin(MAIN_BRANDS), OTHER_BRAND)
    frame["reference"] = frame.previous_relative.fillna(0.0)
    return frame


def reference_predictions(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Objetivo predicho por cada referencia que no aprende nada."""
    return {
        "mediana_previa": pd.Series(0.0, index=frame.index),
        "ultimo_precio": frame.reference,
        # Mediana de la misma bandera en la última semana; sin ella, el último precio.
        "bandera_reciente": frame.brand_recent_relative.fillna(frame.reference),
    }


def build_model(name: str, seed: int) -> Pipeline:
    params = CANDIDATES[name]
    numeric, categorical = list(NUMERIC), list(CATEGORICAL)
    if name == "ridge":
        encoder = ColumnTransformer(
            [
                (
                    "numeric",
                    make_pipeline(
                        SimpleImputer(strategy="median", add_indicator=True), StandardScaler()
                    ),
                    numeric,
                ),
                ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
            ]
        )
        return make_pipeline(encoder, Ridge(**params))
    encoder = ColumnTransformer(
        [
            ("numeric", "passthrough", numeric),
            (
                "categorical",
                OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
                categorical,
            ),
        ]
    )
    categorical_positions = list(range(len(numeric), len(numeric) + len(categorical)))
    regressor = HistGradientBoostingRegressor(
        **params,
        categorical_features=categorical_positions,
        early_stopping=False,
        random_state=seed,
    )
    return make_pipeline(encoder, regressor)


def fit(model: Pipeline, frame: pd.DataFrame) -> Pipeline:
    with threadpool_limits(limits=THREADS):
        return model.fit(_inputs(frame), frame.target - frame.reference)


def predict(model: Pipeline, frame: pd.DataFrame) -> pd.Series:
    """Objetivo predicho: referencia del último precio más la corrección aprendida."""
    with threadpool_limits(limits=THREADS):
        return frame.reference + model.predict(_inputs(frame))


def metrics(frame: pd.DataFrame, predicted: pd.Series) -> dict:
    """Error en ARS/L entre el precio publicado y el precio de referencia predicho."""
    reference_price = frame.prior_median * np.exp(predicted)
    error = (frame.target_price_ars_per_l - reference_price).abs()
    return {
        "examples": len(frame),
        "mae_ars_per_l": float(error.mean()),
        "mape": float((error / frame.target_price_ars_per_l).mean()),
        "p90_ars_per_l": float(error.quantile(0.9)),
    }


def error_analysis(frame: pd.DataFrame, predicted: pd.Series) -> dict:
    """MAE por segmento, para ver dónde falla cada método y no solo el promedio."""
    error = (frame.target_price_ars_per_l - frame.prior_median * np.exp(predicted)).abs()
    change = np.log(frame.target_price_ars_per_l / frame.previous_station_price).abs()
    segments = {
        "bandera": frame.brand_group,
        "producto": frame.product_id.astype(str),
        "franja": frame.schedule_id.astype(str),
        "antiguedad_precio_previo": pd.cut(
            frame.previous_age_days,
            [-np.inf, 7, 30, np.inf],
            labels=["hasta_7_dias", "8_a_30_dias", "mas_de_30_dias"],
        )
        .astype(str)
        .replace("nan", "sin_precio_previo"),
        "cambio_sobre_precio_previo": pd.cut(
            change, [-np.inf, 0.01, 0.05, np.inf], labels=["hasta_1pct", "1_a_5pct", "mas_de_5pct"]
        )
        .astype(str)
        .replace("nan", "sin_precio_previo"),
    }
    return {
        name: {
            str(value): {"examples": int(group.size), "mae_ars_per_l": float(group.mean())}
            for value, group in error.groupby(segment, sort=True)
        }
        for name, segment in segments.items()
    }


def _inputs(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[[*NUMERIC, *CATEGORICAL]]
