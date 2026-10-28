# =====================================================================
# Genera una muestra SINTÉTICA con la misma estructura del panel de
# modelado, para ejecutar la cadena de la Etapa 5 sin datos de CENS.
# Las cifras que produce NO reproducen las de la tesis.
# =====================================================================
suppressPackageStartupMessages({ library(dplyr); library(sf) })
set.seed(2026)
UB <- Sys.getenv("UBICACION_DATA"); OUT <- Sys.getenv("SALIDA", "muestra_sintetica")
dir.create(OUT, showWarnings = FALSE)
d <- readRDS(file.path(UB, "data_final_modelo_cuadrantes_reales_sismos_corr.rds"))
ids <- unique(d$id_cuadrante)
estat <- c("n_elementos", "longitud_red_km", "densidad_terminales", "prop_estrato_1", "prop_estrato_2",
           "prop_no_residencial", "PROM_CANT_MODIFICACIONES", "cantidad_usuarios_cuadrante",
           "prop_transformadores", "n_circuitos_cuadrante", "n_nodos_terminales")
estat <- intersect(estat, names(d))
# 1) atributos estáticos: se reasignan al azar entre cuadrantes (rompe el vínculo con el territorio)
perm <- setNames(sample(ids), ids)
st <- d %>% distinct(id_cuadrante, .keep_all = TRUE) %>% select(id_cuadrante, all_of(estat))
st_s <- st %>% mutate(id_cuadrante = perm[as.character(id_cuadrante)])
s <- d %>% select(-all_of(estat)) %>% left_join(st_s, by = "id_cuadrante")
# 2) variables numéricas dinámicas: remuestreo con ruido multiplicativo
num <- setdiff(names(s)[sapply(s, is.numeric)], c("id_cuadrante", estat, "usuarios_totales"))
for (v in num) { x <- s[[v]]; ok <- !is.na(x)
  s[[v]][ok] <- pmax(0, sample(x[ok]) * exp(rnorm(sum(ok), 0, 0.15))) * ifelse(min(x, na.rm = TRUE) < 0, NA, 1)
  if (min(x, na.rm = TRUE) < 0) s[[v]][ok] <- sample(x[ok]) + rnorm(sum(ok), 0, sd(x[ok]) * 0.15) }
# 3) eventos y respuestas coherentes con la definición del Capítulo 1
p_falla <- mean(d$n_eventos > 0)
s <- s %>% mutate(n_eventos = rbinom(n(), 1, p_falla) * rpois(n(), 2) ,
                  usuarios_afectados = ifelse(n_eventos > 0, round(rlnorm(n(), 3, 1.8)), 0),
                  duracion_total = ifelse(n_eventos > 0, rlnorm(n(), 2.8, 1.2), 0),
                  SAIFI = usuarios_afectados / usuarios_totales,
                  SAIDI = duracion_total * usuarios_afectados / usuarios_totales)
# columnas de texto con información institucional se vacían
for (v in names(s)[sapply(s, is.character)]) if (!v %in% c("id_cuadrante")) s[[v]] <- NA_character_
saveRDS(s, file.path(OUT, "data_final_modelo_cuadrantes_reales_sismos_corr.rds"))
g <- st_read(file.path(UB, "infraestructura_cuadrantes_reales.gpkg"), layer = "cuadrantes_infra_reales", quiet = TRUE)
idc <- if ("id_cuadrante" %in% names(g)) "id_cuadrante" else "CUADRANTE"
st_write(g[, idc], file.path(OUT, "infraestructura_cuadrantes_reales.gpkg"), layer = "cuadrantes_infra_reales",
         delete_dsn = TRUE, quiet = TRUE)
cat("Muestra sintética:", nrow(s), "filas x", ncol(s), "columnas en", OUT, "\n")
