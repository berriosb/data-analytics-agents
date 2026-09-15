"""
make doctor — preflight de versiones y peer-deps para data-analytics-agents.

Verifica que el entorno del usuario tiene lo necesario para correr las
skills sin fallar tarde por dependencias faltantes. Pensado para correr
despues de \`npx data-analytics-agents install --all\` y antes del primer
\`make test\`.

Checks:
  - Sistema: Node >= 18, Python >= 3.10, Git disponible.
  - Python peer-deps core (obligatorias): pandas, numpy, openpyxl, plotly,
    sqlalchemy.
  - Python peer-deps opcionales agrupadas por skill:
    * report-export:    kaleido, python-pptx, weasyprint OR pdfkit
    * statistical:      scipy
    * time-series Tier 2: statsmodels (opcional)
    * ML:               scikit-learn
    * api-builder:      fastapi, uvicorn, pydantic
    * cloud warehouses: snowflake-connector-python, sqlalchemy-bigquery,
                        sqlalchemy-redshift, databricks-sql-connector,
                        databricks-sqlalchemy (cualquiera habilita su warehouse)
  - Tooling: bin/install.js corre sin error (--help), el repo tiene
    AGENTS.md + agents/ + skills/, los 20 skills tienen SKILL.md.

Output: human-readable con simbolos (OK / WARN / FAIL), accionables
(\`pip install ...\`, \`npm install ...\`) al lado de cada FAIL o WARN.

Exit code: 0 si todos los checks REQUIRED pasan, 1 si hay cualquier FAIL
REQUIRED. WARN (opcional faltante) NO falla.

Uso:
    python3 scripts/doctor.py
    # o
    make doctor
"""

from __future__ import annotations

import importlib
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parent.parent
MIN_NODE = 18
MIN_PYTHON = (3, 10)
EXPECTED_SKILLS = (
    "using-data-analytics-agents", "csv-profiler", "excel-profiler",
    "excel-formulas", "pandas-cleaning", "schema-mapper",
    "sql-query-helper", "query-validation", "sql-cloud-warehouse",
    "sql-write", "audit-log", "viz-patterns", "statistical-testing",
    "time-series-patterns", "feature-engineering", "ml-modeling",
    "model-evaluation", "insight-synthesis", "report-export",
    "api-builder",
)


# -----------------------------------------------------------------------
# Tipos y helpers de output
# -----------------------------------------------------------------------

# ANSI colors (desactivados si NO_COLOR esta seteado o stdout no es TTY)
_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def _ok(s: str) -> str:
    return _c("32;1", f"OK   {s}")


def _warn(s: str) -> str:
    return _c("33;1", f"WARN {s}")


def _fail(s: str) -> str:
    return _c("31;1", f"FAIL {s}")


def _section(title: str) -> str:
    bar = "=" * 60
    return _c("36;1", f"\n{bar}\n{title}\n{bar}")


@dataclass
class CheckResult:
    """Resultado de un check individual."""

    name: str
    status: str  # "ok" | "warn" | "fail"
    detail: str = ""
    hint: str = ""  # accionable cuando status != "ok"


# -----------------------------------------------------------------------
# Checks de sistema
# -----------------------------------------------------------------------

def check_node() -> CheckResult:
    """Node >= 18 (para el installer bin/install.js)."""
    node = shutil.which("node")
    if not node:
        return CheckResult("Node.js", "fail",
                           detail="node no encontrado en PATH",
                           hint="Instalar Node.js >= 18: https://nodejs.org/")
    try:
        out = subprocess.check_output([node, "--version"], text=True, timeout=5).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return CheckResult("Node.js", "fail", detail=f"node --version fallo: {e}")
    m = re.match(r"v(\d+)", out)
    if not m:
        return CheckResult("Node.js", "warn",
                           detail=f"version no parseable: {out!r}")
    major = int(m.group(1))
    if major < MIN_NODE:
        return CheckResult(
            "Node.js", "fail",
            detail=f"version {out}, requiere >= v{MIN_NODE}",
            hint=f"Actualizar Node a v{MIN_NODE}+: https://nodejs.org/",
        )
    return CheckResult("Node.js", "ok", detail=out)


def check_python() -> CheckResult:
    """Python >= 3.10 (para los snippets de skills)."""
    v = sys.version_info
    if (v.major, v.minor) < MIN_PYTHON:
        return CheckResult(
            "Python", "fail",
            detail=f"version {v.major}.{v.minor}, requiere >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
            hint="Actualizar Python via pyenv / system package manager",
        )
    return CheckResult("Python", "ok", detail=f"{v.major}.{v.minor}.{v.micro}")


def check_git() -> CheckResult:
    """Git disponible (el installer lo usa para resolver paths)."""
    git = shutil.which("git")
    if not git:
        return CheckResult("git", "warn",
                           detail="git no encontrado",
                           hint="Instalar git para que el installer funcione")
    try:
        out = subprocess.check_output([git, "--version"], text=True, timeout=5).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return CheckResult("git", "warn", detail="git --version fallo")
    return CheckResult("git", "ok", detail=out)


# -----------------------------------------------------------------------
# Checks de Python deps
# -----------------------------------------------------------------------

def _try_import(module_name: str) -> tuple[bool, str]:
    """Intenta importar un modulo y devuelve (ok, version_o_error)."""
    try:
        mod = importlib.import_module(module_name)
        ver = getattr(mod, "__version__", "?")
        return True, ver
    except ImportError as e:
        return False, str(e).split("(")[0].strip()


def check_python_dep(name: str, module: str, required: bool = True) -> CheckResult:
    """Chequea un Python peer-dep."""
    ok, info = _try_import(module)
    status = "ok" if ok else ("fail" if required else "warn")
    return CheckResult(
        name=name,
        status=status,
        detail=f"{module} {info}" if ok else f"{module} no instalado",
        hint=f"pip install {module}" if not ok else "",
    )


# -----------------------------------------------------------------------
# Checks de estructura del repo
# -----------------------------------------------------------------------

def check_repo_layout() -> list[CheckResult]:
    """Chequea que el directorio tiene la estructura minima esperada."""
    results = []
    for required in ("AGENTS.md", "agents", "skills", "bin/install.js"):
        p = REPO_ROOT / required
        if not p.exists():
            results.append(CheckResult(f"layout: {required}", "fail",
                                       hint="Repo clonado incompleto"))
    skills_dir = REPO_ROOT / "skills"
    if skills_dir.exists():
        for s in EXPECTED_SKILLS:
            sp = skills_dir / s / "SKILL.md"
            if not sp.exists():
                results.append(CheckResult(f"skill: {s}/SKILL.md", "fail",
                                           hint="Skill faltante — re-clonar el repo"))
    return results


def check_installer() -> CheckResult:
    """bin/install.js --help corre sin error."""
    installer = REPO_ROOT / "bin" / "install.js"
    if not installer.exists():
        return CheckResult("installer", "fail", detail="bin/install.js no existe")
    node = shutil.which("node")
    if not node:
        return CheckResult("installer", "warn", detail="node no disponible para smoke test")
    try:
        subprocess.check_output([node, str(installer), "--help"],
                                timeout=10, stderr=subprocess.STDOUT)
        return CheckResult("installer", "ok", detail="node bin/install.js --help OK")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return CheckResult("installer", "fail",
                           detail=f"install --help fallo: {e}",
                           hint="Revisar bin/install.js manualmente")


# -----------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------

def main() -> int:
    """Corre todos los checks y devuelve exit code (0 OK, 1 si hay FAIL)."""
    print(_section("data-analytics-agents — make doctor"))
    print(f"Repo: {REPO_ROOT}")
    print(f"Version toolkit: {_try_import_tk_version()}")

    sections: list[tuple[str, list[CheckResult]]] = []

    # Sistema
    sections.append(("Sistema", [
        check_node(),
        check_python(),
        check_git(),
    ]))

    # Core Python deps (obligatorias para data-explorer, sql-analyst, viz)
    core_required = [
        ("pandas", "pandas"),
        ("numpy", "numpy"),
        ("openpyxl (excel-profiler)", "openpyxl"),
        ("plotly (viz-patterns)", "plotly"),
        ("sqlalchemy (sql-analyst)", "sqlalchemy"),
    ]
    sections.append(("Python peer-deps (REQUIRED)", [
        check_python_dep(name, mod, required=True) for name, mod in core_required
    ]))

    # Por skill (opcionales — solo WARN si faltan)
    by_skill = [
        ("report-export (PDF/PNG/PPTX)", [
            ("kaleido", "kaleido"),
            ("python-pptx (PPTX)", "pptx"),
            ("weasyprint o pdfkit (PDF)", None),  # check handled specially
        ]),
        ("statistical-testing", [("scipy", "scipy")]),
        ("time-series Tier 2 (decompose/ADF)", [("statsmodels", "statsmodels")]),
        ("ml-modeler (clasif + regresion)", [("scikit-learn", "sklearn")]),
        ("api-builder (REST API)", [
            ("fastapi", "fastapi"),
            ("uvicorn", "uvicorn"),
            ("pydantic", "pydantic"),
        ]),
        ("sql-cloud-warehouse (algun warehouse)", [
            ("snowflake-connector-python", "snowflake.connector"),
            ("google-cloud-bigquery", "google.cloud.bigquery"),
            ("redshift-connector", "redshift_connector"),
            ("databricks-sql-connector", "databricks.sql"),
        ]),
    ]
    optional_results: list[CheckResult] = []
    for skill_label, deps in by_skill:
        optional_results.append(CheckResult(skill_label, "ok", detail=""))
        for entry in deps:
            name, mod = entry
            if mod is None:
                # special: weasyprint OR pdfkit
                wp_ok, _ = _try_import("weasyprint")
                pk_ok, _ = _try_import("pdfkit")
                if wp_ok or pk_ok:
                    optional_results.append(CheckResult(
                        f"  {name}", "ok",
                        detail="weasyprint" if wp_ok else "pdfkit"))
                else:
                    optional_results.append(CheckResult(
                        f"  {name}", "warn",
                        detail="ni weasyprint ni pdfkit instalados",
                        hint="pip install weasyprint  # o pdfkit"))
            else:
                optional_results.append(check_python_dep(f"  {name}", mod, required=False))
    sections.append(("Python peer-deps (OPTIONAL por skill)", optional_results))

    # Repo layout + installer
    layout = check_repo_layout()
    if layout:
        sections.append(("Estructura del repo", layout))
    sections.append(("Tooling", [check_installer()]))

    # Print y resumen
    fail_count = 0
    warn_count = 0
    for title, results in sections:
        print(_section(title))
        for r in results:
            line = {"ok": _ok, "warn": _warn, "fail": _fail}[r.status](r.name)
            if r.detail:
                line += f"  ({r.detail})"
            if r.hint:
                line += f"\n        {r.hint}"
            print(line)
            if r.status == "fail":
                fail_count += 1
            elif r.status == "warn":
                warn_count += 1

    # Resumen
    print(_section("Resumen"))
    if fail_count == 0 and warn_count == 0:
        print(_ok("Todo OK — el toolkit esta listo para usar."))
        print("Proximo paso: make test")
        return 0
    if fail_count == 0:
        print(_warn(f"Todo OK REQUIRED, {warn_count} opcional(es) faltante(s)."))
        print("Las opcionales se pueden instalar despues — no bloquean tests basicos.")
        return 0
    print(_fail(f"{fail_count} check(s) requerido(s) fallaron."))
    print("Corri los hints de cada FAIL y volve a correr `make doctor`.")
    return 1


def _try_import_tk_version() -> str:
    """Lee la version del toolkit desde package.json sin importar nada."""
    pkg = REPO_ROOT / "package.json"
    if not pkg.exists():
        return "(desconocida)"
    try:
        import json
        with pkg.open() as f:
            return f"v{json.load(f)['version']}"
    except Exception:
        return "(no parseable)"


if __name__ == "__main__":
    sys.exit(main())
