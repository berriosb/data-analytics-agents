"""
Tests de hipotesis pre-aprobados para statistical-testing.

Wrappers sobre scipy.stats que devuelven un dict normalizado con la
misma forma (test / statistic / p_value / n / effect_size /
effect_label / assumptions / note) listo para insight-synthesis.

Solo lectura, sin eval(), argumentos son siempre valores numericos
(Series / ndarray / list[float]) — nunca strings de expresiones.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats

from .effect_size import cohen_label, eta_squared_label, cohens_d


def _drop_nan(*arrays: np.ndarray) -> list[np.ndarray]:
    """Dropea NaN de cada array independientemente."""
    return [a[~np.isnan(a)] for a in arrays]


def t_test_ind(
    a: Any,
    b: Any,
    equal_var: bool = False,
) -> dict[str, Any]:
    """t-test para dos samples independientes (Welch por default).

    Args:
        a, b: samples (Series, ndarray, list). Se dropean NaN.
        equal_var: si True usa Student (varianzas iguales); si False
            usa Welch (mas robusto, default).

    Returns:
        Dict normalizado con test name, statistic, p_value, n, effect_size
        (Cohen's d), effect_label (pequeno/mediano/grande), assumptions,
        note. Si n bajo (<30 por grupo), note recomienda Mann-Whitney.

    Examples:
        >>> from scipy import stats
        >>> import numpy as np
        >>> np.random.seed(42)
        >>> a = np.random.normal(10, 2, 80)
        >>> b = np.random.normal(11, 2, 75)
        >>> res = t_test_ind(a, b)
        >>> res["test"]
        'Welch t-test'
        >>> "p_value" in res
        True
    """
    a, b = _drop_nan(np.asarray(a, dtype=float), np.asarray(b, dtype=float))
    res = stats.ttest_ind(a, b, equal_var=equal_var)
    d = cohens_d(a, b)
    return {
        "test": "Welch t-test" if not equal_var else "Student t-test",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "n": int(len(a) + len(b)),
        "effect_size": float(abs(d)),
        "effect_label": cohen_label(abs(d)),
        "assumptions": [
            "normalidad aproximada (n>=30 por grupo) o verificar con shapiro_test",
        ],
        "note": "" if min(len(a), len(b)) >= 30 else (
            f"n bajo (a={len(a)}, b={len(b)}); preferir mann_whitney_u"
        ),
    }


def mann_whitney_u(a: Any, b: Any) -> dict[str, Any]:
    """Mann-Whitney U — alternativa no parametrica al t-test.

    Args:
        a, b: samples. Se dropean NaN.

    Returns:
        Dict normalizado. effect_size es U / (n_a * n_b) (aprox r).
        No tiene label estandar — effect_label queda en ''.

    Examples:
        >>> from scipy import stats
        >>> import numpy as np
        >>> np.random.seed(42)
        >>> a = np.random.normal(10, 2, 50)
        >>> b = np.random.normal(11, 2, 50)
        >>> res = mann_whitney_u(a, b)
        >>> res["test"]
        'Mann-Whitney U'
    """
    a, b = _drop_nan(np.asarray(a, dtype=float), np.asarray(b, dtype=float))
    if len(a) == 0 or len(b) == 0:
        raise ValueError(
            f"Samples vacios despues de dropear NaN: len(a)={len(a)}, len(b)={len(b)}"
        )
    res = stats.mannwhitneyu(a, b, alternative="two-sided")
    return {
        "test": "Mann-Whitney U",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "n": int(len(a) + len(b)),
        "effect_size": float(res.statistic / (len(a) * len(b))),
        "effect_label": "",  # sin umbral estandar
        "assumptions": [
            "independencia entre observaciones",
            "forma de la distribucion similar entre grupos",
        ],
        "note": "",
    }


def anova_oneway(*groups: Any) -> dict[str, Any]:
    """ANOVA one-way para 3+ grupos (asume normalidad + homocedasticidad).

    Args:
        *groups: 3+ samples (Series, ndarray, list). Se dropean NaN
            de cada grupo independientemente.

    Returns:
        Dict normalizado. effect_size es eta-squared (SS_between / SS_total).

    Raises:
        ValueError: si se pasan menos de 3 grupos.
    """
    if len(groups) < 3:
        raise ValueError(
            f"anova_oneway requiere >= 3 grupos, recibio {len(groups)}"
        )
    arrays = _drop_nan(*[np.asarray(g, dtype=float) for g in groups])
    res = stats.f_oneway(*arrays)
    all_vals = np.concatenate(arrays)
    grand_mean = all_vals.mean()
    ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in arrays)
    ss_total = ((all_vals - grand_mean) ** 2).sum()
    eta2 = ss_between / ss_total if ss_total > 0 else 0.0
    return {
        "test": "ANOVA one-way",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "n": int(sum(len(g) for g in arrays)),
        "effect_size": float(eta2),
        "effect_label": eta_squared_label(eta2),
        "assumptions": [
            "normalidad por grupo",
            "homocedasticidad (verificar con levene_test)",
        ],
        "note": (
            f"{len(arrays)} grupos; si no se cumplen supuestos, usar kruskal_wallis"
        ),
    }
