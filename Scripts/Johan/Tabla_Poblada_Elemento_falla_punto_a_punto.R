# ============================================================
# CRUCE:
# ELEMENTO_FALLA_PIVOTE + tabla_eventos_ajustado + nasa_consolidado
#
# Objetivo:
# Poblar ELEMENTO_FALLA_PIVOTE con toda la serie diaria NASA
# por elemento, e identificar cuándo hubo falla y cuándo no.
# ============================================================

rm(list = ls())
gc()

suppressPackageStartupMessages({
  library(data.table)
  library(readxl)
  library(tools)
  library(lubridate)
})

ruta_base <- "D:/Personal/Documentos maestria/archivos de consulta"

archivo_elementos_patron <- "^ELEMENTO_FALLA_PIVOTE\\.(xlsx|xls|csv)$"
archivo_eventos_patron   <- "^tabla_eventos_ajustado\\.(xlsx|xls|csv)$"
archivo_nasa_patron      <- "^nasa_consolidado.*\\.csv$"

salida_csv_completo <- file.path(ruta_base, "ELEMENTO_FALLA_PIVOTE_POBLADA.csv")
salida_resumen_csv  <- file.path(ruta_base, "RESUMEN_FALLAS_POR_ELEMENTO.csv")
salida_rds_respaldo <- file.path(ruta_base, "ELEMENTO_FALLA_PIVOTE_POBLADA.rds")

guardar_rds_respaldo <- TRUE

normalizar_nombres <- function(x) {
  x <- iconv(x, from = "", to = "ASCII//TRANSLIT")
  x <- toupper(x)
  x <- gsub("[^A-Z0-9]+", "_", x)
  x <- gsub("^_+|_+$", "", x)
  x
}

buscar_archivo <- function(ruta, patron) {
  archivos <- list.files(ruta, full.names = TRUE)
  idx <- grepl(patron, basename(archivos), ignore.case = TRUE)
  encontrados <- archivos[idx]
  if (length(encontrados) == 0) return(NA_character_)
  encontrados[1]
}

validar_columnas <- function(dt, cols, nombre_tabla) {
  faltantes <- setdiff(cols, names(dt))
  if (length(faltantes) > 0) {
    stop(
      paste0(
        "En la tabla ", nombre_tabla,
        " faltan estas columnas: ",
        paste(faltantes, collapse = ", ")
      ),
      call. = FALSE
    )
  }
}

convertir_a_numero <- function(x) {
  if (is.numeric(x)) return(x)
  
  x_chr <- trimws(as.character(x))
  x_chr[x_chr %in% c("", "NA", "NULL", "N/A", "<NA>")] <- NA_character_
  
  tiene_coma <- grepl(",", x_chr)
  x_chr[tiene_coma] <- gsub("\\.", "", x_chr[tiene_coma])
  x_chr[tiene_coma] <- gsub(",", ".", x_chr[tiene_coma])
  
  suppressWarnings(as.numeric(x_chr))
}

convertir_a_datetime <- function(x) {
  
  if (inherits(x, "POSIXt")) return(as.POSIXct(x, tz = "UTC"))
  if (inherits(x, "Date")) return(as.POSIXct(x, tz = "UTC"))
  if (is.numeric(x)) return(as.POSIXct(as.Date(x, origin = "1899-12-30"), tz = "UTC"))
  
  x_chr <- trimws(as.character(x))
  x_chr[x_chr %in% c("", "NA", "NULL", "N/A", "<NA>")] <- NA_character_
  x_chr <- gsub("\\.(\\d{1,9})$", "", x_chr)
  
  res <- suppressWarnings(parse_date_time(
    x_chr,
    orders = c(
      "dmy HMS", "dmy HM", "dmy",
      "ymd HMS", "ymd HM", "ymd",
      "mdy HMS", "mdy HM", "mdy",
      "dmY HMS", "dmY HM", "dmY",
      "Ymd HMS", "Ymd HM", "Ymd"
    ),
    tz = "UTC",
    exact = FALSE
  ))
  
  as.POSIXct(res, origin = "1970-01-01", tz = "UTC")
}

# ------------------------------------------------------------
# 1. UBICAR ARCHIVOS
# ------------------------------------------------------------

archivo_elementos <- buscar_archivo(ruta_base, archivo_elementos_patron)
archivo_eventos   <- buscar_archivo(ruta_base, archivo_eventos_patron)
archivo_nasa      <- buscar_archivo(ruta_base, archivo_nasa_patron)

cat("Archivo elementos: ", archivo_elementos, "\n")
cat("Archivo eventos:   ", archivo_eventos, "\n")
cat("Archivo NASA:      ", archivo_nasa, "\n\n")

if (is.na(archivo_elementos)) stop("No encontré ELEMENTO_FALLA_PIVOTE.", call. = FALSE)
if (is.na(archivo_eventos)) stop("No encontré tabla_eventos_ajustado.", call. = FALSE)
if (is.na(archivo_nasa)) stop("No encontré nasa_consolidado.", call. = FALSE)

# ------------------------------------------------------------
# 2. LEER ARCHIVOS
# ------------------------------------------------------------

ext_elementos <- tolower(file_ext(archivo_elementos))

if (ext_elementos %in% c("xlsx", "xls")) {
  hoja_elementos <- excel_sheets(archivo_elementos)[1]
  elementos <- as.data.table(read_excel(archivo_elementos, sheet = hoja_elementos))
} else {
  elementos <- fread(archivo_elementos, encoding = "UTF-8")
}

setnames(elementos, normalizar_nombres(names(elementos)))
setDT(elementos)

ext_eventos <- tolower(file_ext(archivo_eventos))

if (ext_eventos %in% c("xlsx", "xls")) {
  hoja_eventos <- excel_sheets(archivo_eventos)[1]
  eventos <- as.data.table(read_excel(archivo_eventos, sheet = hoja_eventos))
} else {
  eventos <- fread(archivo_eventos, encoding = "UTF-8")
}

setnames(eventos, normalizar_nombres(names(eventos)))
setDT(eventos)

nasa <- fread(archivo_nasa, encoding = "UTF-8")
setnames(nasa, normalizar_nombres(names(nasa)))
setDT(nasa)

# ------------------------------------------------------------
# 3. VALIDAR COLUMNAS
# ------------------------------------------------------------

validar_columnas(
  elementos,
  c(
    "ID_ACTIVO_ELECTRICO",
    "TIPO_ACTIVO_ELECTRICO",
    "LATITUD",
    "LONGITUD",
    "ALTITUD"
  ),
  "ELEMENTO_FALLA_PIVOTE"
)

validar_columnas(
  eventos,
  c(
    "ID_EVENTO",
    "FECHA_DESCONEXION",
    "FECHA_CONEXION",
    "COMPONENTE_FALLADO",
    "ELEMENTOS_AFECTADOS",
    "USUARIOS_AFECTADOS"
  ),
  "tabla_eventos_ajustado"
)

validar_columnas(
  nasa,
  c(
    "ORIGEN_ELEMENTO",
    "FECHA_CONSULTA",
    "VELOCIDAD_VIENTO_MS",
    "TEMPERATURA_MEDIA_C",
    "HUMEDAD_RELATIVA_PCT",
    "TEMPERATURA_MINIMA_C",
    "TEMPERATURA_MAXIMA_C",
    "PRECIPITACION_TOTAL_MM"
  ),
  "nasa_consolidado"
)

# ------------------------------------------------------------
# 4. ESTANDARIZAR TIPOS
# ------------------------------------------------------------

elementos[, ID_ACTIVO_ELECTRICO := trimws(as.character(ID_ACTIVO_ELECTRICO))]
elementos[, TIPO_ACTIVO_ELECTRICO := trimws(as.character(TIPO_ACTIVO_ELECTRICO))]

elementos[, LATITUD := convertir_a_numero(LATITUD)]
elementos[, LONGITUD := convertir_a_numero(LONGITUD)]
elementos[, ALTITUD := convertir_a_numero(ALTITUD)]

eventos[, ID_EVENTO := as.character(ID_EVENTO)]
eventos[, COMPONENTE_FALLADO := trimws(as.character(COMPONENTE_FALLADO))]
eventos[, FECHA_DESCONEXION_DT := convertir_a_datetime(FECHA_DESCONEXION)]
eventos[, FECHA_CONEXION_DT := convertir_a_datetime(FECHA_CONEXION)]
eventos[, FECHA_EVENTO := as.IDate(FECHA_DESCONEXION_DT)]
eventos[, ELEMENTOS_AFECTADOS := convertir_a_numero(ELEMENTOS_AFECTADOS)]
eventos[, USUARIOS_AFECTADOS := convertir_a_numero(USUARIOS_AFECTADOS)]

nasa[, ORIGEN_ELEMENTO := trimws(as.character(ORIGEN_ELEMENTO))]
nasa[, FECHA_CONSULTA := as.IDate(FECHA_CONSULTA)]

nasa[, VELOCIDAD_VIENTO_MS := convertir_a_numero(VELOCIDAD_VIENTO_MS)]
nasa[, TEMPERATURA_MEDIA_C := convertir_a_numero(TEMPERATURA_MEDIA_C)]
nasa[, HUMEDAD_RELATIVA_PCT := convertir_a_numero(HUMEDAD_RELATIVA_PCT)]
nasa[, TEMPERATURA_MINIMA_C := convertir_a_numero(TEMPERATURA_MINIMA_C)]
nasa[, TEMPERATURA_MAXIMA_C := convertir_a_numero(TEMPERATURA_MAXIMA_C)]
nasa[, PRECIPITACION_TOTAL_MM := convertir_a_numero(PRECIPITACION_TOTAL_MM)]

if ("ORIGEN_LATITUD" %in% names(nasa)) nasa[, ORIGEN_LATITUD := convertir_a_numero(ORIGEN_LATITUD)]
if ("ORIGEN_LONGITUD" %in% names(nasa)) nasa[, ORIGEN_LONGITUD := convertir_a_numero(ORIGEN_LONGITUD)]
if ("ORIGEN_ALTITUD" %in% names(nasa)) nasa[, ORIGEN_ALTITUD := convertir_a_numero(ORIGEN_ALTITUD)]

# ------------------------------------------------------------
# 5. CONTROL DE CALIDAD
# ------------------------------------------------------------

cat("==== CONTROL DE CALIDAD ====\n")
cat("Filas elementos pivote: ", format(nrow(elementos), big.mark = ","), "\n")
cat("Filas eventos:          ", format(nrow(eventos), big.mark = ","), "\n")
cat("Filas NASA:             ", format(nrow(nasa), big.mark = ","), "\n\n")

cat("NAs FECHA_DESCONEXION_DT: ", format(sum(is.na(eventos$FECHA_DESCONEXION_DT)), big.mark = ","), "\n")
cat("NAs FECHA_CONEXION_DT:    ", format(sum(is.na(eventos$FECHA_CONEXION_DT)), big.mark = ","), "\n")
cat("NAs FECHA_EVENTO:         ", format(sum(is.na(eventos$FECHA_EVENTO)), big.mark = ","), "\n\n")

cobertura_nasa <- elementos[ID_ACTIVO_ELECTRICO %in% nasa$ORIGEN_ELEMENTO, .N] / nrow(elementos)
cobertura_eventos <- elementos[ID_ACTIVO_ELECTRICO %in% eventos$COMPONENTE_FALLADO, .N] / nrow(elementos)

cat("Cobertura pivote vs NASA por elemento: ",
    round(cobertura_nasa * 100, 2), "%\n", sep = "")

cat("Cobertura pivote vs eventos por elemento: ",
    round(cobertura_eventos * 100, 2), "%\n\n", sep = "")

# ------------------------------------------------------------
# 6. PREPARAR NASA
# ------------------------------------------------------------

cols_nasa_preferidas <- c(
  "ORIGEN_ELEMENTO",
  "FECHA_CONSULTA",
  "OBJECTID",
  "LATITUD",
  "LONGITUD",
  "ERROR",
  "VELOCIDAD_VIENTO_MS",
  "TEMPERATURA_MEDIA_C",
  "HUMEDAD_RELATIVA_PCT",
  "TEMPERATURA_MINIMA_C",
  "TEMPERATURA_MAXIMA_C",
  "PRECIPITACION_TOTAL_MM",
  "ORIGEN_OBJECTID",
  "ORIGEN_LATITUD",
  "ORIGEN_LONGITUD",
  "ORIGEN_ALTITUD",
  "ORIGEN_TIPO",
  "ORIGEN_UBICACION"
)

cols_nasa_presentes <- intersect(cols_nasa_preferidas, names(nasa))
nasa <- unique(nasa[, ..cols_nasa_presentes])

setnames(nasa, "ORIGEN_ELEMENTO", "ID_ACTIVO_ELECTRICO")
setnames(nasa, "FECHA_CONSULTA", "FECHA")

# Quito filas NASA sin elemento o sin fecha
nasa <- nasa[!is.na(ID_ACTIVO_ELECTRICO) & !is.na(FECHA)]

# ------------------------------------------------------------
# 7. POBLAR ELEMENTOS CON NASA POR ELEMENTO
# ------------------------------------------------------------

elementos_nasa <- nasa[
  elementos,
  on = .(ID_ACTIVO_ELECTRICO),
  allow.cartesian = TRUE
]

# Si NASA trae latitud/longitud propias, se renombran para no confundir
if ("LATITUD" %in% names(elementos_nasa) && "I.LATITUD" %in% names(elementos_nasa)) {
  setnames(elementos_nasa, "LATITUD", "LATITUD_NASA")
  setnames(elementos_nasa, "I.LATITUD", "LATITUD")
}

if ("LONGITUD" %in% names(elementos_nasa) && "I.LONGITUD" %in% names(elementos_nasa)) {
  setnames(elementos_nasa, "LONGITUD", "LONGITUD_NASA")
  setnames(elementos_nasa, "I.LONGITUD", "LONGITUD")
}

if ("ALTITUD" %in% names(elementos_nasa) && "I.ALTITUD" %in% names(elementos_nasa)) {
  setnames(elementos_nasa, "I.ALTITUD", "ALTITUD")
}

# ------------------------------------------------------------
# 8. CONSOLIDAR EVENTOS POR ELEMENTO Y FECHA
# ------------------------------------------------------------

eventos_resumen <- eventos[
  !is.na(COMPONENTE_FALLADO) & !is.na(FECHA_EVENTO),
  .(
    HUBO_FALLA = 1L,
    CANTIDAD_EVENTOS_DIA = .N,
    IDS_EVENTO = paste(unique(ID_EVENTO), collapse = " | "),
    ELEMENTOS_AFECTADOS = sum(ELEMENTOS_AFECTADOS, na.rm = TRUE),
    USUARIOS_AFECTADOS = sum(USUARIOS_AFECTADOS, na.rm = TRUE),
    
    FECHA_DESCONEXION_MIN = {
      vals <- FECHA_DESCONEXION_DT[!is.na(FECHA_DESCONEXION_DT)]
      if (length(vals) == 0) as.POSIXct(NA) else min(vals)
    },
    
    FECHA_CONEXION_MAX = {
      vals <- FECHA_CONEXION_DT[!is.na(FECHA_CONEXION_DT)]
      if (length(vals) == 0) as.POSIXct(NA) else max(vals)
    }
  ),
  by = .(ID_ACTIVO_ELECTRICO = COMPONENTE_FALLADO, FECHA = FECHA_EVENTO)
]

eventos_resumen[
  ,
  DURACION_HORAS_EVENTO := fifelse(
    !is.na(FECHA_DESCONEXION_MIN) & !is.na(FECHA_CONEXION_MAX),
    as.numeric(difftime(FECHA_CONEXION_MAX, FECHA_DESCONEXION_MIN, units = "hours")),
    0
  )
]

# ------------------------------------------------------------
# 9. UNIR EVENTOS A LA TABLA POBLADA
# ------------------------------------------------------------

setkey(elementos_nasa, ID_ACTIVO_ELECTRICO, FECHA)
setkey(eventos_resumen, ID_ACTIVO_ELECTRICO, FECHA)

tabla_final <- eventos_resumen[elementos_nasa]

tabla_final[is.na(HUBO_FALLA), HUBO_FALLA := 0L]
tabla_final[is.na(CANTIDAD_EVENTOS_DIA), CANTIDAD_EVENTOS_DIA := 0L]
tabla_final[is.na(IDS_EVENTO), IDS_EVENTO := ""]
tabla_final[is.na(ELEMENTOS_AFECTADOS), ELEMENTOS_AFECTADOS := 0]
tabla_final[is.na(USUARIOS_AFECTADOS), USUARIOS_AFECTADOS := 0]
tabla_final[is.na(DURACION_HORAS_EVENTO), DURACION_HORAS_EVENTO := 0]

tabla_final[, ESTADO_FALLA := fifelse(HUBO_FALLA == 1, "CON FALLA", "SIN FALLA")]

# ------------------------------------------------------------
# 10. ORDENAR COLUMNAS
# ------------------------------------------------------------

columnas_preferidas <- c(
  "ID_ACTIVO_ELECTRICO",
  "TIPO_ACTIVO_ELECTRICO",
  "FECHA",
  "ESTADO_FALLA",
  "HUBO_FALLA",
  "CANTIDAD_EVENTOS_DIA",
  "IDS_EVENTO",
  "ELEMENTOS_AFECTADOS",
  "USUARIOS_AFECTADOS",
  "FECHA_DESCONEXION_MIN",
  "FECHA_CONEXION_MAX",
  "DURACION_HORAS_EVENTO",
  "LATITUD",
  "LONGITUD",
  "ALTITUD",
  "LATITUD_NASA",
  "LONGITUD_NASA",
  "OBJECTID",
  "ORIGEN_OBJECTID",
  "ORIGEN_TIPO",
  "ORIGEN_UBICACION",
  "VELOCIDAD_VIENTO_MS",
  "TEMPERATURA_MEDIA_C",
  "HUMEDAD_RELATIVA_PCT",
  "TEMPERATURA_MINIMA_C",
  "TEMPERATURA_MAXIMA_C",
  "PRECIPITACION_TOTAL_MM",
  "CANTIDAD_ELEMENTOS",
  "CANTIDAD_USUARIOS",
  "ANTIGUEDAD_RED",
  "EXPANSION_RED",
  "DURACION",
  "FRECUENCIA"
)

columnas_presentes <- intersect(columnas_preferidas, names(tabla_final))
columnas_restantes <- setdiff(names(tabla_final), columnas_presentes)

setcolorder(tabla_final, c(columnas_presentes, columnas_restantes))

# ------------------------------------------------------------
# 11. RESUMEN DE CONTROL
# ------------------------------------------------------------

resumen_control <- tabla_final[
  ,
  .(
    FECHAS_CON_INFO = uniqueN(FECHA),
    DIAS_CON_FALLA = uniqueN(FECHA[HUBO_FALLA == 1]),
    TOTAL_EVENTOS = sum(CANTIDAD_EVENTOS_DIA, na.rm = TRUE),
    TOTAL_ELEMENTOS_AFECTADOS = sum(ELEMENTOS_AFECTADOS, na.rm = TRUE),
    TOTAL_USUARIOS_AFECTADOS = sum(USUARIOS_AFECTADOS, na.rm = TRUE),
    TOTAL_HORAS_EVENTO = sum(DURACION_HORAS_EVENTO, na.rm = TRUE)
  ),
  by = .(ID_ACTIVO_ELECTRICO, TIPO_ACTIVO_ELECTRICO)
]

# ------------------------------------------------------------
# 12. EXPORTAR
# ------------------------------------------------------------

cat("==== EXPORTANDO CSV COMPLETO ====\n")
cat("Esto puede tardar si el archivo final es grande.\n\n")

fwrite(tabla_final, salida_csv_completo, bom = TRUE)
fwrite(resumen_control, salida_resumen_csv, bom = TRUE)

if (guardar_rds_respaldo) {
  saveRDS(tabla_final, salida_rds_respaldo)
}

cat("==== PROCESO FINALIZADO ====\n")
cat("Filas resultado final: ", format(nrow(tabla_final), big.mark = ","), "\n")
cat("CSV completo: ", salida_csv_completo, "\n")
cat("Resumen CSV:  ", salida_resumen_csv, "\n")

if (guardar_rds_respaldo) {
  cat("RDS respaldo: ", salida_rds_respaldo, "\n")
}

cat("\nVista rápida:\n")
print(tabla_final[1:10])

cat("\nConteo general:\n")
print(
  tabla_final[
    ,
    .(
      TOTAL_FILAS = .N,
      FILAS_CON_FALLA = sum(HUBO_FALLA == 1, na.rm = TRUE),
      FILAS_SIN_FALLA = sum(HUBO_FALLA == 0, na.rm = TRUE),
      TOTAL_ELEMENTOS_AFECTADOS = sum(ELEMENTOS_AFECTADOS, na.rm = TRUE),
      TOTAL_USUARIOS_AFECTADOS = sum(USUARIOS_AFECTADOS, na.rm = TRUE)
    )
  ]
)