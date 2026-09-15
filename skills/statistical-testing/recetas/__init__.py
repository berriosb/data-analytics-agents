"""
Recetas pre-aprobadas para statistical-testing (tests de hipotesis
sobre datos limpios).

Modulos:
- effect_size: helpers para tamano de efecto (cohen_label, eta_squared_label,
  cohens_d) — compartidos entre todos los tests.
- tests: wrappers sobre scipy.stats que devuelven un dict normalizado
  con la misma forma (test / statistic / p_value / n / effect_size /
  effect_label / assumptions / note). Insight-synthesis consume esta
  forma para producir el brief.

Cobertura inicial:
- t_test_ind (Welch / Student)
- mann_whitney_u (no parametrica)
- anova_oneway (3+ grupos)

Uso:
    import sys
    sys.path.insert(0, "ruta/al/repo")
    from skills_loader import load_skill_packages
    load_skill_packages()
    from statistical_testing import recetas as st

    import numpy as np
    a = np.random.normal(10, 2, 80)
    b = np.random.normal(11, 2, 75)
    res = st.t_test_ind(a, b)
    print(res["p_value"], res["effect_label"])
"""

from .effect_size import cohen_label, eta_squared_label, cohens_d
from .tests import t_test_ind, mann_whitney_u, anova_oneway

__all__ = [
    "cohen_label",
    "eta_squared_label",
    "cohens_d",
    "t_test_ind",
    "mann_whitney_u",
    "anova_oneway",
]
