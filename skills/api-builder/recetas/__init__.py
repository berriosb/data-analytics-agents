"""
Recetas pre-aprobadas para generar una API REST a partir de una funcion
Python de analisis.

Modulos:
- analyze: inspect de la funcion (signature, type hints, docstring)
- codegen: genera los archivos app.py, models.py, requirements.txt,
  Dockerfile, README.md, tests/test_app.py
- build: orquestador que valida inputs, genera todo, y rollback si falla

NO contiene codigo del usuario ejecutado sin validacion. La firma de la
funcion se inspecciona con stdlib (inspect), no se ejecuta el cuerpo.
"""

from .analyze import analyze_function, FuncInfo
from .codegen import (
    generate_pydantic_model,
    generate_fastapi_app,
    generate_requirements,
    generate_dockerfile,
    generate_readme,
    generate_tests,
)
from .build import build_api, validate_generated_app

__all__ = [
    "analyze_function",
    "FuncInfo",
    "generate_pydantic_model",
    "generate_fastapi_app",
    "generate_requirements",
    "generate_dockerfile",
    "generate_readme",
    "generate_tests",
    "build_api",
    "validate_generated_app",
]