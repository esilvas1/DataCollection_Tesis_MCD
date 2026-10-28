# Reproducibilidad — Proyecto aplicado Grupo 4 (MCD, PUJ Cali)

Metodología basada en ciencia de datos para pronosticar SAIDI y SAIFI por zona en la red de
distribución de una empresa de energía de Norte de Santander.

## 1. Requisitos

- **Datos:** carpeta `Data_Project` (no versionada; contiene datos operativos de la empresa usados
  con autorización). Copie `Cindy/.env.example` como `Cindy/.env` y ajuste `UBICACION_DATA`.
- **R ≥ 4.3** con el entorno fijado en `renv.lock`: ejecute `Rscript instalar_entorno.R` una vez
  para generarlo; en otra máquina basta con `renv::restore()`.
- **Python ≥ 3.10** para la extracción de NASA POWER: `pip install -r requirements.txt`.
- **Docker (opcional):** `docker build -t tesis-saidi-saifi .` desde esta carpeta, después de
  generar `renv.lock`.

**Sin acceso a los datos:** la carpeta `muestra_sintetica/` contiene un panel sintético con la
misma estructura (valores aleatorios). Basta con `UBICACION_DATA=muestra_sintetica` para ejecutar
`Cindy/v4/Etapa5_03_reestimacion_cierre.R SAIDI` de principio a fin; las cifras no coinciden con
las de la tesis, que requieren el panel real (sujeto a autorización de CENS).

## 2. Orden de ejecución

| Etapa (tesis) | Script | Producto |
|---|---|---|
| 1. Extracción | `Edwin/Script.sql`, `Edwin/consulta*.py`, `Cindy/consultaNASA_optimizada_elemento_grilla.py` | Tablas BRAE/OMS/GIS y clima NASA POWER |
| 2. Integración | `Edwin/Consolidada.Rmd`, `Edwin/emparejamiento_eventos.Rmd`, `Cindy/v4/Etapa2_01` a `Etapa2_12` | Panel activo × día y panel cuadrante × semana |
| 2. Corrección sismicidad | `Cindy/v4/Etapa2_13_correccion_sismos.R` | `data_final_modelo_cuadrantes_reales_sismos_corr.rds` |
| 3. EDA | `Edwin/EDA.Rmd` y documentos asociados | Informe descriptivo y exploratorio |
| 4. Ingeniería de variables | `Cindy/v4/Etapa4_01`, `Etapa4_02`, `Edwin/asociacion_depuracion_cuantitativas.Rmd` | Matriz de predictoras *ex ante* |
| 5. Modelado (informes) | `Cindy/v4/Etapa5_01`, `Etapa5_02` | Informes HTML de SAIDI y SAIFI |
| 5. Re-estimación final | `Cindy/v4/Etapa5_03_reestimacion_cierre.R SAIDI` y `... SAIFI` | Todas las cifras del Capítulo 6 de la tesis (`salidas_SAIDI/`, `salidas_SAIFI/`) |
| 6. Reporte técnico | `Cindy/v4/Etapa6_01_reporte_priorizacion.Rmd` | Ranking de cuadrantes y `priorizacion_cuadrantes.csv` |

`Cindy/v4/00_guia_maestra_proyecto.Rmd` describe el flujo completo y las decisiones de cada etapa.

## 3. Verificación

Con el panel original (`data_final_modelo_cuadrantes_reales.rds`) y la especificación original,
`Etapa5_03_reestimacion_cierre.R` reproduce las cifras de los informes preliminares (RMSE de
0,1666 para Pooled OLS y 0,1340 para FE de cuadrante en SAIDI). Con el panel corregido
genera las tablas finales de la tesis. Semilla fija (`123`) en todos los modelos aleatorios.

## 4. Correcciones documentadas (27-oct-2026)

- `Etapa2_07_sismicidad_sgc.Rmd`: unidades de la matriz de distancias (el radio siempre se cumplía)
  y cota superior en la asignación de semanas (los sismos de 2026 caían en la última semana).
- `Etapa2_06_desastres_ungrd.Rmd`: el dataset UNGRD de datos abiertos cubre 2019–2022; las
  variables derivadas son constantes en 2024–2025 y no entran al modelo final.
- `Etapa5_01/02`: el denominador de SAIDI y SAIFI es UT mensual (usuarios totales del sistema).
