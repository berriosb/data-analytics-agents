# Antigravity (agy CLI) adapter

Antigravity CLI (`agy`) soporta personalizaciones a nivel project-local y a nivel usuario:

- **Project-local (recomendado):** agentes en `.agents/agents/*.md` y skills en `.agents/skills/*/`. Requiere que el workspace esté marcado como de confianza (`trustedWorkspaces`).
- **Global:** agentes en `~/.gemini/config/agents/*.md` (o como plugin en `~/.gemini/antigravity-cli/plugins/<name>/`) y skills en `~/.agents/skills/*/`.

Los archivos de agentes requieren frontmatter YAML obligatorio (`name:` y `description:`) para que el parser de `agy` los registre.

## Estructura project-local (creada por `make install-agy` o `make install-all`)

```
.agents/
├── agents/                     # symlinks a ../agents/*.md
│   ├── data-explorer.md
│   ├── ml-modeler.md
│   ├── reporting-analyst.md
│   ├── sql-analyst.md
│   └── using-data-analytics-agents.md
└── skills/                     # symlinks a ../skills/*/
    ├── csv-profiler/SKILL.md
    ├── pandas-cleaning/SKILL.md
    └── ... (20 skills)
```

## Estructura legacy de plugin (`~/.gemini/antigravity-cli/plugins/data-analytics-agents/`)

Este adaptador provee el manifiesto `plugin.json` que `scripts/install.sh` usaba para empaquetar el toolkit como plugin formal:

```
~/.gemini/antigravity-cli/plugins/data-analytics-agents/
├── plugin.json                 # este archivo (manifiesto)
├── agents/                     # symlinks a ../../agents/*.md
│   ├── data-explorer.md
│   ├── ml-modeler.md
│   ├── reporting-analyst.md
│   ├── sql-analyst.md
│   └── using-data-analytics-agents.md
└── skills/                     # symlinks a ../../skills/*/
    └── ...
```

## Verificación

```bash
agy agent                                          # debe listar data-explorer, ml-modeler, etc.
```

## Invocación de los agentes

```bash
# Vía flag --agent
agy -m gemini-3.6-flash --agent data-explorer "analiza ./examples/ventas_sample.csv"
agy --agent sql-analyst "top 5 clientes por revenue"
agy --agent reporting-analyst "tendencia mensual de revenue a ./reports/"
agy --agent ml-modeler "entrenar modelo de churn"

# O vía prompt en cualquier sesión activa
agy "act as data-explorer. Profileá examples/ventas_sample.csv"
```

## Instalación y desinstalación

```bash
make install-agy        # project-local: .agents/agents/ + .agents/skills/
make install-all        # los 5 CLIs project-local
make uninstall-agy      # elimina symlinks de Agy
make uninstall-all      # limpia todo
```
