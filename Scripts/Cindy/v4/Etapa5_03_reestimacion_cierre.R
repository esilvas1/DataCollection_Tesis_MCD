# =====================================================================
# Etapa 5 — re-estimación de cierre (F1: C2–C11)
# Uso:  Rscript etapa5_cierre.R SAIDI   |   Rscript etapa5_cierre.R SAIFI
# Requiere UBICACION_DATA con data_final_modelo_cuadrantes_reales.rds e
# infraestructura_cuadrantes_reales.gpkg. Salidas en ./salidas_<Y>/
# =====================================================================
suppressPackageStartupMessages({
  library(dplyr); library(tidyr); library(ggplot2); library(lubridate); library(knitr)
  library(randomForest); library(ranger); library(sf); library(spdep)
  library(spatialreg); library(lmtest); library(car); library(forecast); library(pROC)
})
select <- dplyr::select; filter <- dplyr::filter
library(sandwich)
# Efectos fijos: se estiman con lm() + dummies (estimación idéntica a fixest::feols);
# errores agrupados con sandwich::vcovCL y Driscoll-Kraay con sandwich::vcovPL.
fe_fit <- function(f_txt, data, fe = character(0)) {
  vars <- all.vars(as.formula(f_txt))
  d <- data %>% select(all_of(c(vars, "id_cuadrante", "semana"))) %>% na.omit() %>%
    mutate(id_f = factor(id_cuadrante), sem_f = factor(semana))
  # efectos fijos primero: así lm() descarta (NA) las variables constantes dentro del cuadrante, como fixest
  rhs <- paste(c(if ("id" %in% fe) "id_f", if ("sem" %in% fe) "sem_f", sub("^[^~]+~", "", f_txt)), collapse = " + ")
  m <- lm(as.formula(paste(sub("~.*", "", f_txt), "~", rhs)), data = d)
  m$fe <- fe; m$datos <- d; m$niv_id <- levels(d$id_f); m$niv_sem <- levels(d$sem_f); m
}
fe_pred <- function(m, nd) {
  nd <- nd %>% mutate(id_f = factor(id_cuadrante, levels = m$niv_id), sem_f = factor(as.character(semana), levels = m$niv_sem))
  ok <- (!("id" %in% m$fe) | !is.na(nd$id_f)) & (!("sem" %in% m$fe) | !is.na(nd$sem_f))
  out <- rep(NA_real_, nrow(nd)); if (any(ok)) out[ok] <- suppressWarnings(predict(m, nd[ok, ])); out
}
fe_coefs <- function(m) {
  b <- coef(m); keep <- !grepl("^(id_f|sem_f)|Intercept", names(b)) & !is.na(b)
  vc <- vcovCL(m, cluster = m$datos$id_f, type = "HC1")
  vd <- vcovPL(m, cluster = m$datos$id_f, order.by = m$datos$semana, lag = "NW1987", adjust = TRUE)
  se_c <- sqrt(diag(vc))[names(b)[keep]]; se_d <- sqrt(diag(vd))[names(b)[keep]]
  df <- length(unique(m$datos$id_f)) - 1
  tibble(variable = names(b)[keep], coef = b[keep], se_cluster = se_c, p_cluster = 2 * pt(-abs(b[keep] / se_c), df),
         se_dk = se_d, p_dk = 2 * pnorm(-abs(b[keep] / se_d)))
}
r2_within <- function(m) { d <- m$datos; y <- model.response(model.frame(m))
  yd <- y - ave(y, d$id_f); rd <- resid(m); 1 - sum(rd^2) / sum(yd^2) }

Y   <- commandArgs(TRUE)[1]; if (is.na(Y)) Y <- "SAIDI"
yl  <- paste0("log_", Y, "1"); ylag <- paste0(Y, "_lag1"); yvec <- paste0(Y, "_vecinos_lag1")
OUT <- paste0(Sys.getenv("PREFIJO", "salidas_"), Y); dir.create(OUT, showWarnings = FALSE)
res <- list()                                   # todo lo que va a la tesis
sink(file.path(OUT, "log.txt"), split = TRUE)
UB  <- Sys.getenv("UBICACION_DATA")

# ---------------------------------------------------------------------
# 0. Preparación idéntica al Rmd de la Etapa 5 (v4)
# ---------------------------------------------------------------------
PANEL <- Sys.getenv("PANEL", file.path(UB, "data_final_modelo_cuadrantes_reales_sismos_corr.rds"))  # panel con sismicidad corregida
cat("Panel:", PANEL, "\n")
data_final <- readRDS(PANEL) %>%
  mutate(id_cuadrante = as.character(id_cuadrante)) %>% arrange(id_cuadrante, semana) %>%
  mutate(hubo_falla = as.integer(n_eventos > 0))
data_final <- data_final %>% group_by(id_cuadrante) %>% arrange(semana) %>%
  mutate(!!ylag := dplyr::lag(.data[[Y]], 1),
         precip_ma4 = zoo::rollmeanr(precip_total_semana, k = 4, fill = NA),
         !!yl := log1p(.data[[Y]])) %>% ungroup()

cuadrantes_infra <- st_read(file.path(UB, "infraestructura_cuadrantes_reales.gpkg"),
                            layer = "cuadrantes_infra_reales", quiet = TRUE) %>%
  mutate(id_cuadrante = as.character(if ("id_cuadrante" %in% names(.)) id_cuadrante else CUADRANTE))
if (sum(!st_is_valid(cuadrantes_infra)) > 0) cuadrantes_infra <- st_make_valid(cuadrantes_infra)
vecinos_nb <- poly2nb(cuadrantes_infra, queen = TRUE, row.names = cuadrantes_infra$id_cuadrante)
pesos_espaciales <- nb2listw(vecinos_nb, style = "W", zero.policy = TRUE)
W <- listw2mat(pesos_espaciales); dimnames(W) <- list(cuadrantes_infra$id_cuadrante, cuadrantes_infra$id_cuadrante)

rezago_esp <- function(d, v, lag_t = FALSE) {
  a <- d %>% select(id_cuadrante, semana, all_of(v)) %>% pivot_wider(names_from = id_cuadrante, values_from = all_of(v))
  s <- a$semana; m <- as.matrix(a %>% select(-semana))[, colnames(W), drop = FALSE]; m[is.na(m)] <- 0
  if (lag_t) { m <- rbind(matrix(0, 1, ncol(m)), m[-nrow(m), , drop = FALSE]) }
  r <- m %*% t(W); colnames(r) <- colnames(W)
  as.data.frame(r) %>% mutate(semana = s) %>% pivot_longer(-semana, names_to = "id_cuadrante", values_to = "val")
}
data_final <- data_final %>%
  left_join(rezago_esp(data_final, Y, TRUE) %>% rename(!!yvec := val), by = c("id_cuadrante", "semana")) %>%
  left_join(rezago_esp(data_final, "ndvi_semanal") %>% rename(ndvi_vecinos = val), by = c("id_cuadrante", "semana")) %>%
  left_join(rezago_esp(data_final, "n_eventos_catastroficos") %>% rename(n_eventos_vecinos = val), by = c("id_cuadrante", "semana"))

semanas <- sort(unique(data_final$semana))
corte   <- semanas[floor(length(semanas) * (1 - 0.15))]
cat(sprintf("Indicador: %s | panel %d filas | corte %s\n", Y, nrow(data_final), corte))

vars_orig <- c("temp_media_semana", "viento_max_semana", "precip_total_semana", "precip_ma4",
               "ndvi_semanal", "n_eventos_catastroficos", "n_sismos_r50", "dist_sismo_min_km_r50",
               ylag, "longitud_red_km", "densidad_terminales", "prop_estrato_1", "prop_estrato_2",
               "prop_no_residencial", "edad_activo_mas_viejo_anios", "PROM_CANT_MODIFICACIONES",
               yvec, "n_eventos_vecinos", "ndvi_vecinos")

# ---------------------------------------------------------------------
# C2. Predictoras ex ante: todo lo observado en t entra rezagado (t-1)
# ---------------------------------------------------------------------
# UNGRD (n_eventos_catastroficos y su rezago espacial n_eventos_vecinos) se excluye: el dataset
# oficial "Emergencias UNGRD" (datos.gov.co wwkg-r6te) cubre 2019-2022 y no se solapa con D_mod,
# por lo que ambas variables son constantes (cero) en 2024-2025.
res$ungrd_constante <- c(n_eventos_catastroficos = n_distinct(data_final$n_eventos_catastroficos),
                         n_eventos_vecinos = n_distinct(data_final$n_eventos_vecinos))
vars_contemp <- c("temp_media_semana", "viento_max_semana", "precip_total_semana", "ndvi_semanal",
                  "n_sismos_r50", "dist_sismo_min_km_r50", "ndvi_vecinos")
data_final <- data_final %>% arrange(id_cuadrante, semana) %>% group_by(id_cuadrante) %>%
  mutate(across(all_of(vars_contemp), ~ dplyr::lag(.x, 1), .names = "{.col}_l1"),
         precip_ma4_l1 = dplyr::lag(precip_ma4, 1)) %>% ungroup()
vars_ea <- c(paste0(vars_contemp, "_l1"), "precip_ma4_l1", ylag, yvec,
             "longitud_red_km", "densidad_terminales", "n_elementos",
             "prop_estrato_1", "prop_estrato_2", "prop_no_residencial",
             "edad_activo_mas_viejo_anios", "PROM_CANT_MODIFICACIONES")
res$vars_ea <- vars_ea

trn <- filter(data_final, semana <= corte, hubo_falla == 1)
tst <- filter(data_final, semana >  corte, hubo_falla == 1)
met <- function(y, p) { ok <- !is.na(y) & !is.na(p)
  c(RMSE = sqrt(mean((y[ok] - p[ok])^2)), MAE = mean(abs(y[ok] - p[ok])), R2 = cor(y[ok], p[ok])^2, n = sum(ok)) }

ajusta_panel <- function(vars, etiqueta) {
  f  <- paste(yl, "~", paste(vars, collapse = " + "))
  m1 <- fe_fit(f, trn); m2 <- fe_fit(f, trn, "id"); m3 <- fe_fit(f, trn, c("id", "sem"))
  tr_rf <- trn %>% select(all_of(c(yl, vars))) %>% na.omit()
  set.seed(123); m4 <- randomForest(as.formula(paste(yl, "~ .")), data = tr_rf, ntree = 500, importance = TRUE)
  te <- tst %>% select(all_of(c(yl, Y, vars)), id_cuadrante, semana) %>% na.omit()
  p  <- list(`Pooled OLS` = fe_pred(m1, te), `FE cuadrante` = fe_pred(m2, te),
             `FE cuadrante+semana` = fe_pred(m3, te), `Random Forest` = predict(m4, te))
  tab <- t(sapply(p, function(x) met(te[[yl]], x))) %>% as.data.frame() %>%
    tibble::rownames_to_column("modelo") %>% mutate(especificacion = etiqueta)
  list(m1 = m1, m2 = m2, m3 = m3, m4 = m4, te = te, pred = p, tab = tab)
}
cat("\n== Especificación original (contemporánea) ==\n")
orig <- ajusta_panel(vars_orig, "original (contemporánea)"); print(orig$tab)
cat("\n== Especificación ex ante (C2) ==\n")
ea   <- ajusta_panel(vars_ea, "ex ante (t-1)"); print(ea$tab)
res$tab_orig <- orig$tab; res$tab_ea <- ea$tab
# Ablación: separar el efecto del rezago del efecto de añadir n_elementos y de quitar UNGRD
cat("\n== Ablación C2 ==\n")
abl <- function(vars, etq) { f <- paste(yl, "~", paste(vars, collapse = " + "))
  m1 <- fe_fit(f, trn); m2 <- fe_fit(f, trn, "id")
  te <- tst %>% select(all_of(c(yl, vars)), id_cuadrante, semana) %>% na.omit()
  tibble(especificacion = etq, RMSE_pooled = met(te[[yl]], fe_pred(m1, te))["RMSE"],
         RMSE_FE = met(te[[yl]], fe_pred(m2, te))["RMSE"], n = nrow(te)) }
v_sin_ungrd <- setdiff(vars_orig, c("n_eventos_catastroficos", "n_eventos_vecinos"))
v_lag_sin_nel <- setdiff(vars_ea, "n_elementos")
res$ablacion <- bind_rows(abl(vars_orig, "original"), abl(v_sin_ungrd, "original sin UNGRD"),
  abl(c(v_sin_ungrd, "n_elementos"), "original sin UNGRD + n_elementos"),
  abl(v_lag_sin_nel, "ex ante sin n_elementos"), abl(vars_ea, "ex ante (final)"))
# contribución por bloque: rezagar solo el clima, solo NDVI, solo sismos
for (b in list(clima = c("temp_media_semana", "viento_max_semana", "precip_total_semana", "precip_ma4"),
               ndvi = c("ndvi_semanal", "ndvi_vecinos"), sismos = c("n_sismos_r50", "dist_sismo_min_km_r50"))) {
  vv <- v_sin_ungrd; for (x in b) vv[vv == x] <- if (x == "precip_ma4") "precip_ma4_l1" else paste0(x, "_l1")
  res$ablacion <- bind_rows(res$ablacion, abl(vv, paste("solo rezago:", paste(b, collapse = ","))))
}
print(res$ablacion)

# ---------------------------------------------------------------------
# C3. Errores estándar agrupados, Driscoll-Kraay y supuestos
# ---------------------------------------------------------------------
cat("\n== C3 ==\n")
m_fe <- ea$m2
res$coef_fe <- fe_coefs(m_fe); print(res$coef_fe, n = 50)
res$coef_pool <- fe_coefs(ea$m1)
d_pool <- trn %>% select(all_of(c(yl, vars_ea))) %>% na.omit()
m_pool <- lm(as.formula(paste(yl, "~ .")), data = d_pool)
res$bp  <- bptest(m_pool); print(res$bp)
res$aliased <- names(coef(m_pool))[is.na(coef(m_pool))]; cat("Variables sin variación (descartadas):", res$aliased, "\n")
m_pool <- lm(as.formula(paste(yl, "~", paste(setdiff(vars_ea, res$aliased), collapse = " + "))), data = d_pool)
res$vif <- car::vif(m_pool); print(round(res$vif, 2))
rr <- m_fe$datos %>% mutate(r = resid(m_fe)) %>% arrange(id_cuadrante, semana) %>% group_by(id_cuadrante) %>%
  mutate(r_l1 = dplyr::lag(r)) %>% ungroup()
res$serial <- summary(lm(r ~ r_l1, data = rr))$coefficients; print(res$serial)
res$r2_within <- r2_within(m_fe); res$r2_fe <- summary(m_fe)$r.squared

# ---------------------------------------------------------------------
# C4. Ajuste de hiperparámetros del RF (OOB + validación temporal interna)
# ---------------------------------------------------------------------
cat("\n== C4 ==\n")
sem_tr <- sort(unique(trn$semana)); corte_int <- sem_tr[floor(length(sem_tr) * 0.85)]
cols   <- c(yl, vars_ea)
tr_all <- trn %>% select(all_of(cols)) %>% na.omit()
tr_int <- trn %>% filter(semana <= corte_int) %>% select(all_of(cols)) %>% na.omit()
va_int <- trn %>% filter(semana >  corte_int) %>% select(all_of(cols)) %>% na.omit()
fy <- as.formula(paste(yl, "~ ."))
p_rf <- ncol(tr_int) - 1; cat("Predictoras en el RF:", p_rf, "\n")
grilla <- expand.grid(mtry = sort(unique(pmin(c(2, 4, 6, 9, 13, p_rf), p_rf))), min.node.size = c(5, 10, 20, 50))
grilla$oob_rmse <- NA_real_; grilla$val_rmse <- NA_real_
for (k in seq_len(nrow(grilla))) {
  m <- ranger(fy, data = tr_int, num.trees = 500, mtry = grilla$mtry[k],
              min.node.size = grilla$min.node.size[k], seed = 123)
  grilla$oob_rmse[k] <- sqrt(m$prediction.error)
  grilla$val_rmse[k] <- sqrt(mean((va_int[[yl]] - predict(m, va_int)$predictions)^2))
}
grilla <- arrange(grilla, val_rmse); print(grilla)
mejor <- grilla[1, ]; res$grilla <- grilla; res$mejor <- mejor; res$corte_int <- corte_int
g <- ggplot(grilla, aes(factor(mtry), factor(min.node.size), fill = val_rmse)) + geom_tile(color = "white") +
  geom_text(aes(label = sprintf("%.4f", val_rmse)), size = 3) +
  scale_fill_gradient(low = "#e8f1fa", high = "#2b5f8a") +
  labs(x = "mtry (variables por división)", y = "Tamaño mínimo de nodo",
       fill = "RMSE de\nvalidación\ninterna") + theme_minimal(base_size = 11)
ggsave(file.path(OUT, paste0("fig_tuning_rf_", Y, ".pdf")), g, width = 6.5, height = 4, device = cairo_pdf)
rf_fin <- ranger(fy, data = tr_all, num.trees = 1000, mtry = mejor$mtry,
                 min.node.size = mejor$min.node.size, importance = "permutation", seed = 123)
imp <- tibble(variable = names(rf_fin$variable.importance), importancia = rf_fin$variable.importance) %>%
  arrange(desc(importancia)) %>% mutate(pct = 100 * importancia / sum(pmax(importancia, 0)))
res$imp_rf <- imp; print(imp, n = 30)
etq <- function(v) gsub("_l1$", " (t-1)", gsub("_lag1$", " (t-1)", v))
g <- ggplot(imp, aes(reorder(etq(variable), importancia), importancia)) + geom_col(fill = "#2b5f8a") +
  coord_flip() + labs(x = NULL, y = "Aumento del ECM al permutar la variable") + theme_minimal(base_size = 11)
ggsave(file.path(OUT, paste0("fig_importancia_rf_", Y, ".pdf")), g, width = 6.5, height = 5, device = cairo_pdf)

# ---------------------------------------------------------------------
# C5. Líneas base, MASE, escala original y Diebold-Mariano
# ---------------------------------------------------------------------
cat("\n== C5 ==\n")
te <- ea$te
media_c <- trn %>% group_by(id_cuadrante) %>% summarise(media = mean(.data[[yl]]))
P <- te %>% left_join(media_c, by = "id_cuadrante") %>%
  mutate(`Persistencia (t-1)` = log1p(.data[[ylag]]),
         `Media del cuadrante` = coalesce(media, mean(media_c$media)),
         `Pooled OLS` = ea$pred$`Pooled OLS`, `FE cuadrante` = ea$pred$`FE cuadrante`,
         `RF sin ajuste` = ea$pred$`Random Forest`,
         `RF ajustado` = predict(rf_fin, te)$predictions)
mods <- c("Persistencia (t-1)", "Media del cuadrante", "Pooled OLS", "FE cuadrante", "RF sin ajuste", "RF ajustado")
tab5 <- lapply(mods, function(v) { mm <- met(P[[yl]], P[[v]])
  tibble(modelo = v, RMSE = mm["RMSE"], MAE = mm["MAE"], R2 = mm["R2"], n = mm["n"],
         MAE_original = mean(abs(P[[Y]] - expm1(P[[v]])), na.rm = TRUE)) }) %>% bind_rows()
tab5 <- tab5 %>% mutate(MASE = MAE / MAE[modelo == "Persistencia (t-1)"],
                        mejora_RMSE_vs_persist = 100 * (1 - RMSE / RMSE[modelo == "Persistencia (t-1)"]),
                        mejora_RMSE_vs_media = 100 * (1 - RMSE / RMSE[modelo == "Media del cuadrante"]))
print(tab5); res$tab5 <- tab5; res$pred_test <- P %>% select(id_cuadrante, semana, all_of(c(Y, yl)), all_of(mods))
e <- function(v) P[[yl]] - P[[v]]
dm <- function(a, b) { ok <- !is.na(e(a)) & !is.na(e(b)); x <- dm.test(e(a)[ok], e(b)[ok], h = 1, power = 2)
  tibble(comparacion = paste(a, "vs", b), DM = unname(x$statistic), p = x$p.value) }
best <- tab5 %>% filter(!grepl("Persist|Media", modelo)) %>% slice_min(RMSE) %>% pull(modelo)
res$dm <- bind_rows(dm("RF ajustado", "FE cuadrante"), dm(best, "Persistencia (t-1)"),
                    dm(best, "Media del cuadrante")); print(res$dm); res$mejor_modelo <- best
g <- ggplot(P, aes(.data[[yl]], .data[[best]])) + geom_point(alpha = .3, size = 1) +
  geom_abline(color = "#b2182b", linetype = "dashed") +
  labs(x = sprintf("log(1 + %s) observado", Y), y = sprintf("log(1 + %s) pronosticado", Y),
       subtitle = sprintf("%s — conjunto de prueba", best)) + theme_minimal(base_size = 11)
ggsave(file.path(OUT, paste0("fig_pred_obs_", Y, ".pdf")), g, width = 5.5, height = 5, device = cairo_pdf)

# ---------------------------------------------------------------------
# C6. Validación de origen móvil (RF ajustado y FE)
# ---------------------------------------------------------------------
cat("\n== C6 ==\n")
origenes <- semanas[c(52, 64, 76, 88)]
roll <- lapply(origenes, function(o) {
  fin <- semanas[min(which(semanas == o) + 12, length(semanas))]
  tr_o <- filter(data_final, semana <= o, hubo_falla == 1)
  te_o <- filter(data_final, semana > o, semana <= fin, hubo_falla == 1) %>%
    select(all_of(unique(c(yl, ylag, vars_ea))), id_cuadrante) %>% na.omit()
  d_o <- tr_o %>% select(all_of(cols)) %>% na.omit()
  m  <- ranger(fy, data = d_o, num.trees = 500, mtry = mejor$mtry, min.node.size = mejor$min.node.size, seed = 123)
  mf <- fe_fit(paste(yl, "~", paste(vars_ea, collapse = " + ")), tr_o, "id")
  tibble(origen = o, fin = fin, n_train = nrow(d_o), n_test = nrow(te_o),
         RMSE_RF = sqrt(mean((te_o[[yl]] - predict(m, te_o)$predictions)^2)),
         RMSE_FE = met(te_o[[yl]], fe_pred(mf, te_o %>% mutate(semana = o)))["RMSE"],
         RMSE_persist = sqrt(mean((te_o[[yl]] - log1p(te_o[[ylag]]))^2)))
}) %>% bind_rows()
print(roll); res$roll <- roll
res$roll_resumen <- roll %>% summarise(across(starts_with("RMSE"), list(media = mean, de = sd)))
print(res$roll_resumen)

# ---------------------------------------------------------------------
# C7. Corte transversal: OLS, SAR, SEM completos (réplica del Rmd)
# ---------------------------------------------------------------------
cat("\n== C7 ==\n")
yp <- paste0(Y, "_ponderado")
pt <- data_final %>% distinct(semana) %>% arrange(semana) %>%
  mutate(t = row_number(), n = n(), w = t / (n * (n + 1) / 2)) %>% select(semana, w)
cs <- data_final %>% left_join(pt, by = "semana") %>% group_by(id_cuadrante) %>%
  summarise(!!yp := sum(.data[[Y]] * w, na.rm = TRUE) / sum(w[!is.na(.data[[Y]])]),
            across(c(n_elementos, prop_transformadores, longitud_red_km, densidad_terminales,
                     prop_estrato_1, prop_estrato_2, prop_no_residencial, edad_activo_mas_viejo_anios,
                     PROM_CANT_MODIFICACIONES, cantidad_usuarios_cuadrante), first),
            ndvi_promedio = mean(ndvi_semanal, na.rm = TRUE),
            dist_sismo_prom_km = mean(dist_sismo_min_km_r50, na.rm = TRUE),
            precip_promedio = mean(precip_total_semana, na.rm = TRUE), .groups = "drop")
preds_cs <- c("n_elementos", "prop_transformadores", "longitud_red_km", "densidad_terminales",
              "prop_estrato_1", "prop_estrato_2", "prop_no_residencial", "edad_activo_mas_viejo_anios",
              "PROM_CANT_MODIFICACIONES", "ndvi_promedio", "dist_sismo_prom_km", "precip_promedio")
f_cs <- as.formula(paste(yp, "~", paste(preds_cs, collapse = " + ")))
cs_sf <- cuadrantes_infra %>% select(id_cuadrante) %>% left_join(cs, by = "id_cuadrante") %>%
  filter(!is.na(.data[[yp]])) %>% filter(if_all(all_of(preds_cs), ~ !is.na(.)))
nb_cs <- subset(vecinos_nb, cuadrantes_infra$id_cuadrante %in% cs_sf$id_cuadrante)
lw_cs <- nb2listw(nb_cs, style = "W", zero.policy = TRUE)
m_ols <- lm(f_cs, data = cs_sf)
m_sar <- lagsarlm(f_cs, data = cs_sf, listw = lw_cs, zero.policy = TRUE)
m_sem <- errorsarlm(f_cs, data = cs_sf, listw = lw_cs, zero.policy = TRUE)
lmt <- tryCatch(lm.RStests(m_ols, lw_cs, test = c("RSerr", "RSlag", "adjRSerr", "adjRSlag"), zero.policy = TRUE),
                error = function(e) lm.LMtests(m_ols, lw_cs, test = c("LMerr", "LMlag", "RLMerr", "RLMlag"), zero.policy = TRUE))
mo_y   <- moran.test(cs_sf[[yp]], lw_cs, zero.policy = TRUE)
mo_ols <- lm.morantest(m_ols, lw_cs, zero.policy = TRUE)
mo_sar <- moran.test(residuals(m_sar), lw_cs, zero.policy = TRUE)
mo_sem <- moran.test(residuals(m_sem), lw_cs, zero.policy = TRUE)
res$cs <- list(n = nrow(cs_sf), R2_ols = summary(m_ols)$r.squared, adjR2_ols = summary(m_ols)$adj.r.squared,
  AIC = c(OLS = AIC(m_ols), SAR = AIC(m_sar), SEM = AIC(m_sem)),
  rho = m_sar$rho, rho_p = summary(m_sar)$LR1$p.value, lambda = m_sem$lambda, lambda_p = summary(m_sem)$LR1$p.value,
  moran_y = c(I = unname(mo_y$estimate[1]), p = mo_y$p.value),
  moran_res = rbind(OLS = c(mo_ols$estimate[1], p = mo_ols$p.value), SAR = c(mo_sar$estimate[1], p = mo_sar$p.value),
                    SEM = c(mo_sem$estimate[1], p = mo_sem$p.value)),
  lm_tests = sapply(lmt, function(x) c(stat = unname(x$statistic), p = x$p.value)),
  coef_ols = summary(m_ols)$coefficients, coef_sar = summary(m_sar)$Coef, coef_sem = summary(m_sem)$Coef)
imp_sar <- summary(impacts(m_sar, listw = lw_cs, R = 500), zstats = TRUE, short = TRUE)
res$cs$impactos <- cbind(as.data.frame(attr(imp_sar$res, "names") %>% {.}),
                         direct = imp_sar$res$direct, indirect = imp_sar$res$indirect, total = imp_sar$res$total)
print(res$cs[c("n", "R2_ols", "AIC", "rho", "rho_p", "lambda", "lambda_p", "moran_y", "moran_res", "lm_tests")])

# ---------------------------------------------------------------------
# C8. Componente de ocurrencia (modelo en dos partes)
# ---------------------------------------------------------------------
cat("\n== C8 ==\n")
vars_occ <- setdiff(vars_ea, c(ylag, yvec))
vars_occ <- c(vars_occ, "hubo_falla_l1")
data_final <- data_final %>% group_by(id_cuadrante) %>% arrange(semana) %>%
  mutate(hubo_falla_l1 = dplyr::lag(hubo_falla, 1)) %>% ungroup()
tr_o <- data_final %>% filter(semana <= corte) %>% select(hubo_falla, all_of(vars_occ)) %>% na.omit() %>%
  mutate(hubo_falla = factor(hubo_falla))
te_o <- data_final %>% filter(semana > corte) %>% select(hubo_falla, all_of(vars_occ), id_cuadrante, semana, all_of(c(Y, yl, ylag, vars_ea))) %>% na.omit()
rf_occ <- ranger(hubo_falla ~ ., data = tr_o, probability = TRUE, num.trees = 500, seed = 123)
te_o$p_falla <- predict(rf_occ, te_o)$predictions[, "1"]
res$auc <- as.numeric(auc(roc(te_o$hubo_falla, te_o$p_falla, quiet = TRUE)))
res$auc_persist <- as.numeric(auc(roc(te_o$hubo_falla, te_o$hubo_falla_l1, quiet = TRUE)))
te_o$y_cond <- predict(rf_fin, te_o)$predictions
te_o <- te_o %>% mutate(E_y = p_falla * expm1(y_cond))
res$dos_partes <- tibble(AUC = res$auc, AUC_persistencia = res$auc_persist,
  MAE_original_incond = mean(abs(te_o[[Y]] - te_o$E_y)),
  MAE_original_cero = mean(abs(te_o[[Y]])),
  spearman_incond = cor(te_o[[Y]], te_o$E_y, method = "spearman"))
print(res$dos_partes)

# ---------------------------------------------------------------------
# C9. Atípicos: regla p99.5 en entrenamiento + sensibilidad
# ---------------------------------------------------------------------
cat("\n== C9 ==\n")
p995 <- quantile(trn[[Y]], 0.995, na.rm = TRUE)
n_atip <- sum(filter(data_final, hubo_falla == 1)[[Y]] > p995, na.rm = TRUE)
trw <- tr_all; trw[[yl]] <- pmin(trw[[yl]], log1p(p995))
m_w <- ranger(fy, data = trw, num.trees = 1000, mtry = mejor$mtry, min.node.size = mejor$min.node.size, seed = 123)
res$atipicos <- tibble(umbral_p995 = p995, n_semanas_sobre_umbral = n_atip,
  pct = 100 * n_atip / sum(data_final$hubo_falla == 1),
  RMSE_test_original = met(P[[yl]], P$`RF ajustado`)["RMSE"],
  RMSE_test_winsorizado = met(P[[yl]], predict(m_w, te)$predictions)["RMSE"])
print(res$atipicos)

# ---------------------------------------------------------------------
# C10. Robustez del corte transversal (réplica de la Parte 8 del Rmd)
# ---------------------------------------------------------------------
cat("\n== C10 ==\n")
m_step <- MASS::stepAIC(m_ols, direction = "both", trace = FALSE)
pf <- names(coef(m_step))[-1]
r2b <- summary(m_step)$r.squared
m_ctrl <- lm(update(formula(m_step), . ~ . + log1p(cantidad_usuarios_cuadrante)), data = cs_sf)
sens <- lapply(pf, function(v) tibble(variable_excluida = v,
  caida_R2 = r2b - summary(lm(as.formula(paste(yp, "~", if (length(setdiff(pf, v))) paste(setdiff(pf, v), collapse = "+") else "1")), data = cs_sf))$r.squared)) %>%
  bind_rows() %>% arrange(desc(caida_R2))
set.seed(123); dp <- st_drop_geometry(cs_sf)
r2p <- replicate(500, { dp$ys <- sample(dp[[yp]]); summary(lm(as.formula(paste("ys ~", if (length(pf)) paste(pf, collapse = "+") else "1")), data = dp))$r.squared })
# Validación cruzada espacial simple: 5 bloques por fila de la malla (k-fold por latitud)
cent <- st_coordinates(suppressWarnings(st_centroid(cs_sf)))
bloque <- cut(rank(cent[, 2]), 5, labels = FALSE)
cv <- sapply(1:5, function(b) { m <- lm(formula(m_step), data = dp[bloque != b, ])
  c(obs = dp[[yp]][bloque == b]) -> o; p <- predict(m, dp[bloque == b, ]); c(sum((o - p)^2), sum((o - mean(dp[[yp]][bloque != b]))^2)) })
res$cs_robustez <- tibble(R2_stepwise = r2b, adjR2_stepwise = summary(m_step)$adj.r.squared,
  n_predictores = length(pf), R2_con_control_usuarios = summary(m_ctrl)$r.squared,
  variable_dominante = sens$variable_excluida[1], caida_max = sens$caida_R2[1],
  p_permutacion = mean(r2p >= r2b), R2_cv_espacial = 1 - sum(cv[1, ]) / sum(cv[2, ]))
res$cs_sens <- sens; res$cs_step_coef <- summary(m_step)$coefficients; res$vif_cs <- if (length(pf) >= 2) car::vif(m_step) else NA
print(res$cs_robustez); print(sens)

# ---------------------------------------------------------------------
# C11. Diccionario de variables
# ---------------------------------------------------------------------
dic <- tibble(variable = names(data_final), tipo = sapply(data_final, function(x) class(x)[1]),
              pct_NA = round(100 * colMeans(is.na(data_final)), 2)) %>%
  mutate(rol = case_when(variable %in% c("id_cuadrante", "semana", "latitud", "longitud") ~ "Llave",
                         variable %in% c("SAIDI", "SAIFI", "log_SAIDI1", "log_SAIFI1") ~ "Respuesta",
                         variable %in% c("usuarios_afectados", "elementos_afectados", "n_eventos", "duracion_total") ~ "Insumo de construcción (ex post)",
                         variable %in% vars_ea ~ "Predictora ex ante",
                         TRUE ~ "No usada en el modelo"))
write.csv(dic, file.path(OUT, "diccionario_variables_panel.csv"), row.names = FALSE)

saveRDS(res, file.path(OUT, paste0("resultados_", Y, ".rds")))
sink()
