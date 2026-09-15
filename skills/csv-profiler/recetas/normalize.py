"""
Normalizacion de nulos para csv-profiler.

Los archivos CSV en pega real vienen con tokens de string que representan
nulos pero que pandas NO reconoce como NaN ('' , 'nan', 'NaN', 'NULL',
'None', '?', etc.). Si no los normalizamos, el conteo de nulos queda
subestimado y las distribuciones se contaminan.

Ademas, los infinitos (np.inf, -np.inf) de divisiones por cero tambien
cuentan como "no nulos" — los normalizamos a NaN para que la estadistica
agregada no explote.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# Tokens de string que representan nulos. FROZENSET para que sea hashable
# y compartible. Caso-insensitive en la practica: '' 'nan' 'NaN' 'NAN'
# 'null' 'NULL' 'None' 'none' '?' — los CSV varian.
NULL_TOKENS: frozenset[str] = frozenset({
    "", "nan", "NaN", "NAN",
    "null", "NULL", "Null",
    "none", "None", "NONE",
    "?",
})

# Wrapper para mantener dtype object despues del replace. Pandas a veces
# intenta coercionar a numerico si todos los tokens matchean; usamos
# un valor centinela explicito.
_REPLACE_VALUE = np.nan


def normalize_nulls(df: pd.DataFrame) -> pd.DataFrame:
    """Reemplaza tokens de string nulos y +/-inf por NaN across all columns.

    Devuelve un NUEVO DataFrame (no muta el original). Esto es importante
    porque el caller puede querer el original sin tocar — la skill
    csv-profiler es read-only.

    Args:
        df: el DataFrame cargado del CSV/Parquet/Excel.

    Returns:
        Copia del DataFrame con nulls normalizados.
    """
    # .replace acepta list/set de strings; NaN es el sentinel canonico.
    # Hacemos replace en 2 pasos para evitar coercion automatica de dtype
    # en columnas que son 100% string-nulls (ej. una columna "comentarios"
    # donde todos los valores son "").
    out = df.copy()
    out = out.replace(list(NULL_TOKENS), _REPLACE_VALUE)
    out = out.replace([np.inf, -np.inf], _REPLACE_VALUE)
    return out


def null_count(series: pd.Series) -> tuple[int, float]:
    """Cuenta nulos despues de la normalizacion. Devuelve (count, pct).

    Args:
        series: una columna del DataFrame (post-normalizacion).

    Returns:
        (n_nulos, pct_nulos) donde pct_nulos esta en [0, 100].
    """
    n = int(series.isna().sum())
    pct = round(float(series.isna().mean()) * 100, 2) if len(series) else 0.0
    return n, pct
