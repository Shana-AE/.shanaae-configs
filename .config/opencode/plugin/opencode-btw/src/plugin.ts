import type { Plugin } from "@opencode-ai/plugin"
import { handled } from "./lib/command-handled"
import { loadConfig } from "./lib/config"
import { getOrCreateBtwSession, promptBtwSession } from "./lib/btw-session"
import type { BtwConfig } from "./lib/types"

type OpencodeClient = Parameters<Plugin>[0] extends infer C
  ? C extends { client: infer Client }
    ? Client
    : never
  : never

interface PluginConfigInput {
  command?: Record<string, { template: string; description: string }>
  agent?: Record<string, unknown>
  default_agent?: string
}

interface CommandExecuteInput {
  command: string
  arguments: string
  sessionID: string
}

export const BtwServerPlugin: Plugin = async ({ client }) => {
  const typedClient = client as unknown as OpencodeClient & {
    session: {
      create: (opts: { body?: { parentID?: string; title?: string } }) => Promise<{ data?: { id: string } }>
      children: (opts: { path: { id: string } }) => Promise<{ data?: Array<{ id: string; title?: string }> }>
      prompt: (opts: {
        path: { id: string }
        body: {
          parts: Array<{ type: string; text: string; ignored?: boolean }>
          noReply?: boolean
          model?: { providerID: string; modelID: string }
          tools?: Record<string, boolean>
        }
      }) => Promise<{ data?: { parts?: Array<{ type: string; text?: string }> }; error?: unknown }>
    }
    tui?: {
      showToast: (opts: {
        body: { message: string; variant?: string; duration?: number }
      }) => Promise<unknown>
    }
    app?: {
      log: (opts: {
        body: { service: string; level: string; message: string; extra?: unknown }
      }) => Promise<unknown>
    }
  }

  let config: BtwConfig = loadConfig()

  async function log(level: string, message: string, extra?: unknown): Promise<void> {
    try {
      await typedClient.app?.log({
        body: { service: "opencode-btw", level, message, extra },
      })
    } catch {
      // logging is best-effort
    }
  }

  return {
    config: async (input: unknown) => {
      const cfg = input as PluginConfigInput & { btw?: unknown }
      cfg.command ??= {}
      cfg.command["btw"] = {
        template: "/btw",
        description: "Quick side question (BTW) — answer shown as toast, no context pollution",
      }
      if (cfg.btw) {
        config = loadConfig(cfg.btw)
      }
    },

    "command.execute.before": async (input: CommandExecuteInput) => {
      if (input.command !== "btw") return

      const question = input.arguments?.trim()
      if (!question) {
        await typedClient.tui?.showToast({
          body: {
            message: "BTW: type /btw <question> or press Ctrl+B",
            variant: "info",
            duration: 5000,
          },
        })
        handled()
      }

      try {
        const btwId = await getOrCreateBtwSession(typedClient as any, input.sessionID, config)
        const answer = await promptBtwSession(typedClient as any, btwId, question!, config)

        const truncated = answer.length > 800 ? answer.slice(0, 800) + "\n…(truncated)" : answer
        await typedClient.tui?.showToast({
          body: {
            message: `💡 ${truncated}`,
            variant: "info",
            duration: config.toastDuration,
          },
        })
      } catch (err) {
        await log("error", "BTW command failed", { error: err instanceof Error ? err.message : String(err) })
        await typedClient.tui?.showToast({
          body: {
            message: `BTW error: ${err instanceof Error ? err.message : String(err)}`,
            variant: "error",
            duration: 5000,
          },
        })
      }

      handled()
    },
  }
}
