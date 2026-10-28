# =====================================================================
# Corrección de las variables sísmicas del panel (Etapa 2.07)
# Bugs corregidos respecto de Etapa2_07_sismicidad_sgc.Rmd:
#  (1) matriz_distancias_km <- matriz_distancias_m / 1000 conserva la
#      unidad "m"; al compararla con set_units(radio, "km") el radio se
#      convierte a metros y la condición resulta siempre verdadera: todos
#      los sismos quedaban "dentro" del radio de todos los cuadrantes.
#  (2) asignar_semana() no tenía cota superior: los sismos de 2026
#      (la extracción llega a ago-2026) se acumulaban en la última
#      semana del panel (2025-12-29).
# Salida: data_final_modelo_cuadrantes_reales_sismos_corr.rds (no
# sobrescribe el panel original).
# =====================================================================
suppressPackageStartupMessages({ library(dplyr); library(sf); library(lubridate); library(readr); library(tidyr) })
UB <- Sys.getenv("UBICACION_DATA")
data_final <- readRDS(file.path(UB, "data_final_modelo_cuadrantes_reales.rds"))
cent <- read_csv(file.path(UB, "centroides_cuadrantes_reales.csv"), show_col_types = FALSE) %>%
  rename(id_cuadrante = CUADRANTE) %>% mutate(id_cuadrante = as.character(id_cuadrante)) %>%
  distinct(id_cuadrante, .keep_all = TRUE)
semanas <- sort(unique(data_final$semana))

sismos <- readRDS(file.path(UB, "sismos_sgc_cache.rds")) %>%
  mutate(local_time = ymd_hms(local_time)) %>% st_zm(drop = TRUE) %>%
  filter(!is.na(latitude), !is.na(longitude),
         local_time >= as.POSIXct(min(semanas)), local_time < as.POSIXct(max(semanas) + 7)) %>%  # corrección (2)
  st_transform(4326)
sismos$semana <- floor_date(as.Date(sismos$local_time), "week", week_start = 1)
stopifnot(all(sismos$semana %in% semanas))
cat(sprintf("Sismos en el periodo del panel: %d (%s a %s)\n", nrow(sismos),
            min(sismos$local_time), max(sismos$local_time)))

cent_sf <- st_as_sf(cent, coords = c("lon", "lat"), crs = 4326, remove = FALSE)
D <- matrix(as.numeric(st_distance(cent_sf, sismos)) / 1000, nrow = nrow(cent_sf))  # km, numérico: corrección (1)

out <- lapply(seq_len(nrow(cent_sf)), function(i) {
  d <- tibble(semana = sismos$semana, mag = sismos$magnitude, dist = D[i, ])
  base <- d %>% group_by(semana) %>% summarise(dist_sismo_min_km = min(dist), .groups = "drop")
  for (r in c(25, 50, 100)) {
    a <- d %>% filter(dist < r) %>% group_by(semana) %>%
      summarise(n = n(), m2 = sum(mag >= 2, na.rm = TRUE), m3 = sum(mag >= 3, na.rm = TRUE),
                m4 = sum(mag >= 4, na.rm = TRUE), mx = max(mag, na.rm = TRUE), .groups = "drop")
    names(a)[-1] <- paste0(c("n_sismos", "n_sismos_m2", "n_sismos_m3", "n_sismos_m4", "magnitud_max"), "_r", r)
    base <- left_join(base, a, by = "semana")
  }
  base %>% mutate(id_cuadrante = cent$id_cuadrante[i])
}) %>% bind_rows()

cols_n <- grep("^n_sismos", names(out), value = TRUE)
nuevo <- data_final %>% mutate(id_cuadrante = as.character(id_cuadrante)) %>%
  select(-any_of(c(grep("sismo|magnitud_max", names(data_final), value = TRUE)))) %>%
  left_join(out, by = c("id_cuadrante", "semana")) %>%
  mutate(across(all_of(cols_n), ~ replace_na(., 0)),
         across(starts_with("magnitud_max"), ~ replace_na(., 0)),
         hubo_sismo_r50 = as.integer(n_sismos_r50 > 0))
for (r in c(25, 50, 100)) nuevo[[paste0("dist_sismo_min_km_r", r)]] <- nuevo$dist_sismo_min_km
nuevo$dist_sismo_min_km <- NULL
stopifnot(nrow(nuevo) == nrow(data_final))

cmp <- tibble(variable = c("n_sismos_r25", "n_sismos_r50", "n_sismos_r100"),
  original_media = sapply(variable, function(v) mean(data_final[[v]])),
  original_cuadrantes_distintos_por_semana = sapply(variable, function(v) mean(tapply(data_final[[v]], data_final$semana, n_distinct))),
  corregido_media = sapply(variable, function(v) mean(nuevo[[v]])),
  corregido_p99 = sapply(variable, function(v) quantile(nuevo[[v]], .99)),
  corregido_max = sapply(variable, function(v) max(nuevo[[v]])),
  corregido_pct_semanas_cero = sapply(variable, function(v) 100 * mean(nuevo[[v]] == 0)))
print(cmp, width = 200)
cat("Máximo semanal (r50) en la última semana — original:", max(data_final$n_sismos_r50[data_final$semana == max(semanas)]),
    "| corregido:", max(nuevo$n_sismos_r50[nuevo$semana == max(semanas)]), "\n")
saveRDS(cmp, "comparacion_sismos.rds")
saveRDS(nuevo, file.path(Sys.getenv("SALIDA", UB), "data_final_modelo_cuadrantes_reales_sismos_corr.rds"))
