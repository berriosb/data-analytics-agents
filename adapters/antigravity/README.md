# Antigravity (agy CLI) adapter

Antigravity CLI (`~/.local/bin/agy`) loads custom agents and skills via
**plugins** staged at `~/.gemini/antigravity-cli/plugins/<name>/`.

This adapter provides the manifest that `install.sh` uses to install the
data-analytics-agents toolkit as an Antigravity plugin.

## Plugin layout

```
~/.gemini/antigravity-cli/plugins/data-analytics-agents/
├── plugin.json                 # this file (manifest)
├── agents/                     # symlinks to ../../agents/*.md
│   ├── data-explorer.md
│   ├── reporting-analyst.md
│   ├── sql-analyst.md
│   └── using-data-analytics-agents.md
└── skills/                     # symlinks to ../../skills/*/
    ├── csv-profiler/SKILL.md
    ├── pandas-cleaning/SKILL.md
    ├── sql-query-helper/SKILL.md
    ├── using-data-analytics-agents/SKILL.md
    └── viz-patterns/SKILL.md
```

## After `make install`

Verify with:

```bash
agy plugin list                                    # should show data-analytics-agents
agy agent                                          # should list data-explorer, etc.
ls ~/.gemini/antigravity-cli/plugins/data-analytics-agents/
ls ~/.gemini/antigravity-cli/plugins/data-analytics-agents/skills/
```

## Invoking the agents

```bash
# Via --agent flag (per-session override)
agy --model gemini-3.6-flash --agent data-explorer \
  "analyze ./examples/ventas_sample.csv"

agy --agent sql-analyst \
  "top 5 customers by revenue last quarter"

agy --agent reporting-analyst \
  "monthly revenue trend, last 90 days, output to ./reports/"
```

## How Antigravity differs from OpenCode / Claude Code

| Aspect | Antigravity CLI | OpenCode / Claude Code |
|---|---|---|
| Custom agents | via Plugins (`~/.gemini/antigravity-cli/plugins/<name>/agents/`) | via dedicated paths in config |
| Custom skills | per-plugin OR global `~/.gemini/antigravity-cli/skills/` OR project `.agents/skills/` | dedicated paths |
| Discovery mechanism | `agy plugin list` and `agy agent` | `--agent <name>` flag at invocation |
| Cloud-sourced agents | also available (managed by Google) | none |
| Schema validation | JSON Schema: `https://antigravity.google/schemas/v1/plugin.json` | YAML frontmatter (informal) |

## Re-installing

```bash
make install        # idempotent — re-runs all steps including Agy
make refresh        # same
make uninstall      # removes all artefacts, including the Antigravity plugin
```

## Caveats

- Antigravity CLI v1.1.8 (current at time of writing). Some features
  documented at `https://antigravity.google/docs/cli/plugins/` may evolve.
- Plugin name must match `^[a-zA-Z0-9-_]+$` — we use `data-analytics-agents`.
- The plugin is staged at the **user** level. Antigravity will discover it
  the next time you invoke `agy` (may require a fresh session).
