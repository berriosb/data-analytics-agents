"""
Perfil por columna + deteccion de outliers IQR para csv-profiler.

Cada funcion opera sobre una sola columna (pd.Series) y devuelve un dict
con metricas estructuradas. El orquestador (futuro `profile_csv`) las
combina en una tabla.

Las metricas siguen el shape que produce el SKILL.md actual (ver paso 3
del Flujo de trabajo) para que el output sea backward-compatible.
"""

from __future__ import annotations

import pandas as pd


def count_outliers_iqr(series: pd.Series, factor: float = 1.5) -> int:
    """Cuenta outliers usando la regla 1.5*IQR.

    Un outlier es un valor que cae fuera de [Q1 - factor*IQR, Q3 + factor*IQR]
    donde IQR = Q3 - Q1.

    Args:
        series: una columna numerica. Se dropean nulos internamente.
        factor: 1.5 (default Tukey) o 3.0 para "extreme outliers".

    Returns:
        Cantidad de outliers. 0 si la serie tiene < 2 valores no-nulos.
    """
    non_null = series.dropna()
    if len(non_null) < 2:
        return 0
    q1 = non_null.quantile(0.25)
    q3 = non_null.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        # Columna constante post-normalizacion — no hay outliers posibles.
        return 0
    lower = q1 - factor * iqr
    upper = q3 + factor * iqr
    return int(((non_null < lower) | (non_null > upper)).sum())


def numeric_stats(series: pd.Series) -> dict[str, float]:
    """Stats descriptivos para una columna numerica no-bool.

    Args:
        series: una columna numerica (int/float). Se dropean nulos.

    Returns:
        Dict con min, max, media, mediana, std, outliers_iqr.
        Devuelve {} si la serie tiene < 1 valor no-nulo.
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return {}
    return {
        "min": float(non_null.min()),
        "max": float(non_null.max()),
        "media": round(float(non_null.mean()), 4),
        "mediana": float(non_null.median()),
        "std": round(float(non_null.std()), 4),
        "outliers_iqr": count_outliers_iqr(series),
    }


def categorical_top(series: pd.Series, n: int = 5) -> str:
    """Top-N valores mas frecuentes como string formateado.

    Formato: 'val1:n1; val2:n2; ...' (repr del valor + ':' + count).
    Usado para la columna 'top5' del perfil.

    Args:
        series: una columna categorica / object.
        n: cantidad de valores top a incluir (default 5).

    Returns:
        String con los top-N valores. Vacio si la serie es 100% nula.
    """
    top = series.value_counts(dropna=True).head(n)
    return "; ".join(f"{v!r}:{c}" for v, c in top.items())


def datetime_range(series: pd.Series) -> dict[str, str]:
    """Min y max de una columna datetime como strings ISO.

    Args:
        series: una columna datetime64.

    Returns:
        Dict con 'min' y 'max' como strings. {} si la serie es 100% nula.
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return {}
    return {
        "min": str(non_null.min()),
        "max": str(non_null.max()),
    }


def profile_column(series: pd.Series) -> dict:
    """Perfil completo de una columna, eligiendo el bloque por dtype.

    Args:
        series: una columna del DataFrame.

    Returns:
        Dict con: columna, dtype, n_nulos, pct_nulos, n_unicos, y
        ademas (segun dtype):
          - numerica: min, max, media, mediana, std, outliers_iqr
          - datetime: min, max (como strings)
          - object/bool: top5 (string con los top-5 valores)
    """
    row = {
        "columna": series.name,
        "dtype": str(series.dtype),
        "n_nulos": int(series.isna().sum()),
        "pct_nulos": round(float(series.isna().mean()) * 100, 2) if len(series) else 0.0,
        "n_unicos": int(series.nunique(dropna=True)),
    }

    # Bloque numerico (excluyendo bool, que es numeric en pandas)
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        row.update(numeric_stats(series))
    elif pd.api.types.is_datetime64_any_dtype(series):
        row.update(datetime_range(series))
    else:
        # object, bool, category, etc. → top-5 valores
        row["top5"] = categorical_top(series)

    return row
