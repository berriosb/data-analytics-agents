"""
Unit tests para `skills/viz-patterns/recetas/chart_selector.py`.

Cobertura:
- recommend_chart_type: cada una de las reglas del SKILL.md
  (tiempo en x, x categorica + y numerica, dos numericas, etc.).
- validate_pie: guardrail de <=5 categorias.
- orientation_for_labels: threshold para cambiar a horizontal.
"""

from __future__ import annotations

import pytest

from viz_patterns import recetas as vp


# -----------------------------------------------------------------------
# recommend_chart_type
# -----------------------------------------------------------------------

class TestRecommendChartType:

    @pytest.mark.parametrize("y_type", ["numeric", None])
    def test_datetime_x_returns_line(self, y_type: str | None) -> None:
        """Regla 1: tiempo en x → line, siempre."""
        assert vp.recommend_chart_type("datetime", y_type) == "line"

    def test_categorical_x_numeric_y_returns_bar(self) -> None:
        """Regla 2: x categorica, y numerica → bar."""
        assert vp.recommend_chart_type("categorical", "numeric") == "bar"

    def test_two_numeric_returns_scatter(self) -> None:
        """Regla 4: dos numericas → scatter."""
        assert vp.recommend_chart_type("numeric", "numeric") == "scatter"

    def test_dense_scatter_returns_density_heatmap(self) -> None:
        """Scatter denso (>2000 puntos) → density_heatmap."""
        assert vp.recommend_chart_type(
            "numeric", "numeric", n_points=3000
        ) == "density_heatmap"

    def test_single_numeric_large_n_returns_histogram(self) -> None:
        """Regla 3a: distribucion de 1 numerica, n grande → histogram."""
        assert vp.recommend_chart_type("numeric", None, n_points=500) == "histogram"

    def test_single_numeric_small_n_returns_box(self) -> None:
        """Regla 3b: distribucion de 1 numerica, n chico → box."""
        assert vp.recommend_chart_type("numeric", None, n_points=50) == "box"

    def test_part_of_whole_with_few_categories_returns_pie(self) -> None:
        """Pie con <=5 categorias → pie."""
        assert vp.recommend_chart_type(
            "categorical", "numeric",
            part_of_whole=True, n_categories=4,
        ) == "pie"

    def test_part_of_whole_with_many_categories_returns_bar(self) -> None:
        """Pie con >5 categorias → bar (pie es ilegible)."""
        assert vp.recommend_chart_type(
            "categorical", "numeric",
            part_of_whole=True, n_categories=8,
        ) == "bar"

    def test_default_falls_back_to_bar(self) -> None:
        """Caso ambiguo → bar (conservador, funciona para casi todo)."""
        # x_type desconocido (no deberia pasar, pero el selector es robusto)
        assert vp.recommend_chart_type("unknown", "numeric") == "bar"


# -----------------------------------------------------------------------
# validate_pie
# -----------------------------------------------------------------------

class TestValidatePie:

    def test_no_warnings_for_small_pie(self) -> None:
        """Pie con <=5 categorias: sin warnings."""
        assert vp.validate_pie(n_categories=3) == []
        assert vp.validate_pie(n_categories=5) == []

    def test_warning_for_large_pie(self) -> None:
        """Pie con >5 categorias: warning explicito."""
        warnings = vp.validate_pie(n_categories=8)
        assert len(warnings) == 1
        assert "8" in warnings[0]
        assert "ilegible" in warnings[0].lower() or "5" in warnings[0]

    def test_warning_when_count_unknown(self) -> None:
        """n_categories=None: warning preventivo (no podemos validar)."""
        warnings = vp.validate_pie(n_categories=None)
        assert len(warnings) == 1
        assert "desconocida" in warnings[0].lower()


# -----------------------------------------------------------------------
# validate_bar_x_not_categorical_for_line
# -----------------------------------------------------------------------

class TestValidateBarDensity:

    def test_no_warnings_for_normal_scatter(self) -> None:
        """Scatter con <5000 puntos: sin warnings."""
        assert vp.validate_bar_x_not_categorical_for_line(500) == []
        assert vp.validate_bar_x_not_categorical_for_line(5000) == []

    def test_warning_for_dense_scatter(self) -> None:
        """Scatter con >5000 puntos: warning explicito."""
        warnings = vp.validate_bar_x_not_categorical_for_line(6000)
        assert len(warnings) == 1
        assert "6000" in warnings[0]


# -----------------------------------------------------------------------
# orientation_for_labels
# -----------------------------------------------------------------------

class TestOrientationForLabels:

    def test_short_labels_vertical(self) -> None:
        """Labels cortos → vertical (default)."""
        assert vp.orientation_for_labels(["A", "B", "C"]) == "v"

    def test_long_label_horizontal(self) -> None:
        """Label largo (>threshold) → horizontal."""
        long_label = "Categoria con nombre muy largo"
        assert vp.orientation_for_labels(["A", "B", long_label]) == "h"

    def test_custom_threshold(self) -> None:
        """El threshold es configurable."""
        labels = ["abc", "def"]  # 3 chars
        # Threshold default 8 → vertical
        assert vp.orientation_for_labels(labels) == "v"
        # Threshold 2 → horizontal (3 > 2)
        assert vp.orientation_for_labels(labels, threshold=2) == "h"

    def test_empty_list(self) -> None:
        """Lista vacia → vertical (default conservador)."""
        assert vp.orientation_for_labels([]) == "v"
