# PRD — `api-builder`

- **Status:** Accepted (2026-09-15)
- **Implementation:** shipped at v0.5.0. Ver [CHANGELOG.md](../../CHANGELOG.md).
- **Owner:** CodeHak (Bastian)
- **ADR relacionado:** [002-end-to-end-delivery](../adr/002-end-to-end-delivery.md)
- **Skills relacionadas:** `reporting-analyst` (carga esta opcional al final), `viz-patterns`, `insight-synthesis`, `report-export`

## Goal

Que un data analyst pueda tomar un análisis terminado (función Python o
notebook con un DataFrame final) y **generar una API REST production-ready**
en un solo comando, lista para servir con uvicorn. La API expone el
resultado del análisis como JSON + opcionalmente como endpoint de
re-cálculo si los inputs cambiaron.

## User story

> Como data analyst en una fintech, terminé un modelo de scoring de
> clientes (función `score_cliente(features) -> dict`). Quiero exponerlo
> como API REST para que el equipo de producto lo consulte desde su app.
> Necesito un comando que me genere:
> - `app.py` con FastAPI + endpoint `POST /score` + endpoint `GET /health`
> - `requirements.txt` con fastapi, uvicorn, pydantic
> - Dockerfile mínimo para deploy
> - README con instrucciones de `uvicorn app:app --reload`
> - Tests pytest que validen el endpoint
>
> Sin tener que escribir FastAPI a mano ni aprender OpenAPI.

## Scope in (v1)

- **Inputs**: una función Python (path al archivo + nombre de la función)
  o un script standalone que devuelve un dict/DataFrame.
- **Outputs generados**:
  - `app.py` — FastAPI app con:
    - `GET /health` → `{"status": "ok"}`
    - `POST /predict` (o nombre custom) → llama la función, valida inputs
      con pydantic, devuelve JSON
    - `GET /docs` → Swagger UI automática (built-in FastAPI)
    - `GET /schema` → JSON con el input schema (pydantic model_json_schema)
  - `models.py` — pydantic models extraídos de los type hints de la función
    (o placeholder si la función no tiene type hints)
  - `requirements.txt` — fastapi, uvicorn, pydantic + las deps de la función
  - `Dockerfile` — python:3.11-slim + pip install + uvicorn
  - `README.md` — cómo correr local + cómo deployar
  - `tests/test_app.py` — pytest con TestClient de FastAPI
- **Validación**: el código generado debe pasar `python -c "import app"` sin
  errores. Si falla, la skill reporta el error y NO escribe archivos a
  disco (rollback).
- **Auth opcional**: API key via header `X-API-Key`, configurada via env
  var. Si no se setea, la API es abierta (para dev). Documentar que prod
  debe usar auth.

## Scope out (v1, queda como follow-up)

- **Streaming responses (SSE/WebSocket)**: fuera de scope. Para forecast
  en tiempo real va como ADR-003.
- **OAuth2 / JWT**: fuera de scope. API key simple en v1; OAuth2 cuando
  el stakeholder lo pida.
- **Async DB queries**: fuera de scope. La skill genera APIs síncronas;
  si la función es async, se respeta pero no se optimiza.
- **Auto-deploy a Vercel/Railway/Fly**: fuera de scope. Generamos el
  código + instrucciones; el usuario decide dónde deployar.

## Workflow (las 6 fases de la skill)

1. **Validar input**: recibir `path/to/analysis.py` y `function_name`.
   Verificar que el archivo existe, que la función existe, e intentar
   importar el módulo (sin ejecutarlo). Si falla, error accionable.
2. **Inspeccionar la función**: usar `inspect.signature()` para leer
   los type hints. Si no hay type hints, generar `models.py` con
   `pydantic.BaseModel` con campos `Any` (placeholder, warning al usuario).
3. **Generar `app.py`**: Jinja2-style template (string substitution) con
   la función inyectada, los modelos pydantic, y los endpoints.
4. **Generar `requirements.txt`**: detectar las imports top-level del
   archivo del usuario y agregar `fastapi`, `uvicorn`, `pydantic`.
5. **Generar `Dockerfile` + `README.md` + `tests/test_app.py`**: templates
   simples con placeholders para el nombre de la función.
6. **Validar**: ejecutar `python -c "import app"` en un subprocess del
   output generado. Si pasa, escribir a disco en `output_dir/`. Si falla,
   rollback (borrar el directorio temporal) y reportar el error.

## Recetas iniciales (snippets pre-aprobados)

- `analyze_function(path, func_name) -> dict` — extrae signature, type
  hints, docstring.
- `generate_pydantic_model(func_info, name) -> str` — genera el código
  Python del modelo pydantic.
- `generate_fastapi_app(func_info, pydantic_code, options) -> str`
- `generate_requirements(analysis_path) -> str`
- `generate_dockerfile() -> str`
- `generate_readme(func_info, output_dir) -> str`
- `generate_tests(func_info, pydantic_code) -> str`
- `build_api(analysis_path, func_name, output_dir) -> Path`

## Templates (referenciados, no hardcodeados en la skill)

- `skills/api-builder/templates/app.py.tmpl`
- `skills/api-builder/templates/requirements.txt.tmpl`
- `skills/api-builder/templates/Dockerfile.tmpl`
- `skills/api-builder/templates/README.md.tmpl`
- `skills/api-builder/templates/test_app.py.tmpl`

## Verificación (criterios de "listo")

- [ ] `examples/api_builder_sample/` con una función de scoring de muestra
      + script `build_demo.py` que corre la skill y genera la API.
- [ ] `make test-api-builder` ejecuta el demo y verifica que:
  - `python -c "import app"` pasa sin errores
  - `pytest tests/test_app.py` pasa
  - El output incluye `requirements.txt` + `Dockerfile` + `README.md`
- [ ] La skill está en `skills/api-builder/SKILL.md` con el template
      de 6 secciones completo.
- [ ] `AGENTS.md` actualizado: `reporting-analyst` carga `api-builder`
      OPCIONAL al final (después de `report-export`).
- [ ] `package.json`: `fastapi`, `uvicorn`, `pydantic` declarados como
      `peerDependencies` opcionales.
- [ ] `bin/install.js` corre sin cambios.

## Estimación

- Specs + templates: 30 min (hecho).
- Implementación SKILL.md + recetas: 3-4 horas.
- Demo + tests: 1.5 horas.
- Actualización AGENTS.md/package.json: 30 min.

**Total: ~5-6 horas de código + tests.**