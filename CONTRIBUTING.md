# Contributing

Gracias por tu interes en data-analytics-agents. Este toolkit vive de
las contribuciones — un nuevo snippet, una skill completa, un agente,
un fix de bug, mejor doc. Esta guia te lleva paso a paso.

> **TL;DR — para agregar funcionalidad nueva:** abrí un issue con la
> propuesta, segui el [flujo ADR/PRD](#flujo-de-diseno-adr--prd),
> escribi tests, corré `make test`, mandá el PR.

## Code of conduct

Se respetuoso. Asumi buena fe del otro. Si algo no funciona, abrí un
issue — no hay espacio para drama en este repo.

## Tipos de contribucion

Hay cuatro tipos de contribucion, cada uno con distinto nivel de
esfuerzo y diseño previo:

| Tipo | Ejemplos | Esfuerzo | Diseno previo |
|---|---|---|---|
| **Fix de bug** | `validate_sql` no detecta SQL con solo comentarios | <1 dia | No |
| **Snippet nuevo en skill existente** | `qualify_clause()` para Databricks | <1 dia | Minimo |
| **Skill nueva** | `data-engineer` para ingesta APIs/S3 | 3-5 dias | **ADR** |
| **Agente nuevo** | Una sexta persona con un workflow nuevo | 3-5 dias | **ADR** |

**Bug fixes y snippets** no requieren propuesta previa — abrí un PR
directo con test que reproduce el bug o ejercita el snippet nuevo.

**Skills y agentes nuevos** tocan la arquitectura del toolkit —
requieren [ADR](#que-es-un-adr) primero.

## Setup local

```bash
git clone https://github.com/berriosb/data-analytics-agents.git
cd data-analytics-agents
make install-all   # registra agentes + skills en los 4 CLIs
make doctor        # chequea Node, Python y peer-deps
make test          # corre smoke + unit tests (debe pasar)
```

El repo esta pensado para editar en vivo — `make install-all` usa
symlinks asi que cualquier cambio en `agents/*.md` o
`skills/*/SKILL.md` se refleja al instante, sin re-instalar.

## Estructura del repo

```
data-analytics/
├── AGENTS.md                          # entry point — registro de personas + skills
├── agents/                            # prompts detallados de las 5 personas
│   ├── using-data-analytics-agents.md # triaje (no ejecuta trabajo)
│   ├── data-explorer.md               # perfil + limpieza
│   ├── sql-analyst.md                 # queries + joins
│   ├── reporting-analyst.md           # graficos + narrativa
│   └── ml-modeler.md                  # modelado supervisado
├── skills/                            # skills top-level (frontmatter: name + description)
│   ├── csv-profiler/SKILL.md          # cada skill es una carpeta con SKILL.md
│   ├── sql-write/
│   │   ├── SKILL.md
│   │   └── recetas/                   # modulos Python importables (opcional)
│   │       ├── validate.py
│   │       ├── execute.py
│   │       └── ...
│   └── ...
├── bin/install.js                     # instalador multi-CLI (Node ESM)
├── examples/                          # datos + scripts de demo por skill
├── tests/                             # unit tests (pytest)
├── scripts/doctor.py                  # preflight (make doctor)
├── docs/
│   ├── architecture.md                # mapa de las 5 personas + 20 skills
│   ├── adr/                           # Architecture Decision Records
│   ├── prd/                           # Product Requirements Documents
│   └── notes/                         # reviews tecnicas one-off
└── Makefile                           # entry point para tests + installs
```

## Como agregar un snippet nuevo a una skill existente

Tomemos el ejemplo de agregar `qualify_clause()` a `sql-cloud-warehouse`
(el mismo que se commiteo en v1.0.1, sirve de guia):

### 1. El snippet en `recetas/<modulo>.py`

```python
# skills/sql-cloud-warehouse/recetas/dialect_snippets.py

def qualify_clause(condition: str, warehouse_type: str) -> str:
    """Docstring explicando que hace, que retorna, y que dialectos soporta."""
    from .errors import UnsupportedQualifyError

    wh = dialect_for(warehouse_type)
    if wh in ("databricks", "snowflake"):
        return f"QUALIFY {condition}"
    raise UnsupportedQualifyError(wh)
```

**Reglas de los snippets:**

- **Sin `eval()` ni `df.query(<expr del usuario>)`** — siempre snippets
  parametrizados con valores explicitos.
- **Sin secretos en claro** — leen `os.environ` y nunca hardcodean
  credenciales.
- **Errores consistentes** — si tu snippet puede fallar, hereda de
  `errors.py` (clases existentes: `MissingDependencyError`,
  `MissingCredentialsError`, etc.) o agrega una nueva clase con
  mensaje accionable.
- **Funciones puras preferidas** — sin estado mutable global. Si el
  snippet necesita estado (ej. `audit-log`), usá un backend
  (JSONL/SQLite) que la skill carga explicitamente.

### 2. Export en `__init__.py`

```python
# skills/sql-cloud-warehouse/recetas/__init__.py
from .dialect_snippets import (
    date_trunc, safe_cast, conditional, current_timestamp,
    top_n, identifier_quote, qualify_clause,  # <-- nuevo
    dialect_for, DIALECTS,
)
from .errors import (
    MissingDependencyError, MissingCredentialsError,
    UnsupportedQualifyError,  # <-- nuevo si agregaste error class
)
```

### 3. Tests en `tests/`

```python
# tests/test_sql_cloud_warehouse_dialect.py

class TestQualifyClause:

    @pytest.mark.parametrize("warehouse", ["databricks", "snowflake"])
    def test_emits_qualify_for_native_dialects(self, warehouse: str) -> None:
        assert scw.qualify_clause("rn = 1", warehouse) == "QUALIFY rn = 1"

    @pytest.mark.parametrize("warehouse", ["bigquery", "redshift"])
    def test_raises_for_unsupported_dialects(self, warehouse: str) -> None:
        with pytest.raises(scw.UnsupportedQualifyError):
            scw.qualify_clause("rn = 1", warehouse)
```

**Reglas de los tests:**

- Cubri happy path + edge cases + errores.
- Si el snippet toma warehouse_type, parametriza los 4 dialectos.
- Si el snippet puede fallar con un error custom, testea que se levante
  el error correcto (no un `Exception` generico).

### 4. Doc en el SKILL.md de la skill

Agrega el snippet a la tabla "Recetas pre-aprobadas (importables)" del
SKILL.md, con el nombre y una linea de descripcion. Si el snippet
cambia el comportamiento dialecto-aware, actualiza la tabla
"Diferencias de sintaxis clave".

### 5. Verificar

```bash
make test-unit                           # tu test nuevo debe pasar
make doctor                              # nada debe romperse
make list                                # symlinks siguen OK
```

## Como agregar una skill nueva

Esto es mas serio — una skill nueva toca el frontmatter (que los 4
CLIs auto-descubren) y posiblemente requiere actualizar
`AGENTS.md` + la seccion de "Arquitectura" si la carga algun agente.

### Flujo de diseno (ADR + PRD)

1. **Abre un issue** describiendo la skill nueva. Por que la necesitamos,
   que problema resuelve, en que flujo entra.
2. **Escribi un PRD** en `docs/prd/<skill>.md` usando el template de
   PRD existente (ver `docs/prd/sql-write.md` o `docs/prd/api-builder.md`
   como ejemplo). Status inicial: `Draft`.
3. **Si la skill cambia la arquitectura del toolkit** (toca mas de una
   skill existente o agrega un agente), escribi un ADR en
   `docs/adr/00X-<titulo>.md` explicando la decision y referenciando
   el PRD. Status inicial: `Draft`.
4. **Esperá review** — el owner del repo revisa el PRD/ADR antes de
   mergear el codigo. Esto evita trabajo rehecho.
5. **Una vez aprobado el PRD**, implementá siguiendo el patron de las
   skills existentes (ver `docs/architecture.md` para el mapa).
6. **Status del PRD → Accepted** con fecha, en el mismo PR que cierra
   la skill.

### Template minimo de una skill

```
skills/<skill-name>/
├── SKILL.md               # frontmatter (name + description) + 6 secciones
├── recetas/               # modulos Python importables (si la skill los tiene)
│   ├── __init__.py
│   ├── <modulo>.py
│   └── ...
├── templates/             # templates Jinja o archivos base (opcional)
└── README.md              # opcional, solo si la skill tiene muchos templates
```

### Frontmatter obligatorio

```yaml
---
name: <skill-name>
description: <1-2 oraciones que dicen que hace la skill y cuando se carga>.
  Las palabras trigger van al final de la description para que los 4
  CLIs auto-descubran la skill.
---
```

**El description es el contrato con el CLI.** Incluye:

- Que hace la skill (verbo + objeto).
- Cuando se carga (trigger phrases).
- Que **no** hace (negative triggers — ej. "no usar para SQL local").

Si el description es vago, el CLI no la va a cargar nunca.

### Template del SKILL.md

6 secciones, en este orden:

1. **Descripcion general** — que hace la skill en 1 parrafo.
2. **Cuando usar** — bullets con trigger phrases + "no usar cuando..."
3. **Flujo de trabajo** — pasos numerados, con snippets de codigo.
4. **Justificaciones comunes** — "X es seguro porque..." (anti-racionalizacion).
5. **Senales de alerta** — errores accionables que el agente debe reconocer.
6. **Verificacion** — criterios de "listo" + como testear.

Ver `skills/sql-write/SKILL.md` o `skills/audit-log/SKILL.md` como
referencia completa.

## Como agregar un agente nuevo

Esto requiere un ADR + coordinacion con `skills/using-data-analytics-agents/SKILL.md`
(la tabla de enrutamiento).

1. Mismo flujo que skill nueva: issue + PRD + ADR.
2. Crea `agents/<persona>.md` siguiendo el template de los 5 existentes:
   - **Perspectiva** (1 parrafo + lista de opiniones)
   - **Cuando invocar** (triggers + negativos)
   - **Flujo de trabajo** (pasos numerados, que skills carga en orden)
   - **Senales de alerta** (cuando bloquear / escalar)
   - **Evidencia requerida** (que tiene que entregar al final)
   - **Regla de decision** (continuar / bloquear / escalar)
3. Actualiza `skills/using-data-analytics-agents/SKILL.md` — la tabla
   de enrutamiento agrega una fila para el agente nuevo con sus trigger
   phrases y skills que carga.
4. Actualiza `AGENTS.md` — el "Inicio rapido" + la seccion "Personas
   disponibles" + la tabla de skills que carga cada agente.
5. Actualiza `docs/architecture.md` — el diagrama de triaje + el
   grafo de skill reference.

## Convenciones

(Resumen; el detalle vive en `AGENTS.md` seccion "Convenciones".)

- **Markdown con tildes y enes** (español rioplatense). Identificadores
  en markdown en lowercase + guiones (`csv-profiler`, no `CSVProfiler`).
- **Personas** (`agents/*.md`): sin frontmatter, markdown plano.
- **Skills** (`skills/*/SKILL.md`): solo `name` + `description` en
  frontmatter YAML. Trigger phrases en la description.
- **6 secciones** en cada SKILL.md (ver template arriba).
- **Snippets pre-aprobados** — sin `eval()`, sin secrets hardcodeados,
  errores consistentes.
- **Visualizaciones** — sin ejes truncados, sin ejes duales, sin 3D.
- **Instalador** (`bin/install.js`) siempre usa symlinks.

## Tests

- **Unit tests**: `tests/test_<skill>_<modulo>.py`, descubiertos por
  pytest. Cubren snippets en `skills/<name>/recetas/`.
- **Smoke tests**: por skill, ejecutables via `make test-<skill>`
  (ej. `make test-csv`, `make test-sql-write`). Cubren examples
  end-to-end en `examples/<skill>_sample/`.

```bash
make test                # todos los tests
make test-unit           # solo unit tests
make test-<skill>        # smoke test de una skill especifica
make doctor              # preflight de versiones y peer-deps
```

Si agregas una skill nueva, agrega tambien su `make test-<skill>`
target en el Makefile + su `examples/<skill>_sample/` con datos
de muestra + scripts de demo.

## Pull requests

- Un PR = un cambio logico. Si estas agregando 3 skills, hace 3 PRs.
- Title: `feat: <descripcion corta>` o `fix: <descripcion corta>` o
  `docs: <descripcion corta>`. Match el estilo de los commits
  existentes en `git log --oneline`.
- Body: que cambia + por que + como testearlo. Si cierra un issue,
  usar `Closes #N`.
- Antes de pedir review, asegurate que:
  - `make test` pasa localmente
  - `make doctor` no reporta FAIL nuevos
  - El CHANGELOG.md esta actualizado si el cambio es user-facing
  - Si agregaste skill/agente, el PRD (y ADR si aplica) esta en `docs/`

## Donde pedir ayuda

- **Issues** en GitHub para bugs, propuestas, preguntas.
- **Discusiones de diseno** via los PRDs/ADRs en `docs/prd/` y `docs/adr/`.
- **Code review** via comentarios en el PR.

Bienvenido a bordo.
