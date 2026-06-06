# LEER EL ARCHIVO CSV data_consolidada.csv usando UBICACION_DATA del .env
library(readr)

# Cargar .env (raiz del proyecto: Scripts/Edwin -> ../../.env)
env_path <- file.path("..", "..", ".env")
if (file.exists(".env")) {
  readRenviron(".env")
} else if (file.exists(env_path)) {
  readRenviron(env_path)
}

UBICACION_DATA <- Sys.getenv("UBICACION_DATA")
if (UBICACION_DATA == "") {
  stop("UBICACION_DATA no esta definida. Verifica el archivo .env en la raiz del proyecto.")
}

data_consolidada <- read_csv(file.path(UBICACION_DATA, "data_consolidada.csv"))
dim(data_consolidada)

# columna DURACION_min del CSV (variable DURACION en documentacion; unidades: minutos)
min_duracion <- min(data_consolidada$DURACION_min)
print(min_duracion)

max_duracion <- max(data_consolidada$DURACION_min)
print(max_duracion)


# columnas de data_consolidada
colnames(data_consolidada)

# dimension de la data
dim(data_consolidada)



# identificar la mediana del campo cant_elementos cuando cant_elementos es mayor a 0
median_cant_elementos <- median(data_consolidada$CANTIDAD_ELEMENTOS[data_consolidada$CANTIDAD_ELEMENTOS > 0])
print(median_cant_elementos)

# imprimir los 10 primeros valores de la columna CANTIDAD_ELEMENTOS cuando CANTIDAD_ELEMENTOS es mayor a 0
print(data_consolidada$CANTIDAD_ELEMENTOS[data_consolidada$CANTIDAD_ELEMENTOS > 0][1:1000])

# identificar el valor max de la columna CANTIDAD_ELEMENTOS
max_cant_elementos <- max(data_consolidada$CANTIDAD_ELEMENTOS)
print(max_cant_elementos)

# cantidad de elementos = 2
cantidad_elementos_2 <- sum(data_consolidada$CANTIDAD_ELEMENTOS == 2)
print(cantidad_elementos_2)

# imprimir una fila de la data_consolidada cunado la cantidad de elementos es 2 
print(data_consolidada[data_consolidada$CANTIDAD_ELEMENTOS == 2,])

# imprimir una fila de la data_consolidada cunado la cantidad de elementos es 3
print(data_consolidada[data_consolidada$CANTIDAD_ELEMENTOS == 3,])

# imprimir una fila de la data_consolidada cunado la cantidad de elementos es 4
print(data_consolidada[data_consolidada$CANTIDAD_ELEMENTOS == 4,])

# imprimir una fila de la data_consolidada cunado la cantidad de elementos es 5
View(data_consolidada[data_consolidada$CANTIDAD_ELEMENTOS == 5,])


