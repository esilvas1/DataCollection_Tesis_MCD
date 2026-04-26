# 📊 Capítulo 10. Modelación no paramétrica de SAIDI


# -----------------------------------------------------------
# 🌲 9. Modelo 3: Random Forest (SAIDI)
# -----------------------------------------------------------


1. Introducción

En este capítulo se implementa un modelo de aprendizaje automático basado en Random Forest para predecir el indicador SAIDI. A diferencia de los modelos lineales, este enfoque permite capturar relaciones no lineales, interacciones complejas y efectos umbral entre las variables explicativas.

El objetivo es evaluar si un modelo no paramétrico mejora la capacidad predictiva frente a los modelos econométricos tradicionales.

2. Preparación de datos
library(dplyr)

df_rf <- panel_semana %>%
  select(
    SAIDI,
    temp_media_semana,
    humedad_media_semana,
    precip_total_semana,
    viento_max_semana,
    lluvia_intensa,
    viento_fuerte,
    SAIDI_lag1, SAIDI_lag2, SAIDI_lag3,
    lluvia_lag2,
    viento_lag1
  ) %>%
  na.omit()
3. Recipe

👉 Aquí sí tiene más sentido usar recipe()

library(recipes)

rec_rf <- recipe(SAIDI ~ ., data = df_rf) %>%
  step_impute_median(all_predictors())
4. Especificación del modelo
library(parsnip)

rf_spec <- rand_forest(
  trees = 300,
  mtry = 4,
  min_n = 10
) %>%
  set_engine("ranger") %>%
  set_mode("regression")
5. Workflow
library(workflows)

wf_rf <- workflow() %>%
  add_recipe(rec_rf) %>%
  add_model(rf_spec)

fit_rf <- fit(wf_rf, data = df_rf)
6. Importancia de variables
library(vip)

vip(extract_fit_parsnip(fit_rf)$fit)

👉 Esto permite identificar qué variables explican más SAIDI

7. Evaluación del modelo (in-sample)
library(Metrics)

pred_rf <- predict(fit_rf, df_rf) %>%
  bind_cols(df_rf)

rmse_rf <- rmse(pred_rf$SAIDI, pred_rf$.pred)
mae_rf  <- mae(pred_rf$SAIDI, pred_rf$.pred)

rmse_rf
mae_rf
8. Validación temporal (Train/Test)
library(rsample)

panel_semana <- panel_semana %>% arrange(semana)

split <- initial_time_split(panel_semana, prop = 0.8)

train <- training(split)
test  <- testing(split)

fit_rf_train <- fit(wf_rf, data = train)

pred_test <- predict(fit_rf_train, test)

rmse_test <- rmse(test$SAIDI, pred_test$.pred)
mae_test  <- mae(test$SAIDI, pred_test$.pred)

rmse_test
mae_test
9. Validación rolling
library(purrr)

rolling_splits <- rolling_origin(
  panel_semana,
  initial = 5000,
  assess = 1000,
  skip = 1000,
  cumulative = TRUE
)

eval_rf <- function(split) {
  
  train <- analysis(split)
  test  <- assessment(split)
  
  fit <- fit(wf_rf, data = train)
  pred <- predict(fit, test)
  
  data.frame(
    rmse = rmse(test$SAIDI, pred$.pred),
    mae  = mae(test$SAIDI, pred$.pred)
  )
}

resultados_rf <- map_df(rolling_splits$splits, eval_rf)

summary(resultados_rf)
10. Comparación con modelo lineal
tabla_rf <- data.frame(
  Modelo = c("Regresión con rezagos", "Random Forest"),
  RMSE = c(rmse_lags, rmse_rf),
  MAE  = c(mae_lags, mae_rf)
)

knitr::kable(tabla_rf, digits = 3)
11. Interpretación

El modelo Random Forest permite capturar relaciones no lineales entre variables climáticas y la duración de las interrupciones. La importancia de variables muestra que factores como precipitación, viento y rezagos del sistema tienen un papel relevante en la explicación de SAIDI.

12. Ventajas y limitaciones
Ventajas:
  Captura no linealidades
Maneja interacciones automáticamente
Mayor capacidad predictiva
Limitaciones:
  Menor interpretabilidad
No permite inferencia causal directa
Sensible a tuning de hiperparámetros
13. Conclusión

El modelo Random Forest constituye una herramienta potente para mejorar la predicción de SAIDI, especialmente en presencia de relaciones complejas no lineales. Sin embargo, su uso debe complementarse con modelos econométricos para fines interpretativos.
