"""Estadisticos del bloque climatico semanal tras corregir la agregacion."""

import os

import numpy as np
import pandas as pd
from scipy import stats

BASE = r"D:/OneDrive - PUJ Cali/Projecto_Grado_Javeriana/Data_Project"
CLIMA = ["temp_media_semana", "temp_max_semana", "temp_min_semana",
         "humedad_media_semana", "viento_medio_semana", "viento_max_semana",
         "precip_total_semana"]
OPER = ["n_eventos", "usuarios_afectados", "elementos_afectados", "duracion_total"]

agr = pd.read_csv(os.path.join(BASE, "data_agrupada.csv"), parse_dates=["semana"])
mod = pd.read_csv(os.path.join(BASE, "data_agrupada_mod.csv"), parse_dates=["semana"])


def extremos(x):
    x = x.dropna()
    n = len(x)
    p1, q1, med, q3, p99 = np.percentile(x, [1, 25, 50, 75, 99])
    iqr = q3 - q1
    o15 = ((x < q1 - 1.5 * iqr) | (x > q3 + 1.5 * iqr)).sum()
    o30 = ((x < q1 - 3.0 * iqr) | (x > q3 + 3.0 * iqr)).sum()
    op = ((x < p1) | (x > p99)).sum()
    cv = x.std(ddof=1) / x.mean() if x.mean() != 0 else np.nan
    return dict(n=n, mediana=med, media=x.mean(), sd=x.std(ddof=1), cv=cv,
                q1=q1, q3=q3, p1=p1, p99=p99, min=x.min(), max=x.max(),
                asimetria=stats.skew(x, bias=False), curtosis=stats.kurtosis(x, bias=False),
                pct_out15=100 * o15 / n, pct_out30=100 * o30 / n, pct_p1p99=100 * op / n,
                pct_ceros=100 * (x == 0).mean())


print("=" * 100)
print("EXTREMOS Y DESCRIPTIVOS -- clima semanal, tabla completa (N=90.128)")
res = pd.DataFrame({c: extremos(agr[c]) for c in CLIMA}).T
pd.set_option("display.width", 200, "display.float_format", lambda v: f"{v:,.3f}")
print(res[["mediana", "media", "sd", "cv", "asimetria", "curtosis", "q1", "q3", "p99",
           "min", "max", "pct_out15", "pct_out30", "pct_p1p99", "pct_ceros"]].to_string())

print()
print("=" * 100)
print("CLIMA SEMANAL en D_mod (N=36.120)")
res_mod = pd.DataFrame({c: extremos(mod[c]) for c in CLIMA}).T
print(res_mod[["mediana", "media", "sd", "cv", "asimetria", "curtosis", "q1", "q3", "p99",
               "pct_out15", "pct_out30", "pct_p1p99", "pct_ceros"]].to_string())

print()
print("=" * 100)
print("SPEARMAN clima x operativo (D_mod, panel completo)")
filas = []
for c in CLIMA:
    for o in OPER:
        r, p = stats.spearmanr(mod[c], mod[o])
        filas.append(dict(clima=c, oper=o, rho=round(r, 3), p=p))
sp = pd.DataFrame(filas)
print(sp.pivot(index="clima", columns="oper", values="rho").to_string())
print()
print(sp[sp.clima == "precip_total_semana"].to_string())

print()
print("SPEARMAN clima x operativo (tabla completa N=90.128)")
filas = []
for c in CLIMA:
    for o in OPER:
        r, p = stats.spearmanr(agr[c], agr[o])
        filas.append(dict(clima=c, oper=o, rho=round(r, 3), p=p))
print(pd.DataFrame(filas).pivot(index="clima", columns="oper", values="rho").to_string())

print()
print("=" * 100)
print("PCA bloque climatico (D_mod, variables estandarizadas)")
X = mod[CLIMA].dropna()
Z = (X - X.mean()) / X.std(ddof=1)
U, S, Vt = np.linalg.svd(Z.values, full_matrices=False)
var = S ** 2 / (len(Z) - 1)
prop = var / var.sum()
print("varianza explicada:", np.round(100 * prop, 2))
print("acumulada:", np.round(100 * np.cumsum(prop), 2))
load = pd.DataFrame(Vt[:3].T, index=CLIMA, columns=["PC1", "PC2", "PC3"])
print(load.round(3).to_string())

print()
print("PCA con precipitacion en escala log(1+x)")
Xl = X.copy()
Xl["precip_total_semana"] = np.log1p(Xl["precip_total_semana"])
Zl = (Xl - Xl.mean()) / Xl.std(ddof=1)
U, S, Vt = np.linalg.svd(Zl.values, full_matrices=False)
prop = (S ** 2) / (S ** 2).sum()
print("varianza explicada:", np.round(100 * prop, 2))
print(pd.DataFrame(Vt[:3].T, index=CLIMA, columns=["PC1", "PC2", "PC3"]).round(3).to_string())

print()
print("=" * 100)
print("Muestra de filas usadas en las tablas de ejemplo")
pares = [(1, "2020-12-28"), (1, "2021-01-04"), (3, "2021-01-04"), (12, "2021-01-11"),
         (45, "2021-01-18"), (117, "2021-01-25"), (203, "2021-02-01"),
         (45, "2021-02-08"), (117, "2021-02-15")]
idx = pd.MultiIndex.from_tuples([(c, pd.Timestamp(s)) for c, s in pares])
sub = agr.set_index(["id_cuadrante", "semana"]).reindex(idx)
print(sub[CLIMA + OPER].round(2).to_string())

print()
print("VIF del bloque climatico (D_mod)")
Zc = Z.values
for i, c in enumerate(CLIMA):
    otros = np.delete(Zc, i, axis=1)
    beta, *_ = np.linalg.lstsq(otros, Zc[:, i], rcond=None)
    r2 = 1 - ((Zc[:, i] - otros @ beta) ** 2).sum() / (Zc[:, i] ** 2).sum()
    print(f"  {c}: VIF={1/(1-r2):.2f}")
