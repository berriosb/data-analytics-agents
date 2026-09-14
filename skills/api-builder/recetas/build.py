"""
Orquestador: toma un archivo Python + nombre de funcion, genera la API
completa, valida que importa sin errores, y escribe a disco.

Si la validacion falla, hace rollback (borra el directorio temporal) y
reporta el error al usuario.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .analyze import analyze_function
from .codegen import (
    generate_pydantic_model,
    generate_fastapi_app,
    generate_requirements,
    generate_dockerfile,
    generate_readme,
    generate_tests,
)


def build_api(analysis_path: str | Path, func_name: str,
              output_dir: str | Path,
              endpoint: str | None = None,
              api_key: str | None = None) -> dict[str, object]:
    """Construye la API completa y la escribe en output_dir.

    Returns:
        {"output_dir": Path, "files": list[str], "warnings": list[str]}

    Raises:
        Si la validacion del codigo generado falla, hace rollback y
        propaga la excepcion original.
    """
    analysis_path = Path(analysis_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Analizar la funcion
    info = analyze_function(analysis_path, func_name)

    # 2. Generar todos los archivos en memoria
    pydantic_code = generate_pydantic_model(info)
    app_code = generate_fastapi_app(info, pydantic_code, endpoint, api_key)
    reqs_code = generate_requirements(info)
    docker_code = generate_dockerfile()
    readme_code = generate_readme(info, endpoint or "predict")
    tests_code = generate_tests(info, endpoint or "predict")

    # 3. Validar: escribir en directorio temporal, importar, rollback
    tmp = Path(tempfile.mkdtemp(prefix="api_builder_"))
    try:
        # El analysis.py se copia tal cual (necesario para que app.py lo importe)
        shutil.copy2(analysis_path, tmp / "analysis.py")
        (tmp / "app.py").write_text(app_code, encoding="utf-8")
        validate_generated_app(tmp)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise

    # 4. Validacion OK — escribir en output_dir
    files_written: list[str] = []
    (output_dir / "analysis.py").write_text(
        Path(analysis_path).read_text(encoding="utf-8"), encoding="utf-8"
    )
    files_written.append("analysis.py")
    (output_dir / "app.py").write_text(app_code, encoding="utf-8")
    files_written.append("app.py")
    (output_dir / "requirements.txt").write_text(reqs_code, encoding="utf-8")
    files_written.append("requirements.txt")
    (output_dir / "Dockerfile").write_text(docker_code, encoding="utf-8")
    files_written.append("Dockerfile")
    (output_dir / "README.md").write_text(readme_code, encoding="utf-8")
    files_written.append("README.md")
    (output_dir / "tests").mkdir(exist_ok=True)
    (output_dir / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (output_dir / "tests" / "test_app.py").write_text(tests_code, encoding="utf-8")
    files_written.append("tests/test_app.py")

    shutil.rmtree(tmp, ignore_errors=True)

    return {
        "output_dir": output_dir,
        "files": files_written,
        "warnings": info.warnings,
        "func": info.func.name,
    }


def validate_generated_app(generated_dir: Path) -> None:
    """Verifica que `app.py` importa sin errores en el directorio dado.

    Ejecuta `python -c "import app"` en un subprocess. Si falla, levanta
    RuntimeError con el stderr completo.
    """
    result = subprocess.run(
        [sys.executable, "-c", "import app; print('OK')"],
        cwd=str(generated_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"El codigo generado no importa. stderr:\n{result.stderr}"
        )
    if "OK" not in result.stdout:
        raise RuntimeError(
            f"El codigo generado no imprime 'OK'. stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )