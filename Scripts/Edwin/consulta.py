import requests
import pandas as pd
from io import StringIO

# ==========================
# CONFIGURACIÓN GENERAL
# ==========================
fecha_inicial = "20210101"   # formato YYYYMMDD
fecha_final = "20251231"     # formato YYYYMMDD

archivo_entrada = r"D:\Descargas\ELEMENTO_FALLA_CUADRANTE.csv"
archivo_salida_csv = r"D:\Descargas\resultado_nasa_power_cuadrante.csv"
archivo_salida_xlsx = r"D:\Descargas\resultado_nasa_power_cuadrante.xlsx"

# Cuadrante a consultar
id_cuadrante_filtrar = 34

# Columnas del archivo
col_cuadrante = "ID_CUADRANTE"
col_lon_cuadrante = "LATITUD_CUADRANTE"   # se troca para ajustar con el archivo que está al reves 
col_lat_cuadrante = "LONGITUD_CUADRANTE"

# Variables meteorológicas
parametros_nasa = ("PRECTOT", "T2M", "T2M_MAX", "T2M_MIN", "RH2M", "WS2M")


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
        print("\n--- RESPUESTA REAL DE NASA POWER ---")
        for j, linea in enumerate(lineas[:40]):
            print(f"{j}: {linea}")
        print("--- FIN RESPUESTA NASA POWER ---\n")
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
def leer_archivo_origen(ruta_archivo, sep=",", encoding="utf-8"):
    df = pd.read_csv(
        ruta_archivo,
        sep=sep,
        encoding=encoding,
        dtype=str,
        keep_default_na=False
    )
    df.columns = [col.strip() for col in df.columns]
    return df


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
df_origen = leer_archivo_origen(archivo_entrada, sep=",", encoding="utf-8")

print("Columnas detectadas:", list(df_origen.columns))
print("Fecha inicial:", fecha_inicial)
print("Fecha final:", fecha_final)
print("Total filas origen:", len(df_origen))

# Filtrar cuadrante
df_filtrado = df_origen[df_origen[col_cuadrante].astype(str).str.strip() == str(id_cuadrante_filtrar)].copy()

print(f"Filtro aplicado por cuadrante = {id_cuadrante_filtrar}")
print("Total filas luego del filtro:", len(df_filtrado))

if df_filtrado.empty:
    raise ValueError(f"No se encontraron registros para el cuadrante {id_cuadrante_filtrar}")

# Obtener coordenadas únicas de cuadrante
df_coords = df_filtrado[[col_lat_cuadrante, col_lon_cuadrante]].drop_duplicates().copy()

print("Coordenadas únicas del cuadrante:", len(df_coords))
print(df_coords.head())

if len(df_coords) > 1:
    print("Advertencia: el cuadrante tiene más de una coordenada única. Se usará la primera.")

lat = normalizar_numero(df_coords.iloc[0][col_lat_cuadrante])
lon = normalizar_numero(df_coords.iloc[0][col_lon_cuadrante])

if lat is None or lon is None:
    raise ValueError("La latitud/longitud del cuadrante no es válida.")

if not (-90 <= lat <= 90):
    raise ValueError(f"Latitud fuera de rango: {lat}")

if not (-180 <= lon <= 180):
    raise ValueError(f"Longitud fuera de rango: {lon}")

print(f"Consultando NASA POWER para cuadrante {id_cuadrante_filtrar} con lat={lat}, lon={lon}")

respuesta_csv = nasa_power_daily_point_csv_text(
    lat=lat,
    lon=lon,
    start_yyyymmdd=fecha_inicial,
    end_yyyymmdd=fecha_final,
    parameters=parametros_nasa,
    community="AG"
)

df_resultado = extraer_tabla_power(respuesta_csv)

# Agregar metadata
df_resultado["id_cuadrante"] = id_cuadrante_filtrar
df_resultado["latitud_cuadrante"] = lat
df_resultado["longitud_cuadrante"] = lon
df_resultado["cantidad_elementos_cuadrante"] = len(df_filtrado)

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

# Guardar
df_resultado.to_csv(archivo_salida_csv, index=False, encoding="utf-8-sig")

with pd.ExcelWriter(archivo_salida_xlsx, engine="openpyxl") as writer:
    df_resultado.to_excel(writer, index=False, sheet_name="resultado")

print("Proceso terminado.")
print("Archivo CSV guardado en:", archivo_salida_csv)
print("Archivo XLSX guardado en:", archivo_salida_xlsx)
print("Total filas resultado:", len(df_resultado))