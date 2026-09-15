"""
Recetas pre-aprobadas para csv-profiler (perfilado de solo lectura
de CSV / Parquet / Excel).

Modulos:
- normalize: deteccion y reemplazo de tokens de nulos ('', 'nan',
  'NULL', '?', etc.) + reemplazo de +/-inf por NaN.
- profile: perfil por columna (dtype, nulos, unicos, top-N, outliers
  via regla 1.5*IQR, rango datetime).

Uso:
    import sys
    sys.path.insert(0, "ruta/al/repo")
    from skills_loader import load_skill_packages
    load_skill_packages()
    from csv_profiler import recetas as cp

    import pandas as pd
    df = pd.read_csv("data.csv")
    df_norm = cp.normalize_nulls(df)
    rows = [cp.profile_column(df_norm[col]) for col in df_norm.columns]
"""

from .normalize import normalize_nulls, null_count, NULL_TOKENS
from .profile import (
    count_outliers_iqr, numeric_stats, categorical_top,
    datetime_range, profile_column,
)

__all__ = [
    "normalize_nulls",
    "null_count",
    "NULL_TOKENS",
    "count_outliers_iqr",
    "numeric_stats",
    "categorical_top",
    "datetime_range",
    "profile_column",
]
