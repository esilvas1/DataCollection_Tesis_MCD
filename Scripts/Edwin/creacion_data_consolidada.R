library(tidyverse)

tabla_eventos_ajustado <- read_csv("C:/Users/User/Documents/DataCollection_Tesis_MCD/DATA/tabla_eventos_ajustado.csv")
tabla_eventos_ajustado_1 <- tabla_eventos_ajustado %>%
  mutate(
    FECHA_DESCONEXION = dmy_hm(FECHA_DESCONEXION),
    FECHA_CONEXION = dmy_hm(FECHA_CONEXION)
  )
tabla_eventos_ajustado_2 <- tabla_eventos_ajustado_1 %>%
  mutate(
    anio = year(FECHA_DESCONEXION),
    mes = floor_date(FECHA_DESCONEXION, "month"),
    semana = floor_date(FECHA_DESCONEXION, "week"),
    day = floor_date(FECHA_DESCONEXION, "day")
  )
tabla_eventos_ajustado_3 <- tabla_eventos_ajustado_2 %>%
  mutate(
    FECHA_DESCONEXION = as.Date(FECHA_DESCONEXION),
    FECHA_CONEXION = as.Date(FECHA_CONEXION)
  )
tabla_eventos_ajustado_4 <- tabla_eventos_ajustado_3 %>%
  mutate(
    FECHA_DESCONEXION = as.Date(FECHA_DESCONEXION),
    FECHA_CONEXION = as.Date(FECHA_CONEXION)
  )
tabla_eventos_ajustado_5 <- tabla_eventos_ajustado_4 %>%  
  mutate(
    FECHA_DESCONEXION = as.Date(FECHA_DESCONEXION),
    FECHA_CONEXION = as.Date(FECHA_CONEXION)
  )
tabla_eventos_ajustado_6 <- tabla_eventos_ajustado_5 %>%
  mutate(
    FECHA_DESCONEXION = as.Date(FECHA_DESCONEXION),
    FECHA_CONEXION = as.Date(FECHA_CONEXION)
  )
tabla_eventos_ajustado_7 <- tabla_eventos_ajustado_6 %>%
  mutate(
    FECHA_DESCONEXION = as.Date(FECHA_DESCONEXION),
    FECHA_CONEXION = as.Date(FECHA_CONEXION)
  )
tabla_eventos_ajustado_8 <- tabla_eventos_ajustado_7 %>%
  mutate(
    FECHA_DESCONEXION = as.Date(FECHA_DESCONEXION),
    FECHA_CONEXION = as.Date(FECHA_CONEXION)
  )
tabla_eventos_ajustado_9 <- tabla_eventos_ajustado_8 %>%
  mutate(
    FECHA_DESCONEXION = as.Date(FECHA_DESCONEXION),
    FECHA_CONEXION = as.Date(FECHA_CONEXION)
  )
tabla_eventos_ajustado_10 <- tabla_eventos_ajustado_9 %>%
  mutate(
    FECHA_DESCONEXION = as.Date(FECHA_DESCONEXION),
  )
tabla_eventos_ajustado_10 %>% write_csv("C:/Users/User/Documents/DataCollection_Tesis_MCD/DATA/tabla_eventos_ajustado_10.csv")
