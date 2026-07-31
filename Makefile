PROJECT_DIR := $(shell pwd)
INSTALLER   := node ./bin/install.js
SH_INSTALL  := ./scripts/install.sh
TARGET      := $(HOME)

.PHONY: help \
        install-opencode install-claude install-codex install-agy install-all install-auto \
        uninstall-opencode uninstall-claude uninstall-codex uninstall-agy uninstall-all \
        install-skills uninstall-skills install-sh-agy uninstall-sh-agy cleanup-legacy \
        list skills docs test-csv test-sql

help:
	@echo "data-analytics-agents — toolkit multi-CLI de personas"
	@echo ""
	@echo "Inicio rápido (instalación project-local para cualquier CLI)"
	@echo "  make install-opencode    Arregla el descubrimiento de OpenCode (registra 4 personas)"
	@echo "  make install-claude      Project-local: agentes + skills para Claude Code"
	@echo "  make install-codex       Project-local: skills para Codex"
	@echo "  make install-agy         Stagea el plugin de Antigravity (user-level, --global)"
	@echo "  make install-all         Los 4 CLIs a la vez"
	@echo "  make install-auto        Solo para los CLIs que estén en el PATH (--auto)"
	@echo ""
	@echo "Limpieza"
	@echo "  make uninstall-opencode  Elimina los symlinks de OpenCode"
	@echo "  make uninstall-claude    Elimina los symlinks de Claude Code"
	@echo "  make uninstall-codex     Elimina los symlinks de Codex"
	@echo "  make uninstall-agy       Elimina el plugin de Agy"
	@echo "  make uninstall-all       Elimina todo"
	@echo ""
	@echo "User-level (legacy, vía scripts/install.sh)"
	@echo "  make install-skills      Symlinkea skills a ~/.agents/skills/"
	@echo "  make uninstall-skills    Elimina esos symlinks"
	@echo "  make cleanup-legacy      Elimina symlinks VIEJOS por CLI de revisiones anteriores"
	@echo ""
	@echo "Descubrimiento / smoke tests"
	@echo "  make list         Muestra qué está instalado y dónde"
	@echo "  make skills       Muestra las 8 skills a nivel usuario"
	@echo "  make docs         Abre los archivos markdown clave"
	@echo "  make test-csv     Smoke test de csv-profiler sobre examples/ventas_sample.csv"
	@echo "  make test-sql     Conecta a examples/notes_example.sqlite"

# ---- instalaciones project-local (la ruta principal) ------------------------

install-opencode:
	$(INSTALLER) install --opencode

install-claude:
	$(INSTALLER) install --claude

install-codex:
	$(INSTALLER) install --codex

install-agy:
	$(INSTALLER) install --agy --global

install-all: install-opencode install-claude install-codex install-agy

install-auto:
	$(INSTALLER) install --auto

# ---- desinstalaciones ------------------------------------------------------

uninstall-opencode:
	$(INSTALLER) uninstall --opencode

uninstall-claude:
	$(INSTALLER) uninstall --claude

uninstall-codex:
	$(INSTALLER) uninstall --codex

uninstall-agy:
	$(INSTALLER) uninstall --agy --global

uninstall-all: uninstall-opencode uninstall-claude uninstall-codex uninstall-agy

# ---- instalaciones user-level legacy (para usuarios sin Node 18+) ------------

install-skills:
	$(SH_INSTALL) install-skills --target $(TARGET)

uninstall-skills:
	$(SH_INSTALL) uninstall-skills --target $(TARGET)

install-sh-agy:
	$(SH_INSTALL) install-agy --target $(TARGET)

uninstall-sh-agy:
	$(SH_INSTALL) uninstall-agy --target $(TARGET)

cleanup-legacy:
	$(SH_INSTALL) cleanup-legacy --target $(TARGET)

# ---- descubrimiento --------------------------------------------------------

list:
	@echo "--- raíz del proyecto (AGENTS.md auto-descubierto por los 4 CLIs) ---"
	@ls -1 $(PROJECT_DIR)/AGENTS.md
	@echo ""
	@echo "--- agents/ (fuente de verdad de las personas) ---"
	@ls -1 $(PROJECT_DIR)/agents/
	@echo ""
	@echo "--- skills/ (fuente de verdad de las skills) ---"
	@ls -1 $(PROJECT_DIR)/skills/
	@echo ""
	@echo "--- instalaciones project-local (./.opencode, ./.claude, ./.agents) ---"
	@ls -la $(PROJECT_DIR)/.opencode 2>/dev/null || echo "  (no hay .opencode/ — corré 'make install-opencode')"
	@ls -la $(PROJECT_DIR)/.claude 2>/dev/null || echo "  (no hay .claude/ — corré 'make install-claude')"
	@ls -la $(PROJECT_DIR)/.agents 2>/dev/null || echo "  (no hay .agents/ — corré 'make install-codex')"
	@echo ""
	@echo "--- skills user-level (~/.agents/skills/, compartidas por todos los CLIs) ---"
	@ls -1 $(HOME)/.agents/skills/ 2>/dev/null | grep -E "(csv-profiler|pandas-cleaning|sql-query-helper|schema-mapper|query-validation|viz-patterns|insight-synthesis|using-data-analytics-agents)" || echo "  (ninguna — corré 'make install-skills')"
	@echo ""
	@echo "--- plugin de Antigravity (user-level, opcional) ---"
	@ls -1 $(HOME)/.gemini/antigravity-cli/plugins/data-analytics-agents/ 2>/dev/null || echo "  (no instalado — corré 'make install-agy')"
	@echo ""
	@echo "--- agentes registrados en OpenCode ---"
	@opencode agent list 2>/dev/null | grep -E "^[a-z][a-z-]+ \(" | sort -u || echo "  (opencode no está en el PATH)"

skills:
	@ls -1 $(HOME)/.agents/skills/ 2>/dev/null | grep -E "(csv-profiler|pandas-cleaning|sql-query-helper|schema-mapper|query-validation|viz-patterns|insight-synthesis|using-data-analytics-agents)"

docs:
	@echo "Abrí estos:"
	@echo "  $(PROJECT_DIR)/AGENTS.md              — punto de entrada (lo leen todos los CLIs)"
	@echo "  $(PROJECT_DIR)/agents/<name>.md       — prompts detallados de las personas"
	@echo "  $(PROJECT_DIR)/skills/<name>/SKILL.md — cuerpos detallados de las skills"
	@echo "  $(PROJECT_DIR)/bin/install.js         — instalador multi-CLI"

test-csv:
	@echo "Corre los snippets de csv-profiler localmente sobre examples/ventas_sample.csv"
	@python3 -c "import pandas as pd, numpy as np; df=pd.read_csv('examples/ventas_sample.csv'); df=df.replace(['','nan','NaN','null','NULL','None','?'], np.nan); df=df.replace([np.inf,-np.inf], np.nan); print('forma:', df.shape); print('nulos por columna:'); print(df.isna().sum()); print('duplicados:', int(df.duplicated().sum()))"

test-sql:
	@echo "Conecta a examples/notes_example.sqlite"
	@python3 -c "import sqlite3; c=sqlite3.connect('examples/notes_example.sqlite'); print('clientes/productos/pedidos:', c.execute('SELECT (SELECT count(*) FROM customers),(SELECT count(*) FROM products),(SELECT count(*) FROM orders)').fetchone())"