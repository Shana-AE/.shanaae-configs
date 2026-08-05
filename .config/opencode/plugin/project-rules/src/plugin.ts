import { existsSync, readFileSync, readdirSync, statSync } from "node:fs"
import { homedir } from "node:os"
import { join } from "node:path"
import type { Plugin } from "@opencode-ai/plugin"

interface ProjectRuleSpec {
  deps?: string[]
  files?: string[]
  rules: string[]
}

interface ProjectRulesOptions {
  projects?: Record<string, ProjectRuleSpec>
}

const DEFAULT_PROJECTS: Record<string, ProjectRuleSpec> = {
  vue: {
    deps: ["vue"],
    files: ["**/*.vue", "vite.config.ts", "vite.config.js", "nuxt.config.ts", "nuxt.config.js", "quasar.conf.js"],
    rules: ["~/.shanaae/configs/ai/user_rules/vue-learning.md"],
  },
  harmonyos: {
    files: ["oh-package.json5", "build-profile.json5", "hvigorfile.ts", "hvigorfile.js", ".hvigor"],
    rules: ["~/.shanaae/configs/ai/user_rules/harmonyos-learning.md"],
  },
}

const SKIP_DIRS = new Set(["node_modules", ".git", "dist", "build", ".hvigor", ".idea", ".vscode"])

// Safety bound so glob checks can't stall boot on huge trees (e.g. $HOME).
const MAX_WALKED = 3000

function hasDeps(dir: string, deps: string[]): boolean {
  const pkgPath = join(dir, "package.json")
  if (!existsSync(pkgPath)) return false
  try {
    const pkg = JSON.parse(readFileSync(pkgPath, "utf8"))
    const all = {
      ...(pkg.dependencies ?? {}),
      ...(pkg.devDependencies ?? {}),
      ...(pkg.peerDependencies ?? {}),
      ...(pkg.optionalDependencies ?? {}),
    }
    return deps.some((dep) => all[dep])
  } catch {
    return false
  }
}

function collectFiles(dir: string, depth: number, out: string[]): void {
  if (depth > 5 || out.length >= MAX_WALKED) return
  let entries: string[]
  try {
    entries = readdirSync(dir)
  } catch {
    return
  }
  for (const entry of entries) {
    if (SKIP_DIRS.has(entry)) continue
    if (entry.startsWith(".")) continue
    const full = join(dir, entry)
    let stat
    try {
      stat = statSync(full)
    } catch {
      continue
    }
    if (stat.isDirectory()) collectFiles(full, depth + 1, out)
    else out.push(entry)
  }
}

function hasFileMarker(dir: string, pattern: string): boolean {
  if (!pattern.includes("*")) return existsSync(join(dir, pattern))
  const extMatch = pattern.match(/\*\.([a-zA-Z0-9]+)$/)
  const suffix = extMatch ? `.${extMatch[1]}` : pattern.replace("*", "")
  const files: string[] = []
  collectFiles(dir, 0, files)
  return files.some((file) => file.endsWith(suffix))
}

function matches(dir: string, spec: ProjectRuleSpec): boolean {
  if (spec.deps?.length && hasDeps(dir, spec.deps)) return true
  if (spec.files?.length && spec.files.some((pattern) => hasFileMarker(dir, pattern))) return true
  return false
}

function expandHome(p: string): string {
  return p.startsWith("~/") ? join(homedir(), p.slice(2)) : p
}

export const ProjectRulesPlugin: Plugin = (input, options) => {
  const directory = (input as { directory?: string }).directory || process.cwd()

  return {
    config: (cfg) => {
      const opts = (options as ProjectRulesOptions | undefined) ?? {}
      const projects = { ...DEFAULT_PROJECTS, ...(opts.projects ?? {}) }

      const instructions = cfg.instructions ?? []
      for (const [name, spec] of Object.entries(projects)) {
        if (!spec?.rules?.length) continue
        if (!matches(directory, spec)) continue
        for (const rule of spec.rules) {
          const abs = expandHome(rule)
          if (!instructions.includes(abs)) instructions.push(abs)
        }
      }
    },
  }
}
