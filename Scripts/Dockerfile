# Entorno reproducible del proyecto aplicado (Grupo 4, MCD PUJ Cali)
# Construir (desde la carpeta Scripts):  docker build -t tesis-saidi-saifi .
# Ejecutar:   docker run --rm -v /ruta/Data_Project:/data -e UBICACION_DATA=/data \
#               tesis-saidi-saifi Rscript Cindy/v4/Etapa5_03_reestimacion_cierre.R SAIDI
FROM rocker/geospatial:4.4.1

WORKDIR /proyecto
COPY renv.lock renv.lock
RUN R -e "install.packages('renv', repos = 'https://cloud.r-project.org')" \
 && R -e "renv::restore(lockfile = 'renv.lock', prompt = FALSE)"

COPY requirements.txt requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends python3-pip \
 && pip3 install --no-cache-dir --break-system-packages -r requirements.txt \
 && rm -rf /var/lib/apt/lists/*

COPY . /proyecto
ENV UBICACION_DATA=/data
CMD ["R"]
