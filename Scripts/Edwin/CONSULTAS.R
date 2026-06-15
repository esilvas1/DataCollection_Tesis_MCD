# LEER EL ARCHIVO CSV data_consolidada.csv usando UBICACION_DATA del .env
library(tidyverse)

# Cargar .env (raiz del proyecto: Scripts/Edwin -> ../../.env)
env_path <- file.path("..", "..", ".env")
if (file.exists(".env")) {
  readRenviron(".env")
} else if (file.exists(env_path)) {
  readRenviron(env_path)
}

UBICACION_DATA <- Sys.getenv("UBICACION_DATA")
if (UBICACION_DATA == "") {
  stop("UBICACION_DATA no esta definida. Verifica el archivo .env en la raiz del proyecto.")
}

data_consolidada <- read_csv(file.path(UBICACION_DATA, "tabla_eventos_ajustado.csv"))
dim(data_consolidada)

data_consolidada <- data_consolidada |>
  mutate(
    FECHA_DESCONEXION = dmy_hm(FECHA_DESCONEXION),
    FECHA_CONEXION = dmy_hm(FECHA_CONEXION),
    anio = year(FECHA_DESCONEXION),
    mes = floor_date(FECHA_DESCONEXION, "month"),
    semana = floor_date(FECHA_DESCONEXION, "week"),
    duracion = (FECHA_CONEXION - FECHA_DESCONEXION)*24*60,
  )

  dim(data_consolidada)

# agrupar por anio y contar cuantos eventos por año existen
data_consolidada_anio <- data_consolidada |>
  group_by(anio) |>
  summarise(duracion_total = sum(duracion, na.rm = TRUE), .groups = "drop")

data_consolidada_anio  



