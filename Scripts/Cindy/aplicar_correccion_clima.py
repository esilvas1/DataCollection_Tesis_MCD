"""Sustituye el bloque climatico de las tablas agregadas por la version corregida."""

import os
import shutil

import pandas as pd

BASE = r"D:/OneDrive - PUJ Cali/Projecto_Grado_Javeriana/Data_Project"
CLIMA = os.path.join(BASE, "clima_cuadrante_semana.csv")
OBJETIVOS = ["data_agrupada.csv", "data_agrupada_mod.csv",
             "data_agrupada_por_cuadrante_semana.csv"]

CLIMA_COLS = ["temp_media_semana", "temp_max_semana", "temp_min_semana",
              "humedad_media_semana", "viento_medio_semana", "viento_max_semana",
              "precip_total_semana"]

clima = pd.read_csv(CLIMA, parse_dates=["semana"])[["id_cuadrante", "semana"] + CLIMA_COLS]

for nombre in OBJETIVOS:
    ruta = os.path.join(BASE, nombre)
    if not os.path.exists(ruta):
        print(f"omitido (no existe): {nombre}")
        continue
    respaldo = ruta.replace(".csv", "_precip_inflada.csv")
    if not os.path.exists(respaldo):
        shutil.copy2(ruta, respaldo)
    df = pd.read_csv(ruta, parse_dates=["semana"])
    orden = df.columns.tolist()
    antes = df["precip_total_semana"].median()
    df = df.drop(columns=CLIMA_COLS).merge(clima, on=["id_cuadrante", "semana"], how="left")
    df = df[orden]
    faltan = df["precip_total_semana"].isna().sum()
    df.to_csv(ruta, index=False)
    print(f"{nombre}: {df.shape}, mediana precip {antes:,.1f} -> "
          f"{df['precip_total_semana'].median():,.2f} mm, NA={faltan}")
