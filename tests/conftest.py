"""
conftest.py — fixtures compartidos para los unit tests del toolkit.

Los skills tienen guion en el nombre (`sql-write`, `audit-log`), que Python
no permite en imports. Usamos `skills_loader.py` (que vive en la raíz del
repo) para registrar alias `sql_write`, `audit_log`, etc. que mapean a
los directorios `skills/<name>/`.

Despues de cargar los paquetes, importamos explicitamente cada submodulo
de `recetas/` y aliasamos bajo el nombre alternativo (underscore <-> hyphen),
asi `from sql_write.recetas.errors import X` (ruta underscore, usada en tests)
y `from .errors import X` dentro del skill (ruta hyphen que arma Python
en runtime) resuelven al MISMO objeto modulo. Sin esto, `isinstance`
falla porque las clases son distintas aunque tengan el mismo nombre.

El bootstrap corre en module-load time (antes de que pytest colecte los
tests), asi los `from sql_write import recetas` top-level de cada test
file funcionan sin tener que mover los imports adentro de cada test.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

# Pares (underscore, hyphen) para los skills con `recetas/`.
SKILL_NAME_PAIRS: list[tuple[str, str]] = [
    ("sql_write", "sql-write"),
    ("audit_log", "audit-log"),
    ("excel_formulas", "excel-formulas"),
    ("report_export", "report-export"),
    ("sql_cloud_warehouse", "sql-cloud-warehouse"),
    ("api_builder", "api-builder"),
    ("csv_profiler", "csv-profiler"),
    ("viz_patterns", "viz-patterns"),
    ("statistical_testing", "statistical-testing"),
]


def _bootstrap_skills_loader() -> None:
    """Carga `skills_loader.py` y registra los paquetes de skills en sys.modules."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from skills_loader import load_skill_packages  # type: ignore[import-not-found]

    load_skill_packages()


def _prime_and_alias_skill_submodules() -> None:
    """Importa cada `<skill>.recetas.*` por la ruta hyphen (que es como el
    codigo interno del skill termina resolviendo) y registra el mismo
    modulo bajo el nombre underscore. Asi `from sql_write.recetas.errors`
    en un test ve la misma clase que `from .errors` dentro del skill.
    """
    for underscore, hyphen in SKILL_NAME_PAIRS:
        recetas_module_name = f"{hyphen}.recetas"
        try:
            recetas = importlib.import_module(recetas_module_name)
        except ImportError:
            continue
        # Walk todos los submodulos de recetas.* que Python ya cargo
        # (los carga al ejecutar validate.py, classify.py, etc.).
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith(recetas_module_name + "."):
                tail = mod_name[len(hyphen):]
                underscore_name = underscore + tail
                sys.modules[underscore_name] = sys.modules[mod_name]


# Bootstrap al cargar el modulo, antes de que pytest importe los test files.
_bootstrap_skills_loader()
_prime_and_alias_skill_submodules()
