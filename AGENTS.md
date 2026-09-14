# Data Analytics Agents

El punto de entrada unificado para OpenCode, Claude Code, Codex y Antigravity
CLI (Agy). Este archivo se auto-descubre en la raíz del proyecto, así que
cualquier CLI que se lance desde este directorio toma las personas de abajo
como contexto.

> **Inicio rápido** — para registrar las 4 personas como agentes reales en
> OpenCode (y como agentes/skills project-local en Claude Code, Codex y Agy),
> corré estos dos pasos desde el directorio del proyecto de data analytics
> destino:
>
> ```bash
> # 1. Instalá el toolkit como dev dependency (deja el paquete en node_modules/):
> npm install --save-dev data-analytics-agents
>
> # 2. Corré el instalador (registra agents + skills en los 4 CLIs):
> npx data-analytics-agents install --all
> ```
>
> Alternativas:
>
> ```bash
> # Vía skills.sh (solo skills, sin agents):
> npx skills add berriosb/data-analytics-agents
>
> # Vía clone directo (alternativa sin npm):
> git clone https://github.com/berriosb/data-analytics-agents.git
> cd data-analytics-agents && make install-all
> ```
>
> **Por qué dos pasos en el flujo npm**: `npm install` deja el toolkit en
> `node_modules/data-analytics-agents/` (persistente). El instalador crea
> los symlinks hacia ahí, así no se rompen cuando npm limpia el cache de
> `npx`. Un solo comando, idempotente, usa symlinks así que `agents/*.md` y
> `skills/*/` siguen siendo la única fuente de verdad. Destinos:
>
> | CLI | Qué se instala |
> |---|---|
> | OpenCode | `.opencode/agents/<name>.md` + `.opencode/skills/<name>` |
> | Claude Code | `.claude/agents/<name>.md` + `.claude/skills/<name>` |
> | Codex | `.agents/skills/<name>` (Codex lee los agentes desde AGENTS.md) |
> | Antigravity | plugin staged en `~/.gemini/antigravity-cli/plugins/` |

## Por qué este archivo solo no alcanza

`AGENTS.md` se carga como **contexto** por cada CLI desde el cwd — así que el
patrón "act as `<persona>`" funciona en todos lados. Pero OpenCode, Claude
Code y Codex también mantienen un registro separado de **agentes** que se
pueden invocar con `--agent <name>`. Esos registros buscan archivos en rutas
específicas por CLI (`.opencode/agents/`, `.claude/agents/`, etc.), y no
leen `AGENTS.md`.

`bin/install.js` cierra esa brecha haciendo symlinks de `agents/*.md` y
`skills/*/` a la ubicación esperada por cada CLI. Sin él:

- OpenCode: solo los 7 agentes default están registrados; las 4 personas
  son invisibles para `opencode agent list` y `--agent <name>`.
- Claude Code: los agentes se cargan desde `AGENTS.md` pero solo como
  contexto; el `.claude/agents/` project-local queda vacío.
- Codex: igual que Claude — los agentes vienen solo de `AGENTS.md`.

> La arquitectura anterior basada en instalación (symlinks a
> `~/.config/opencode/agent/`, `~/.claude/agents/`, etc.) fue abandonada en
> favor de este diseño más simple: **un `AGENTS.md` por proyecto, un
> `bin/install.js` para registrar agentes project-local, un
> `~/.agents/skills/` por usuario para skills globales**.

## Arquitectura (por qué las skills viven arriba, no dentro de los agentes)

Las skills son **top-level** (`skills/<name>/SKILL.md`) y **referenciadas**
por los agentes por nombre, no anidadas dentro de cada agente. Cada agente
declara qué skills carga en el paso 1 de su `Flujo de trabajo`:

| Agente | Skills que carga (en orden) |
|---|---|
| `using-data-analytics-agents` | (ninguna — triaje puro, sin carga de skills) |
| `data-explorer` | `csv-profiler` → `pandas-cleaning` → `statistical-testing` / `time-series-patterns` |
| `sql-analyst` | `schema-mapper` → `sql-query-helper` → `query-validation` |
| `reporting-analyst` | `viz-patterns` → `statistical-testing` / `time-series-patterns` → `insight-synthesis` |
| `ml-modeler` | `feature-engineering` → `ml-modeling` → `model-evaluation` → `insight-synthesis` |

Esto es intencional, no un descuido:

- **Reusabilidad**: `csv-profiler` podría ser cargada legítimamente por un
  futuro agente sin arrastrar `pandas-cleaning`. Skills top-level evitan el
  acoplamiento accidental.
- **Fuente única de verdad**: editar `skills/csv-profiler/SKILL.md`
  actualiza el archivo usado por todos los agentes y cualquier script
  futuro (`make test-csv`) sin recorrer carpetas de agentes.
- **Un archivo = un trabajo**: el archivo de un agente se queda enfocado en
  persona y workflow; el de una skill se queda enfocado en las recetas.
  Mezclarlos tiende a hinchar ambos.

Si necesitás notas privadas por agente (p. ej. un `data-explorer.notes.md`
que no sea parte del registro público de skills), ponelas al lado del
archivo del agente — no contamines el namespace compartido de `skills/`.

## Personas disponibles

Invocá cualquier persona con `act as <name>` (funciona en los cuatro CLIs).
Los prompts detallados viven en `agents/<name>.md` — la mayoría de los CLIs
leen el archivo relevante cuando les pedís actuar como esa persona.

| Persona | Alcance (una línea) | Prompt detallado |
|---|---|---|
| `using-data-analytics-agents` | Triaje / enrutamiento | `agents/using-data-analytics-agents.md` |
| `data-explorer` | Perfilado + limpieza de CSV / Parquet / Excel | `agents/data-explorer.md` |
| `sql-analyst` | Inspección de esquema + consultas SQL (sqlite / postgres / mysql / duckdb) | `agents/sql-analyst.md` |
| `reporting-analyst` | Gráficos Plotly + reporte escrito | `agents/reporting-analyst.md` |
| `ml-modeler` | Modelado supervisado (clasificación + regresión, scikit-learn) | `agents/ml-modeler.md` |

### Cuándo usar cuál

- **Pedido nuevo, ambiguo**: arrancar con `using-data-analytics-agents`
  para enrutamiento.
- **Hay un CSV / Parquet / Excel** sin DB: `data-explorer`.
- **Hay una SQLite / SQL DB / archivo SQL**: `sql-analyst`.
- **Ya hay números agregados o un dataframe limpio**: `reporting-analyst`.
- **Hay features + target definido, quiere predecir**: `ml-modeler`.

## Skills

Cada skill vive en `skills/<name>/SKILL.md` con frontmatter `name` +
`description`. Una vez que la skill está symlinkeada a
`~/.agents/skills/<name>/` (setup único, ver "Instalación opcional" abajo),
los cuatro CLIs la auto-descubren y la cargan a demanda según las palabras
trigger de la `description`.

| Skill | Cuándo el agente debería cargarla | Contenido detallado |
|---|---|---|
| `using-data-analytics-agents` | Decisión de clasificación / enrutamiento | `skills/using-data-analytics-agents/SKILL.md` |
| `csv-profiler` | Primer encuentro con un archivo tabular | `skills/csv-profiler/SKILL.md` |
| `pandas-cleaning` | Pasos de limpieza tras aprobación del perfil | `skills/pandas-cleaning/SKILL.md` |
| `schema-mapper` | Primer encuentro con una base de datos desconocida | `skills/schema-mapper/SKILL.md` |
| `sql-query-helper` | Idiomas SQL según motor | `skills/sql-query-helper/SKILL.md` |
| `query-validation` | Revisión de una consulta antes de uso en producción | `skills/query-validation/SKILL.md` |
| `viz-patterns` | Selección de tipo de gráfico + recetas Plotly | `skills/viz-patterns/SKILL.md` |
| `statistical-testing` | Tests estadísticos de EDA (t-test, ANOVA, chi², correlaciones) sobre datos limpios | `skills/statistical-testing/SKILL.md` |
| `time-series-patterns` | Análisis de series temporales (resampling, rolling, lags, descomposición, ADF, forecast naive) | `skills/time-series-patterns/SKILL.md` |
| `feature-engineering` | Encoding, escalado, splits, polinomios, balanceo (preprocesamiento para ML) | `skills/feature-engineering/SKILL.md` |
| `ml-modeling` | Entrenar modelos supervisados sklearn (linear, logistic, tree, RF, GBM, CV) | `skills/ml-modeling/SKILL.md` |
| `model-evaluation` | Métricas de clasificación/regresión, ROC/PR, matriz de confusión, feature importance, learning curves | `skills/model-evaluation/SKILL.md` |
| `insight-synthesis` | Convertir hallazgos → insights priorizados (Y Qué / Por Qué / Ahora Qué) | `skills/insight-synthesis/SKILL.md` |

`schema-mapper` se carga **antes** de `sql-query-helper` (que provee idiomas
para *escribir* consultas); `schema-mapper` cubre el paso de *descubrimiento*
que produce el diccionario de datos y los join paths sobre los que se apoya
el escritor. `query-validation` se carga **después** de `sql-query-helper`
para cubrir el pase de *revisión* antes de que la consulta salga. Por último,
`insight-synthesis` se carga **después** de `viz-patterns` para conectar
gráficos → insights priorizados.

`statistical-testing` es **opcional** en ambos flujos (no es siempre
necesaria). En `data-explorer` se carga **después** de `pandas-cleaning`
porque presupone datos limpios; en `reporting-analyst` se carga **entre**
`viz-patterns` y `insight-synthesis` cuando un hallazgo visual necesita un
número de p-value / tamaño de efecto para no quedar como "se ve más alto".
`data-explorer` también la puede cargar para responder preguntas analíticas
del estilo "¿es la diferencia significativa?" antes de pasar el control a
`reporting-analyst`.

`time-series-patterns` sigue el mismo patrón: opcional, se carga **después**
de `pandas-cleaning` cuando hay una dimensión temporal explícita en el
dataset y la pregunta es de tendencia / estacionalidad / forecast a corto
plazo. En `reporting-analyst` se usa para producir descomposiciones y
overlays de rolling stats antes de la narrativa. Cubre el hueco que
`statistical-testing` deja fuera explícitamente (autocorrelación: los
tests paramétricos asumen independencia y dan p-values falsos sobre
series con autocorrelación).

`feature-engineering` → `ml-modeling` → `model-evaluation` forman la
cadena de ML v2 para `ml-modeler`. El orden importa: el split es sagrado
(primero, antes de cualquier fit), después encoding y escalado (fit solo
en train), después modelos, después evaluación sobre el test set sagrado
**una sola vez**. `insight-synthesis` se aplica al final si el modelo
genera decisiones; `reporting-analyst` se invoca después para producir
los gráficos (matriz de confusión, ROC, learning curve, feature
importances).

## Ejemplos de invocación por CLI

Todos los CLIs son agnósticos al modelo. Elegí el modelo al momento de la
invocación. **Corré `make install-all` antes** así cada CLI ve a las personas
como agentes registrados reales (no solo contexto vía `AGENTS.md`).

### Codex

```bash
cd ~/Proyectos/data-analytics
make install-all   # única vez, registra las personas para OpenCode + Claude + Codex + Agy

# Flag --agent (después de instalar)
codex -m gpt-5.5 --agent data-explorer exec "Profileá examples/ventas_sample.csv y pará."

# o vía act-as en el prompt (funciona sin instalar también)
codex -m gpt-5.5 exec "act as data-explorer. Profileá examples/ventas_sample.csv y pará."
codex -m gpt-5.5 exec "act as sql-analyst. En examples/notes_example.sqlite, dame el top 5 de clientes por revenue."
codex -m gpt-5.5 exec "act as reporting-analyst. Tendencia mensual de revenue, últimos 90 días, salida a ./reports/."
```

### OpenCode

```bash
cd ~/Proyectos/data-analytics
make install-all

# Flag --agent (después de instalar) — registra la persona de forma nativa
opencode -m minimax-coding-plan/MiniMax-M3 --agent data-explorer "Profileá examples/ventas_sample.csv y pará."
opencode -m gemini-3.6-flash --agent sql-analyst "Top 5 de clientes por revenue desde examples/notes_example.sqlite."
opencode -m minimax-coding-plan/MiniMax-M3 --agent reporting-analyst "Tendencia mensual de revenue, salida a ./reports/."

# o vía act-as en el prompt
opencode -m minimax-coding-plan/MiniMax-M3 "act as data-explorer. Profileá examples/ventas_sample.csv y pará."
```

Verificar con: `opencode agent list` — debería incluir `data-explorer`,
`sql-analyst`, `reporting-analyst`, `using-data-analytics-agents`.

### Claude Code

```bash
cd ~/Proyectos/data-analytics
make install-all

claude -m opus --agent data-explorer "Profileá examples/ventas_sample.csv y pará."
claude -m opus --agent sql-analyst "Top 5 de clientes por revenue desde examples/notes_example.sqlite."
claude -m opus --agent reporting-analyst "Tendencia mensual de revenue, salida a ./reports/."
```

### Antigravity CLI (`agy`)

```bash
cd ~/Proyectos/data-analytics
make install-all   # instala el plugin de agy globalmente (el único CLI que requiere --global)

agy -m gemini-3.6-flash --agent data-explorer "Profileá examples/ventas_sample.csv y pará."
agy -m "Claude Opus 4.6 (Thinking)" --agent sql-analyst "Top 5 de clientes por revenue."
agy -m gemini-3.6-flash --agent reporting-analyst "Tendencia mensual de revenue, salida a ./reports/."
```

## Por qué "act as" funciona en cada CLI

Cada CLI soportado auto-descubre un `AGENTS.md` a nivel de proyecto (o
`CLAUDE.md` / `GEMINI.md`) y lo agrega al system prompt. Entonces cuando
escribís "act as `data-explorer`", el agente tiene la definición de la
persona en contexto y se auto-organiza alrededor de ella. Los archivos
markdown detallados de las personas en `agents/<name>.md` son la fuente de
verdad para ese rol; si algún agente se siente poco instruido, pedile al
CLI que `@agents/data-explorer.md` (o directamente que lea el archivo con
sus tools).

## Instalación opcional (solo si tus skills no están ya en `~/.agents/skills/`)

Si `~/.agents/skills/` todavía no contiene `csv-profiler`, `pandas-cleaning`,
`sql-query-helper`, `schema-mapper`, `query-validation`, `viz-patterns`,
`insight-synthesis`, y `using-data-analytics-agents`, corré:

```bash
make install-skills   # symlinks skills/<name>/ -> ~/.agents/skills/<name>
```

Este es el **único** paso de instalación requerido, y funciona igual para
los cuatro CLIs (comparten `~/.agents/skills/`). Alternativamente, corré
`make install-codex` (o `--all`) para instalar skills compatibles con
Codex en el `.agents/skills/` project-local.

## Plugin opcional de Antigravity (Agy)

Si además querés las personas de data-analytics disponibles vía
`agy --agent <name>` (en vez del estilo "act as" de arriba), instalá el
manifest del plugin incluido:

```bash
make install-agy      # stagea plugins/data-analytics-agents en ~/.gemini/antigravity-cli/plugins/
```

Después de esto, `agy plugin list` debería mostrar `data-analytics-agents` y
`agy agent` debería listar las cuatro personas. **Ambos estilos funcionan en
simultáneo** — elegí el que prefieras por sesión. `make install-all`
incluye este paso.

## Qué hace `bin/install.js`

`bin/install.js` (también expuesto como el bin `data-analytics-agents` vía
`package.json`) es el instalador project-local. Solo crea symlinks — nunca
copia — así que `agents/*.md` y `skills/*/` siguen siendo la fuente única de
verdad.

```
node ./bin/install.js install --opencode   # → .opencode/agents/ + .opencode/skills/
node ./bin/install.js install --claude     # → .claude/agents/ + .claude/skills/
node ./bin/install.js install --codex      # → .agents/skills/
node ./bin/install.js install --agy        # → ~/.gemini/antigravity-cli/plugins/...
node ./bin/install.js install --all        # los 4 CLIs a la vez
node ./bin/install.js install --auto       # solo para CLIs cuyo binario esté en PATH
node ./bin/install.js list                 # muestra el estado actual
node ./bin/install.js uninstall --all     # elimina todo lo que enlazamos
```

Tras publicar el paquete a npm, los mismos comandos funcionan como
`npx data-analytics-agents install --opencode` desde cualquier proyecto.

## Qué reemplaza esto

Las revisiones anteriores de este proyecto symlinkeaban las personas al
directorio de configuración privado de cada CLI (`~/.config/opencode/agent/`,
`~/.claude/agents/`, plugins de Agy). Eso hacía `make install` obligatorio
y editar `agents/<name>.md` requería un `make refresh`.

El diseño actual mantiene el enfoque de symlinks (así las ediciones son
live) pero reemplaza la instalación manual per-CLI por un único CLI
`bin/install.js` que maneja los 4 CLIs (`make install-all`). Editar
`agents/<name>.md` o `skills/<name>/SKILL.md` sigue tomándose de inmediato —
sin re-instalar.

Para limpiar los symlinks legacy (si existen de instalaciones aún más
viejas):

```bash
make cleanup-legacy   # elimina los symlinks viejos por CLI, deja ~/.agents/skills/ intacto
```
