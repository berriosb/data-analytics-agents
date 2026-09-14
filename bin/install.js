#!/usr/bin/env node
// bin/install.js — instalador multi-CLI para data-analytics-agents.
//
// Instala agentes (personas) y skills (recetas) en los directorios
// project-local o user-level esperados por OpenCode, Claude Code, Codex y
// Antigravity (agy). Siempre usa symlinks así que `agents/*.md` y `skills/*/`
// siguen siendo la única fuente de verdad.
//
// Uso:
//   node ./bin/install.js install [--opencode] [--claude] [--codex] [--agy]
//                                [--all] [--auto] [--global]
//   node ./bin/install.js uninstall [...]
//   node ./bin/install.js list
//   node ./bin/install.js help
//
// Sin dependencias externas. Node >= 18.

import { existsSync, lstatSync, readlinkSync, symlinkSync, unlinkSync, mkdirSync, readdirSync, rmSync, statSync } from "node:fs";
import { dirname, join, relative, resolve, basename } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { homedir } from "node:os";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, "..");

const AGENTS_DIR = join(REPO_ROOT, "agents");
const SKILLS_DIR = join(REPO_ROOT, "skills");
const ADAPTERS_DIR = join(REPO_ROOT, "adapters");

const AGENT_NAMES = ["data-explorer", "sql-analyst", "reporting-analyst", "ml-modeler", "using-data-analytics-agents"];
const SKILL_NAMES = [
  "csv-profiler",
  "pandas-cleaning",
  "sql-query-helper",
  "schema-mapper",
  "query-validation",
  "viz-patterns",
  "statistical-testing",
  "time-series-patterns",
  "feature-engineering",
  "ml-modeling",
  "model-evaluation",
  "insight-synthesis",
  "using-data-analytics-agents",
];

// ---- helpers de salida ------------------------------------------------------

const COLORS = { reset: "\x1b[0m", dim: "\x1b[2m", green: "\x1b[32m", yellow: "\x1b[33m", red: "\x1b[31m", cyan: "\x1b[36m", bold: "\x1b[1m" };
const c = (color, s) => process.stdout.isTTY ? `${COLORS[color]}${s}${COLORS.reset}` : s;
const log = (s) => console.log(s);
const info = (s) => log(`  ${c("cyan", "ℹ")} ${s}`);
const ok = (s) => log(`  ${c("green", "✓")} ${s}`);
const skip = (s) => log(`  ${c("dim", "·")} ${s}`);
const warn = (s) => log(`  ${c("yellow", "⚠")} ${s}`);
const err = (s) => log(`  ${c("red", "✗")} ${s}`);
const header = (s) => log(`\n${c("bold", s)}`);

// ---- definiciones de rutas --------------------------------------------------

// Cada entrada describe el layout de instalación de un CLI para un scope.
// `mode` es "project" (relativo a cwd) o "global" (relativo a home).
// `agents` y `skills` son funciones que devuelven un array de pares {src, dst}.

function pathsForCli(cli, scope) {
  const cwd = process.cwd();
  const home = homedir();
  const projRoot = scope === "global" ? home : cwd;
  const prefix = scope === "global" ? home : cwd;

  const agentSrc = (name) => join(AGENTS_DIR, `${name}.md`);
  const skillSrc = (name) => join(SKILLS_DIR, name);

  const layouts = {
    opencode: () => {
      const agents = AGENT_NAMES.map((name) => ({
        kind: "agent",
        name,
        src: agentSrc(name),
        dst: join(projRoot, ".opencode", "agents", `${name}.md`),
      }));
      const skills = SKILL_NAMES.map((name) => ({
        kind: "skill",
        name,
        src: skillSrc(name),
        dst: join(projRoot, ".opencode", "skills", name),
      }));
      return [...agents, ...skills];
    },
    claude: () => {
      const agents = AGENT_NAMES.map((name) => ({
        kind: "agent",
        name,
        src: agentSrc(name),
        dst: join(projRoot, ".claude", "agents", `${name}.md`),
      }));
      const skills = SKILL_NAMES.map((name) => ({
        kind: "skill",
        name,
        src: skillSrc(name),
        dst: join(projRoot, ".claude", "skills", name),
      }));
      return [...agents, ...skills];
    },
    codex: () => {
      // Codex lee skills de .agents/skills/ (proyecto) o ~/.agents/skills/ (usuario).
      // No tiene un directorio agents/ separado — se apoya en AGENTS.md.
      const skills = SKILL_NAMES.map((name) => ({
        kind: "skill",
        name,
        src: skillSrc(name),
        dst: join(projRoot, ".agents", "skills", name),
      }));
      return skills;
    },
    agy: () => {
      // Antigravity CLI usa un layout de directorio plugin bajo ~/.gemini/.
      // Siempre global — no hay modelo de plugin project-local.
      if (scope !== "global") return [];
      const pluginRoot = join(home, ".gemini", "antigravity-cli", "plugins", "data-analytics-agents");
      const out = [];
      out.push({
        kind: "plugin-manifest",
        name: "data-analytics-agents",
        src: join(ADAPTERS_DIR, "antigravity", "plugin.json"),
        dst: join(pluginRoot, "plugin.json"),
      });
      for (const name of AGENT_NAMES) {
        out.push({
          kind: "agent",
          name,
          src: agentSrc(name),
          dst: join(pluginRoot, "agents", `${name}.md`),
        });
      }
      for (const name of SKILL_NAMES) {
        out.push({
          kind: "skill",
          name,
          src: skillSrc(name),
          dst: join(pluginRoot, "skills", name),
        });
      }
      return out;
    },
  };

  return layouts[cli]();
}

// ---- operaciones de filesystem ----------------------------------------------

function ensureParentDir(p) {
  mkdirSync(dirname(p), { recursive: true });
}

function relink(src, dst) {
  // src es absoluto (anclado a REPO_ROOT). Para el symlink queremos una ruta
  // que sobreviva a que se mueva el destino: usamos una ruta relativa a dst.
  const target = relative(dirname(dst), src);
  ensureParentDir(dst);
  // Chequeos previos.
  if (existsSync(dst) || lstatSyncSafe(dst)) {
    const lst = lstatSync(dst);
    if (lst.isSymbolicLink()) {
      const existing = readlinkSync(dst);
      const existingResolved = resolve(dirname(dst), existing);
      const srcResolved = resolve(src);
      if (existingResolved === srcResolved) {
        return { action: "exists" };
      }
      throw new Error(`se rehusa sobreescribir symlink existente\n    ${dst} -> ${existing}\n    se esperaba -> ${src}\n    eliminá manualmente o corré uninstall primero`);
    }
    throw new Error(`se rehusa sobreescribir elemento no-symlink en ${dst}`);
  }
  unlinkSyncSafe(dst);
  symlinkSync(target, dst);
  return { action: "created", target };
}

function unlink(dst) {
  if (!existsSync(dst) && !lstatSyncSafe(dst)) return { action: "absent" };
  const lst = lstatSync(dst);
  if (!lst.isSymbolicLink() && !lst.isDirectory() && !lst.isFile()) {
    return { action: "absent" };
  }
  // Solo eliminar si es un symlink que creamos nosotros O un dir vacío que creamos.
  if (lst.isSymbolicLink()) {
    unlinkSync(dst);
    return { action: "removed" };
  }
  // Para directorios, solo eliminar si están vacíos (creamos el dir hoja).
  try {
    rmSync(dst, { recursive: true, force: false });
    return { action: "removed" };
  } catch (e) {
    return { action: "skipped-non-empty", error: e.message };
  }
}

function lstatSyncSafe(p) {
  try { return lstatSync(p); } catch { return null; }
}

function unlinkSyncSafe(p) {
  try { unlinkSync(p); } catch { /* noop */ }
}

// ---- detección --------------------------------------------------------------

function detectClis() {
  const checks = {
    opencode: ["opencode"],
    claude: ["claude"],
    codex: ["codex"],
    agy: ["agy"],
  };
  const present = new Set();
  for (const [cli, bins] of Object.entries(checks)) {
    for (const bin of bins) {
      const r = spawnSync("which", [bin], { encoding: "utf8" });
      if (r.status === 0 && r.stdout.trim()) {
        present.add(cli);
        break;
      }
    }
  }
  return present;
}

// ---- install / uninstall / list ---------------------------------------------

function install(scope, clis) {
  let total = 0, created = 0, existed = 0;
  for (const cli of clis) {
    const items = pathsForCli(cli, scope);
    if (items.length === 0) {
      skip(`${c("bold", cli)} (sin entradas project-local; usá --global para este CLI)`);
      continue;
    }
    header(`${c("bold", cli)}  ${c("dim", `(${scope})`)}`);
    for (const it of items) {
      total++;
      if (!existsSync(it.src)) {
        err(`${it.kind} ${c("bold", it.name)} — falta origen: ${it.src}`);
        continue;
      }
      try {
        const { action, target } = relink(it.src, it.dst);
        if (action === "created") {
          ok(`${it.kind.padEnd(15)} ${c("cyan", it.name)}  ${c("dim", "→")}  ${it.dst.replace(process.cwd() + "/", "./")}  ${c("dim", `→ ${target}`)}`);
          created++;
        } else {
          skip(`${it.kind.padEnd(15)} ${c("cyan", it.name)}  ${c("dim", "(ya enlazado)")}`);
          existed++;
        }
      } catch (e) {
        err(`${it.kind} ${c("bold", it.name)} — ${e.message.split("\n")[0]}`);
      }
    }
  }
  return { total, created, existed };
}

function uninstall(scope, clis) {
  let total = 0, removed = 0, absent = 0;
  for (const cli of clis) {
    const items = pathsForCli(cli, scope);
    if (items.length === 0) continue;
    header(`${c("bold", cli)}  ${c("dim", `(${scope})`)}`);
    for (const it of items) {
      total++;
      const { action, error } = unlink(it.dst);
      if (action === "removed") {
        ok(`${it.kind.padEnd(15)} ${c("cyan", it.name)}  ${c("dim", "✗ " + it.dst.replace(process.cwd() + "/", "./"))}`);
        removed++;
      } else if (action === "absent") {
        skip(`${it.kind.padEnd(15)} ${c("cyan", it.name)}  ${c("dim", "(no estaba instalado)")}`);
        absent++;
      } else {
        warn(`${it.kind.padEnd(15)} ${c("cyan", it.name)}  ${c("dim", "(salteado: " + (error || "no vacío") + ")")}`);
      }
    }
  }
  return { total, removed, absent };
}

function list(scope) {
  const clis = ["opencode", "claude", "codex", "agy"];
  for (const cli of clis) {
    const items = pathsForCli(cli, scope);
    if (items.length === 0) continue;
    header(`${c("bold", cli)}  ${c("dim", `(${scope})`)}`);
    for (const it of items) {
      const lst = lstatSyncSafe(it.dst);
      if (!lst) {
        skip(`${it.kind.padEnd(15)} ${c("cyan", it.name)}  ${c("dim", "(no instalado)")}`);
      } else if (lst.isSymbolicLink()) {
        const target = readlinkSync(it.dst);
        ok(`${it.kind.padEnd(15)} ${c("cyan", it.name)}  ${c("dim", "→ " + target)}`);
      } else {
        warn(`${it.kind.padEnd(15)} ${c("cyan", it.name)}  ${c("dim", "(existe pero no es symlink)")}`);
      }
    }
  }
}

// ---- dispatch del CLI --------------------------------------------------------

const USAGE = `
${c("bold", "data-analytics-agents")} — instalador multi-CLI

${c("bold", "Uso:")}
  data-analytics-agents install [flags]
  data-analytics-agents uninstall [flags]
  data-analytics-agents list [flags]
  data-analytics-agents help

${c("bold", "Alcance:")}
  (por defecto)            project-local (./.opencode/, ./.claude/, etc.)
  --global, -g             user-level (~/.config/opencode/, ~/.claude/, ~/.agents/, ~/.gemini/)

${c("bold", "Targets (combinables; default = --all):")}
  --opencode, -o           OpenCode (agents + skills)
  --claude, -c             Claude Code (agents + skills)
  --codex, -x              Codex (skills; los agentes van vía AGENTS.md)
  --agy, -a                Antigravity CLI (plugin; solo global)
  --all                    los 4 CLIs a la vez

${c("bold", "Otros flags:")}
  --auto                   instalar solo para los CLIs cuyo binario esté en PATH
  --dry-run                imprime acciones sin tocar el filesystem

${c("bold", "Ejemplos:")}
  data-analytics-agents install --opencode           # arregla el problema de agentes en OpenCode
  data-analytics-agents install --all                # project-local para los 4 CLIs
  data-analytics-agents install --auto --global      # user-level, CLIs auto-detectados
  data-analytics-agents uninstall --all              # elimina todo lo que enlazamos
  data-analytics-agents list                         # muestra el estado actual

${c("bold", "Notas:")}
  Siempre usa symlinks (nunca copia). Editá los archivos en ${c("cyan", "agents/")} o
  ${c("cyan", "skills/")} y los cambios se reflejan al instante. Re-correr install
  es seguro (idempotente).
`;

function parseArgs(argv) {
  const args = argv.slice(2);
  const cmd = args[0] || "help";
  const flags = new Set(args.slice(1));
  return { cmd, flags };
}

function selectedClis(flags) {
  const requested = [];
  if (flags.has("--opencode") || flags.has("-o")) requested.push("opencode");
  if (flags.has("--claude") || flags.has("-c")) requested.push("claude");
  if (flags.has("--codex") || flags.has("-x")) requested.push("codex");
  if (flags.has("--agy") || flags.has("-a")) requested.push("agy");
  if (flags.has("--all")) requested.push("opencode", "claude", "codex", "agy");
  return requested.length ? [...new Set(requested)] : ["opencode", "claude", "codex", "agy"];
}

function preflight() {
  const problems = [];
  if (!existsSync(AGENTS_DIR)) problems.push(`falta el directorio agents/ en ${AGENTS_DIR}`);
  if (!existsSync(SKILLS_DIR)) problems.push(`falta el directorio skills/ en ${SKILLS_DIR}`);
  for (const name of AGENT_NAMES) {
    if (!existsSync(join(AGENTS_DIR, `${name}.md`))) problems.push(`falta agents/${name}.md`);
  }
  for (const name of SKILL_NAMES) {
    if (!existsSync(join(SKILLS_DIR, name, "SKILL.md"))) problems.push(`falta skills/${name}/SKILL.md`);
  }
  return problems;
}

function main() {
  const { cmd, flags } = parseArgs(process.argv);

  if (flags.has("--help") || flags.has("-h") || cmd === "help" || cmd === "--help") {
    log(USAGE);
    return 0;
  }

  const scope = flags.has("--global") || flags.has("-g") ? "global" : "project";
  const dryRun = flags.has("--dry-run");
  const auto = flags.has("--auto");

  if (cmd !== "install" && cmd !== "uninstall" && cmd !== "list") {
    err(`comando desconocido: ${cmd}\n`);
    log(USAGE);
    return 2;
  }

  if (cmd === "list") {
    list(scope);
    return 0;
  }

  const problems = preflight();
  if (problems.length) {
    err("preflight falló:");
    for (const p of problems) err(`  - ${p}`);
    err(`este script debe correrse desde adentro del repo data-analytics-agents`);
    return 1;
  }

  let clis = selectedClis(flags);
  if (auto) {
    const present = detectClis();
    clis = clis.filter((c) => present.has(c));
    if (clis.length === 0) {
      warn("--auto: no se encontró ninguno de opencode / claude / codex / agy en PATH; nada para hacer");
      return 0;
    }
    info(`--auto detectó: ${clis.join(", ")}`);
  }

  // Agy es solo global; avisamos al usuario cuando lo pide project-local.
  if (clis.includes("agy") && scope !== "global") {
    warn("--agy solo soporta --global (Antigravity no tiene modelo de plugin project-local); se saltea agy");
    clis = clis.filter((c) => c !== "agy");
    if (clis.length === 0) return 0;
  }

  log(`${c("bold", "data-analytics-agents")} ${c("dim", `v0.1.0 — ${cmd} (${scope}${dryRun ? ", dry-run" : ""})`)}`);

  if (dryRun) {
    for (const cli of clis) {
      const items = pathsForCli(cli, scope);
      if (items.length === 0) continue;
      header(`${c("bold", cli)}  ${c("dim", `(${scope})`)}`);
      for (const it of items) {
        log(`  ${c("dim", "[dry-run]")} ${it.kind.padEnd(15)} ${it.name.padEnd(28)} ${c("dim", "→ " + it.dst)}`);
      }
    }
    return 0;
  }

  const fn = cmd === "install" ? install : uninstall;
  const summary = fn(scope, clis);

  header(c("bold", "Resumen"));
  if (cmd === "install") {
    log(`  ${c("green", String(summary.created))} creados, ${c("dim", String(summary.existed))} ya enlazados, ${summary.total} total`);
    log("");
    info(`verificá con: ${c("cyan", "opencode agent list")}`);
    info(`o listá el estado actual: ${c("cyan", "data-analytics-agents list")}`);
  } else {
    log(`  ${c("yellow", String(summary.removed))} eliminados, ${c("dim", String(summary.absent))} no estaban instalados`);
  }
  return 0;
}

process.exit(main());