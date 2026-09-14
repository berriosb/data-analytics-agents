---
name: api-builder
description: Genera una API REST production-ready (FastAPI + Dockerfile + tests + README) a partir de una funcion Python de analisis. Usese al final del flujo cuando el stakeholder quiere consumir el analisis como servicio, no como reporte estatico. La skill inspecciona la firma con stdlib (NO ejecuta side effects), genera codigo en un directorio temporal, valida que importa sin errores, y rollback si falla. Auth opcional via API key (env var); sin auth por default (dev).
---

# API Builder

Toma una función Python de análisis terminada y la convierte en una API REST
lista para servir con `uvicorn`. Cierra el ciclo "del análisis al servicio"
mencionado por el video BYOA.

## Descripción general

A diferencia de las skills de análisis (que viven en el flujo de trabajo),
esta opera **al final del pipeline** como servicio de empaquetado. Recibe:

- Una ruta a un archivo `.py` con una función callable
- El nombre de la función

Y produce en `output_dir/`:
- `analysis.py` — copia del input original
- `app.py` — FastAPI app con `/health`, `/schema`, y el endpoint de la función
- `requirements.txt` — fastapi + uvicorn + pydantic + imports del usuario
- `Dockerfile` — python:3.11-slim + uvicorn
- `README.md` — instrucciones de uso local + deploy
- `tests/test_app.py` — pytest con TestClient de FastAPI

## Cuándo usar

Invocar esta skill cuando el pedido matchee con alguno de:

- "Tengo esta función `score_cliente(...)`. Expónla como API REST."
- "Quiero servir el forecast como endpoint para el equipo de pricing."
- "Necesito una API lista para deployar en Railway/Fly/Vercel."
- "Convertime el notebook en un servicio que el front pueda consumir."

**No** invocar cuando:

- El usuario todavía está explorando datos → seguir en el flujo normal.
- Necesita un dashboard interactivo con UI → eso es Streamlit/Gradio,
  no REST. Si lo pide, escalar a ADR-003.
- El usuario quiere deployar **directamente** sin ver el código → fuera
  de scope v1 (la skill genera código, no deploya).

## Flujo de trabajo

1. **Validar inputs**: recibir `--analysis-path`, `--func-name`,
   `--output-dir`, `--endpoint`, `--api-key` (opcional). Verificar que
   el archivo existe y que el nombre de función está en el módulo
   (vía `inspect`, sin ejecutar side effects).
2. **Analizar la función** con `analyze_function(path, func_name)`:
   extrae signature, type hints, docstring, imports del archivo.
   Si algún param no tiene type hint, warning al usuario y se usa `Any`.
3. **Generar código** en memoria:
   - Pydantic model de input (`generate_pydantic_model`)
   - FastAPI app (`generate_fastapi_app`)
   - Requirements, Dockerfile, README, tests
4. **Validar** que el código generado importa sin errores en un directorio
   temporal (`validate_generated_app`). Si falla, rollback y reportar
   el error completo al usuario.
5. **Escribir a disco** en `output_dir/` (con `analysis.py` copiado tal cual).
6. **Reportar** la lista de archivos generados + warnings al usuario.

## Recetas pre-aprobadas (importables)

```python
import sys
sys.path.insert(0, "ruta/al/repo")
from skills_loader import load_skill_packages
load_skill_packages("skills")

from api_builder.recetas import (
    analyze_function,                    # inspect de la funcion
    generate_pydantic_model,             # model pydantic del input
    generate_fastapi_app,                # codigo de app.py
    generate_requirements,               # requirements.txt
    generate_dockerfile, generate_readme, generate_tests,
    build_api,                            # orquestador end-to-end
    validate_generated_app,              # check de import
)
```

Las recetas son funciones puras excepto `build_api` (que escribe a
disco). Para testing, se puede llamar cada `generate_*` por separado.

## CLI rápido (uso desde el agente o terminal)

```bash
# Demo end-to-end con la funcion score_cliente de muestra
python examples/api_builder_sample/build_demo.py

# O ad-hoc contra tu propia funcion
python -c "
import sys; sys.path.insert(0, '.')
from skills_loader import load_skill_packages
load_skill_packages('skills')
from api_builder.recetas import build_api
result = build_api(
    analysis_path='mi_analisis.py',
    func_name='mi_funcion',
    output_dir='out_api',
    endpoint='predict',     # opcional, default 'predict'
    api_key=None,           # opcional, setear para requerir X-API-Key
)
print(result)
"
```

## Templates

Los archivos generados NO son hardcodeados — cada `generate_*` toma
`AnalyzeResult` y produce un string. Los "templates" están embebidos
en `recetas/codegen.py` como f-strings.

Si querés customizar el aspecto (e.g. agregar CORS, logging, rate
limiting), editá `generate_fastapi_app` directamente. Es 1 archivo,
~150 líneas.

## Justificaciones comunes

- **Por qué FastAPI y no Flask?** FastAPI genera docs automáticas en
  `/docs` (Swagger UI), valida inputs con pydantic, y es async-native.
  Para entregar "ya hay docs en `/docs`" al manager, gana.
- **Por qué no usar `exec()` para "ver" qué hace la función?** Porque
  podría tener side effects (mandar emails, escribir DB). Solo leemos
  signature y type hints con stdlib. La función se ejecuta **solo** cuando
  el endpoint recibe un request.
- **Por qué validar en directorio temporal antes de escribir?** Para
  rollback si el código generado no compila. Mejor fallar limpio que
  dejar archivos rotos en `output_dir/`.
- **Por qué API key y no JWT/OAuth?** Porque JWT requiere issuer,
  JWKS, refresh tokens — overkill para v1. API key es 1 línea de
  código y cubre el caso "no quiero que internet use mi endpoint".

## Señales de alerta

- Función sin type hints en sus parámetros → warning, pydantic usa `Any`.
  La API funciona pero sin validación. Sugerir al usuario agregar type hints.
- Función con side effects al importar (e.g. `print()`, `requests.get()`
  a un endpoint externo en el top-level) → esos se ejecutan al cargar
  el módulo en la API. Warning al usuario.
- Función con `*args` / `**kwargs` no soportados → error accionable.
- `output_dir/` ya existe con archivos → se sobreescriben. Warning.
- `pip install` de requirements falla en runtime → el usuario lo ve
  cuando corre `uvicorn app:app`, no en la generación.

## Verificación

Criterios de "listo" (ver `docs/prd/api-builder.md`):

- [x] `examples/api_builder_sample/` con `analysis.py` (función de
      scoring) + `build_demo.py` que genera la API completa.
- [x] `make test-api-builder` ejecuta el demo y verifica que:
  - `python -c "import app"` pasa (validación interna)
  - `pytest tests/test_app.py` pasa (3/3 OK: health, schema, endpoint)
  - API responde en vivo: `GET /health`, `POST /predict`, `GET /schema`
- [x] La skill está en `skills/api-builder/SKILL.md` con el template
      de 6 secciones completo.
- [x] `AGENTS.md` actualizado: `reporting-analyst` carga `api-builder`
      OPCIONAL al final (después de `report-export`).
- [x] `package.json`: `fastapi`, `uvicorn`, `pydantic` declarados como
      peerDeps opcionales.

## Dependencias

- **fastapi** >= 0.110 — peerDep opcional
- **uvicorn[standard]** >= 0.27 — peerDep opcional (servidor ASGI)
- **pydantic** >= 2.0 — peerDep opcional
- **pytest** + **httpx** (transitivo de TestClient) — para correr los tests

Si una dep no está, el usuario debe `pip install -r requirements.txt`
**en el directorio generado**, no globalmente. La skill no instala nada.