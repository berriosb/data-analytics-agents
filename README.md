# data-analytics-agents

[![npm version](https://img.shields.io/npm/v/data-analytics-agents.svg)](https://www.npmjs.com/package/data-analytics-agents)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-berriosb%2Fdata--analytics--agents-blue)](https://github.com/berriosb/data-analytics-agents)

Un toolkit multi-CLI de agentes y skills para trabajo de **data analytics** —
impulsado por un único `AGENTS.md` en la raíz del proyecto, con un
`bin/install.js` de un comando para registrar agentes project-local.

OpenCode, Claude Code, Codex y Antigravity CLI (`agy`) auto-descubren todos
`AGENTS.md` cuando se lanzan desde el directorio del proyecto y levantan
las cinco personas (`data-explorer`, `sql-analyst`, `reporting-analyst`,
`ml-modeler`, `using-data-analytics-agents`) más veinte skills
(`csv-profiler`, `pandas-cleaning`, `sql-query-helper`, `schema-mapper`,
`query-validation`, `viz-patterns`, `statistical-testing`,
`time-series-patterns`, `feature-engineering`, `ml-modeling`,
`model-evaluation`, `insight-synthesis`, `using-data-analytics-agents`,
`excel-profiler`, `excel-formulas`, `report-export`, `sql-cloud-warehouse`,
`sql-write`, `audit-log`, `api-builder`).

```
data-analytics/
├── AGENTS.md                   # ⭐ fuente única de verdad — leído por cada CLI desde cwd
├── agents/                     # prompts detallados de las personas (referenciados desde AGENTS.md)
│   ├── using-data-analytics-agents.md
│   ├── data-explorer.md
│   ├── sql-analyst.md
│   ├── reporting-analyst.md
│   └── ml-modeler.md
├── skills/                     # formato SKILL.md (frontmatter: name + description)
│   ├── using-data-analytics-agents/SKILL.md
│   ├── csv-profiler/SKILL.md
│   ├── excel-profiler/SKILL.md
│   ├── excel-formulas/SKILL.md
│   ├── pandas-cleaning/SKILL.md
│   ├── schema-mapper/SKILL.md
│   ├── sql-query-helper/SKILL.md
│   ├── query-validation/SKILL.md
│   ├── sql-cloud-warehouse/SKILL.md
│   ├── sql-write/SKILL.md
│   ├── audit-log/SKILL.md
│   ├── viz-patterns/SKILL.md
│   ├── statistical-testing/SKILL.md
│   ├── time-series-patterns/SKILL.md
│   ├── feature-engineering/SKILL.md
│   ├── ml-modeling/SKILL.md
│   ├── model-evaluation/SKILL.md
│   ├── insight-synthesis/SKILL.md
│   ├── report-export/SKILL.md
│   └── api-builder/SKILL.md
├── bin/install.js              # ⭐ instalador multi-CLI (Node ESM, 0 deps, dynamic discovery)
├── package.json                # expone el bin `data-analytics-agents`
├── requirements-dev.txt        # dependencias Python para correr tests
├── adapters/antigravity/       # manifest del plugin de Agy (usado por install.js)
├── examples/                   # muestras y smoke tests ejecutables
├── scripts/install.sh          # instalador user-level legacy (solo skills + Agy)
├── Makefile                    # wrapper fino alrededor de bin/install.js y tests
└── README.md                   # este archivo
```

## Documentación adicional

- [`docs/architecture.md`](docs/architecture.md) — mapa mental de las
  5 personas + 20 skills: triaje, handoffs entre agentes, y grafo
  de qué skill carga cada agente. **Leer primero** si vas a
  contribuir.
- [`docs/adr/`](docs/) — Architecture Decision Records (2 ADRs
  cubren v0.3.0–v0.9.0; el release v1.0.0 los cierra).
- [`docs/prd/`](docs/) — Product Requirements Documents de las 7
  skills complejas (api-builder, audit-log, excel-formulas,
  excel-profiler, report-export, sql-cloud-warehouse, sql-write).
- [`CHANGELOG.md`](CHANGELOG.md) — qué cambió en cada versión y los
  criterios para v1.0.

## Inicio rápido

### Vía npm (recomendada — agents + skills)

```bash
# 1. Desde el directorio del proyecto de data analytics destino,
#    instalá el toolkit como dev dependency:
npm install --save-dev data-analytics-agents

# 2. Corré el instalador (registra agents + skills en los 4 CLIs):
npx data-analytics-agents install --all
```

**Por qué este patrón y no `npx ... install --all` directo**: el primer
`npm install` deja el toolkit en `node_modules/data-analytics-agents/`
(persistente). El segundo paso crea los symlinks hacia ahí, así que no se
rompen cuando npm limpia el cache de `npx`.

### Vía skills.sh (solo skills, sin agents)

```bash
npx skills add berriosb/data-analytics-agents
```

Compatible con el formato estándar `skills/<name>/SKILL.md` de skills.sh.
Solo instala las skills (no las personas).

### Vía GitHub clone (instalación manual)

```bash
git clone https://github.com/berriosb/data-analytics-agents.git
cd data-analytics-agents
make install-all
```

---

Una vez instalado en tu proyecto, podés invocar las personas con `--agent`:

```bash
# OpenCode
opencode -m minimax-coding-plan/MiniMax-M3 --agent data-explorer "Perfilá examples/ventas_sample.csv y pará."

# Codex
codex -m gpt-5.5 --agent sql-analyst exec "Top 5 de clientes por revenue."

# Claude Code
claude -m opus --agent reporting-analyst "Tendencia mensual de revenue."

# Antigravity
agy -m gemini-3.6-flash --agent data-explorer "Perfilá examples/ventas_sample.csv."
```

`npx data-analytics-agents install --all` (o `make install-all`) es
**idempotente** (usa symlinks); correrlo de nuevo es un no-op. Después de
que corrió, las ediciones a `agents/<name>.md` y `skills/<name>/SKILL.md`
se toman en el acto por cada CLI — sin re-instalar.

### Verificar el estado

```bash
# Desde el proyecto destino:
npx data-analytics-agents list   # muestra los symlinks activos
opencode agent list             # debe incluir data-explorer, sql-analyst, …
```

## Por qué hace falta un instalador

Cada CLI soportado auto-carga `AGENTS.md` a nivel de proyecto (o `CLAUDE.md`
/ `GEMINI.md`) en el system prompt. Con las personas listadas en la raíz
del proyecto, podés escribir `act as <persona>` y el agente se auto-organiza
alrededor de ese rol.

Pero para usar el flag nativo `--agent <name>` de cada CLI (p. ej.
`opencode --agent data-explorer`), los archivos de las personas también
tienen que estar registrados en la ubicación esperada por cada CLI.
`bin/install.js` los symlinkea ahí:

| CLI | Ruta de instalación project-local | Notas |
|---|---|---|
| **OpenCode** | `.opencode/agents/<name>.md` + `.opencode/skills/<name>` | Hace que `opencode agent list` muestre las 4 personas |
| **Claude Code** | `.claude/agents/<name>.md` + `.claude/skills/<name>` | Hace que `claude --agent <name>` funcione |
| **Codex** | `.agents/skills/<name>` (sin agentes project-local — usa `AGENTS.md`) | Solo skills |
| **Antigravity CLI** | `~/.gemini/antigravity-cli/plugins/data-analytics-agents/` (siempre global) | Hace que `agy --agent <name>` funcione |

Las skills se referencian por nombre y residen en `~/.agents/skills/` una
vez que corrés `make install-skills` (instalación user-level; algunos CLIs
también leen de `.agents/skills/` por proyecto).

## Invocar personas (después de `make install-all`)

```bash
cd ~/Proyectos/data-analytics

# OpenCode (cualquier modelo)
opencode -m minimax-coding-plan/MiniMax-M3 --agent data-explorer "Perfilá examples/ventas_sample.csv y pará."

# Codex (cualquier modelo)
codex -m gpt-5.5 --agent sql-analyst exec "Top 5 de clientes por revenue desde examples/notes_example.sqlite."

# Claude Code (cualquier modelo)
claude -m opus --agent reporting-analyst "Tendencia mensual de revenue, salida a ./reports/."

# Antigravity (Agy)
agy -m gemini-3.6-flash --agent data-explorer "Perfilá examples/ventas_sample.csv."
```

Si no querés correr el instalador, el estilo "act as" funciona en todos los
CLIs porque `AGENTS.md` se auto-carga como contexto:

```bash
opencode -m minimax-coding-plan/MiniMax-M3 "act as data-explorer. Perfilá examples/ventas_sample.csv y pará."
```

El prompt completo de la persona vive en `agents/<name>.md`. Si el soporte
de tools de un CLI es suficientemente bueno, va a leer ese archivo cuando
digas `act as data-explorer` y las instrucciones detalladas entran en
contexto.

## Cómo usarlo en tus proyectos de data analytics

Una vez publicado a npm, este toolkit se usa así en cualquier proyecto de
análisis de datos. Ejemplo end-to-end con un proyecto nuevo:

```bash
# 1. Creá tu proyecto de data analytics (cualquier directorio)
mkdir ~/Proyectos/mi-ventas-q4
cd ~/Proyectos/mi-ventas-q4
git init -q -b main
echo "data/" > .gitignore

# 2. Sumá el toolkit como dev dependency
npm init -y >/dev/null
npm install --save-dev data-analytics-agents

# 3. Registrá las 5 personas y las 20 skills en los CLIs que uses
npx data-analytics-agents install --all
# → crea .opencode/, .claude/, .agents/ con symlinks al toolkit

# 4. (Opcional) agregá tu AGENTS.md para darle contexto a tu proyecto
cat > AGENTS.md <<'EOF'
# Mi proyecto de ventas Q4

Datos en ./data/ventas_2024.csv. Perfil: una fila por transacción.
Usar data-explorer para perfilado inicial, sql-analyst para queries
si hay una DB, reporting-analyst para reportes ejecutivos.
EOF

# 5. Invocá una persona desde cualquier CLI
opencode -m minimax-coding-plan/MiniMax-M3 --agent data-explorer "Perfilá ./data/ventas_2024.csv y dame el top 5 de productos por revenue."
codex -m gpt-5.5 --agent reporting-analyst exec "Tendencia mensual de revenue Q4 2024, salida a ./reports/."
```

**El paso 3 es clave**: corre el installer una sola vez por proyecto. Después
de eso, los symlinks en `.opencode/`, `.claude/`, `.agents/` apuntan a
`./node_modules/data-analytics-agents/` y se mantienen vivos aunque npm
limpie caches o reinstales.

Si más adelante agregás una skill o una persona al toolkit (subís una nueva
versión a npm):

```bash
cd ~/Proyectos/mi-ventas-q4
npm update data-analytics-agents
npx data-analytics-agents install --all   # idempotente, no-op si nada cambió
```

Los symlinks siguen apuntando al mismo lugar, las ediciones se reflejan al
instante, no hace falta re-correr nada.

## Instalación opcional por CLI

```bash
# Solo arreglar OpenCode (el caso más común — sin esto, `opencode agent list`
# solo muestra los 7 agentes default)
make install-opencode

# Solo Claude Code
make install-claude

# Solo Codex (solo skills)
make install-codex

# Solo Agy (plugin)
make install-agy

# Auto-detectar qué CLIs están instalados e instalar para esos
make install-auto
```

Todos estos mapean a `node ./bin/install.js install --<cli>`. Ver
`node ./bin/install.js help` para la lista completa de flags.

## Matriz de soporte multi-CLI

| CLI | Lee `AGENTS.md` desde cwd | Lee `~/.agents/skills/` | Tiene flag `--agent` | ¿Necesita `make install-<cli>`? |
|---|---|---|---|---|
| **OpenCode** | ✅ | ✅ | ✅ (en `.opencode/agents/`) | ✅ para `--agent` |
| **Claude Code** | ✅ | ✅ | ✅ (en `.claude/agents/`) | ✅ para `--agent` |
| **Codex** | ✅ | ✅ | ❌ (usar `act as <name>` en el prompt) | ✅ para skills |
| **Antigravity CLI (`agy`)** | ✅ (también `GEMINI.md`) | ✅ (vía plugin después de `make install-agy`) | ✅ (después de `make install-agy`) | ✅ para `--agent` |

**TL;DR**: Corré `make install-all` una vez por proyecto, después usá
cualquiera de los flags `--agent <name>`. Editá `agents/*.md` o
`skills/*/SKILL.md` y los cambios toman efecto al instante.

## Tests

```bash
make list                    # muestra qué está instalado y dónde
make skills                  # lista de skills disponibles a nivel usuario
make test                    # corre TODOS los smoke + unit tests offline disponibles
make test-unit               # solo los unit tests (pytest tests/, ~155 tests sobre snippets de skills)

# Tests individuales por componente (smoke):
make test-csv                # csv-profiler sobre CSV de muestra
make test-sql                # consulta básica SQLite de muestra
make test-stats              # statistical-testing sobre datos sintéticos
make test-ts                 # time-series-patterns sobre datos sintéticos
make test-ml                 # pipeline ML supervisado (clasif + regresión)
make test-excel              # excel-profiler (hojas, headers, celdas combinadas)
make test-excel-formulas     # excel-formulas (extracción y clasificación AST)
make test-export-html        # report-export (HTML standalone con base64 inline)
make test-sql-cloud-offline  # sql-cloud-warehouse (snippets dialecto-aware y validaciones)
make test-api-builder        # api-builder (generación FastAPI + validación pytest)
make test-sql-write          # sql-write (guardrails contra queries destructivas)
make test-audit-log          # audit-log (trazabilidad y redacción de PII)
```

Los **smoke tests** validan que los examples en `examples/` corren
end-to-end. Los **unit tests** (`make test-unit`, en `tests/`) ejercitan
los snippets pre-aprobados de las skills con módulo `recetas/`
(api-builder, audit-log, excel-formulas, report-export, sql-cloud-warehouse,
sql-write) — happy path + edge cases + guardrails de seguridad (PII
redaction, SQL blockers, dialecto-aware SQL).

## Limpieza

```bash
make uninstall-all       # elimina todos los symlinks project-local
make cleanup-legacy      # elimina los symlinks VIEJOS por CLI de revisiones anteriores
```

## Convenciones

- **Personas** (`agents/*.md`) sin frontmatter, markdown plano.
- **Skills** (`skills/<name>/SKILL.md`) llevan solo `name` + `description` en
  frontmatter YAML, con palabras trigger en la descripción.
- **Skills siguen un template de 6 secciones**: Descripción general / Cuándo
  usar / Flujo de trabajo / Justificaciones comunes / Señales de alerta /
  Verificación.
- **Limpieza nunca usa `eval()` ni `df.query(<expr del usuario>)`** abierto;
  solo snippets pre-aprobados.
- **Los gráficos nunca usan ejes truncados, ejes duales ni 3D**.
- **El instalador** (`bin/install.js`) siempre usa symlinks — nunca copia —
  así que `agents/*.md` y `skills/*/` se mantienen como fuente única de
  verdad.

## De dónde vienen los patrones

- El esquema de skill, el template de 6 secciones y el patrón de
  anti-racionalización están inspirados en
  [`vaquarkhan/data-engineering-agent-skills`](https://github.com/vaquarkhan/data-engineering-agent-skills).
- El workflow perfil → limpieza → gráfico y los defaults de Plotly están
  inspirados en
  [`jenyss/DataAnalyticsAIAgent`](https://github.com/jenyss/DataAnalyticsAIAgent),
  con los caveats de seguridad corregidos (sin `eval`, soporte multi-formato).
- El patrón de **instalador multi-CLI estilo `npx`** está inspirado en
  [`vercel-labs/skills`](https://github.com/vercel-labs/skills) (el CLI de
  `skills.sh`), adaptado para agentes (que `skills.sh` no maneja) y para la
  superficie objetivo de los 4 CLIs usada acá.

## Estado del v2

Extensión de Data Science **implementada**: el agente `ml-modeler` + 3
skills (`feature-engineering`, `ml-modeling`, `model-evaluation`)
permiten modelado supervisado completo (clasificación + regresión) sobre
features + target limpios, con disciplina de train/test split, baseline
previo, cross-validation, y evaluación completa (métricas + matriz de
confusión / residuos + ROC/PR + feature importance + learning curves).

**Dependencias del usuario** (no son deps de npm — el toolkit es Node; el
agente las trae del entorno Python del usuario):

- `pandas`, `numpy` — ya necesarias para `pandas-cleaning`,
  `time-series-patterns`.
- `scipy` — para `statistical-testing`.
- `scikit-learn` — para el pipeline ML completo.
- `statsmodels` — opcional, solo para los snippets Tier 2 de
  `time-series-patterns` (decompose, ADF, ACF/PACF).

## Extensiones v0.3.0 - v0.8.0 (ADR-001 y ADR-002)

Además del ciclo clásico de EDA y modelado supervisado, el toolkit incorpora capacidades de entrega de extremo a extremo:

- **ADR-001 (v0.2.0 – v0.4.0: Entrega Ejecutiva y Cloud)**:
  - `excel-profiler`: perfilado robusto de hojas Excel corporativas complejas (detección de hoja con datos reales, headers desplazados y celdas combinadas).
  - `report-export`: exportación ejecutiva a PDF (WeasyPrint), presentaciones PPTX (python-pptx) y HTML autónomo interactivo (base64 inline).
  - `sql-cloud-warehouse`: conexión e introspección a Snowflake, BigQuery, Redshift y Databricks (Spark SQL) con snippets dialecto-aware (`DATE_TRUNC`, `SAFE_CAST`/`TRY_CAST`, condicionales).

- **ADR-002 (v0.5.0 – v0.8.0: Análisis a Servicio con Guardrails)**:
  - `api-builder`: conversión de funciones Python de análisis/scoring en servicios REST vivos con FastAPI, validación Pydantic, Dockerfile y tests pytest.
  - `excel-formulas`: auditoría y parsing de fórmulas Excel a AST textual con categorización funcional y detección de volatilidad.
  - `sql-write`: guardrails de escritura SQL en modo conservador (`CREATE TABLE IF NOT EXISTS`, `INSERT`; dry-run obligatorio y bloqueo estricto de sentencias destructivas `DROP`/`UPDATE`/`DELETE`).
  - `audit-log`: trazabilidad transversal append-only con redacción automática de datos sensibles (PII: emails, teléfonos, RUTs).

**Fuera de alcance actual** (extensiones futuras):
- Búsqueda exhaustiva de hiperparámetros automatizada (`AutoML`).
- Modelos no supervisados (clustering, PCA).
- Deep learning (Keras, PyTorch).

## Qué cambió en esta revisión (vs el diseño anterior con `make install`)

Las revisiones anteriores symlinkeaban cada persona al directorio de
configuración privado de cada CLI (`~/.config/opencode/agent/`,
`~/.claude/agents/`, plugins de Agy). Eso hacía la instalación obligatoria
y las ediciones requerían un `make refresh`.

El diseño actual se deshace de eso:
- Las personas están listadas en `AGENTS.md` en la raíz del proyecto.
- Los cuatro CLIs lo auto-descubren desde cwd.
- Un único `bin/install.js` registra las personas como agentes reales en la
  ubicación esperada por cada CLI (sigue con symlinks, sigue editable en vivo).
- La instalación user-level ahora es opcional (`make install-skills` para
  `~/.agents/skills/`).

Si instalaste una revisión anterior, corré `make cleanup-legacy` para
eliminar los symlinks viejos por CLI. La nueva arquitectura no depende de
ellos.