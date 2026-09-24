# Feature: clarify-package-python-bindings

**Status:** in_progress
**Branch:** main (autorizado por el usuario; sin PR por ahora)
**Goal:** el `package.json` deja de mentir sobre deps Python. Las peerDeps
reales migran a un `pyproject.toml` declarado como `[project.optional-dependencies]`,
queda documentado el doble canal (npm para instalar el toolkit, pip para las
recetas dev/test), y `skills_loader.py` deja de ser un parche misterioso.

## Contexto

Análisis previo mostró que el toolkit tiene tres tensiones que confunden al
contributor nuevo:

1. `package.json#peerDependencies` declara 21 paquetes Python (pandas,
   sqlalchemy, snowflake-connector-python, fastapi, ...). npm los ignora
   silenciosamente. Un dev que vea `peerDependencies` asume que `npm install`
   las instala. No lo hace.
2. `skills/<name>/recetas/*.py` es una librería Python real con `__init__.py`,
   `__all__`, tests que la importan y examples que la corren. Pero no hay forma
   de consumirla como paquete — el usuario tiene que clonar el repo o armar su
   propio `pyproject.toml`.
3. `skills_loader.py` existe solo porque Python no acepta guiones en nombres
   de módulos, y los nombres de skills siguen la convención de skills.sh
   (`sql-write`, no `sql_write`). No tiene README que explique por qué existe;
   `tests/conftest.py` duplica su bootstrap en `_bootstrap_skills_loader`.

## Scope

Dentro de scope:

- Crear `pyproject.toml` con `[project]` metadata + `[project.optional-dependencies]`
  declarando las peerDeps reales + tool config (pytest, ruff). Marcado claramente
  como **no publicado a PyPI** — es dev convenience local.
- Limpiar `package.json`: borrar `peerDependencies` y `peerDependenciesMeta`.
  Queda con 0 deps (el bin ESM no necesita nada).
- Mejorar `skills_loader.py` con docstring completo + exponer `bootstrap()`
  pública que reúna la lógica que ahora vive duplicada en `tests/conftest.py`.
- Refactor `tests/conftest.py` para reusar `bootstrap()`.
- Actualizar `requirements-dev.txt` para que sea un shortcut a `pip install
  -e .[dev]`.
- Actualizar `README.md` y `AGENTS.md` con el flujo correcto.
- Verificar que `make doctor`, `make test-unit` y `node ./bin/install.js list`
  pasan.

Fuera de scope:

- No publicar a PyPI.
- No renombrar skills (`sql-write` → `sql_write` rompería skills.sh).
- No migrar el bin a Python.
- No separar el paquete en dos.
- No tocar archivos sin commit del usuario (`.gitignore`, `AGENTS.md`,
  `skills/sql-write/SKILL.md` ya tienen cambios locales no relacionados).

## Tasks

Ver `todo` list activa. Las 7 tareas mapean 1:1 con los cambios arriba.

## Acceptance criteria

- `pip install -e .[dev]` instala todas las peerDeps reales y deja las
  recetas importables (`python -c "import sys; sys.path.insert(0,'.'); from
  skills_loader import bootstrap; bootstrap(); from sql_write import recetas"`)
- `pip install -e .[dev]` falla limpio si Python < 3.10 o si faltan peerDeps
  opcionales.
- `npm install` y `npx data-analytics-agents install --all` siguen
  funcionando exactamente igual que antes.
- `make test-unit` corre los 10 tests existentes y pasan.
- `node ./bin/install.js list` muestra los 5 agentes y 20 skills.
- `make doctor` no introduce nuevos warnings.
- `package.json` queda con 0 deps y 0 peerDeps.
- `pyproject.toml` declara explícitamente que NO se publica a PyPI
  (comentario en el header + classifiers).

## Evidence (commits)

Pendiente — se completa al cerrar cada tarea.

## Risks

- El refactor de `skills_loader.py` podría romper los examples que lo
  importan. Mitigación: la API pública (`load_skill_packages`, nueva
  `bootstrap`) mantiene el mismo comportamiento; `_bootstrap_skills_loader`
  privado de `conftest.py` se reemplaza por `bootstrap()`.
- Quitar las peerDeps del `package.json` podría sorprender a quien copy-paste
  el archivo esperando verlas. Mitigación: el README explica que las deps
  Python viven ahora en `pyproject.toml` con el mismo versionado.
