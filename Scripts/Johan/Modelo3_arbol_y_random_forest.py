# ============================================================
# MODELOS ÁRBOL DE DECISIÓN Y RANDOM FOREST
# Incidencia climática sobre fallas eléctricas
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
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.ensemble import RandomForestClassifier
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
OUTPUT_DIR = r"D:\Personal\Documentos maestria\archivos de consulta\salidas_modelo_arbol_rf"
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHUNK_SIZE = 800_000
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
# 2. FUNCIONES AUXILIARES
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
        "ID_ACTIVO_ELECTRICO": ["ID_ACTIVO_ELECTRICO", "IDACTIVOELECTRICO", "ELEMENTO"],
        "FECHA": ["FECHA", "FECHAHORA", "FECHA_HORA"],
        "HUBO_FALLA": ["HUBO_FALLA", "HUBOFALLA", "FALLA"],

        "VELOCIDAD_VIENTO_MS": ["VELOCIDAD_VIENTO_MS", "VELOCIDADVIENTOMS", "WS2M"],
        "TEMPERATURA_MEDIA_C": ["TEMPERATURA_MEDIA_C", "TEMPERATURAMEDIAC", "T2M"],
        "HUMEDAD_RELATIVA_PCT": ["HUMEDAD_RELATIVA_PCT", "HUMEDADRELATIVAPCT", "RH2M"],
        "TEMPERATURA_MINIMA_C": ["TEMPERATURA_MINIMA_C", "TEMPERATURAMINIMAC", "T2M_MIN"],
        "TEMPERATURA_MAXIMA_C": ["TEMPERATURA_MAXIMA_C", "TEMPERATURAMAXIMAC", "T2M_MAX"],
        "PRECIPITACION_TOTAL_MM": ["PRECIPITACION_TOTAL_MM", "PRECIPITACIONTOTALMM", "PRECTOT"],

        "TIPO_ACTIVO_ELECTRICO": ["TIPO_ACTIVO_ELECTRICO", "TIPOACTIVOELECTRICO", "TIPO"],
        "ORIGEN_TIPO": ["ORIGEN_TIPO", "ORIGENTIPO"],
        "ORIGEN_UBICACION": ["ORIGEN_UBICACION", "ORIGENUBICACION", "UBICACION"],
        "ESTADO_FALLA": ["ESTADO_FALLA", "ESTADOFALLA"],

        "LATITUD": ["LATITUD"],
        "LONGITUD": ["LONGITUD"],
        "ALTITUD": ["ALTITUD"],
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


def detect_reader(path: str) -> str:
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        first_line = f.readline().strip()

    if ";" in first_line:
        return "semicolon"
    return "comma"


def get_chunk_iterator(path: str, chunk_size: int) -> Iterator[pd.DataFrame]:
    mode = detect_reader(path)
    sep = ";" if mode == "semicolon" else ","
    print(f"Modo de lectura detectado: {mode}")

    for chunk in pd.read_csv(
        path,
        sep=sep,
        chunksize=chunk_size,
        encoding="utf-8-sig",
        low_memory=False
    ):
        yield chunk


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


# ============================================================
# 3. FEATURE ENGINEERING
# ============================================================

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
    if "USUARIOS_AFECTADOS" in df.columns:
        df["USUARIOS_AFECTADOS"] = pd.to_numeric(df["USUARIOS_AFECTADOS"], errors="coerce").fillna(0)

    if "ELEMENTOS_AFECTADOS" in df.columns:
        df["ELEMENTOS_AFECTADOS"] = pd.to_numeric(df["ELEMENTOS_AFECTADOS"], errors="coerce").fillna(0)

    if "USUARIOS_AFECTADOS" in df.columns and "CANTIDAD_ELEMENTOS" in df.columns:
        df["SEVERIDAD_USUARIOS_ELEMENTO"] = (
            df["USUARIOS_AFECTADOS"] / df["CANTIDAD_ELEMENTOS"].replace(0, np.nan)
        ).replace([np.inf, -np.inf], np.nan).fillna(0)

    if "ELEMENTOS_AFECTADOS" in df.columns and "CANTIDAD_ELEMENTOS" in df.columns:
        df["SEVERIDAD_ELEMENTOS_ELEMENTO"] = (
            df["ELEMENTOS_AFECTADOS"] / df["CANTIDAD_ELEMENTOS"].replace(0, np.nan)
        ).replace([np.inf, -np.inf], np.nan).fillna(0)

    return df


def add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values([ID_COL, DATE_COL]).copy()

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
                    df.groupby(ID_COL)[col]
                    .transform(lambda s: s.shift(1).rolling(window, min_periods=1).sum())
                )

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

    for col in EXPECTED_CLIMATE_COLS:
        if col in df.columns:
            for lag in [1, 3, 7]:
                df[f"{col}_LAG_{lag}"] = df.groupby(ID_COL)[col].shift(lag)

    if TARGET_COL in df.columns:
        df["FALLA_LAG_1"] = df.groupby(ID_COL)[TARGET_COL].shift(1)

        df["FALLA_ULT_7D"] = (
            df.groupby(ID_COL)[TARGET_COL]
            .transform(lambda s: s.shift(1).rolling(7, min_periods=1).sum())
        )

        df["FALLA_ULT_15D"] = (
            df.groupby(ID_COL)[TARGET_COL]
            .transform(lambda s: s.shift(1).rolling(15, min_periods=1).sum())
        )

    severity_cols = [
        "USUARIOS_AFECTADOS",
        "ELEMENTOS_AFECTADOS",
        "SEVERIDAD_USUARIOS_ELEMENTO",
        "SEVERIDAD_ELEMENTOS_ELEMENTO"
    ]

    for col in severity_cols:
        if col in df.columns:
            df[f"{col}_LAG_1"] = df.groupby(ID_COL)[col].shift(1)

            df[f"{col}_ULT_7D"] = (
                df.groupby(ID_COL)[col]
                .transform(lambda s: s.shift(1).rolling(7, min_periods=1).sum())
            )

            df[f"{col}_ULT_15D"] = (
                df.groupby(ID_COL)[col]
                .transform(lambda s: s.shift(1).rolling(15, min_periods=1).sum())
            )

    df[MODEL_TARGET_COL] = df.groupby(ID_COL)[TARGET_COL].shift(-1)

    return df


# ============================================================
# 4. CARGA Y PREPARACIÓN DE DATOS
# ============================================================

def load_and_prepare_dataset(csv_path: str, chunk_size: int) -> pd.DataFrame:
    prepared_chunks = []
    total_rows = 0

    for i, chunk in enumerate(get_chunk_iterator(csv_path, chunk_size), start=1):
        if i == 1 or i % 50 == 0:
            print(f"\nLeyendo bloque {i}...")

        chunk = normalize_columns(chunk)

        if i == 1:
            print("Columnas detectadas:")
            print(chunk.columns.tolist())

        mapping = build_column_mapping(chunk.columns.tolist())
        chunk = chunk.rename(columns=mapping)

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

        numeric_candidates = (
            [TARGET_COL]
            + EXPECTED_CLIMATE_COLS
            + EXPECTED_STATIC_NUMERIC_COLS
            + EXPECTED_OPTIONAL_EVENT_COLS
        )

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

        chunk = chunk.dropna(subset=[ID_COL, DATE_COL, TARGET_COL])
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
        raise ValueError("No se pudieron cargar bloques válidos.")

    df = pd.concat(prepared_chunks, ignore_index=True)
    del prepared_chunks
    gc.collect()

    df = reduce_memory_usage(df)
    df = df.sort_values([ID_COL, DATE_COL]).reset_index(drop=True)
    df = add_lag_features(df)

    df.dropna(subset=[MODEL_TARGET_COL], inplace=True)
    df[MODEL_TARGET_COL] = df[MODEL_TARGET_COL].astype("int8")

    df = reduce_memory_usage(df)

    return df


# ============================================================
# 5. EVALUACIÓN DE MODELOS
# ============================================================

def evaluate_model(model, X_test, y_test, model_name: str) -> Dict:
    y_prob = model.predict_proba(X_test)[:, 1]
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
    print("\nReporte de clasificación:")
    print(classification_report(y_test, y_pred, zero_division=0))

    return metrics


# ============================================================
# 6. PROCESO PRINCIPAL
# ============================================================

print("Preparando dataset...")
df = load_and_prepare_dataset(CSV_PATH, CHUNK_SIZE)

print("\nDimensión final del dataset:")
print(df.shape)

print("\nRango de fechas:")
print(f"{df[DATE_COL].min()} -> {df[DATE_COL].max()}")

print("\nDistribución del target de modelado:")
print(df[MODEL_TARGET_COL].value_counts())
print(df[MODEL_TARGET_COL].value_counts(normalize=True))


# ============================================================
# 7. MUESTREO BALANCEADO
# ============================================================

df_pos = df.loc[df[MODEL_TARGET_COL] == 1]
df_neg = df.loc[df[MODEL_TARGET_COL] == 0]

if len(df_pos) == 0:
    raise ValueError("No hay casos positivos para entrenar el modelo.")

n_neg = min(len(df_neg), len(df_pos) * 4)

df_neg_smp = df_neg.sample(n=n_neg, random_state=RANDOM_STATE)
df_model = pd.concat([df_pos, df_neg_smp], ignore_index=True)

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

print("\nFecha de corte temporal:", cut_date)
print("Train:", train_df.shape)
print("Test :", test_df.shape)


# ============================================================
# 9. VARIABLES DEL MODELO
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

print("\nVariables numéricas:", len(numeric_cols))
print("Variables categóricas:", len(categorical_cols))


# ============================================================
# 10. PREPROCESAMIENTO
# ============================================================

preprocessor = ColumnTransformer(
    transformers=[
        (
            "num",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median"))
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
        )
    ],
    remainder="drop"
)


# ============================================================
# 11. MODELO 1 - ÁRBOL DE DECISIÓN
# ============================================================

tree_model = Pipeline(steps=[
    ("preprocessor", preprocessor),
    ("classifier", DecisionTreeClassifier(
        max_depth=10,
        min_samples_leaf=50,
        class_weight="balanced",
        random_state=RANDOM_STATE
    ))
])

print("\nEntrenando Árbol de Decisión...")
tree_model.fit(X_train, y_train)

metrics_tree = evaluate_model(
    tree_model,
    X_test,
    y_test,
    "DecisionTree"
)


# ============================================================
# 12. MODELO 2 - RANDOM FOREST
# ============================================================

rf_model = Pipeline(steps=[
    ("preprocessor", preprocessor),
    ("classifier", RandomForestClassifier(
        n_estimators=100,
        max_depth=12,
        min_samples_leaf=30,
        class_weight="balanced_subsample",
        n_jobs=-1,
        random_state=RANDOM_STATE
    ))
])

print("\nEntrenando Random Forest...")
rf_model.fit(X_train, y_train)

metrics_rf = evaluate_model(
    rf_model,
    X_test,
    y_test,
    "RandomForest"
)


# ============================================================
# 13. COMPARACIÓN DE MODELOS
# ============================================================

results_df = pd.DataFrame([
    metrics_tree,
    metrics_rf
]).sort_values(
    ["pr_auc", "roc_auc"],
    ascending=False
)

results_path = os.path.join(OUTPUT_DIR, "metricas_arbol_random_forest.csv")

results_df.to_csv(
    results_path,
    index=False,
    encoding="utf-8-sig"
)

print("\nResumen métricas:")
print(results_df)

best_model_name = results_df.iloc[0]["modelo"]

print(f"\nMejor modelo entre Árbol y Random Forest: {best_model_name}")


# ============================================================
# 14. IMPORTANCIA DE VARIABLES
# ============================================================

best_model = rf_model if best_model_name == "RandomForest" else tree_model
classifier = best_model.named_steps["classifier"]
fitted_preprocessor = best_model.named_steps["preprocessor"]

feature_names = fitted_preprocessor.get_feature_names_out()
importances = classifier.feature_importances_

importance_df = pd.DataFrame({
    "feature": feature_names,
    "importance": importances
}).sort_values(
    "importance",
    ascending=False
)

importance_path = os.path.join(OUTPUT_DIR, "importancia_variables_arbol_rf.csv")

importance_df.to_csv(
    importance_path,
    index=False,
    encoding="utf-8-sig"
)

print("\nTop 20 variables importantes:")
print(importance_df.head(20))


# ============================================================
# 15. REGLAS DEL ÁRBOL DE DECISIÓN
# ============================================================

tree_classifier = tree_model.named_steps["classifier"]
tree_preprocessor = tree_model.named_steps["preprocessor"]

tree_feature_names = tree_preprocessor.get_feature_names_out()

tree_rules = export_text(
    tree_classifier,
    feature_names=list(tree_feature_names),
    max_depth=4
)

rules_path = os.path.join(OUTPUT_DIR, "reglas_arbol_decision.txt")

with open(rules_path, "w", encoding="utf-8") as f:
    f.write(tree_rules)

print("\nReglas principales del árbol de decisión guardadas en:")
print(rules_path)

print("\nVista parcial de reglas:")
print(tree_rules[:3000])


# ============================================================
# 16. PREDICCIONES EN TEST
# ============================================================

if best_model_name == "RandomForest":
    y_prob_test = rf_model.predict_proba(X_test)[:, 1]
else:
    y_prob_test = tree_model.predict_proba(X_test)[:, 1]

preds = test_df[[ID_COL, DATE_COL]].copy()
preds["y_true"] = y_test.values
preds["prob_falla"] = y_prob_test
preds["pred_05"] = (y_prob_test >= 0.5).astype(int)

preds_path = os.path.join(OUTPUT_DIR, "predicciones_test_arbol_rf.csv")

preds.to_csv(
    preds_path,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# 17. RESUMEN FINAL
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
    "top_variables": importance_df.head(20).to_dict(orient="records")
}

summary_path = os.path.join(OUTPUT_DIR, "resumen_arbol_random_forest.json")

with open(summary_path, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print("\nArchivos generados:")
print(" -", results_path)
print(" -", importance_path)
print(" -", rules_path)
print(" -", preds_path)
print(" -", summary_path)

print("\n=== FIN DEL PROCESO ÁRBOL / RANDOM FOREST ===")