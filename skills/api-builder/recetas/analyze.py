"""
Inspeccion estatica de una funcion Python via stdlib (inspect).

NO ejecuta el cuerpo de la funcion — solo lee signature, type hints y
docstring. Esto es critico para la seguridad: una funcion con side effects
(que escriba a DB, mande emails, etc.) NO se ejecuta al inspeccionarla.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, get_type_hints


@dataclass
class ParamInfo:
    name: str
    annotation: str          # str del type hint (no evaluamos)
    required: bool
    default: Any             # None si no tiene default


@dataclass
class FuncInfo:
    name: str
    module_path: str
    qualified_name: str
    docstring: str
    params: list[ParamInfo]
    return_annotation: str   # str del return type hint


@dataclass
class AnalyzeResult:
    func: FuncInfo
    imports: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def analyze_function(path: str | Path, func_name: str) -> AnalyzeResult:
    """Inspecciona la funcion sin ejecutarla y devuelve un FuncInfo.

    Raises:
        FileNotFoundError si el archivo no existe
        ImportError si el modulo no se puede cargar (syntax error)
        AttributeError si la funcion no existe en el modulo
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe el archivo: {p}")
    if not p.suffix == ".py":
        raise ValueError(f"Solo se aceptan archivos .py, recibio {p.suffix}")

    # Cargar el modulo por path sin ejecutar side effects
    spec = importlib.util.spec_from_file_location(f"_api_builder_{p.stem}", p)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar el modulo desde {p}")
    mod = importlib.util.module_from_spec(spec)

    # Los side effects del modulo top-level (e.g. `import pandas as pd`)
    # son inevitables al cargar, pero el cuerpo de la funcion NO se ejecuta.
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        raise ImportError(
            f"Error cargando {p} (probable syntax error o import faltante): {e}"
        ) from e

    if not hasattr(mod, func_name):
        raise AttributeError(
            f"'{func_name}' no existe en {p}. Funciones disponibles: "
            f"{[n for n in dir(mod) if not n.startswith('_') and callable(getattr(mod, n))]}"
        )
    func = getattr(mod, func_name)
    if not callable(func):
        raise TypeError(f"'{func_name}' en {p} no es callable.")

    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    params: list[ParamInfo] = []
    warnings: list[str] = []
    for pname, param in sig.parameters.items():
        if pname == "self":
            continue
        ann = hints.get(pname, param.annotation)
        ann_str = _annotation_to_str(ann)
        # Si no tiene type hint, warning
        if ann is inspect.Parameter.empty:
            warnings.append(
                f"Parametro '{pname}' sin type hint — se generara pydantic Any."
            )
            ann_str = "Any"
        params.append(ParamInfo(
            name=pname,
            annotation=ann_str,
            required=(param.default is inspect.Parameter.empty),
            default=None if param.default is inspect.Parameter.empty else param.default,
        ))

    ret = hints.get("return", sig.return_annotation)
    ret_str = _annotation_to_str(ret) if ret is not inspect.Parameter.empty else "Any"

    func_info = FuncInfo(
        name=func_name,
        module_path=str(p),
        qualified_name=f"{p.stem}.{func_name}",
        docstring=(func.__doc__ or "").strip(),
        params=params,
        return_annotation=ret_str,
    )
    return AnalyzeResult(
        func=func_info,
        imports=_detect_imports(p),
        warnings=warnings,
    )


def _annotation_to_str(ann: Any) -> str:
    """Convierte un type hint a string sin evaluarlo."""
    if ann is inspect.Parameter.empty or ann is None:
        return "Any"
    if isinstance(ann, str):
        return ann
    # Tipos built-in (float, int, str, bool, list, dict, etc.) — usar __name__
    if hasattr(ann, "__name__"):
        return ann.__name__
    # typing.Optional[int], typing.List[int], etc — usar repr limpio
    s = repr(ann)
    # Simplificar typing.X a X
    return s.replace("typing.", "")


def _detect_imports(path: Path) -> list[str]:
    """Lee el archivo y extrae los imports top-level para requirements."""
    imports = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("import "):
            parts = s.split()
            if len(parts) >= 2:
                # `import foo.bar` -> foo; `import foo as bar` -> foo
                imports.add(parts[1].split(".")[0])
        elif s.startswith("from "):
            parts = s.split()
            if len(parts) >= 4 and parts[0] == "from" and parts[2] == "import":
                imports.add(parts[1].split(".")[0])
    # Filtrar stdlib basica (no agregar a requirements)
    stdlib = {
        "os", "sys", "re", "json", "math", "time", "datetime", "typing",
        "pathlib", "collections", "functools", "itertools", "random",
        "string", "io", "csv", "ast", "inspect", "importlib",
    }
    return sorted(imports - stdlib)