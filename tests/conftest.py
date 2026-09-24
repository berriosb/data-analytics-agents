"""
conftest.py — bootstrap de pytest para los unit tests del toolkit.

Los nombres de skills siguen la convención de skills.sh (con guiones:
`sql-write`, `audit-log`, etc.), pero Python no permite guiones en
identificadores de módulos. `skills_loader.py` resuelve eso registrando
aliases hyphen ↔ underscore en `sys.modules`. Este conftest llama al
bootstrap en module-load time, antes de que pytest colecte los tests,
para que los `from sql_write import recetas` top-level de cada test file
resuelvan sin más ceremonia.

Razón para no duplicar el bootstrap acá: la lógica vive en
`skills_loader.py` y es usada también por `examples/*/demo_*.py`. Si la
duplicamos, los dos sitios se desincronizan (ya pasó). Llamar a
`bootstrap()` directo es lo correcto.
"""

from __future__ import annotations

import sys
from pathlib import Path

# El loader vive en la raíz del repo.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skills_loader import bootstrap  # noqa: E402

# Bootstrap antes de pytest importe los test files.
bootstrap()
