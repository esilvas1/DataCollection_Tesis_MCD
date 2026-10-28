# =====================================================================
# Fija el entorno de R del proyecto con renv y genera renv.lock.
# Ejecutar UNA VEZ desde la carpeta Scripts del repositorio, en la máquina donde
# se generaron los informes, y versionar renv.lock en git.
# =====================================================================
if (!requireNamespace("renv", quietly = TRUE)) install.packages("renv")
paquetes <- c(
  # manipulación y visualización
  "tidyverse", "dplyr", "tidyr", "readr", "readxl", "lubridate", "data.table", "scales",
  "ggplot2", "patchwork", "GGally", "corrplot", "viridis", "gganimate", "gifski", "transformr",
  "magick", "leaflet", "htmlwidgets", "kableExtra", "knitr", "rmarkdown", "broom", "rstatix",
  # espacial
  "sf", "sp", "spdep", "spatialreg", "gstat", "spatstat", "geojsonsf", "units", "gridExtra",
  # modelos y validación
  "fixest", "randomForest", "ranger", "Metrics", "MASS", "car", "lmtest", "sandwich",
  "forecast", "pROC", "zoo"
)
renv::init(bare = TRUE)
install.packages(setdiff(paquetes, rownames(installed.packages())))
renv::snapshot(packages = paquetes, prompt = FALSE)
message("renv.lock generado. Para reconstruir el entorno en otra máquina: renv::restore()")
