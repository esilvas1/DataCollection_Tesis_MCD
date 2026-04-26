📊 Capítulo 12. Modelación de SAIFI con Random Forest
-----------------------------------------------------------
  1. Objetivo
-----------------------------------------------------------
  El objetivo de este capítulo es estimar un modelo de Random Forest para
predecir SAIFI (frecuencia de interrupciones), capturando relaciones no
lineales, interacciones complejas y posibles efectos de umbral asociados
a variables climáticas y operativas. Se compara su desempeño frente al
modelo GLM (Poisson / Binomial Negativa) desarrollado previamente.
-----------------------------------------------------------
  🧱 2. Preparación del entorno
-----------------------------------------------------------
  library(dplyr)
library(ggplot2)
library(randomForest)
library(Metrics)
library(rsample)
library(tidyr)
library(vip)
-----------------------------------------------------------
  📥 3. Preparación de datos
-----------------------------------------------------------
  # Variables contemporáneas + rezagos relevantes (ajusta según tu cap. previo)
  df_saifi <- panel_semana %>%
  select(
    SAIFI,
    temp_media_semana, humedad_media_semana,
    precip_total_semana, viento_max_semana,
    lluvia_intensa, viento_fuerte,
    SAIFI_lag1, SAIFI_lag2,
    lluvia_lag1, viento_lag1
  ) %>%
  na.omit() %>%
  arrange(semana)

summary(df_saifi$SAIFI)
-----------------------------------------------------------
  ⏱️ 4. Train/Test temporal
-----------------------------------------------------------
  split <- initial_time_split(df_saifi, prop = 0.8)

train <- training(split)
test  <- testing(split)
-----------------------------------------------------------
  🌲 5. Especificación del modelo Random Forest
-----------------------------------------------------------
  set.seed(123)

modelo_rf_saifi <- randomForest(
  SAIFI ~ .,
  data = train,
  ntree = 300,
  mtry = floor(sqrt(ncol(train) - 1)),
  importance = TRUE
)

modelo_rf_saifi
-----------------------------------------------------------
  🔮 6. Predicción (out-of-sample)
-----------------------------------------------------------
  pred_rf <- predict(modelo_rf_saifi, newdata = test)
-----------------------------------------------------------
  📏 7. Evaluación de desempeño
-----------------------------------------------------------
  rmse_rf <- rmse(test$SAIFI, pred_rf)
mae_rf  <- mae(test$SAIFI, pred_rf)

rmse_rf
mae_rf
Nota:
  Aunque SAIFI es un conteo, evaluamos con RMSE/MAE para comparabilidad
con otros modelos. También puedes reportar métricas adicionales si lo deseas.
-----------------------------------------------------------
  📊 8. Comparación gráfica (real vs predicho)
-----------------------------------------------------------
  ggplot(data.frame(real = test$SAIFI, pred = pred_rf),
         aes(x = real, y = pred)) +
  geom_point(alpha = 0.3) +
  geom_abline(slope = 1, intercept = 0, color = "red") +
  theme_minimal() +
  labs(
    title = "SAIFI observado vs predicho (Random Forest)",
    x = "Valor real",
    y = "Valor predicho"
  )
-----------------------------------------------------------
  📉 9. Distribución de errores
-----------------------------------------------------------
  errores_rf <- abs(test$SAIFI - pred_rf)

ggplot(data.frame(error = errores_rf), aes(x = error)) +
  geom_histogram(bins = 30) +
  theme_minimal() +
  labs(title = "Distribución del error absoluto - RF (SAIFI)")
-----------------------------------------------------------
  🌲 10. Importancia de variables
-----------------------------------------------------------
  importance(modelo_rf_saifi)
varImpPlot(modelo_rf_saifi)
Interpretación:
  Variables con mayor importancia indican mayor contribución a la
reducción del error en el bosque. Permiten identificar drivers
climáticos y operativos de la frecuencia de fallas.
-----------------------------------------------------------
  🔁 11. Validación rolling (robustez)
-----------------------------------------------------------
  rolling_splits <- rolling_origin(
    df_saifi,
    initial = 5000,
    assess = 1000,
    skip = 1000,
    cumulative = TRUE
  )

eval_rf <- function(split) {
  train <- analysis(split)
  test  <- assessment(split)
  
  modelo <- randomForest(
    SAIFI ~ .,
    data = train,
    ntree = 200
  )
  
  pred <- predict(modelo, newdata = test)
  
  data.frame(
    rmse = rmse(test$SAIFI, pred),
    mae  = mae(test$SAIFI, pred)
  )
}

library(purrr)

resultados_rolling <- map_df(rolling_splits$splits, eval_rf)

summary(resultados_rolling)
-----------------------------------------------------------
  📊 12. Comparación con modelo GLM (Poisson / NB)
-----------------------------------------------------------
  # Asumiendo que ya tienes predicciones del modelo NB:
  # pred_nb (del capítulo anterior)
  
  # Si no, puedes reconstruir rápidamente:
  library(MASS)

modelo_nb <- glm.nb(
  SAIFI ~ temp_media_semana + humedad_media_semana +
    precip_total_semana + viento_max_semana +
    lluvia_intensa + viento_fuerte,
  data = train
)

pred_nb <- predict(modelo_nb, newdata = test, type = "response")

rmse_nb <- rmse(test$SAIFI, pred_nb)
mae_nb  <- mae(test$SAIFI, pred_nb)

tabla_comp <- data.frame(
  Modelo = c("Binomial Negativa", "Random Forest"),
  RMSE = c(rmse_nb, rmse_rf),
  MAE  = c(mae_nb, mae_rf)
)

knitr::kable(tabla_comp, digits = 3)
-----------------------------------------------------------
  🔍 13. Discusión de resultados
-----------------------------------------------------------
  - El modelo GLM (NB) es interpretable y consistente con la naturaleza
de conteo de SAIFI, pero impone una forma funcional específica.
- Random Forest captura no linealidades, interacciones y umbrales
(por ejemplo, efectos de lluvia extrema o viento fuerte).
- Si RF reduce RMSE/MAE frente a NB:
  → evidencia de relaciones no lineales relevantes.
- Si NB es competitivo:
  → modelo más parsimonioso y explicable puede ser preferible.
-----------------------------------------------------------
  ⚠️ 14. Consideraciones metodológicas
-----------------------------------------------------------
  - RF no modela explícitamente la distribución de conteos.
- Menor interpretabilidad frente a GLM.
- Sensible a la selección de variables y tamaño de muestra.
- No incorpora explícitamente sobredispersión (como NB).
-----------------------------------------------------------
  🏆 15. Conclusión
-----------------------------------------------------------
  El modelo Random Forest constituye una alternativa robusta para la
predicción de SAIFI, especialmente en presencia de relaciones no lineales.
Su desempeño comparativo frente al modelo binomial negativo permitirá
determinar si se prioriza capacidad predictiva o interpretabilidad
en la selección final del modelo.