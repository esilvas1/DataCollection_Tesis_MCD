import requests
import pandas as pd
from io import StringIO
import time
import os
import sys



# ==========================
# CONFIGURACIÓN GENERAL
# ==========================
fecha_inicial = "20210101"
fecha_final = "20251231"

archivo_entrada = r"D:\Descargas\cuadrantes proyecto\ELEMENTO_FALLA_CUADRANTE_800.csv"
carpeta_salida = r"D:\Descargas\salida_nasa_objetos"

if len(sys.argv) >= 3:
    objectid_inicio = int(sys.argv[1])
    objectid_fin = int(sys.argv[2])
else:
    objectid_inicio = 1
    objectid_fin = 10  # valor por defecto para pruebas

col_objectid = "OBJECTID"
col_lat = "LATITUD"
col_lon = "LONGITUD"

parametros_nasa = ("PRECTOT", "T2M", "T2M_MAX", "T2M_MIN", "RH2M", "WS2M")

os.makedirs(carpeta_salida, exist_ok=True)

archivo_salida_csv = os.path.join(
    carpeta_salida,
    f"nasa_objectid_{objectid_inicio}_{objectid_fin}.csv"
)

archivo_log_errores = os.path.join(
    carpeta_salida,
    f"errores_objectid_{objectid_inicio}_{objectid_fin}.csv"
)


# ==========================
# FUNCIONES NASA POWER
# ==========================
def nasa_power_daily_point_csv_text(
    lat,
    lon,
    start_yyyymmdd,
    end_yyyymmdd,
    parameters=("PRECTOT", "T2M", "T2M_MAX", "T2M_MIN", "RH2M", "WS2M"),
    community="AG"
):
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": ",".join(parameters),
        "community": community,
        "longitude": lon,
        "latitude": lat,
        "start": start_yyyymmdd,
        "end": end_yyyymmdd,
        "format": "CSV"
    }

    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.text


def extraer_tabla_power(csv_text):
    lineas = [linea for linea in csv_text.splitlines() if linea.strip()]

    inicio_tabla = None
    for i, linea in enumerate(lineas):
        linea_upper = linea.upper().strip()
        if (
            linea_upper.startswith("YEAR,MO,DY")
            or linea_upper.startswith("YEAR,DOY")
            or linea_upper.startswith("DATE,")
        ):
            inicio_tabla = i
            break

    if inicio_tabla is None:
        raise ValueError("No se encontró el encabezado de la tabla en la respuesta de NASA POWER.")

    texto_tabla = "\n".join(lineas[inicio_tabla:])
    df = pd.read_csv(StringIO(texto_tabla), engine="python")

    if {"YEAR", "MO", "DY"}.issubset(df.columns):
        df["fecha_consulta"] = pd.to_datetime(
            df["YEAR"].astype(str) + "-" +
            df["MO"].astype(str).str.zfill(2) + "-" +
            df["DY"].astype(str).str.zfill(2),
            errors="coerce"
        )
        df.drop(columns=["YEAR", "MO", "DY"], inplace=True)

    elif {"YEAR", "DOY"}.issubset(df.columns):
        df["fecha_consulta"] = (
            pd.to_datetime(df["YEAR"].astype(str), format="%Y", errors="coerce")
            + pd.to_timedelta(df["DOY"] - 1, unit="D")
        )
        df.drop(columns=["YEAR", "DOY"], inplace=True)

    elif "DATE" in df.columns:
        df["fecha_consulta"] = pd.to_datetime(df["DATE"], errors="coerce")
        df.drop(columns=["DATE"], inplace=True)

    else:
        raise ValueError("No se encontró una estructura de fecha reconocible en la tabla NASA POWER.")

    return df


# ==========================
# LECTURA DEL ARCHIVO
# ==========================
def leer_archivo_origen(ruta_archivo):
    """
    Intenta leer el CSV con varias codificaciones.
    """
    codificaciones = ["utf-8", "cp1252", "latin-1"]
    ultimo_error = None

    for enc in codificaciones:
        try:
            df = pd.read_csv(
                ruta_archivo,
                sep=";",
                encoding=enc,
                dtype=str,
                keep_default_na=False
            )
            df.columns = [col.strip() for col in df.columns]
            print(f"Archivo leído correctamente con encoding: {enc}")
            return df
        except Exception as e:
            ultimo_error = e
            print(f"No se pudo leer con encoding {enc}: {e}")

    raise ValueError(f"No fue posible leer el archivo. Último error: {ultimo_error}")


def normalizar_numero(valor):
    if pd.isna(valor):
        return None

    texto = str(valor).strip()

    if texto == "":
        return None

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except ValueError:
        return None


# ==========================
# PROCESO PRINCIPAL
# ==========================
df_origen = leer_archivo_origen(archivo_entrada)

print("Columnas detectadas:", list(df_origen.columns))
print("Fecha inicial:", fecha_inicial)
print("Fecha final:", fecha_final)
print("Total filas origen:", len(df_origen))

columnas_requeridas = [col_objectid, col_lat, col_lon]
faltantes = [c for c in columnas_requeridas if c not in df_origen.columns]
if faltantes:
    raise ValueError(f"Faltan columnas requeridas: {faltantes}")

df_origen[col_objectid] = pd.to_numeric(df_origen[col_objectid], errors="coerce")
df_origen = df_origen.dropna(subset=[col_objectid]).copy()
df_origen[col_objectid] = df_origen[col_objectid].astype(int)

df_filtrado = df_origen[
    (df_origen[col_objectid] >= objectid_inicio) &
    (df_origen[col_objectid] <= objectid_fin)
].copy()

print(f"Filtro aplicado por OBJECTID: {objectid_inicio} - {objectid_fin}")
print("Total filas luego del filtro:", len(df_filtrado))

if df_filtrado.empty:
    raise ValueError("No se encontraron registros en ese rango de OBJECTID")

resultados = []
errores = []

for _, row in df_filtrado.iterrows():
    objectid = row[col_objectid]
    lat = normalizar_numero(row[col_lat])
    lon = normalizar_numero(row[col_lon])

    try:
        if lat is None or lon is None:
            raise ValueError("Lat/Lon inválida")

        if not (-90 <= lat <= 90):
            raise ValueError(f"Latitud fuera de rango: {lat}")

        if not (-180 <= lon <= 180):
            raise ValueError(f"Longitud fuera de rango: {lon}")

        respuesta_csv = nasa_power_daily_point_csv_text(
            lat=lat,
            lon=lon,
            start_yyyymmdd=fecha_inicial,
            end_yyyymmdd=fecha_final,
            parameters=parametros_nasa,
            community="AG"
        )

        df_temp = extraer_tabla_power(respuesta_csv)

        if df_temp.empty:
            raise ValueError("NASA POWER no devolvió datos")

        df_temp["OBJECTID"] = objectid
        df_temp["latitud"] = lat
        df_temp["longitud"] = lon

        for col in df_filtrado.columns:
            df_temp[f"origen_{col}"] = row[col]

        resultados.append(df_temp)

        print(f"OBJECTID {objectid}: OK ({len(df_temp)} días)")
        time.sleep(0.2)

    except Exception as e:
        errores.append({
            "OBJECTID": objectid,
            "latitud": lat,
            "longitud": lon,
            "error": str(e)
        })
        print(f"OBJECTID {objectid}: error -> {e}")

if resultados:
    df_resultado = pd.concat(resultados, ignore_index=True)
else:
    df_resultado = pd.DataFrame()

rename_map = {
    "PRECTOT": "precipitacion_total_mm",
    "PRECTOTCORR": "precipitacion_total_mm",
    "T2M": "temperatura_media_c",
    "T2M_MAX": "temperatura_maxima_c",
    "T2M_MIN": "temperatura_minima_c",
    "RH2M": "humedad_relativa_pct",
    "WS2M": "velocidad_viento_ms"
}

df_resultado.rename(columns=rename_map, inplace=True)

if not df_resultado.empty:
    df_resultado.to_csv(archivo_salida_csv, index=False, encoding="utf-8-sig")
    print("Archivo guardado en:", archivo_salida_csv)
    print("Total filas resultado:", len(df_resultado))
else:
    print("No se generaron datos para guardar.")

if errores:
    pd.DataFrame(errores).to_csv(archivo_log_errores, index=False, encoding="utf-8-sig")
    print("Archivo de errores guardado en:", archivo_log_errores)