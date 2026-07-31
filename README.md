# data-analytics-agents

Un toolkit multi-CLI de agentes y skills para trabajo de **data analytics** —
impulsado por un único `AGENTS.md` en la raíz del proyecto, con un
`bin/install.js` de un comando para registrar agentes project-local.

OpenCode, Claude Code, Codex y Antigravity CLI (`agy`) auto-descubren todos
`AGENTS.md` cuando se lanzan desde el directorio del proyecto y levantan las
cuatro personas (`data-explorer`, `sql-analyst`, `reporting-analyst`,
`using-data-analytics-agents`) más ocho skills (`csv-profiler`,
`pandas-cleaning`, `sql-query-helper`, `schema-mapper`, `query-validation`,
`viz-patterns`, `insight-synthesis`, `using-data-analytics-agents`).

```
data-analytics/
├── AGENTS.md                   # ⭐ fuente única de verdad — leído por cada CLI desde cwd
├── agents/                     # prompts detallados de las personas (referenciados desde AGENTS.md)
│   ├── using-data-analytics-agents.md
│   ├── data-explorer.md
│   ├── sql-analyst.md
│   └── reporting-analyst.md
├── skills/                     # formato SKILL.md (frontmatter: name + description)
│   ├── using-data-analytics-agents/SKILL.md
│   ├── csv-profiler/SKILL.md
│   ├── pandas-cleaning/SKILL.md
│   ├── sql-query-helper/SKILL.md
│   ├── schema-mapper/SKILL.md
│   ├── query-validation/SKILL.md
│   ├── viz-patterns/SKILL.md
│   └── insight-synthesis/SKILL.md
├── bin/install.js              # ⭐ instalador multi-CLI (Node ESM, 0 deps)
├── package.json                # expone el bin `data-analytics-agents`
├── adapters/antigravity/       # manifest del plugin de Agy (usado por install.js)
├── examples/                   # CSV y SQLite de muestra para smoke-testing
├── scripts/install.sh          # instalador user-level legacy (solo skills + Agy)
├── Makefile                    # wrapper fino alrededor de bin/install.js
└── README.md                   # este archivo
```

## Inicio rápido

```bash
cd ~/Proyectos/data-analytics

# Instalación project-local — registra las 4 personas como agentes reales
# en OpenCode, Claude Code, Codex, y como plugin de Agy (global).
make install-all          # alias: npm run install -- --all

# Verificar
opencode agent list       # debería incluir data-explorer, sql-analyst, …

# Smoke test
opencode -m minimax-coding-plan/MiniMax-M3 --agent data-explorer "decí hola"
```

`make install-all` es **idempotente** (usa symlinks); correrlo de nuevo es un
no-op. Después de que corrió, las ediciones a `agents/<name>.md` y
`skills/<name>/SKILL.md` se toman en el acto por cada CLI — sin re-instalar.

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

## Smoke tests

```bash
make list          # muestra qué está instalado y dónde
make skills        # lista de skills disponibles a nivel usuario
make test-csv      # corre los snippets de csv-profiler sobre el CSV de muestra
make test-sql      # conecta a la SQLite de muestra
```

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

## v2 (no implementado aún)

Extensión de Data Science: 1 agente nuevo (`ml-modeler`) + 3-4 skills nuevas
(`statistical-testing`, `ml-modeling`, `feature-engineering`, `model-evaluation`).
La skill de triaje los va a enrutar. Agregar una entrada en `AGENTS.md` y un
archivo nuevo en `agents/`/`skills/`. La infra queda igual.

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