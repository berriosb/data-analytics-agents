"""
Loader para importar `skills.report-export.recetas.*` desde cualquier script.

Python no permite nombres con guion en imports, asi que exponemos el paquete
como `report_export` (subrayando el guion) via este modulo. Se usa asi:

    import sys
    sys.path.insert(0, "ruta/al/repo")
    from skills_loader import load_skill_packages
    load_skill_packages()
    from report_export import recetas  # ahora funciona
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


def load_skill_packages(skills_root: str | Path = "skills") -> None:
    """Carga todos los subdirs de `skills/` como paquetes `report_export`,
    `excel_profiler`, etc. (guion -> subrayado).
    """
    root = Path(skills_root).resolve()
    if not root.exists():
        return
    for skill_dir in sorted(root.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
            continue
        # El guion en el nombre del directorio no es legal como modulo Python
        py_name = skill_dir.name.replace("-", "_")
        # Inyectar el directorio padre del skill en sys.path para que
        # `import report_export.recetas` funcione.
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        # Crear alias `py_name` -> `skill_dir.name` si difieren
        if py_name != skill_dir.name and py_name not in sys.modules:
            # Cargamos el modulo real primero
            try:
                real_mod = importlib.import_module(skill_dir.name)
            except ImportError:
                # El skill no es importable directamente (caso comun con guion).
                # Cargamos SKILL.md como un sentinel vacio y registramos el alias.
                spec = importlib.util.spec_from_file_location(
                    py_name, skill_dir / "__init__.py",
                    submodule_search_locations=[str(skill_dir)],
                )
                if spec is None:
                    continue
                mod = importlib.util.module_from_spec(spec)
                mod.__path__ = [str(skill_dir)]
                sys.modules[py_name] = mod
                # Tambien registramos el nombre original (con guion) por si
                # algun script quiere `import report-export.recetas` directo.
                sys.modules[skill_dir.name] = mod
                continue
            sys.modules[py_name] = real_mod