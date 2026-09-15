"""
Selector del tipo de grafico correcto segun tipos de variables y pregunta.

Implementa la tabla de decision del SKILL.md de viz-patterns como
funciones puras testeables. El orquestador (futuro `recommend_chart`)
puede llamarla sin instanciar nada de Plotly.

Las reglas siguen el orden:
1. Tiempo en x → line.
2. X categorica, Y numerica → bar.
3. Distribucion de una numerica → histogram si n grande, sino box.
4. Dos numericas → scatter.
5. Partes de un todo → pie solo si <=5 categorias.
"""

from __future__ import annotations

from typing import Literal


ChartType = Literal[
    "line", "bar", "histogram", "box", "violin",
    "scatter", "density_heatmap", "pie", "heatmap",
]


def recommend_chart_type(
    x_type: str,
    y_type: str | None = None,
    *,
    n_points: int | None = None,
    n_categories: int | None = None,
    part_of_whole: bool = False,
) -> str:
    """Recomienda el tipo de grafico segun los tipos de variables y la pregunta.

    Args:
        x_type: 'datetime' | 'numeric' | 'categorical'.
        y_type: 'numeric' | 'categorical' | None (para histogramas de 1D).
        n_points: cantidad de filas del dataset (opcional, para scatter denso).
        n_categories: cantidad de categorias unicas en x (opcional, para pie).
        part_of_whole: True si la pregunta es "partes de un todo" (usa pie/bar).

    Returns:
        Nombre del chart type ('line', 'bar', 'histogram', etc.).
        Para un caso ambiguo, devuelve 'bar' como default conservador.

    Examples:
        >>> recommend_chart_type('datetime', 'numeric')
        'line'
        >>> recommend_chart_type('categorical', 'numeric')
        'bar'
        >>> recommend_chart_type('numeric')
        'histogram'
        >>> recommend_chart_type('numeric', 'numeric', n_points=3000)
        'density_heatmap'
    """
    # Regla 1: tiempo en x → line.
    if x_type == "datetime":
        return "line"

    # Regla 5: partes de un todo → pie (con guardrail) o bar.
    if part_of_whole and y_type == "numeric":
        if n_categories is not None and n_categories <= 5:
            return "pie"
        # Si >5 categorias, pie es ilegible → bar.
        return "bar"

    # Regla 4: dos numericas → scatter (o density_heatmap si es denso).
    if x_type == "numeric" and y_type == "numeric":
        if n_points is not None and n_points > 2000:
            return "density_heatmap"
        return "scatter"

    # Regla 2: x categorica, y numerica → bar.
    if x_type == "categorical" and y_type == "numeric":
        return "bar"

    # Regla 3: una distribucion numerica → histogram si n grande, sino box.
    if x_type == "numeric" and y_type is None:
        if n_points is not None and n_points > 200:
            return "histogram"
        return "box"

    # Default conservador.
    return "bar"


def validate_pie(n_categories: int | None) -> list[str]:
    """Devuelve warnings cuando un pie chart no es apropiado.

    Args:
        n_categories: cantidad de categorias (None si desconocida).

    Returns:
        Lista de warnings (vacia si todo OK). El orquestador decide si
        mostrarlos al usuario o bloquear el render.
    """
    warnings = []
    if n_categories is None:
        warnings.append(
            "Pie chart: cantidad de categorias desconocida. "
            "Recomendado <=5; si >5, usar bar ordenada."
        )
        return warnings
    if n_categories > 5:
        warnings.append(
            f"Pie chart con {n_categories} categorias es ilegible. "
            "Recomendado <=5; para >5 usar bar ordenada o agrupar en 'Otros'."
        )
    return warnings


def validate_bar_x_not_categorical_for_line(n_points: int) -> list[str]:
    """Reglas de densidad para scatter y density_heatmap."""
    if n_points > 5000:
        return [
            f"Scatter con {n_points} puntos es denso. "
            "Recomendado cambiar a density_heatmap o reducir marcadores."
        ]
    return []


def orientation_for_labels(labels: list[str], threshold: int = 8) -> Literal["h", "v"]:
    """Recomienda orientacion de bar chart segun longitud de labels.

    Args:
        labels: lista de categorias del eje X.
        threshold: longitud maxima (caracteres) para mantener vertical.

    Returns:
        'h' (horizontal) si algun label supera threshold, sino 'v' (vertical).
    """
    if any(len(str(l)) > threshold for l in labels):
        return "h"
    return "v"
