# 📊 Capítulo 9. Modelación de SAIFI
#1. Introducción

# En este capítulo se modela la frecuencia de interrupciones del servicio eléctrico (SAIFI), la cual corresponde a una variable de conteo. Dado que estos datos presentan características particulares como asimetría, discreción y posible sobredispersión, se emplean modelos de regresión de conteo, específicamente Poisson y Binomial Negativa.

# El objetivo es identificar la especificación más adecuada en términos de ajuste estadístico y capacidad predictiva.
# 
# 
# 2. Especificación del modelo
# 
# Se modela:
#   
#   $SAIFI_t=f(X_t)$
# 
# donde X_t
# 
# 
# incluye variables climáticas y operativas.

# -----------------------------------------------------------
# 🔢 1. Modelo 2: Poisson / Binomial Negativa (SAIFI)
# -----------------------------------------------------------
#🔹 3. Preparación de datos
# library(dplyr)

df_saifi <- panel_semana %>%
  select(
    SAIFI,
    precip_total_semana,
    viento_max_semana,
    temp_media_semana,
    humedad_media_semana,
    lluvia_intensa,
    viento_fuerte
  ) %>%
  na.omit()
#🔹 4. Modelo Poisson
# 4.1 Estimación
modelo_poisson <- glm(
  SAIFI ~ precip_total_semana + viento_max_semana +
    temp_media_semana + humedad_media_semana +
    lluvia_intensa + viento_fuerte,
  family = poisson(link = "log"),
  data = df_saifi
)

summary(modelo_poisson)
4.2 Interpretación
Los coeficientes representan cambios en el logaritmo de la tasa esperada
Se interpretan como efectos multiplicativos sobre SAIFI
🔹 5. Diagnóstico de sobredispersión
5.1 Evaluación numérica
mean_saifi <- mean(df_saifi$SAIFI)
var_saifi  <- var(df_saifi$SAIFI)

mean_saifi
var_saifi

👉 Regla clave:
  
  Poisson asume: Var = Media
Si Var >> Media → hay sobredispersión
5.2 Test formal
dispersion_test <- sum(residuals(modelo_poisson, type = "pearson")^2) / modelo_poisson$df.residual
dispersion_test

👉 Interpretación:
  
  ≈ 1 → OK

1.5 → sobredispersión

2 → fuerte sobredispersión

5.3 Diagnóstico gráfico
library(ggplot2)

ggplot(df_saifi, aes(x = SAIFI)) +
  geom_histogram(bins = 30, fill = "steelblue", alpha = 0.7) +
  labs(title = "Distribución de SAIFI") +
  theme_minimal()
# Residuos vs ajustados
plot(fitted(modelo_poisson), residuals(modelo_poisson, type = "pearson"),
     xlab = "Valores ajustados",
     ylab = "Residuos de Pearson",
     main = "Diagnóstico de sobredispersión")
abline(h = 0, col = "red")

👉 Si los residuos crecen con el valor ajustado → evidencia de sobredispersión

🔹 6. Modelo Binomial Negativa
6.1 Estimación
library(MASS)

modelo_nb <- glm.nb(
  SAIFI ~ precip_total_semana + viento_max_semana +
    temp_media_semana + humedad_media_semana +
    lluvia_intensa + viento_fuerte,
  data = df_saifi
)

summary(modelo_nb)
6.2 Interpretación
Introduce parámetro de dispersión adicional
Permite Var > Media
Más flexible que Poisson
🔹 7. Comparación de modelos
7.1 AIC
AIC(modelo_poisson, modelo_nb)

👉 Menor AIC = mejor modelo

7.2 Evaluación predictiva
library(Metrics)

pred_pois <- predict(modelo_poisson, type = "response")
pred_nb   <- predict(modelo_nb, type = "response")

rmse_pois <- rmse(df_saifi$SAIFI, pred_pois)
rmse_nb   <- rmse(df_saifi$SAIFI, pred_nb)

mae_pois <- mae(df_saifi$SAIFI, pred_pois)
mae_nb   <- mae(df_saifi$SAIFI, pred_nb)

data.frame(
  Modelo = c("Poisson", "Negativa Binomial"),
  RMSE = c(rmse_pois, rmse_nb),
  MAE  = c(mae_pois, mae_nb)
)
7.3 Comparación gráfica
df_compare <- data.frame(
  real = df_saifi$SAIFI,
  poisson = pred_pois,
  nb = pred_nb
)

ggplot(df_compare, aes(x = real)) +
  geom_point(aes(y = poisson), color = "blue", alpha = 0.3) +
  geom_point(aes(y = nb), color = "darkgreen", alpha = 0.3) +
  geom_abline(slope = 1, intercept = 0) +
  theme_minimal() +
  labs(title = "Comparación de predicciones")
🔹 8. Validación temporal
8.1 Train/Test
library(rsample)

panel_semana <- panel_semana %>% arrange(semana)

split <- initial_time_split(panel_semana, prop = 0.8)

train <- training(split)
test  <- testing(split)

modelo_nb_train <- glm.nb(
  SAIFI ~ precip_total_semana + viento_max_semana +
    temp_media_semana + humedad_media_semana +
    lluvia_intensa + viento_fuerte,
  data = train
)

pred_test <- predict(modelo_nb_train, newdata = test, type = "response")

rmse_test <- rmse(test$SAIFI, pred_test)
mae_test  <- mae(test$SAIFI, pred_test)

rmse_test
mae_test
8.2 Rolling validation
library(purrr)

rolling_splits <- rolling_origin(
  panel_semana,
  initial = 5000,
  assess = 1000,
  skip = 1000,
  cumulative = TRUE
)

eval_model_nb <- function(split) {
  train <- analysis(split)
  test  <- assessment(split)
  
  modelo <- glm.nb(
    SAIFI ~ precip_total_semana + viento_max_semana +
      temp_media_semana + humedad_media_semana +
      lluvia_intensa + viento_fuerte,
    data = train
  )
  
  pred <- predict(modelo, newdata = test, type = "response")
  
  data.frame(
    rmse = rmse(test$SAIFI, pred),
    mae  = mae(test$SAIFI, pred)
  )
}

resultados_rolling <- map_df(rolling_splits$splits, eval_model_nb)

summary(resultados_rolling)
🔹 9. Selección del modelo final

Dado que:
  
  Existe sobredispersión significativa
El modelo binomial negativa presenta mejor ajuste (AIC menor)
Mejora las métricas predictivas

👉 Se selecciona el modelo binomial negativa como especificación final.

🔹 10. Conclusión

El análisis evidencia que la modelación de SAIFI requiere considerar la naturaleza de conteo y la sobredispersión presente en los datos. El modelo binomial negativo permite capturar de forma más adecuada la variabilidad del proceso, proporcionando mejores resultados en términos de ajuste y predicción.
