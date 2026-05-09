# ============================================================
# MODELO DE INCIDENCIA CLIMÁTICA SOBRE FALLAS / DESCONEXIONES
# Versión ajustada para ELEMENTO_FALLA_PIVOTE_POBLADA.csv
# ============================================================

import os
import gc
import csv
import json
import warnings
from typing import Iterator, List, Dict

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    confusion_matrix,
    classification_report
)

warnings.filterwarnings("ignore")

# ============================================================
# 1. CONFIGURACIÓN
# ============================================================

CSV_PATH = r"D:\Personal\Documentos maestria\archivos de consulta\ELEMENTO_FALLA_PIVOTE_POBLADA.csv"
OUTPUT_DIR = r"D:\Personal\Documentos maestria\archivos de consulta\salidas_modelo"
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHUNK_SIZE = 800_000
BATCH_SIZE_SCORING = 400_000
RANDOM_STATE = 42

TARGET_COL = "HUBO_FALLA"
MODEL_TARGET_COL = "HUBO_FALLA_NEXT_DAY"
DATE_COL = "FECHA"
ID_COL = "ID_ACTIVO_ELECTRICO"

EXPECTED_CLIMATE_COLS = [
    "VELOCIDAD_VIENTO_MS",
    "TEMPERATURA_MEDIA_C",
    "HUMEDAD_RELATIVA_PCT",
    "TEMPERATURA_MINIMA_C",
    "TEMPERATURA_MAXIMA_C",
    "PRECIPITACION_TOTAL_MM"
]

EXPECTED_STATIC_NUMERIC_COLS = [
    "LATITUD",
    "LONGITUD",
    "ALTITUD",
    "LATITUD_NASA",
    "LONGITUD_NASA",
    "OBJECTID",
    "ORIGEN_OBJECTID",
    "ORIGEN_LATITUD",
    "ORIGEN_LONGITUD",
    "ORIGEN_ALTITUD",
    "CANTIDAD_ELEMENTOS",
    "CANTIDAD_USUARIOS",
    "ANTIGUEDAD_RED",
    "EXPANSION_RED",
    "DURACION",
    "FRECUENCIA"
]

EXPECTED_STATIC_CATEGORICAL_COLS = [
    "TIPO_ACTIVO_ELECTRICO",
    "ORIGEN_TIPO",
    "ORIGEN_UBICACION",
    "ESTADO_FALLA"
]

EXPECTED_OPTIONAL_EVENT_COLS = [
    "CANTIDAD_EVENTOS_DIA",
    "DURACION_HORAS_EVENTO",
    "ELEMENTOS_AFECTADOS",
    "USUARIOS_AFECTADOS"
]

# ============================================================
# 2. UTILIDADES DE COLUMNAS
# ============================================================

def clean_colname(col: str) -> str:
    if col is None:
        return ""
    col = str(col).replace("\ufeff", "").strip()
    return " ".join(col.split())


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [clean_colname(c) for c in df.columns]
    return df


def standardize_colname_for_match(col: str) -> str:
    c = clean_colname(col).upper()
    return c.replace(" ", "").replace("-", "").replace(".", "").replace("/", "_")


def build_column_mapping(real_columns: List[str]) -> Dict[str, str]:
    normalized = {standardize_colname_for_match(c): c for c in real_columns}

    alias_groups = {
        "ID_ACTIVO_ELECTRICO": [
            "ID_ACTIVO_ELECTRICO",
            "IDACTIVOELECTRICO",
            "ELEMENTO",
            "ID_ELEMENTO",
            "ACTIVO_ELECTRICO"
        ],
        "FECHA": ["FECHA", "FECHAHORA", "FECHA_HORA", "DATE"],
        "HUBO_FALLA": ["HUBO_FALLA", "HUBOFALLA", "FALLA", "TIENE_FALLA", "EVENTO_FALLA"],

        "VELOCIDAD_VIENTO_MS": ["VELOCIDAD_VIENTO_MS", "VELOCIDADVIENTOMS", "WS2M"],
        "TEMPERATURA_MEDIA_C": ["TEMPERATURA_MEDIA_C", "TEMPERATURAMEDIAC", "T2M"],
        "HUMEDAD_RELATIVA_PCT": ["HUMEDAD_RELATIVA_PCT", "HUMEDADRELATIVAPCT", "RH2M"],
        "TEMPERATURA_MINIMA_C": ["TEMPERATURA_MINIMA_C", "TEMPERATURAMINIMAC", "T2M_MIN"],
        "TEMPERATURA_MAXIMA_C": ["TEMPERATURA_MAXIMA_C", "TEMPERATURAMAXIMAC", "T2M_MAX"],
        "PRECIPITACION_TOTAL_MM": ["PRECIPITACION_TOTAL_MM", "PRECIPITACIONTOTALMM", "PRECTOT"],

        "TIPO_ACTIVO_ELECTRICO": ["TIPO_ACTIVO_ELECTRICO", "TIPOACTIVOELECTRICO", "TIPO"],
        "ORIGEN_TIPO": ["ORIGEN_TIPO", "ORIGENTIPO"],
        "ORIGEN_UBICACION": ["ORIGEN_UBICACION", "ORIGENUBICACION", "UBICACION", "UBICACIÓN"],
        "ESTADO_FALLA": ["ESTADO_FALLA", "ESTADOFALLA"],

        "LATITUD": ["LATITUD"],
        "LONGITUD": ["LONGITUD"],
        "ALTITUD": ["ALTITUD"],
        "LATITUD_NASA": ["LATITUD_NASA", "LATITUDNASA"],
        "LONGITUD_NASA": ["LONGITUD_NASA", "LONGITUDNASA"],
        "OBJECTID": ["OBJECTID"],
        "ORIGEN_OBJECTID": ["ORIGEN_OBJECTID", "ORIGENOBJECTID"],
        "ORIGEN_LATITUD": ["ORIGEN_LATITUD", "ORIGENLATITUD"],
        "ORIGEN_LONGITUD": ["ORIGEN_LONGITUD", "ORIGENLONGITUD"],
        "ORIGEN_ALTITUD": ["ORIGEN_ALTITUD", "ORIGENALTITUD"],

        "CANTIDAD_ELEMENTOS": ["CANTIDAD_ELEMENTOS", "CANTIDADELEMENTOS"],
        "CANTIDAD_USUARIOS": ["CANTIDAD_USUARIOS", "CANTIDADUSUARIOS"],
        "ANTIGUEDAD_RED": ["ANTIGUEDAD_RED", "ANTIGÜEDAD_RED", "ANTIGUEDADRED"],
        "EXPANSION_RED": ["EXPANSION_RED", "EXPANSIÓN_RED", "EXPANSIONRED"],
        "DURACION": ["DURACION", "DURACIÓN"],
        "FRECUENCIA": ["FRECUENCIA"],

        "CANTIDAD_EVENTOS_DIA": ["CANTIDAD_EVENTOS_DIA", "CANTIDADEVENTOSDIA"],
        "DURACION_HORAS_EVENTO": ["DURACION_HORAS_EVENTO", "DURACIONHORASEVENTO"],
        "ELEMENTOS_AFECTADOS": ["ELEMENTOS_AFECTADOS", "ELEMENTOSAFECTADOS"],
        "USUARIOS_AFECTADOS": ["USUARIOS_AFECTADOS", "USUARIOSAFECTADOS"]
    }

    mapping = {}
    for canonical, aliases in alias_groups.items():
        for alias in aliases:
            alias_norm = standardize_colname_for_match(alias)
            if alias_norm in normalized:
                mapping[normalized[alias_norm]] = canonical
                break

    return mapping

# ============================================================
# 3. LECTORES ROBUSTOS
# ============================================================

def iter_standard_csv(path: str, sep: str, chunk_size: int = 300_000) -> Iterator[pd.DataFrame]:
    for chunk in pd.read_csv(
        path,
        sep=sep,
        chunksize=chunk_size,
        encoding="utf-8-sig",
        low_memory=False
    ):
        yield chunk


def iter_weird_csv(path: str, chunk_size: int = 300_000) -> Iterator[pd.DataFrame]:
    rows = []

    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        header_line = next(f).rstrip("\n")
        header = next(csv.reader([header_line]))
        header = [clean_colname(h) for h in header]

        for line in f:
            line = line.rstrip("\n")

            if line.startswith('"') and line.endswith('"'):
                line = line[1:-1].replace('""', '"')

            rows.append(next(csv.reader([line])))

            if len(rows) >= chunk_size:
                yield pd.DataFrame(rows, columns=header)
                rows = []

        if rows:
            yield pd.DataFrame(rows, columns=header)


def detect_reader(path: str) -> str:
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        first_line = f.readline().strip()
        second_line = f.readline().strip()

    if ";" in first_line:
        return "semicolon"
    if "," in first_line:
        return "comma"
    if second_line.startswith('"') and second_line.endswith('"'):
        return "weird"

    return "comma"


def get_chunk_iterator(path: str, chunk_size: int = 300_000) -> Iterator[pd.DataFrame]:
    mode = detect_reader(path)
    print(f"Modo de lectura detectado: {mode}")

    if mode == "semicolon":
        return iter_standard_csv(path, sep=";", chunk_size=chunk_size)
    elif mode == "comma":
        return iter_standard_csv(path, sep=",", chunk_size=chunk_size)
    else:
        return iter_weird_csv(path, chunk_size=chunk_size)

# ============================================================
# 4. UTILIDADES DE DATOS
# ============================================================

def safe_to_numeric(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def reduce_memory_usage(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if pd.api.types.is_integer_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], downcast="integer")
        elif pd.api.types.is_float_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], downcast="float")
    return df


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    df["ANIO"] = df[DATE_COL].dt.year
    df["MES"] = df[DATE_COL].dt.month
    df["DIA"] = df[DATE_COL].dt.day
    df["DIA_SEMANA"] = df[DATE_COL].dt.dayofweek
    df["ES_FIN_SEMANA"] = (df["DIA_SEMANA"] >= 5).astype("int8")
    df["TRIMESTRE"] = df[DATE_COL].dt.quarter
    return df


def add_climate_features(df: pd.DataFrame) -> pd.DataFrame:
    if "TEMPERATURA_MAXIMA_C" in df.columns and "TEMPERATURA_MINIMA_C" in df.columns:
        df["AMPLITUD_TERMICA"] = df["TEMPERATURA_MAXIMA_C"] - df["TEMPERATURA_MINIMA_C"]

    if "PRECIPITACION_TOTAL_MM" in df.columns:
        df["LLUVIA_BINARIA"] = (df["PRECIPITACION_TOTAL_MM"] > 0).astype("int8")
        df["LLUVIA_INTENSA"] = (df["PRECIPITACION_TOTAL_MM"] >= 10).astype("int8")

    if "VELOCIDAD_VIENTO_MS" in df.columns:
        df["VIENTO_ALTO"] = (df["VELOCIDAD_VIENTO_MS"] >= 5).astype("int8")

    return df


def add_severity_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Crea variables de severidad descriptiva.
    Las variables originales del mismo día se excluyen del modelo para evitar fuga.
    Sus rezagos sí pueden usarse porque representan historia previa.
    """

    if "USUARIOS_AFECTADOS" in df.columns:
        df["USUARIOS_AFECTADOS"] = pd.to_numeric(df["USUARIOS_AFECTADOS"], errors="coerce").fillna(0)

    if "ELEMENTOS_AFECTADOS" in df.columns:
        df["ELEMENTOS_AFECTADOS"] = pd.to_numeric(df["ELEMENTOS_AFECTADOS"], errors="coerce").fillna(0)

    if "USUARIOS_AFECTADOS" in df.columns and "CANTIDAD_ELEMENTOS" in df.columns:
        df["SEVERIDAD_USUARIOS_ELEMENTO"] = (
            df["USUARIOS_AFECTADOS"] / (df["CANTIDAD_ELEMENTOS"].replace(0, np.nan))
        ).replace([np.inf, -np.inf], np.nan).fillna(0)

    if "ELEMENTOS_AFECTADOS" in df.columns and "CANTIDAD_ELEMENTOS" in df.columns:
        df["SEVERIDAD_ELEMENTOS_ELEMENTO"] = (
            df["ELEMENTOS_AFECTADOS"] / (df["CANTIDAD_ELEMENTOS"].replace(0, np.nan))
        ).replace([np.inf, -np.inf], np.nan).fillna(0)

    return df


def add_lag_features(df: pd.DataFrame, group_col: str, date_col: str, climate_cols: List[str]) -> pd.DataFrame:
    df = df.sort_values([group_col, date_col]).copy()

    # ============================================================
    # ESTRÉS ACUMULADO POR VARIABLE
    # ============================================================

    stress_cols = [
        "PRECIPITACION_TOTAL_MM",
        "HUMEDAD_RELATIVA_PCT",
        "VELOCIDAD_VIENTO_MS",
        "TEMPERATURA_MEDIA_C"
    ]

    for col in stress_cols:
        if col in df.columns:
            for window in [3, 7, 15]:
                df[f"{col}_STRESS_{window}D"] = (
                    df.groupby(group_col)[col]
                    .transform(lambda s: s.shift(1).rolling(window, min_periods=1).sum())
                )

    # ============================================================
    # ÍNDICE DE ESTRÉS COMBINADO
    # ============================================================

    stress_components = []

    for col in [
        "PRECIPITACION_TOTAL_MM_STRESS_7D",
        "HUMEDAD_RELATIVA_PCT_STRESS_7D",
        "VELOCIDAD_VIENTO_MS_STRESS_7D"
    ]:
        if col in df.columns:
            stress_components.append(df[col])

    if len(stress_components) > 0:
        df["STRESS_TOTAL_7D"] = sum(stress_components)

    # ============================================================
    # LAGS CLIMÁTICOS
    # ============================================================

    for col in climate_cols:
        if col in df.columns:
            for lag in [1, 3, 7]:
                df[f"{col}_LAG_{lag}"] = df.groupby(group_col)[col].shift(lag)

    # ============================================================
    # HISTÓRICO DE FALLAS
    # ============================================================

    if TARGET_COL in df.columns:
        df["FALLA_LAG_1"] = df.groupby(group_col)[TARGET_COL].shift(1)

        df["FALLA_ULT_7D"] = (
            df.groupby(group_col)[TARGET_COL]
            .transform(lambda s: s.shift(1).rolling(7, min_periods=1).sum())
        )

        df["FALLA_ULT_15D"] = (
            df.groupby(group_col)[TARGET_COL]
            .transform(lambda s: s.shift(1).rolling(15, min_periods=1).sum())
        )

    # ============================================================
    # HISTÓRICO DE SEVERIDAD
    # ============================================================

    severity_cols = [
        "USUARIOS_AFECTADOS",
        "ELEMENTOS_AFECTADOS",
        "SEVERIDAD_USUARIOS_ELEMENTO",
        "SEVERIDAD_ELEMENTOS_ELEMENTO"
    ]

    for col in severity_cols:
        if col in df.columns:
            df[f"{col}_LAG_1"] = df.groupby(group_col)[col].shift(1)

            df[f"{col}_ULT_7D"] = (
                df.groupby(group_col)[col]
                .transform(lambda s: s.shift(1).rolling(7, min_periods=1).sum())
            )

            df[f"{col}_ULT_15D"] = (
                df.groupby(group_col)[col]
                .transform(lambda s: s.shift(1).rolling(15, min_periods=1).sum())
            )

    # ============================================================
    # TARGET FUTURO
    # ============================================================

    df[MODEL_TARGET_COL] = df.groupby(group_col)[TARGET_COL].shift(-1)

    return df


def evaluate_model(model, X_test, y_test, model_name: str) -> Dict:
    if hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X_test)[:, 1]
    else:
        y_prob = 1 / (1 + np.exp(-model.decision_function(X_test)))

    y_pred = (y_prob >= 0.5).astype(int)

    metrics = {
        "modelo": model_name,
        "roc_auc": float(roc_auc_score(y_test, y_prob)),
        "pr_auc": float(average_precision_score(y_test, y_prob)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0))
    }

    print(f"\n===== {model_name} =====")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    print("\nMatriz de confusión:")
    print(confusion_matrix(y_test, y_pred))
    print("\nReporte:")
    print(classification_report(y_test, y_pred, zero_division=0))

    return metrics


def month_name_es(m: int) -> str:
    nombres = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }
    return nombres.get(int(m), str(m))


def find_best_cyclic_windows(monthly_df: pd.DataFrame, value_col: str, window_sizes=(2, 3, 4)) -> pd.DataFrame:
    base = monthly_df.sort_values("MES")[["MES", value_col]].copy().reset_index(drop=True)

    if len(base) != 12:
        return pd.DataFrame()

    doubled = pd.concat([base, base], ignore_index=True)

    rows = []
    for w in window_sizes:
        for s in range(12):
            window = doubled.iloc[s:s+w]
            meses = window["MES"].tolist()

            rows.append({
                "window_size": w,
                "meses": "-".join(str(int(m)) for m in meses),
                "meses_nombre": " - ".join(month_name_es(m) for m in meses),
                "score_mean": window[value_col].mean(),
                "score_sum": window[value_col].sum()
            })

    return pd.DataFrame(rows).sort_values(["window_size", "score_mean"], ascending=[True, False])


def agg_risk(group_df: pd.DataFrame, group_cols):
    return (
        group_df.groupby(group_cols)
        .agg(
            probabilidad_media=("prob_falla", "mean"),
            probabilidad_pico=("prob_falla", "max"),
            ocurrencia_real=(MODEL_TARGET_COL, "mean")
        )
        .reset_index()
    )


def score_in_batches(
    df_full: pd.DataFrame,
    feature_cols: List[str],
    model_logit,
    model_hgb,
    fitted_preprocessor,
    best_model_name: str,
    batch_size: int = 200_000
) -> pd.DataFrame:
    parts = []
    n = len(df_full)

    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        print(f"  Scoring filas {start:,} - {end:,} de {n:,}...")

        batch = df_full.iloc[start:end].copy()
        batch_X = batch.reindex(columns=feature_cols, fill_value=np.nan)

        for col in batch_X.select_dtypes(include="object").columns:
            batch_X[col] = batch_X[col].astype(str)

        if best_model_name == "HistGradientBoosting":
            batch_probs = model_hgb.predict_proba(
                fitted_preprocessor.transform(batch_X)
            )[:, 1]
        else:
            batch_probs = model_logit.predict_proba(batch_X)[:, 1]

        keep_cols = [c for c in [ID_COL, DATE_COL, "ANIO", "MES", "TRIMESTRE"] if c in batch.columns]
        out = batch[keep_cols].copy()
        out["prob_falla"] = batch_probs
        out[MODEL_TARGET_COL] = batch[MODEL_TARGET_COL].values if MODEL_TARGET_COL in batch.columns else np.nan

        parts.append(out)

        del batch, batch_X, batch_probs, out
        gc.collect()

    return pd.concat(parts, ignore_index=True)


# ============================================================
# 5. CARGA Y PREPARACIÓN
# ============================================================

def load_and_prepare_dataset(csv_path: str, chunk_size: int = 300_000) -> pd.DataFrame:
    prepared_chunks = []
    total_rows = 0

    for i, chunk in enumerate(get_chunk_iterator(csv_path, chunk_size=chunk_size), start=1):
        if i == 1 or i % 50 == 0:
            print(f"\nLeyendo bloque {i}...")

        chunk = normalize_columns(chunk)

        if i == 1:
            print("Columnas originales detectadas:")
            print(chunk.columns.tolist())

        mapping = build_column_mapping(chunk.columns.tolist())
        chunk = chunk.rename(columns=mapping)

        if i == 1:
            print("\nMapeo detectado:")
            print(mapping)
            print("\nColumnas luego del renombre:")
            print(chunk.columns.tolist())

        required = [ID_COL, DATE_COL, TARGET_COL]
        missing = [c for c in required if c not in chunk.columns]

        if missing:
            raise ValueError(
                f"Columnas obligatorias faltantes: {missing}\n"
                f"Disponibles: {chunk.columns.tolist()}"
            )

        candidate_cols = (
            [ID_COL, DATE_COL, TARGET_COL]
            + EXPECTED_CLIMATE_COLS
            + EXPECTED_STATIC_NUMERIC_COLS
            + EXPECTED_STATIC_CATEGORICAL_COLS
            + EXPECTED_OPTIONAL_EVENT_COLS
        )

        chunk = chunk[[c for c in candidate_cols if c in chunk.columns]].copy()

        numeric_candidates = [
            TARGET_COL,
            "CANTIDAD_EVENTOS_DIA",
            "DURACION_HORAS_EVENTO",
            "ELEMENTOS_AFECTADOS",
            "USUARIOS_AFECTADOS",
            "SEVERIDAD_USUARIOS_ELEMENTO",
            "SEVERIDAD_ELEMENTOS_ELEMENTO",
            "LATITUD",
            "LONGITUD",
            "ALTITUD",
            "CANTIDAD_ELEMENTOS",
            "CANTIDAD_USUARIOS",
            "ANTIGUEDAD_RED",
            "EXPANSION_RED",
            "VELOCIDAD_VIENTO_MS",
            "TEMPERATURA_MEDIA_C",
            "HUMEDAD_RELATIVA_PCT",
            "TEMPERATURA_MINIMA_C",
            "TEMPERATURA_MAXIMA_C",
            "PRECIPITACION_TOTAL_MM",
            "OBJECTID",
            "ELEMENTO_X",
            "ELEMENTO_Y"
        ]

        chunk = safe_to_numeric(chunk, [c for c in numeric_candidates if c in chunk.columns])
        chunk[DATE_COL] = pd.to_datetime(chunk[DATE_COL], errors="coerce")

        if chunk[TARGET_COL].dtype == object:
            chunk[TARGET_COL] = (
                chunk[TARGET_COL]
                .astype(str)
                .str.strip()
                .str.lower()
                .replace({
                    "si": 1,
                    "sí": 1,
                    "true": 1,
                    "verdadero": 1,
                    "no": 0,
                    "false": 0,
                    "falso": 0
                })
            )
            chunk[TARGET_COL] = pd.to_numeric(chunk[TARGET_COL], errors="coerce")

        chunk = chunk.dropna(subset=[ID_COL, DATE_COL, TARGET_COL]).copy()
        chunk[TARGET_COL] = chunk[TARGET_COL].astype("int8")

        chunk = add_time_features(chunk)
        chunk = add_climate_features(chunk)
        chunk = add_severity_features(chunk)

        prepared_chunks.append(chunk)
        total_rows += len(chunk)

        if i == 1 or i % 50 == 0:
            print(f"Filas válidas acumuladas: {total_rows:,}")

        del chunk
        gc.collect()

    if not prepared_chunks:
        raise ValueError("No se pudieron cargar bloques válidos del archivo.")

    df = pd.concat(prepared_chunks, ignore_index=True)
    del prepared_chunks
    gc.collect()

    df = reduce_memory_usage(df)
    df = df.sort_values([ID_COL, DATE_COL]).reset_index(drop=True)

    climate_cols_present = [c for c in EXPECTED_CLIMATE_COLS if c in df.columns]
    df = add_lag_features(df, ID_COL, DATE_COL, climate_cols_present)

    return df


# ============================================================
# 6. PROCESO PRINCIPAL
# ============================================================

print("Preparando dataset...")
df = load_and_prepare_dataset(CSV_PATH, chunk_size=CHUNK_SIZE)

df.dropna(subset=[MODEL_TARGET_COL], inplace=True)
df[MODEL_TARGET_COL] = df[MODEL_TARGET_COL].astype("int8")
gc.collect()

print("\nDimensión final:")
print(df.shape)

print("\nRango de fechas:")
print(f"{df[DATE_COL].min()} -> {df[DATE_COL].max()}")

print("\nDistribución de la variable objetivo original (conteos):")
print(df[TARGET_COL].value_counts(dropna=False))

print("\nDistribución de la variable objetivo original (proporciones):")
print(df[TARGET_COL].value_counts(normalize=True, dropna=False))

print(f"\nDistribución del target de modelado ({MODEL_TARGET_COL}) - conteos:")
print(df[MODEL_TARGET_COL].value_counts(dropna=False))

print(f"\nDistribución del target de modelado ({MODEL_TARGET_COL}) - proporciones:")
print(df[MODEL_TARGET_COL].value_counts(normalize=True, dropna=False))

diag = pd.DataFrame({
    "columna": df.columns,
    "dtype": [str(df[c].dtype) for c in df.columns],
    "nulos": [df[c].isna().sum() for c in df.columns],
    "pct_nulos": [df[c].isna().mean() * 100 for c in df.columns],
    "n_unicos": [df[c].nunique(dropna=True) for c in df.columns]
})

diag.to_csv(
    os.path.join(OUTPUT_DIR, "diagnostico_columnas.csv"),
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# 7. MUESTREO BALANCEADO
# ============================================================

df_pos = df.loc[df[MODEL_TARGET_COL] == 1]
df_neg = df.loc[df[MODEL_TARGET_COL] == 0]
gc.collect()

if len(df_pos) > 0:
    n_neg = min(len(df_neg), len(df_pos) * 4)
    df_neg_smp = df_neg.sample(n=n_neg, random_state=RANDOM_STATE)
    df_model = pd.concat([df_pos, df_neg_smp], ignore_index=True)
else:
    df_model = df.sample(min(len(df), 500_000), random_state=RANDOM_STATE).copy()

df_model = df_model.sort_values(DATE_COL).reset_index(drop=True)

print("\nDimensión muestra de modelado:")
print(df_model.shape)

print("\nDistribución target en muestra:")
print(df_model[MODEL_TARGET_COL].value_counts())
print(df_model[MODEL_TARGET_COL].value_counts(normalize=True))


# ============================================================
# 8. SPLIT TEMPORAL
# ============================================================

cut_date = df_model[DATE_COL].quantile(0.70)

train_df = df_model.loc[df_model[DATE_COL] <= cut_date]
test_df = df_model.loc[df_model[DATE_COL] > cut_date]
gc.collect()

print("\nFecha de corte temporal:", cut_date)
print("Train:", train_df.shape)
print("Test :", test_df.shape)


# ============================================================
# 9. VARIABLES
# ============================================================

exclude_cols = {
    TARGET_COL,
    MODEL_TARGET_COL,
    DATE_COL,
    "ESTADO_FALLA",
    "CANTIDAD_EVENTOS_DIA",
    "DURACION_HORAS_EVENTO",
    "ELEMENTOS_AFECTADOS",
    "USUARIOS_AFECTADOS",
    "IDS_EVENTO",
    "FECHA_DESCONEXION_MIN",
    "FECHA_CONEXION_MAX",
    "UBICACION",
    "ORIGEN_UBICACION"
}

feature_cols = [c for c in df_model.columns if c not in exclude_cols]

X_train = train_df[feature_cols].copy()
y_train = train_df[MODEL_TARGET_COL].copy()

X_test = test_df[feature_cols].copy()
y_test = test_df[MODEL_TARGET_COL].copy()

for col in X_train.select_dtypes(include="object").columns:
    X_train[col] = X_train[col].astype(str)
    X_test[col] = X_test[col].astype(str)

numeric_cols = X_train.select_dtypes(include=[np.number]).columns.tolist()
categorical_cols = [
    c for c in X_train.select_dtypes(include=["object", "category"]).columns
    if c != ID_COL
]

print("\nNuméricas:", len(numeric_cols))
print("Categóricas:", len(categorical_cols))


# ============================================================
# 10. PREPROCESAMIENTO
# ============================================================

preprocessor = ColumnTransformer(
    transformers=[
        (
            "num",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler())
            ]),
            numeric_cols
        ),
        (
            "cat",
            Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
            ]),
            categorical_cols
        ),
    ],
    remainder="drop"
)


# ============================================================
# 11. MODELO 1 - REGRESIÓN LOGÍSTICA
# ============================================================

logit_model = Pipeline(steps=[
    ("preprocessor", preprocessor),
    ("classifier", LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        random_state=RANDOM_STATE
    ))
])

print("\nEntrenando regresión logística...")
logit_model.fit(X_train, y_train)

metrics_logit = evaluate_model(logit_model, X_test, y_test, "LogisticRegression")


# ============================================================
# 12. MODELO 2 - HIST GRADIENT BOOSTING
# ============================================================

fitted_preprocessor = logit_model.named_steps["preprocessor"]

X_train_trans = fitted_preprocessor.transform(X_train)
X_test_trans = fitted_preprocessor.transform(X_test)

hgb_model = HistGradientBoostingClassifier(
    learning_rate=0.05,
    max_iter=300,
    max_depth=8,
    min_samples_leaf=50,
    l2_regularization=0.1,
    random_state=RANDOM_STATE
)

print("\nEntrenando HistGradientBoostingClassifier...")
hgb_model.fit(X_train_trans, y_train)

metrics_hgb = evaluate_model(hgb_model, X_test_trans, y_test, "HistGradientBoosting")


# ============================================================
# 13. COMPARACIÓN Y MEJOR MODELO
# ============================================================

results_df = pd.DataFrame([metrics_logit, metrics_hgb]).sort_values(
    ["pr_auc", "roc_auc"],
    ascending=False
)

results_df.to_csv(
    os.path.join(OUTPUT_DIR, "metricas_modelos.csv"),
    index=False,
    encoding="utf-8-sig"
)

print("\nResumen métricas:")
print(results_df)

best_model_name = results_df.iloc[0]["modelo"]
print(f"\nMejor modelo: {best_model_name}")


# ============================================================
# 14. IMPORTANCIA DE VARIABLES
# ============================================================

feature_names = fitted_preprocessor.get_feature_names_out()
coefs = logit_model.named_steps["classifier"].coef_[0]
n_f = min(len(feature_names), len(coefs))

importance_df = pd.DataFrame({
    "feature": feature_names[:n_f],
    "coef": coefs[:n_f],
    "importance_abs": np.abs(coefs[:n_f])
}).sort_values("importance_abs", ascending=False)

importance_df.to_csv(
    os.path.join(OUTPUT_DIR, "importancia_variables.csv"),
    index=False,
    encoding="utf-8-sig"
)

print("\nTop 20 variables importantes:")
print(importance_df.head(20))


# ============================================================
# 15. PREDICCIONES EN TEST
# ============================================================

if best_model_name == "HistGradientBoosting":
    y_prob_test = hgb_model.predict_proba(X_test_trans)[:, 1]
else:
    y_prob_test = logit_model.predict_proba(X_test)[:, 1]

preds = test_df[[ID_COL, DATE_COL]].copy()
preds["y_true"] = y_test.values
preds["prob_falla"] = y_prob_test
preds["pred_05"] = (y_prob_test >= 0.5).astype(int)

preds.to_csv(
    os.path.join(OUTPUT_DIR, "predicciones_test.csv"),
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# 16. RESUMEN PARCIAL
# ============================================================

summary = {
    "csv_path": CSV_PATH,
    "n_total_registros": int(len(df)),
    "n_modelado": int(len(df_model)),
    "fecha_min": str(df[DATE_COL].min()),
    "fecha_max": str(df[DATE_COL].max()),
    "tasa_falla_original": float(df[TARGET_COL].mean()),
    "tasa_falla_modelada_next_day": float(df[MODEL_TARGET_COL].mean()),
    "mejor_modelo": best_model_name,
    "metricas": results_df.to_dict(orient="records"),
    "top_variables": importance_df.head(15).to_dict(orient="records")
}

with open(os.path.join(OUTPUT_DIR, "resumen_modelo.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)


# ============================================================
# 17. SCORING COMPLETO POR BLOQUES
# ============================================================

print("\nGenerando scoring para todos los datos por bloques...")

df_scoring = score_in_batches(
    df_full=df,
    feature_cols=feature_cols,
    model_logit=logit_model,
    model_hgb=hgb_model,
    fitted_preprocessor=fitted_preprocessor,
    best_model_name=best_model_name,
    batch_size=BATCH_SIZE_SCORING
)

df_scoring.to_csv(
    os.path.join(OUTPUT_DIR, "scoring_completo.csv"),
    index=False,
    encoding="utf-8-sig"
)

print(f"Scoring completo: {len(df_scoring):,} filas.")

# ============================================================
# 18. RANKING DE ELEMENTOS POR RIESGO
# ============================================================

print("\nConstruyendo ranking de riesgo por elemento...")

ranking_elementos = (
    df_scoring.groupby(ID_COL)
    .agg(
        PROB_FALLA_PROMEDIO=("prob_falla", "mean"),
        PROB_FALLA_MAX=("prob_falla", "max"),
        TOTAL_REGISTROS=(ID_COL, "count"),
        OCURRENCIA_REAL=(MODEL_TARGET_COL, "mean")
    )
    .reset_index()
)

fallas_reales = (
    df.groupby(ID_COL)
    .agg(
        TOTAL_FALLAS=(TARGET_COL, "sum"),
        USUARIOS_AFECTADOS_TOTAL=("USUARIOS_AFECTADOS", "sum"),
        ELEMENTOS_AFECTADOS_TOTAL=("ELEMENTOS_AFECTADOS", "sum")
    )
    .reset_index()
)

ranking_elementos = ranking_elementos.merge(
    fallas_reales,
    on=ID_COL,
    how="left"
)

ranking_elementos["RIESGO_RELATIVO"] = (
    ranking_elementos["PROB_FALLA_PROMEDIO"] *
    np.log1p(ranking_elementos["TOTAL_FALLAS"] + 1)
)

ranking_elementos = ranking_elementos.sort_values(
    by="RIESGO_RELATIVO",
    ascending=False
)

ranking_elementos.to_csv(
    os.path.join(OUTPUT_DIR, "ranking_elementos_riesgo.csv"),
    index=False,
    encoding="utf-8-sig"
)

print("\nTop 20 elementos con mayor riesgo:")
print(ranking_elementos.head(20))

# ============================================================
# 19. RANKING DE EVENTOS CRÍTICOS
# ============================================================

print("\nCalculando eventos más críticos...")

eventos_criticos = df[df["HUBO_FALLA"] == 1].copy()

eventos_criticos["SEVERIDAD_EVENTO"] = (
    eventos_criticos["USUARIOS_AFECTADOS"] /
    (eventos_criticos["ELEMENTOS_AFECTADOS"] + 1)
)

eventos_criticos = eventos_criticos.sort_values(
    by="SEVERIDAD_EVENTO",
    ascending=False
)

print("\nTop 20 eventos más críticos:")
print(eventos_criticos[
    [
        ID_COL,
        "FECHA",
        "USUARIOS_AFECTADOS",
        "ELEMENTOS_AFECTADOS",
        "SEVERIDAD_EVENTO"
    ]
].head(20))


# ============================================================
# 20. ANÁLISIS DE VARIABLES CLIMÁTICAS EN FALLAS
# ============================================================

print("\nAnalizando condiciones climáticas en fallas...")

clima_cols = [
    "VELOCIDAD_VIENTO_MS",
    "TEMPERATURA_MEDIA_C",
    "HUMEDAD_RELATIVA_PCT",
    "PRECIPITACION_TOTAL_MM"
]

df_fallas = df[df["HUBO_FALLA"] == 1]
df_no_fallas = df[df["HUBO_FALLA"] == 0]

comparacion_clima = []

for col in clima_cols:
    if col in df.columns:
        comparacion_clima.append({
            "VARIABLE": col,
            "MEDIA_FALLA": df_fallas[col].mean(),
            "MEDIA_NO_FALLA": df_no_fallas[col].mean(),
            "DIFERENCIA": df_fallas[col].mean() - df_no_fallas[col].mean()
        })

comparacion_clima = pd.DataFrame(comparacion_clima)

print("\nComparación clima fallas vs no fallas:")
print(comparacion_clima)


# ============================================================
# 21. EXPORTAR RESULTADOS
# ============================================================

print("\nGuardando resultados...")

output_dir = os.path.dirname(CSV_PATH)

ranking_path = os.path.join(output_dir, "ranking_elementos_riesgo.csv")
eventos_path = os.path.join(output_dir, "eventos_criticos.csv")
clima_path = os.path.join(output_dir, "analisis_clima_fallas.csv")

ranking_elementos.to_csv(ranking_path, index=False)
eventos_criticos.to_csv(eventos_path, index=False)
comparacion_clima.to_csv(clima_path, index=False)

print("\nArchivos generados:")
print(" -", ranking_path)
print(" -", eventos_path)
print(" -", clima_path)


# ============================================================
# 22. CONCLUSIONES AUTOMÁTICAS (AYUDA TESIS)
# ============================================================

print("\n=== INSIGHTS AUTOMÁTICOS ===")

top_riesgo = ranking_elementos.iloc[0]

print(f"\nElemento con mayor riesgo: {top_riesgo[ID_COL]}")
print(f"Probabilidad promedio: {top_riesgo['PROB_FALLA_PROMEDIO']:.4f}")
print(f"Total fallas: {int(top_riesgo['TOTAL_FALLAS'])}")

top_evento = eventos_criticos.iloc[0]

print("\nEvento más crítico:")
print(f"Elemento: {top_evento[ID_COL]}")
print(f"Usuarios afectados: {int(top_evento['USUARIOS_AFECTADOS'])}")
print(f"Severidad: {top_evento['SEVERIDAD_EVENTO']:.2f}")

if not comparacion_clima.empty:
    var_mayor = comparacion_clima.sort_values(
        by="DIFERENCIA",
        ascending=False
    ).iloc[0]

    print("\nVariable climática más asociada a fallas:")
    print(f"{var_mayor['VARIABLE']} (diferencia: {var_mayor['DIFERENCIA']:.2f})")

print("\n=== FIN DEL PROCESO ===")