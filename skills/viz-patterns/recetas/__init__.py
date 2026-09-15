"""
Recetas pre-aprobadas para viz-patterns (selector de tipo de grafico
segun tipos de variables y pregunta, mas helpers de validacion).

Modulos:
- chart_selector: recommend_chart_type() que mapea (x_type, y_type,
  n_points, n_categories, part_of_whole) -> chart type. Implementa
  la tabla de decision del SKILL.md como funciones puras testeables
  (sin instanciar Plotly).
- styling: apply_output_styling() que aplica el layout standard
  (template simple_white, fonts, margins) que el SKILL.md documenta
  como "Configuracion de salida".

Uso:
    import sys
    sys.path.insert(0, "ruta/al/repo")
    from skills_loader import load_skill_packages
    load_skill_packages()
    from viz_patterns import recetas as vp

    # Recomendacion del chart type
    chart = vp.recommend_chart_type("datetime", "numeric")  # 'line'

    # Validacion
    warnings = vp.validate_pie(n_categories=8)  # ["Pie chart con 8 categorias..."]
"""

from .chart_selector import (
    recommend_chart_type, validate_pie, validate_bar_x_not_categorical_for_line,
    orientation_for_labels, ChartType,
)

__all__ = [
    "recommend_chart_type",
    "validate_pie",
    "validate_bar_x_not_categorical_for_line",
    "orientation_for_labels",
    "ChartType",
]
