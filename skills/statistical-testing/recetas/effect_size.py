"""
Helpers para los tests estadisticos pre-aprobados de statistical-testing.

Funciones puras que devuelven sizes de efecto y labels cualitativos
("pequeno", "mediano", "grande") siguiendo las convenciones de Cohen
(1988) para d y eta-squared.

Estos helpers se comparten entre t_test_ind, t_test_paired,
t_test_1samp, anova_oneway, kruskal_wallis.
"""

from __future__ import annotations

import numpy as np


# Umbrales de Cohen (1988) para d de Cohen:
#   < 0.2  → insignificante
#   < 0.5  → pequeno
#   < 0.8  → mediano
#   >= 0.8 → grande
COHEN_THRESHOLDS = (0.2, 0.5, 0.8)
COHEN_LABELS = ("insignificante", "pequeno", "mediano", "grande")


def cohen_label(d: float | None) -> str:
    """Label cualitativo de un Cohen's d.

    Args:
        d: Cohen's d (magnitud absoluta). Si es None o no es un
            numero, devuelve ''.

    Returns:
        Uno de 'insignificante' / 'pequeno' / 'mediano' / 'grande' / ''.
    """
    if d is None or not np.isfinite(d):
        return ""
    d = abs(d)
    for thr, label in zip(COHEN_THRESHOLDS, COHEN_LABELS):
        if d < thr:
            return label
    return COHEN_LABELS[-1]


def eta_squared_label(eta: float | None) -> str:
    """Label cualitativo de eta-squared o epsilon-squared.

    Umbrales estandar (Cohen 1988):
        < 0.01 → insignificante
        < 0.06 → pequeno
        < 0.14 → mediano
        >= 0.14 → grande

    Args:
        eta: tamano de efecto eta-squared o epsilon-squared.

    Returns:
        Label cualitativo o '' si eta es None / no finito.
    """
    if eta is None or not np.isfinite(eta):
        return ""
    if eta < 0.01:
        return "insignificante"
    if eta < 0.06:
        return "pequeno"
    if eta < 0.14:
        return "mediano"
    return "grande"


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Cohen's d con pooled SD entre dos samples.

    Args:
        a, b: numpy arrays (post-dropeo de nulos). Se asume dtype float.

    Returns:
        Cohen's d = (mean(a) - mean(b)) / sqrt((var(a)+var(b))/2).
        Devuelve 0.0 si la varianza pooled es 0 (samples identicas).
    """
    pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    if pooled == 0:
        return 0.0
    return float((a.mean() - b.mean()) / pooled)
