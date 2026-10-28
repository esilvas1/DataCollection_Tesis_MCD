# =====================================================================
#  CÓDIGO DE CIERRE – TG GRUPO 4 (SAIDI / SAIFI por cuadrante × semana)
#  Bloques para agregar a Etapa5_01 / Etapa5_02 (o a un Etapa5_03 nuevo).
#  Supone los objetos y nombres que ya usan los .Rmd:
#    data_final (panel D_mod con SAIDI, SAIFI, hubo_falla, id_cuadrante,
#    semana, ...), pesos_espaciales (listw queen), vars_modelo, corte.
#  REVISAR nombres de columnas marcados con  # <-- verificar
# =====================================================================

library(dplyr); library(tidyr); library(lubridate); library(ggplot2)
library(fixest); library(ranger); library(spdep); library(spatialreg)
library(lmtest); library(pROC); library(forecast); library(knitr)

# ---------------------------------------------------------------------
# C0. PASO 0 – ¿Qué fórmula de SAIDI/SAIFI trae el CSV?  (OBS-01)
#     La guía maestra lo marca como pendiente CRÍTICO.
#     El Capítulo 1 (intocable) define:
#       SAIFI = usuarios_afectados / UT_m(s)
#       SAIDI = duracion_total * usuarios_afectados / UT_m(s)
# ---------------------------------------------------------------------
# Este chunk sí se puede correr (eval=TRUE) para generar la tabla
# real desde el .rds actual, en vez de la lista estática de abajo:
#
Sys.setenv(UBICACION_DATA = "C:/Users/User/OneDrive - PUJ Cali/Archivos de EDWIN SILVA SALAS - Projecto_Grado_Javeriana/Data_Project")
data_final <- readRDS(file.path(Sys.getenv("UBICACION_DATA"), "data_final_modelo_cuadrantes_reales.rds"))

chk <- data_final %>%
  mutate(
    SAIFI_cap1  = usuarios_afectados / usuarios_totales,
    SAIDI_cap1  = duracion_total * usuarios_afectados / usuarios_totales,
    SAIFI_local = usuarios_afectados / cantidad_usuarios_cuadrante,
    SAIDI_local = duracion_total / cantidad_usuarios_cuadrante
  )
tibble(
  formula = c("Cap. 1 (UT del sistema)", "Local (usuarios del cuadrante)"),
  max_dif_SAIDI = c(max(abs(chk$SAIDI - chk$SAIDI_cap1),  na.rm = TRUE),
                    max(abs(chk$SAIDI - chk$SAIDI_local), na.rm = TRUE)),
  max_dif_SAIFI = c(max(abs(chk$SAIFI - chk$SAIFI_cap1),  na.rm = TRUE),
                    max(abs(chk$SAIFI - chk$SAIFI_local), na.rm = TRUE))
) %>% kable(digits = 8)
# ¿usuarios_totales varía por mes (UT_m(s)) o es constante?
data_final %>% group_by(mes = floor_date(semana, "month")) %>%
  summarise(UT = n_distinct(usuarios_totales)) %>% count(UT)
# Si la diferencia mínima NO es la del Cap. 1, recalcular SAIDI/SAIFI con la
# fórmula del Cap. 1 (con UT mensual) y re-ejecutar TODO lo que sigue.

# ---------------------------------------------------------------------
# C1. Robustez del indicador: versión evento a evento (Apéndice P1)
# ---------------------------------------------------------------------
# Requiere: data_final (cargado en C0), dplyr, lubridate, readxl, knitr
eventos <- read.csv(file.path(Sys.getenv("UBICACION_DATA"), "tabla_eventos_ajustado.csv"),
                    fileEncoding = "UTF-8-BOM")
# El mapa elemento -> cuadrante solo existe en .xls; CUADRANTE_1 usa la misma numeracion (1-344) que id_cuadrante
mapa_cuad <- readxl::read_excel(file.path(Sys.getenv("UBICACION_DATA"), "Distribución de Cuadrantes",
                                          "ELEMENTO_FALLA_CUADRANTE_800.xls")) %>%
  distinct(ELEMENTO, .keep_all = TRUE) %>%
  select(COMPONENTE_FALLADO = ELEMENTO, id_cuadrante = CUADRANTE_1)
# UT mensual: se toma del propio panel (columna usuarios_totales, un valor por mes; verificado en C0)
ut_sem <- data_final %>% mutate(semana = as.Date(semana)) %>% distinct(semana, UT = usuarios_totales)

saidi_ev <- eventos %>%
  mutate(ini = as.POSIXct(FECHA_DESCONEXION, format = "%d/%m/%Y %H:%M", tz = "UTC"),
         fin = as.POSIXct(FECHA_CONEXION,    format = "%d/%m/%Y %H:%M", tz = "UTC"),
         D_h = as.numeric(difftime(fin, ini, units = "hours")),
         semana = floor_date(as.Date(ini), "week", week_start = 1)) %>%
  filter(year(semana) %in% 2024:2025) %>%
  inner_join(mapa_cuad, by = "COMPONENTE_FALLADO") %>%
  mutate(id_cuadrante = as.integer(id_cuadrante)) %>%
  group_by(id_cuadrante, semana) %>%
  summarise(n_ev = n(), DxU = sum(D_h * USUARIOS_AFECTADOS), .groups = "drop") %>%
  inner_join(ut_sem, by = "semana") %>%
  mutate(SAIDI_ev = DxU / UT)

comp <- data_final %>% filter(hubo_falla == 1) %>%
  mutate(semana = as.Date(semana), id_cuadrante = as.integer(id_cuadrante)) %>%
  select(id_cuadrante, semana, SAIDI) %>%
  inner_join(saidi_ev, by = c("id_cuadrante", "semana"))
top20 <- function(v) comp %>% group_by(id_cuadrante) %>% summarise(m = mean(.data[[v]])) %>%
  slice_max(m, n = 20) %>% pull(id_cuadrante)
tibble(
  pct_un_evento   = 100 * mean(comp$n_ev == 1),
  spearman        = cor(comp$SAIDI, comp$SAIDI_ev, method = "spearman"),
  coincide_top20  = 100 * length(intersect(top20("SAIDI"), top20("SAIDI_ev"))) / 20,
  razon_mediana   = median(comp$SAIDI / comp$SAIDI_ev),
  razon_p25       = quantile(comp$SAIDI / comp$SAIDI_ev, .25),
  razon_p75       = quantile(comp$SAIDI / comp$SAIDI_ev, .75)
) %>% kable(digits = 3)
# Esperado (verificado en Python 27-oct): 46.3 | 0.874 | 65 | 1.797 | 1.00 | 4.67

# ---------------------------------------------------------------------
# C2. Predictoras realmente ex ante (OBS-04 / NV-01): rezagar todo lo
#     que se observa en la semana t.
# ---------------------------------------------------------------------
vars_contemp <- c("temp_media_semana", "viento_max_semana", "precip_total_semana",
                  "ndvi_semanal", "n_eventos_catastroficos", "n_sismos_r50",
                  "dist_sismo_min_km_r50", "n_eventos_vecinos", "ndvi_vecinos")
data_final <- data_final %>% arrange(id_cuadrante, semana) %>% group_by(id_cuadrante) %>%
  mutate(across(all_of(vars_contemp), ~ lag(.x, 1), .names = "{.col}_l1"),
         precip_ma4_l1 = lag(zoo::rollmeanr(precip_total_semana, 4, fill = NA), 1)) %>%
  ungroup()
vars_modelo_exante <- c(paste0(vars_contemp, "_l1"), "precip_ma4_l1",
                        "SAIDI_lag1", "SAIDI_vecinos_lag1",                 # SAIFI_* en el modelo de SAIFI
                        "longitud_red_km", "densidad_terminales", "n_elementos",
                        "prop_estrato_1", "prop_estrato_2", "prop_no_residencial",
                        "edad_activo_mas_viejo_anios", "PROM_CANT_MODIFICACIONES")
# Partición única (OBS-03): la misma que hoy usa el .Rmd (corte = 2025-09-08)
train <- data_final %>% filter(semana <= corte)
test  <- data_final %>% filter(semana >  corte)

# ---------------------------------------------------------------------
# C3. Errores estándar agrupados y diagnóstico de supuestos (OBS-06)
# ---------------------------------------------------------------------
f_fe <- as.formula(paste("log_SAIDI1 ~", paste(vars_modelo_exante, collapse = " + "), "| id_cuadrante"))
m_fe <- feols(f_fe, data = filter(train, hubo_falla == 1), cluster = ~id_cuadrante)
m_fe_dk <- summary(m_fe, vcov = "DK", panel.id = ~id_cuadrante + semana)   # Driscoll-Kraay
etable(m_fe, m_fe_dk, headers = c("Cluster cuadrante", "Driscoll-Kraay"))
m_pool <- lm(as.formula(paste("log_SAIDI1 ~", paste(vars_modelo_exante, collapse = " + "))),
             data = filter(train, hubo_falla == 1))
bptest(m_pool)                    # heterocedasticidad (Breusch-Pagan)
car::vif(m_pool)                  # VIF del modelo final
res <- filter(train, hubo_falla == 1) %>% mutate(r = resid(m_fe)) %>%
  arrange(id_cuadrante, semana) %>% group_by(id_cuadrante) %>% mutate(r_l1 = lag(r))
summary(lm(r ~ r_l1, data = res)) # autocorrelación serial de residuos (tipo Wooldridge)

# ---------------------------------------------------------------------
# C4. Ajuste de hiperparámetros del RF con OOB + validación temporal
#     interna DENTRO del entrenamiento (OBS-05 / NV-04)
# ---------------------------------------------------------------------
tr <- filter(train, hubo_falla == 1) %>% select(log_SAIDI1, all_of(vars_modelo_exante)) %>% na.omit()
corte_int <- sort(unique(filter(train, hubo_falla == 1)$semana)) %>% {.[floor(length(.) * 0.85)]}
tr_int  <- filter(train, hubo_falla == 1, semana <= corte_int) %>% select(names(tr)) %>% na.omit()
val_int <- filter(train, hubo_falla == 1, semana >  corte_int) %>% select(names(tr)) %>% na.omit()
grilla <- expand.grid(mtry = c(2, 4, 6, 8, 10, 14), min.node.size = c(5, 10, 20, 50))
grilla$oob_rmse <- NA; grilla$val_rmse <- NA
set.seed(123)
for (k in seq_len(nrow(grilla))) {
  m <- ranger(log_SAIDI1 ~ ., data = tr_int, num.trees = 500, mtry = grilla$mtry[k],
              min.node.size = grilla$min.node.size[k], seed = 123)
  grilla$oob_rmse[k] <- sqrt(m$prediction.error)
  grilla$val_rmse[k] <- sqrt(mean((val_int$log_SAIDI1 - predict(m, val_int)$predictions)^2))
}
grilla %>% arrange(val_rmse) %>% kable(digits = 4)       # TABLA para la tesis
ggplot(grilla, aes(factor(mtry), factor(min.node.size), fill = val_rmse)) + geom_tile() +
  geom_text(aes(label = round(val_rmse, 4)), size = 3) +
  labs(x = "mtry", y = "min.node.size", fill = "RMSE validación") + theme_minimal()  # FIGURA
mejor <- grilla[which.min(grilla$val_rmse), ]
rf_final <- ranger(log_SAIDI1 ~ ., data = tr, num.trees = 1000, mtry = mejor$mtry,
                   min.node.size = mejor$min.node.size, importance = "permutation", seed = 123)

# ---------------------------------------------------------------------
# C5. Línea base, métricas en escala original, MASE y Diebold-Mariano
#     (OBS-10)
# ---------------------------------------------------------------------
te <- filter(test, hubo_falla == 1) %>% select(id_cuadrante, semana, log_SAIDI1, SAIDI,
                                                all_of(vars_modelo_exante)) %>% na.omit()
media_cuad <- filter(train, hubo_falla == 1) %>% group_by(id_cuadrante) %>%
  summarise(media = mean(log_SAIDI1))
preds <- te %>% left_join(media_cuad, by = "id_cuadrante") %>%
  mutate(p_persist = log1p(SAIDI_lag1),
         p_media   = coalesce(media, mean(media_cuad$media)),
         p_fe      = predict(m_fe, newdata = te),
         p_rf      = predict(rf_final, te)$predictions)
met <- function(y, p) c(RMSE = sqrt(mean((y - p)^2, na.rm = TRUE)), MAE = mean(abs(y - p), na.rm = TRUE),
                        R2 = cor(y, p, use = "complete.obs")^2)
tab <- sapply(c("p_persist", "p_media", "p_fe", "p_rf"), function(v) met(preds$log_SAIDI1, preds[[v]]))
mae_ing <- tab["MAE", "p_persist"]
rbind(tab, MASE = tab["MAE", ] / mae_ing,
      MAE_original = sapply(c("p_persist", "p_media", "p_fe", "p_rf"),
                            function(v) mean(abs(preds$SAIDI - expm1(preds[[v]])), na.rm = TRUE))) %>%
  kable(digits = 4)
e_rf <- preds$log_SAIDI1 - preds$p_rf; e_fe <- preds$log_SAIDI1 - preds$p_fe
dm.test(e_rf[!is.na(e_fe)], e_fe[!is.na(e_fe)], h = 1, power = 2)   # RF vs FE

# ---------------------------------------------------------------------
# C6. Validación de origen móvil (NV-05)
# ---------------------------------------------------------------------
semanas <- sort(unique(data_final$semana))
origenes <- semanas[c(52, 64, 76, 88)]     # 4 orígenes, ventanas de ~12 semanas
rolling <- lapply(origenes, function(o) {
  fin <- semanas[min(which(semanas == o) + 12, length(semanas))]
  tr_o <- filter(data_final, semana <= o, hubo_falla == 1) %>% select(names(tr)) %>% na.omit()
  te_o <- filter(data_final, semana > o, semana <= fin, hubo_falla == 1) %>% select(names(tr)) %>% na.omit()
  m <- ranger(log_SAIDI1 ~ ., data = tr_o, num.trees = 500, mtry = mejor$mtry,
              min.node.size = mejor$min.node.size, seed = 123)
  tibble(origen = o, RMSE = sqrt(mean((te_o$log_SAIDI1 - predict(m, te_o)$predictions)^2)))
}) %>% bind_rows()
rolling %>% summarise(media = mean(RMSE), de = sd(RMSE))

# ---------------------------------------------------------------------
# C7. Modelos espaciales completos (OBS-09): LM robustos, Moran de
#     residuos, rho/lambda, impactos, AIC verificado
# ---------------------------------------------------------------------
m_ols_cs <- lm(formula_espacial, data = cross_section_sf)
lm.RStests(m_ols_cs, pesos_espaciales_cs, test = c("RSerr", "RSlag", "adjRSerr", "adjRSlag"))
lm.morantest(m_ols_cs, pesos_espaciales_cs)
m_sar <- lagsarlm(formula_espacial, data = cross_section_sf, listw = pesos_espaciales_cs)
m_sem <- errorsarlm(formula_espacial, data = cross_section_sf, listw = pesos_espaciales_cs)
c(OLS = AIC(m_ols_cs), SAR = AIC(m_sar), SEM = AIC(m_sem))   # <-- este es el AIC que va a la tesis
summary(m_sar)$rho; summary(m_sem)$lambda
summary(impacts(m_sar, listw = pesos_espaciales_cs, R = 500), zstats = TRUE)
moran.test(residuals(m_sar), pesos_espaciales_cs)

# ---------------------------------------------------------------------
# C8. Componente de ocurrencia (modelo en dos partes) (OBS-02)
# ---------------------------------------------------------------------
vars_occ <- setdiff(vars_modelo_exante, c("SAIDI_lag1", "SAIDI_vecinos_lag1"))
rf_occ <- ranger(factor(hubo_falla) ~ ., data = train %>% select(hubo_falla, all_of(vars_occ)) %>% na.omit(),
                 probability = TRUE, num.trees = 500, seed = 123)
te_occ <- test %>% select(hubo_falla, all_of(vars_occ), id_cuadrante, semana, SAIDI) %>% na.omit()
te_occ$p_falla <- predict(rf_occ, te_occ)$predictions[, "1"]
auc(roc(te_occ$hubo_falla, te_occ$p_falla))                       # AUC del componente de ocurrencia
# Valor esperado incondicional: E[Y] = P(falla) * E[Y | falla]

# ---------------------------------------------------------------------
# C9. Atípicos (OBS-20): regla documentada + sensibilidad
# ---------------------------------------------------------------------
p995 <- quantile(filter(train, hubo_falla == 1)$duracion_total, 0.995, na.rm = TRUE)
sum(data_final$duracion_total > p995, na.rm = TRUE)   # n.º de semanas afectadas -> reportar
# Re-estimar el modelo con duracion_total winsorizada en p995 y comparar el RMSE (tabla de sensibilidad)

# ---------------------------------------------------------------------
# C10. Tabla de robustez del corte transversal (OBS-08 / NV-09)
# ---------------------------------------------------------------------
r2 <- function(f, d) summary(lm(f, data = d))$r.squared
f_base <- formula_espacial
f_ctrl <- update(f_base, . ~ . + log1p(cantidad_usuarios_cuadrante))
tibble(R2_base = r2(f_base, cross_section_sf), R2_con_control_usuarios = r2(f_ctrl, cross_section_sf),
       caida_max_por_exclusion = max(sensibilidad$caida_R2), variable_dominante = variable_dominante,
       p_permutacion = mean(r2_permutados >= r2_base)) %>% kable(digits = 3)

# ---------------------------------------------------------------------
# C11. Diccionario de variables para el catálogo (OBS-11)
# ---------------------------------------------------------------------
diccionario <- tibble(variable = names(data_final),
                      tipo = sapply(data_final, function(x) class(x)[1]),
                      pct_NA = round(100 * colMeans(is.na(data_final)), 2)) %>%
  mutate(rol = case_when(variable %in% c("id_cuadrante", "semana", "latitud", "longitud") ~ "Llave",
                         variable %in% c("SAIDI", "SAIFI") ~ "Respuesta",
                         variable %in% c("usuarios_afectados", "elementos_afectados", "n_eventos", "duracion_total") ~ "Excluida (ex post)",
                         variable %in% vars_modelo_exante ~ "Predictora ex ante",
                         TRUE ~ "No usada en el modelo"))
write.csv(diccionario, "diccionario_variables_panel.csv", row.names = FALSE)
knitr::kable(diccionario, format = "latex", booktabs = TRUE)   # pegar como Tabla tab:catalogo_variables
