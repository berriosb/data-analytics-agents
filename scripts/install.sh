#!/usr/bin/env bash
# install.sh — instalador mínimo y opcional para el toolkit data-analytics-agents.
#
# El punto de entrada PRIMARIO es AGENTS.md en la raíz del proyecto. Cada uno
# de OpenCode, Claude Code, Codex y Antigravity CLI (agy) auto-descubre ese
# archivo cuando se lanza desde este directorio. No se requiere instalación
# para usar las personas.
#
# Este script solo maneja lo que AGENTS.md por sí solo no puede:
#
#   1. Skills universales: symlink skills/<name>/ -> ~/.agents/skills/<name>
#      para que los cuatro CLIs (que comparten esa ruta) puedan levantar las
#      skills a nivel usuario.
#
#   2. Plugin de Antigravity (opcional): si preferís la invocación
#      `agy --agent <name>` en vez de "act as <name>", instalá el plugin
#      incluido.
#
# Uso:
#   ./scripts/install.sh install-skills           # symlink solo de skills
#   ./scripts/install.sh install-agy              # stagea el plugin de Agy solo
#   ./scripts/install.sh install-all              # ambos, idempotente
#   ./scripts/install.sh uninstall-skills         # elimina los symlinks que creamos en ~/.agents/skills/<name>
#   ./scripts/install.sh uninstall-agy            # elimina el plugin de Agy
#   ./scripts/install.sh cleanup-legacy           # elimina symlinks VIEJOS por CLI de revisiones anteriores
#
# Usá --uninstall para remover; los args de arriba son los nombres de acción.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_SRC="$REPO_ROOT/skills"
TARGET="${TARGET:-$HOME}"

AGY_PLUGIN_DIR="$TARGET/.gemini/antigravity-cli/plugins/data-analytics-agents"
AGY_PLUGIN_JSON_SRC="$REPO_ROOT/adapters/antigravity/plugin.json"

LINK_NAMES=(csv-profiler pandas-cleaning sql-query-helper schema-mapper query-validation viz-patterns statistical-testing time-series-patterns feature-engineering ml-modeling model-evaluation insight-synthesis using-data-analytics-agents)

log() { printf "[install] %s\n" "$*"; }
err() { printf "[install][ERROR] %s\n" "$*" >&2; }

# ---- helpers de bajo nivel --------------------------------------------------

link_or_copy() {
  local src="$1"
  local dst="$2"
  mkdir -p "$(dirname "$dst")"
  rm -f "$dst"
  ln -s "$src" "$dst"
  log "  symlink  $dst -> $src"
}

remove_if_linked_or_file() {
  local dst="$1"
  if [[ -L "$dst" || -f "$dst" ]]; then
    rm -f "$dst"
    log "  removed  $dst"
  fi
}

# ---- acciones ---------------------------------------------------------------

install_skills() {
  log "Instalando skills: $TARGET/.agents/skills/"
  for d in "$SKILLS_SRC"/*/; do
    [[ -d "$d" ]] || continue
    name="$(basename "$d")"
    link_or_copy "$d" "$TARGET/.agents/skills/$name"
  done
  log "Listo. Verificá con: ls -1 $TARGET/.agents/skills/"
}

uninstall_skills() {
  log "Eliminando los symlinks de skills que creamos en $TARGET/.agents/skills/"
  for n in "${LINK_NAMES[@]}"; do
    remove_if_linked_or_file "$TARGET/.agents/skills/$n"
  done
}

install_agy() {
  log "Instalando el plugin de Antigravity: $AGY_PLUGIN_DIR/"
  if [[ ! -f "$AGY_PLUGIN_JSON_SRC" ]]; then
    err "falta $AGY_PLUGIN_JSON_SRC"; exit 1
  fi
  link_or_copy "$AGY_PLUGIN_JSON_SRC" "$AGY_PLUGIN_DIR/plugin.json"

  # agents/
  for f in "$REPO_ROOT/agents"/*.md; do
    [[ -f "$f" ]] || continue
    name="$(basename "$f" .md)"
    link_or_copy "$f" "$AGY_PLUGIN_DIR/agents/$name.md"
  done
  # skills/
  for d in "$SKILLS_SRC"/*/; do
    [[ -d "$d" ]] || continue
    name="$(basename "$d")"
    link_or_copy "$d" "$AGY_PLUGIN_DIR/skills/$name"
  done
  log "Listo. Verificá con: agy plugin list"
}

uninstall_agy() {
  log "Eliminando el directorio del plugin de Antigravity: $AGY_PLUGIN_DIR/"
  if [[ -d "$AGY_PLUGIN_DIR" ]]; then
    find "$AGY_PLUGIN_DIR" -type l -delete 2>/dev/null || true
    find "$AGY_PLUGIN_DIR" -type f -delete 2>/dev/null || true
    find "$AGY_PLUGIN_DIR" -type d -empty -delete 2>/dev/null || true
    log "  cleaned  $AGY_PLUGIN_DIR/"
  fi
}

cleanup_legacy() {
  log "Limpiando symlinks legacy por CLI (de revisiones anteriores de este toolkit)"
  for n in data-explorer sql-analyst reporting-analyst using-data-analytics-agents; do
    remove_if_linked_or_file "$TARGET/.claude/agents/$n.md"
    remove_if_linked_or_file "$TARGET/.claude/commands/$n.md"
    remove_if_linked_or_file "$TARGET/.config/opencode/agent/$n/agent.md"
    remove_if_linked_or_file "$TARGET/.gemini/antigravity-cli/plugins/data-analytics-agents/agents/$n.md"
  done
  log "Listo. Los agentes por CLI ahora se leen directamente desde AGENTS.md."
}

# ---- dispatch ---------------------------------------------------------------

ACTION="${1:-}"
shift || true

case "$ACTION" in
  install-skills)   install_skills ;;
  uninstall-skills) uninstall_skills ;;
  install-agy)      install_agy ;;
  uninstall-agy)    uninstall_agy ;;
  install-all)      install_skills; install_agy ;;
  uninstall-all)    uninstall_skills; uninstall_agy ;;
  cleanup-legacy)   cleanup_legacy ;;
  -h|--help|"")
    cat <<EOF
Uso: ./scripts/install.sh <acción>

  install-skills    symlink skills/<name>/ a ~/.agents/skills/<name>
  install-agy       stagea el plugin de Antigravity en ~/.gemini/antigravity-cli/plugins/data-analytics-agents/
  install-all       hace ambos
  uninstall-skills  elimina los symlinks que creamos
  uninstall-agy     elimina el plugin de Agy
  uninstall-all     ambas des-instalaciones
  cleanup-legacy    elimina symlinks viejos por CLI de revisiones anteriores

Recordatorio: las personas están disponibles para OpenCode, Claude Code, Codex
y Agy sin ninguna instalación — auto-descubren AGENTS.md desde este directorio.
EOF
    ;;
  *)
    err "Acción desconocida: $ACTION (corré sin args para ver la ayuda)"
    exit 1
    ;;
esac