"""Recalcula el clima por cuadrante-semana en dos etapas (cuadrante-dia -> semana).

La precipitacion original se sumaba sobre las filas activo-dia del panel consolidado,
por lo que quedaba multiplicada por el numero de activos del cuadrante.
"""

import os
import sys

import numpy as np
import pandas as pd

BASE = r"D:/OneDrive - PUJ Cali/Projecto_Grado_Javeriana/Data_Project"
CONSOLIDADA = os.path.join(BASE, "data_consolidada.csv")
MAPEO = os.path.join(BASE, "Distribución de Cuadrantes", "ELEMENTO_FALLA_CUADRANTE_800.xls")
SALIDA_DIA = os.path.join(BASE, "clima_cuadrante_dia.csv")
SALIDA_SEMANA = os.path.join(BASE, "clima_cuadrante_semana.csv")

MEAN_COLS = ["temperatura_media_c", "humedad_relativa_pct", "velocidad_viento_ms",
             "precipitacion_total_mm"]
MAX_COLS = ["temperatura_maxima_c", "velocidad_viento_ms"]
MIN_COLS = ["temperatura_minima_c"]
CLIMA_COLS = sorted(set(MEAN_COLS + MAX_COLS + MIN_COLS))
USE_COLS = ["ELEMENTO", "FECHA_DIA"] + CLIMA_COLS

mapeo = pd.read_excel(MAPEO)
col_cuad = [c for c in mapeo.columns if c.upper().startswith("CUADRANTE_1")][0]
mapeo = mapeo[["ELEMENTO", col_cuad]].drop_duplicates(subset="ELEMENTO")
mapeo.columns = ["ELEMENTO", "id_cuadrante"]
print(f"mapeo elementos: {len(mapeo)}", flush=True)

partes = []
filas = 0
for i, chunk in enumerate(pd.read_csv(CONSOLIDADA, usecols=USE_COLS,
                                      chunksize=3_000_000, low_memory=False)):
    chunk = chunk.merge(mapeo, on="ELEMENTO", how="inner")
    g = chunk.groupby(["id_cuadrante", "FECHA_DIA"], sort=False)
    agg = {}
    for c in MEAN_COLS:
        agg[f"{c}__sum"] = g[c].sum(min_count=1)
        agg[f"{c}__n"] = g[c].count()
    for c in MAX_COLS:
        agg[f"{c}__max"] = g[c].max()
    for c in MIN_COLS:
        agg[f"{c}__min"] = g[c].min()
    partes.append(pd.DataFrame(agg).reset_index())
    filas += len(chunk)
    print(f"chunk {i}: acumuladas {filas:,} filas", flush=True)

parcial = pd.concat(partes, ignore_index=True)
g = parcial.groupby(["id_cuadrante", "FECHA_DIA"], sort=False)
spec = {c: "sum" for c in parcial.columns if c.endswith(("__sum", "__n"))}
spec.update({c: "max" for c in parcial.columns if c.endswith("__max")})
spec.update({c: "min" for c in parcial.columns if c.endswith("__min")})
dia = g.agg(spec).reset_index()

for c in MEAN_COLS:
    dia[c] = dia[f"{c}__sum"] / dia[f"{c}__n"].replace(0, np.nan)
dia["temperatura_maxima_c"] = dia["temperatura_maxima_c__max"]
dia["velocidad_viento_ms_max"] = dia["velocidad_viento_ms__max"]
dia["temperatura_minima_c"] = dia["temperatura_minima_c__min"]
dia["n_activos_dia"] = dia["precipitacion_total_mm__n"]

dia = dia[["id_cuadrante", "FECHA_DIA", "n_activos_dia",
           "temperatura_media_c", "temperatura_maxima_c", "temperatura_minima_c",
           "humedad_relativa_pct", "velocidad_viento_ms", "velocidad_viento_ms_max",
           "precipitacion_total_mm"]]
dia["FECHA_DIA"] = pd.to_datetime(dia["FECHA_DIA"])
dia.to_csv(SALIDA_DIA, index=False)
print(f"clima cuadrante-dia: {dia.shape} -> {SALIDA_DIA}", flush=True)

dia["semana"] = dia["FECHA_DIA"] - pd.to_timedelta(dia["FECHA_DIA"].dt.weekday, unit="D")
semana = dia.groupby(["id_cuadrante", "semana"]).agg(
    dias_semana=("FECHA_DIA", "nunique"),
    n_activos_medio=("n_activos_dia", "mean"),
    temp_media_semana=("temperatura_media_c", "mean"),
    temp_max_semana=("temperatura_maxima_c", "max"),
    temp_min_semana=("temperatura_minima_c", "min"),
    humedad_media_semana=("humedad_relativa_pct", "mean"),
    viento_medio_semana=("velocidad_viento_ms", "mean"),
    viento_max_semana=("velocidad_viento_ms_max", "max"),
    precip_total_semana=("precipitacion_total_mm", "sum"),
).reset_index()
semana.to_csv(SALIDA_SEMANA, index=False)
print(f"clima cuadrante-semana: {semana.shape} -> {SALIDA_SEMANA}", flush=True)
print(semana["precip_total_semana"].describe(), flush=True)
