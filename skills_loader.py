"""
skills_loader.py — bootstrap para importar `skills.<name>.recetas.*` desde
scripts y tests.

Por qué existe este archivo
───────────────────────────

Los nombres de skills siguen la convención de skills.sh y de npm: usan guion
(`sql-write`, `audit-log`, `excel-formulas`, etc.). Python NO permite guiones
en identificadores de módulos: `import sql-write` falla con SyntaxError.

Hay tres opciones para resolver esto y descartamos dos:

1. Renombrar los directorios a `sql_write/` etc. → ROMPE skills.sh, npm y los
   4 CLIs que auto-descubren skills por nombre con guion.
2. Crear `__init__.py` con `__path__` hackeado manualmente por skill → 9
   archivos duplicados que se desincronizan cada vez que se agrega una skill.
3. **Este archivo:** un bootstrap pequeño y auto-descubrible que registra
   cada `skills/<hyphen>/` bajo el nombre `<hyphen>` Y `<underscore>` en
   `sys.modules`. El guion se reemplaza programáticamente, no en el
   filesystem.

Consecuencia operativa: para usar las recetas desde un script Python, basta
con una línea:

    >>> from skills_loader import bootstrap
    >>> bootstrap()
    >>> from sql_write import recetas as sw     # alias underscore
    >>> from sql-write import recetas as sw_h   # alias hyphen (mismo modulo)

Sin este bootstrap, ni los tests ni los examples pueden `import` las
recetas directamente, y `isinstance(err, BlockedOperationError)` falla
porque las clases son objetos distintos en cada namespace.

Este archivo está excluido del tarball npm (ver `.npmignore`:
`skills_loader.py`). Es dev-convenience local — el toolkit distribuido son
los SKILL.md y los `recetas/*.py` como spec de referencia para los LLMs.

API pública
───────────

- `bootstrap()` — entry point único. Hace lo que tests/conftest.py y los
  examples necesitan en una llamada. Idempotente.
- `load_skill_packages(skills_root)` — primera mitad: registra `sql-write`
  etc. en sys.modules vía path-spec hack. Bajo nivel; normalmente no se
  llama directo.
- `prime_and_alias_submodules(skills_root)` — segunda mitad: importa cada
  `recetas/__init__.py` por la ruta hyphen (como el código interno del skill
  los resuelve) y registra el mismo módulo bajo el nombre underscore.
  Sin esto, los tests que hacen `from sql_write.recetas.errors import X` y
  el código de skill que hace `from .errors import X` terminan con clases
  distintas.

Uso en tests (vía conftest.py):

    from skills_loader import bootstrap
    bootstrap()

Uso en examples (vía demo_offline.py, build_demo.py, etc.):

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from skills_loader import bootstrap
    bootstrap()
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Iterable


__all__ = ["bootstrap", "load_skill_packages", "prime_and_alias_submodules"]


def load_skill_packages(skills_root: str | Path = "skills") -> None:
    """Registra cada subdir de `skills/` como paquete importable, con alias
    hyphen→underscore en sys.modules.

    Para cada `skills/<hyphen-name>/`, intenta `importlib.import_module` por
    el nombre hyphen. Si el nombre tiene guion (lo normal), eso falla con
    SyntaxError esperado — en ese caso arma un `ModuleSpec` a mano desde el
    `__init__.py` y registra DOS alias: el hyphen y el underscore.

    Si el nombre no tiene guion (raro pero posible), solo registra el
    nombre original.
    """
    root = Path(skills_root).resolve()
    if not root.exists():
        return
    if str(root) not in sys.path:
        # `root` es el directorio `skills/`. Aunque los registros manuales
        # en sys.modules hacen que `import sql_write` resuelva sin sys.path,
        # anadir `skills/` ayuda a herramientas externas (pytest, ruff) a
        # descubrir los modulos cuando hacen auto-import.
        sys.path.insert(0, str(root))

    for skill_dir in sorted(root.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
            continue
        hyphen_name = skill_dir.name
        underscore_name = hyphen_name.replace("-", "_")

        # Caso 1: el nombre no tiene guion — import directo.
        if underscore_name == hyphen_name:
            try:
                importlib.import_module(hyphen_name)
            except ImportError:
                pass
            continue

        # Caso 2: el nombre tiene guion — armamos el spec a mano.
        # Pasamos el path aunque el archivo no exista: importlib lo trata
        # como namespace package sin loader y aun asi permite resolver
        # submodulos bajo `submodule_search_locations`. Pasar `None` en
        # origin devuelve spec=None y rompe el bootstrap.
        spec = importlib.util.spec_from_file_location(
            underscore_name,
            str(skill_dir / "__init__.py"),
            submodule_search_locations=[str(skill_dir)],
        )
        if spec is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        mod.__path__ = [str(skill_dir)]
        sys.modules[underscore_name] = mod
        # Tambien registramos el nombre hyphen por si algun script lo quiere.
        # (Nota: importlib NO puede importar por nombre hyphen directamente;
        # solo se usa como key de sys.modules para resoluciones internas.)
        sys.modules.setdefault(hyphen_name, mod)


def prime_and_alias_submodules(skills_root: str | Path = "skills") -> None:
    """Importa cada `<skill>.recetas` por la ruta hyphen y registra el MISMO
    módulo bajo el nombre underscore.

    Por qué: cuando `skills/sql-write/recetas/validate.py` hace
    `from .errors import BlockedOperationError`, Python resuelve el módulo
    `sql-write.recetas.errors` (con guion, porque así se llama el
    directorio). Si un test después hace
    `from sql_write.recetas.errors import BlockedOperationError`, Python
    trata `sql_write.recetas.errors` como un módulo DISTINTO (porque el
    nombre string difiere), aunque apunte al mismo archivo. `isinstance`
    falla porque son clases distintas.

    Esta función cierra ese gap recorriendo los submodulos ya cargados
    en `sys.modules` bajo el namespace hyphen y copiándolos al namespace
    underscore.
    """
    root = Path(skills_root).resolve()
    if not root.exists():
        return
    for skill_dir in sorted(root.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
            continue
        hyphen_name = skill_dir.name
        underscore_name = hyphen_name.replace("-", "_")
        recetas_module_name = f"{hyphen_name}.recetas"
        try:
            importlib.import_module(recetas_module_name)
        except ImportError:
            # Skill sin modulo recetas/ (ej. excel-profiler, schema-mapper).
            continue
        # Walk los submodulos cargados bajo el namespace hyphen.
        prefix_hyphen = f"{hyphen_name}."
        for mod_name in list(sys.modules.keys()):
            if not mod_name.startswith(prefix_hyphen):
                continue
            tail = mod_name[len(hyphen_name):]
            underscore_full = underscore_name + tail
            sys.modules.setdefault(underscore_full, sys.modules[mod_name])


def bootstrap(skills_root: str | Path = "skills") -> None:
    """Entry point único. Hace las dos cosas juntas. Idempotente.

    Equivalente a:

        load_skill_packages(skills_root)
        prime_and_alias_submodules(skills_root)

    Uso típico en conftest.py o en un demo script:

        from skills_loader import bootstrap
        bootstrap()

    Si `skills_root` no existe (ej. cuando el toolkit está instalado vía
    npm y `skills/` no está en el cwd), las dos funciones retornan
    silenciosamente — el bootstrap no rompe nada si falla.
    """
    load_skill_packages(skills_root)
    prime_and_alias_submodules(skills_root)
