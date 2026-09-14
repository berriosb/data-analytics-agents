"""
Demo end-to-end de `api-builder`: toma examples/api_builder_sample/analysis.py
+ funcion `score_cliente`, genera la API completa y la valida.

Uso:
    python examples/api_builder_sample/build_demo.py
"""

from __future__ import annotations

import shutil
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from skills_loader import load_skill_packages
load_skill_packages("skills")

from api_builder.recetas import build_api


EXAMPLE_DIR = Path(__file__).parent
ANALYSIS_PY = EXAMPLE_DIR / "analysis.py"
OUT_DIR = EXAMPLE_DIR / "out_api"


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)

    result = build_api(
        analysis_path=ANALYSIS_PY,
        func_name="score_cliente",
        output_dir=OUT_DIR,
        endpoint="score",
    )

    print(f"=== API generada en {result['output_dir']} ===")
    for f in result["files"]:
        path = result["output_dir"] / f
        print(f"  {f:30s}  {path.stat().st_size:>6} bytes")
    if result["warnings"]:
        print("\nWarnings:")
        for w in result["warnings"]:
            print(f"  - {w}")

    # Smoke test: importar la app generada y correr el test
    print("\n=== Smoke test: pytest sobre la API generada ===")
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_app.py", "-v"],
        cwd=str(OUT_DIR),
        capture_output=True,
        text=True,
    )
    print(r.stdout[-500:] if r.stdout else "")
    if r.returncode != 0:
        print(f"FAIL: pytest returncode {r.returncode}")
        print(r.stderr[-500:])
        sys.exit(1)

    print("\nOK: API generada + tests pasaron.")


if __name__ == "__main__":
    main()