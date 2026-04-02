import requests
import pandas as pd
from io import StringIO
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# ==========================
# CONFIGURACIÓN
# ==========================
fecha_inicial = "20210101"
fecha_final = "20251231"

archivo_entrada = r"C:\Users\User\Downloads\ELEMENTO_FALLA_PIVOTE (1).xlsx"

carpeta_salida = r"C:\Users\User\Downloads\nasa_power_por_mes"
archivo_consolidado = r"C:\Users\User\Downloads\nasa_power_consolidado.csv"

os.makedirs(carpeta_salida, exist_ok=True)

col_id = "ID_ACTIVO_ELECTRICO"
col_lat = "LATITUD"
col_lon = "LONGITUD"

# 🔥 CORREGIDO
parametros_nasa = ("PRECTOTCORR", "T2M", "T2M_MAX", "T2M_MIN", "RH2M", "WS2M")

session = requests.Session()

# ==========================
# FUNCIONES
# ==========================
def nasa_power_daily_point_csv_text(lat, lon, retries=3):
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": ",".join(parametros_nasa),
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": fecha_inicial,
        "end": fecha_final,
        "format": "CSV"
    }

    for intento in range(retries):
        try:
            r = session.get(url, params=params, timeout=60)

            if r.status_code == 200:
                return r.text
            else:
                print(f"⚠️ Error HTTP {r.status_code}")
                print(r.text[:300])

        except Exception as e:
            print(f"⚠️ Exception: {e}")

        time.sleep(2 * (intento + 1))

    return None


def extraer_tabla_power(csv_text):
    if csv_text is None:
        return None

    lineas = [l for l in csv_text.splitlines() if l.strip()]

    # Buscar encabezado dinámicamente
    inicio = None
    for i, linea in enumerate(lineas):
        if "YEAR" in linea.upper():
            inicio = i
            break

    if inicio is None:
        print("⚠️ No se encontró encabezado")
        return None

    try:
        df = pd.read_csv(StringIO("\n".join(lineas[inicio:])), engine="python")
    except Exception as e:
        print("⚠️ Error leyendo CSV:", e)
        return None

    # ==========================
    # MANEJO DE FECHAS (ROBUSTO)
    # ==========================
    if {"YEAR", "MO", "DY"}.issubset(df.columns):
        df["fecha_consulta"] = pd.to_datetime(
            df["YEAR"].astype(str) + "-" +
            df["MO"].astype(str).str.zfill(2) + "-" +
            df["DY"].astype(str).str.zfill(2),
            errors="coerce"
        )
        df.drop(columns=["YEAR", "MO", "DY"], inplace=True)

    elif {"YEAR", "DOY"}.issubset(df.columns):
        # 🔥 FORMATO REAL NASA
        df["fecha_consulta"] = pd.to_datetime(
            df["YEAR"].astype(str) + df["DOY"].astype(str).str.zfill(3),
            format="%Y%j",
            errors="coerce"
        )
        df.drop(columns=["YEAR", "DOY"], inplace=True)

    elif "DATE" in df.columns:
        df["fecha_consulta"] = pd.to_datetime(
            df["DATE"], format="%Y%m%d", errors="coerce"
        )
        df.drop(columns=["DATE"], inplace=True)

    else:
        print("⚠️ Formato de fecha no reconocido")
        return None

    return df


def leer_excel(ruta):
    df = pd.read_excel(ruta, dtype=str)
    df.columns = [c.strip().upper().replace("\ufeff", "") for c in df.columns]
    return df


def normalizar_numero(valor):
    try:
        return float(str(valor).replace(",", "."))
    except:
        return None


# ==========================
# CARGA DATOS
# ==========================
df_origen = leer_excel(archivo_entrada)

df_coords = df_origen[[col_lat, col_lon]].drop_duplicates()

# 🔧 PRUEBA CONTROLADA
# df_coords = df_coords.sample(10)

print("Total coordenadas únicas:", len(df_coords))


# ==========================
# PROCESAMIENTO PARALELO
# ==========================
resultados = []

def procesar_coord(row):
    lat = normalizar_numero(row[col_lat])
    lon = normalizar_numero(row[col_lon])

    if lat is None or lon is None:
        return None

    try:
        respuesta = nasa_power_daily_point_csv_text(lat, lon)

        if respuesta is None:
            return None

        df_res = extraer_tabla_power(respuesta)

        if df_res is None or df_res.empty:
            print(f"⚠️ Sin datos para {lat}, {lon}")
            return None

        if "fecha_consulta" not in df_res.columns:
            return None

        df_res["latitud"] = lat
        df_res["longitud"] = lon

        return df_res

    except Exception as e:
        print(f"⚠️ Error en coordenada {lat},{lon}: {e}")
        return None


print("\nProcesando en paralelo...")

with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [
        executor.submit(procesar_coord, row)
        for _, row in df_coords.iterrows()
    ]

    for future in as_completed(futures):
        res = future.result()
        if res is not None:
            resultados.append(res)

print("Resultados válidos:", len(resultados))


if len(resultados) == 0:
    raise ValueError("❌ No se obtuvieron datos válidos de NASA")


# ==========================
# UNIR RESULTADOS
# ==========================
df_clima = pd.concat(resultados, ignore_index=True)


# ==========================
# MERGE CON ELEMENTOS
# ==========================
df_origen["LATITUD"] = df_origen["LATITUD"].apply(normalizar_numero)
df_origen["LONGITUD"] = df_origen["LONGITUD"].apply(normalizar_numero)

df_total = df_origen.merge(
    df_clima,
    left_on=["LATITUD", "LONGITUD"],
    right_on=["latitud", "longitud"],
    how="left"
)


# ==========================
# CREAR MES-AÑO
# ==========================
df_total["mes_anio"] = df_total["fecha_consulta"].dt.to_period("M").astype(str)


# ==========================
# EXPORTAR POR MES
# ==========================
print("\nExportando por mes...")

for mes, df_mes in df_total.groupby("mes_anio"):

    archivo_mes = os.path.join(
        carpeta_salida,
        f"nasa_power_{mes}.csv"
    )

    df_mes.to_csv(archivo_mes, index=False, encoding="utf-8-sig")

    print(f"{mes} ✔")


# ==========================
# CONSOLIDADO FINAL
# ==========================
df_total.to_csv(archivo_consolidado, index=False, encoding="utf-8-sig")

print("\n✅ Consolidado listo")
print("Archivo:", archivo_consolidado)