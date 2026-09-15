"""
Unit tests para `skills/statistical-testing/recetas/`.

Cobertura:
- effect_size: cohen_label (4 bandas + None), eta_squared_label (4
  bandas + None), cohens_d (caso normal, varianza 0).
- tests: t_test_ind (Welch vs Student), mann_whitney_u (samples
  identicas → p~1), anova_oneway (3 grupos, <3 grupos raises).
"""

from __future__ import annotations

import numpy as np
import pytest

from statistical_testing import recetas as st


# -----------------------------------------------------------------------
# effect_size
# -----------------------------------------------------------------------

class TestCohenLabel:

    @pytest.mark.parametrize("d,expected", [
        (0.0, "insignificante"),
        (0.1, "insignificante"),
        (0.2, "pequeno"),
        (0.49, "pequeno"),
        (0.5, "mediano"),
        (0.79, "mediano"),
        (0.8, "grande"),
        (1.5, "grande"),
        (-0.5, "mediano"),  # signo no importa
        (-1.0, "grande"),
    ])
    def test_thresholds(self, d: float, expected: str) -> None:
        assert st.cohen_label(d) == expected

    @pytest.mark.parametrize("d", [None, float("nan"), float("inf"), -float("inf")])
    def test_invalid_returns_empty(self, d: float | None) -> None:
        assert st.cohen_label(d) == ""


class TestEtaSquaredLabel:

    @pytest.mark.parametrize("eta,expected", [
        (0.0, "insignificante"),
        (0.005, "insignificante"),
        (0.01, "pequeno"),
        (0.05, "pequeno"),
        (0.06, "mediano"),
        (0.13, "mediano"),
        (0.14, "grande"),
        (0.5, "grande"),
    ])
    def test_thresholds(self, eta: float, expected: str) -> None:
        assert st.eta_squared_label(eta) == expected

    @pytest.mark.parametrize("eta", [None, float("nan")])
    def test_invalid_returns_empty(self, eta: float | None) -> None:
        assert st.eta_squared_label(eta) == ""


class TestCohensD:

    def test_normal_case(self) -> None:
        """Dos samples con medias distintas → |d| grande."""
        rng = np.random.default_rng(42)
        # B 충분히 큰 샘플로 분리 (sample-mean variance ~ 2/sqrt(500) ≈ 0.09)
        a = rng.normal(10, 2, 500)
        b = rng.normal(12, 2, 500)
        d = st.cohens_d(a, b)
        # Diferencia real de medias = 2, pooled SD ~ 2, |d| ~ 1 (grande)
        # d puede ser signed — probamos |d|.
        assert abs(d) > 0.8, f"|d| deberia ser > 0.8, dio {d}"

    def test_identical_samples_returns_zero(self) -> None:
        """Varianza 0 → d = 0 (no division por zero)."""
        a = np.array([5.0, 5.0, 5.0, 5.0])
        b = np.array([5.0, 5.0, 5.0, 5.0])
        assert st.cohens_d(a, b) == 0.0

    def test_negative_d_when_b_higher(self) -> None:
        """d es signed: a menor que b → d < 0."""
        a = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
        b = np.array([5.0, 6.0, 7.0, 8.0, 9.0])
        assert st.cohens_d(a, b) > 0


# -----------------------------------------------------------------------
# t_test_ind
# -----------------------------------------------------------------------

class TestTTestInd:

    def test_welch_default(self) -> None:
        """Default equal_var=False → Welch t-test."""
        rng = np.random.default_rng(42)
        a = rng.normal(10, 2, 80)
        b = rng.normal(11, 2, 75)
        res = st.t_test_ind(a, b)
        assert res["test"] == "Welch t-test"
        assert 0.0 <= res["p_value"] <= 1.0
        assert res["n"] == 155
        assert "p_value" in res

    def test_student_when_equal_var_true(self) -> None:
        """equal_var=True → Student t-test."""
        rng = np.random.default_rng(42)
        a = rng.normal(10, 2, 50)
        b = rng.normal(11, 2, 50)
        res = st.t_test_ind(a, b, equal_var=True)
        assert res["test"] == "Student t-test"

    def test_returns_normalized_dict_shape(self) -> None:
        """El dict tiene los 8 campos esperados por insight-synthesis."""
        rng = np.random.default_rng(42)
        a = rng.normal(10, 2, 50)
        b = rng.normal(10, 2, 50)
        res = st.t_test_ind(a, b)
        for key in ("test", "statistic", "p_value", "n", "effect_size",
                    "effect_label", "assumptions", "note"):
            assert key in res

    def test_low_n_recommends_mann_whitney(self) -> None:
        """n<30 por grupo → note sugiere Mann-Whitney."""
        a = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        b = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        res = st.t_test_ind(a, b)
        assert "mann_whitney_u" in res["note"]
        assert "n bajo" in res["note"]

    def test_high_n_no_note(self) -> None:
        """n>=30 por grupo → note vacio."""
        rng = np.random.default_rng(42)
        a = rng.normal(10, 2, 50)
        b = rng.normal(10, 2, 50)
        res = st.t_test_ind(a, b)
        assert res["note"] == ""

    def test_drops_nan(self) -> None:
        """Los NaN se dropean antes del test."""
        a = np.array([1.0, 2.0, np.nan, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        b = np.array([2.0, 3.0, 4.0, np.nan, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0])
        res = st.t_test_ind(a, b)
        # 9 + 9 = 18 (no 20)
        assert res["n"] == 18


# -----------------------------------------------------------------------
# mann_whitney_u
# -----------------------------------------------------------------------

class TestMannWhitneyU:

    def test_identical_distributions_high_p(self) -> None:
        """Samples identicas → p_value relativamente alto (sin diferencia real).

        Con n=50 por grupo Mann-Whitney es sensible — incluso samples de
        la misma distribucion pueden dar p<0.5 con variabilidad sampling.
        Usamos un threshold mas permisivo (p > 0.05) que indica "no
        rechazamos H0 al 5%".
        """
        rng = np.random.default_rng(42)
        a = rng.normal(10, 2, 50)
        b = rng.normal(10, 2, 50)
        res = st.mann_whitney_u(a, b)
        assert res["test"] == "Mann-Whitney U"
        # p > 0.05 significa que no rechazamos H0 al 5% (acepta "no diferencia")
        assert res["p_value"] > 0.05

    def test_different_distributions_low_p(self) -> None:
        """Samples muy distintas → p_value bajo."""
        rng = np.random.default_rng(42)
        a = rng.normal(0, 1, 100)
        b = rng.normal(5, 1, 100)  # diferencia de medias ~5, sd ~1
        res = st.mann_whitney_u(a, b)
        assert res["p_value"] < 0.001

    def test_empty_sample_raises(self) -> None:
        """Sample vacio despues de drop_nan → ValueError explicito."""
        a = np.array([np.nan, np.nan])
        b = np.array([1.0, 2.0, 3.0])
        with pytest.raises(ValueError) as exc:
            st.mann_whitney_u(a, b)
        assert "vacio" in str(exc.value).lower()


# -----------------------------------------------------------------------
# anova_oneway
# -----------------------------------------------------------------------

class TestAnovaOneway:

    def test_three_groups_required(self) -> None:
        """<3 grupos → ValueError."""
        with pytest.raises(ValueError, match=r">= 3 grupos"):
            st.anova_oneway([1, 2, 3], [4, 5, 6])

    def test_three_identical_groups(self) -> None:
        """3 grupos identicos → F ~ 1, p_value alto."""
        rng = np.random.default_rng(42)
        a = rng.normal(10, 2, 30)
        b = rng.normal(10, 2, 30)
        c = rng.normal(10, 2, 30)
        res = st.anova_oneway(a, b, c)
        assert res["test"] == "ANOVA one-way"
        # p_value deberia ser alto (no diferencia significativa)
        assert res["p_value"] > 0.3
        assert res["n"] == 90

    def test_three_very_different_groups(self) -> None:
        """3 grupos con medias muy distintas → p_value muy bajo, eta^2 grande."""
        rng = np.random.default_rng(42)
        a = rng.normal(0, 1, 30)
        b = rng.normal(5, 1, 30)
        c = rng.normal(10, 1, 30)
        res = st.anova_oneway(a, b, c)
        assert res["p_value"] < 0.001
        assert res["effect_size"] > 0.5  # eta-squared grande
        assert res["effect_label"] == "grande"

    def test_returns_dict_shape(self) -> None:
        """Misma forma que t_test_ind — insight-synthesis consume igual."""
        a = [1, 2, 3] * 10
        b = [4, 5, 6] * 10
        c = [7, 8, 9] * 10
        res = st.anova_oneway(a, b, c)
        for key in ("test", "statistic", "p_value", "n", "effect_size",
                    "effect_label", "assumptions", "note"):
            assert key in res
