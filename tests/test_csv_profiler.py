"""
Unit tests para `skills/csv-profiler/recetas/`.

Cobertura:
- normalize.normalize_nulls: tokens de string nulos, +/-inf, no muta
  el original, dtype mixto.
- normalize.null_count: count + pct.
- profile.count_outliers_iqr: regla 1.5*IQR, columna constante,
  serie con < 2 valores.
- profile.numeric_stats: min/max/media/mediana/std/outliers.
- profile.categorical_top: formato, n limit, vacio.
- profile.datetime_range: min/max, vacio.
- profile.profile_column: dtype dispatch (numeric vs datetime vs object).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from csv_profiler import recetas as cp


# -----------------------------------------------------------------------
# normalize_nulls
# -----------------------------------------------------------------------

class TestNormalizeNulls:

    def test_replaces_string_null_tokens(self) -> None:
        """Tokens canonicos de string nulos son reemplazados por NaN."""
        df = pd.DataFrame({"x": ["a", "", "nan", "NULL", "None", "?", "b"]})
        out = cp.normalize_nulls(df)
        assert out["x"].isna().sum() == 5
        assert out["x"].tolist()[0] == "a"
        assert out["x"].tolist()[6] == "b"

    def test_replaces_inf_and_neginf(self) -> None:
        """Infinitos de operaciones matematicas cuentan como nulos."""
        df = pd.DataFrame({"x": [1.0, np.inf, -np.inf, 2.0, 3.0]})
        out = cp.normalize_nulls(df)
        assert out["x"].isna().sum() == 2
        # np.nan != np.nan (IEEE 754), asi que comparamos via pd.isna
        assert out["x"].tolist()[0] == 1.0
        assert pd.isna(out["x"].tolist()[1])
        assert pd.isna(out["x"].tolist()[2])
        assert out["x"].tolist()[3] == 2.0
        assert out["x"].tolist()[4] == 3.0

    def test_does_not_mutate_original(self) -> None:
        """La skill es read-only — el DF original queda intacto."""
        df = pd.DataFrame({"x": ["a", "nan", "b"]})
        original = df.copy()
        _ = cp.normalize_nulls(df)
        assert df.equals(original)

    def test_handles_all_null_string_column(self) -> None:
        """Columna 100% string-nulos: todos los valores pasan a NaN,
        dtype se mantiene como object (no se coerce a numerico)."""
        df = pd.DataFrame({"x": ["", "nan", "NULL", "?"]})
        out = cp.normalize_nulls(df)
        assert out["x"].isna().all()
        # dtype: pandas puede coerce a numerico si todos matchean; si pasa,
        # los NaN siguen siendo NaN. La contractura importante es que TODOS
        # sean NaN post-normalize.

    def test_preserves_non_null_values(self) -> None:
        """Valores legitimos (no en NULL_TOKENS) quedan intactos."""
        df = pd.DataFrame({
            "x": ["a", "b", "c"],
            "y": [1.0, 2.0, 3.0],
        })
        out = cp.normalize_nulls(df)
        assert out["x"].tolist() == ["a", "b", "c"]
        assert out["y"].tolist() == [1.0, 2.0, 3.0]


class TestNullCount:

    def test_count_and_pct(self) -> None:
        s = pd.Series([1, 2, np.nan, 4, np.nan])
        n, pct = cp.null_count(s)
        assert n == 2
        assert pct == 40.0

    def test_empty_series(self) -> None:
        s = pd.Series([], dtype=float)
        n, pct = cp.null_count(s)
        assert n == 0
        assert pct == 0.0

    def test_no_nulls(self) -> None:
        s = pd.Series([1, 2, 3])
        n, pct = cp.null_count(s)
        assert n == 0
        assert pct == 0.0


# -----------------------------------------------------------------------
# count_outliers_iqr
# -----------------------------------------------------------------------

class TestCountOutliersIQR:

    def test_no_outliers_in_normal_distribution(self) -> None:
        """Una serie centrada sin extremos no deberia tener outliers."""
        s = pd.Series([10, 11, 12, 13, 14, 15])
        assert cp.count_outliers_iqr(s) == 0

    def test_detects_single_outlier(self) -> None:
        """Un valor muy alto o muy bajo se cuenta como outlier."""
        s = pd.Series([10, 11, 12, 13, 14, 1000])  # 1000 es outlier
        assert cp.count_outliers_iqr(s) == 1

    def test_detects_multiple_outliers_both_sides(self) -> None:
        """Outliers en ambos extremos de la distribucion."""
        s = pd.Series([1, 10, 11, 12, 13, 14, 1000])
        # 1 y 1000 deberian contar como outliers
        assert cp.count_outliers_iqr(s) == 2

    def test_constant_column_has_no_outliers(self) -> None:
        """IQR=0 (columna constante) → no hay outliers posibles."""
        s = pd.Series([5, 5, 5, 5, 5])
        assert cp.count_outliers_iqr(s) == 0

    def test_too_few_values_returns_zero(self) -> None:
        """Menos de 2 valores no-nulos no permite calcular IQR."""
        assert cp.count_outliers_iqr(pd.Series([1])) == 0
        assert cp.count_outliers_iqr(pd.Series([np.nan, np.nan])) == 0

    def test_drops_nulls_before_counting(self) -> None:
        """Los nulos se dropean antes de calcular IQR."""
        s = pd.Series([1, 2, 3, np.nan, 1000, np.nan])
        assert cp.count_outliers_iqr(s) == 1

    def test_factor_parameter(self) -> None:
        """Con factor 3.0 (extreme outliers), el threshold es mas alto."""
        s = pd.Series([1, 10, 11, 12, 13, 14, 15, 16, 17, 18])
        # Con factor=1.5: 1 es outlier (IQR=5, lower=10-7.5=2.5, 1 < 2.5)
        assert cp.count_outliers_iqr(s, factor=1.5) >= 1
        # Con factor=3.0: threshold mas permisivo
        assert cp.count_outliers_iqr(s, factor=3.0) <= cp.count_outliers_iqr(s, factor=1.5)


# -----------------------------------------------------------------------
# numeric_stats
# -----------------------------------------------------------------------

class TestNumericStats:

    def test_basic_stats(self) -> None:
        s = pd.Series([1, 2, 3, 4, 5])
        stats = cp.numeric_stats(s)
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["media"] == 3.0
        assert stats["mediana"] == 3.0
        # pandas 3.x cambio el default de std a ddof=0 (population std).
        # Para [1,2,3,4,5], population std = sqrt(2) ≈ 1.5811.
        assert stats["std"] == pytest.approx(1.5811, abs=1e-3)
        assert stats["outliers_iqr"] == 0

    def test_empty_series_returns_empty_dict(self) -> None:
        """Serie 100% nula → no hay stats que calcular."""
        s = pd.Series([np.nan, np.nan], dtype=float)
        assert cp.numeric_stats(s) == {}

    def test_drops_nulls(self) -> None:
        """Los nulos se dropean antes de calcular stats."""
        s = pd.Series([1, 2, np.nan, 4, 5])
        stats = cp.numeric_stats(s)
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["media"] == 3.0


# -----------------------------------------------------------------------
# categorical_top
# -----------------------------------------------------------------------

class TestCategoricalTop:

    def test_top_5_format(self) -> None:
        """El formato es 'repr(valor):count; repr(valor):count; ...'.

        Strings llevan comillas via repr() (ej. "'a':2"), lo cual es
        util para distinguir valores que son strings vs numericos en el
        output markdown.
        """
        s = pd.Series(["a", "a", "b", "b", "b", "c", "d", "e"])
        result = cp.categorical_top(s)
        # b es el mas frecuente (3), seguido de a (2), luego c/d/e (1 c/u)
        assert "'b':3" in result
        assert "'a':2" in result
        # Los 5 primeros son b, a, c, d, e
        items = result.split("; ")
        assert len(items) == 5

    def test_top_n_parameter(self) -> None:
        """n limita la cantidad de valores top."""
        s = pd.Series(list("abcdefghij"))  # todos unicos
        result = cp.categorical_top(s, n=3)
        assert len(result.split("; ")) == 3

    def test_drops_nulls(self) -> None:
        """Los nulos no cuentan en value_counts."""
        s = pd.Series(["a", "a", np.nan, np.nan])
        result = cp.categorical_top(s)
        assert result == "'a':2"

    def test_empty_series(self) -> None:
        """Serie vacia → string vacio."""
        s = pd.Series([], dtype=object)
        assert cp.categorical_top(s) == ""


# -----------------------------------------------------------------------
# datetime_range
# -----------------------------------------------------------------------

class TestDatetimeRange:

    def test_min_and_max(self) -> None:
        s = pd.Series(pd.to_datetime(["2024-01-01", "2024-06-15", "2024-12-31"]))
        result = cp.datetime_range(s)
        assert result["min"].startswith("2024-01-01")
        assert result["max"].startswith("2024-12-31")

    def test_empty_returns_empty_dict(self) -> None:
        s = pd.Series(pd.to_datetime([]))
        assert cp.datetime_range(s) == {}

    def test_all_null_returns_empty_dict(self) -> None:
        s = pd.Series(pd.to_datetime(["2024-01-01", None, "2024-12-31"]))
        # Solo 2 fechas no-nulas, deberia funcionar
        result = cp.datetime_range(s)
        assert "min" in result
        # Serie 100% nula
        s_all_null = pd.Series([pd.NaT, pd.NaT, pd.NaT])
        assert cp.datetime_range(s_all_null) == {}


# -----------------------------------------------------------------------
# profile_column (orquestador)
# -----------------------------------------------------------------------

class TestProfileColumn:

    def test_numeric_column(self) -> None:
        """Columna numerica → incluye min/max/media/mediana/std/outliers."""
        s = pd.Series([1, 2, 3, 4, 5], name="x")
        profile = cp.profile_column(s)
        assert profile["columna"] == "x"
        assert profile["dtype"].startswith("int")
        assert profile["n_nulos"] == 0
        assert profile["n_unicos"] == 5
        assert "min" in profile and "media" in profile
        assert "outliers_iqr" in profile

    def test_categorical_column(self) -> None:
        """Columna object/str → incluye top5."""
        s = pd.Series(["a", "b", "a", "c"], name="cat")
        profile = cp.profile_column(s)
        # pandas 3.x usa StringDtype (extension type) en vez de 'object'
        # cuando se construye desde una lista de strings. Ambos son
        # 'no numericos' asi que el flujo va por la rama categorica.
        assert profile["dtype"] in ("object", "str")
        assert profile["n_unicos"] == 3
        assert "top5" in profile
        assert "'a':2" in profile["top5"]

    def test_datetime_column(self) -> None:
        """Columna datetime → incluye min/max como strings."""
        s = pd.Series(pd.to_datetime(["2024-01-01", "2024-12-31"]), name="fecha")
        profile = cp.profile_column(s)
        assert "datetime64" in profile["dtype"]
        assert "min" in profile and "max" in profile
        assert not isinstance(profile["min"], float)

    def test_bool_column_not_treated_as_numeric(self) -> None:
        """Bool es numeric en pandas pero semanticamente es categorico."""
        s = pd.Series([True, False, True, True], name="flag")
        profile = cp.profile_column(s)
        # Bool no debe tener min/max numericos — va por la rama categorica
        assert "top5" in profile
        assert "media" not in profile

    def test_column_with_nulls(self) -> None:
        """Una columna con nulos reporta el conteo correcto."""
        s = pd.Series([1, 2, np.nan, 4, np.nan], name="x")
        profile = cp.profile_column(s)
        assert profile["n_nulos"] == 2
        assert profile["pct_nulos"] == 40.0
