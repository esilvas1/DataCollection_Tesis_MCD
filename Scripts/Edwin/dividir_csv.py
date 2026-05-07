# Script para dividir el CSV
import pandas as pd

df = pd.read_csv('DATA/Eventos_BRAE.csv')
chunk_size = 500000  # Registros por archivo

for i, start in enumerate(range(0, len(df), chunk_size)):
    chunk = df[start:start + chunk_size]
    chunk.to_csv(f'DATA/Eventos_BRAE_part{i+1}.csv', index=False)