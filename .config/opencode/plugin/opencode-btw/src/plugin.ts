import type { Plugin } from "@opencode-ai/plugin"
import { loadConfig } from "./lib/config"
import { getOrCreateBtwSession, promptBtwSession } from "./lib/btw-session"
import type { BtwConfig } from "./lib/types"

type OpencodeClient = Parameters<Plugin>[0] extends infer C
  ? C extends { client: infer Client }
    ? Client
    : never
  : never

interface PluginConfigInput {
  agent?: Record<string, unknown>
  default_agent?: string
}

interface CommandExecuteInput {
  command: string
  arguments: string
  sessionID: string
}

const BTW_DEPRECATION_NOTICE =
  "[opencode-btw] DEPRECATED: this plugin uses the v1 plugin API " +
  "(command.execute.before + client.tui.showToast), which the opencode v2 plugin " +
  "system (@opencode-ai/plugin/v2/effect) will replace. Re-migrate when opencode v2 ships. " +
  "See README.md in this plugin directory."

/**
 * /btw — quick side question answered in an isolated child session, surfaced via a
 * TUI toast. The main conversation is not disturbed.
 *
 * @deprecated Uses the v1 plugin API (`command.execute.before` + `client.tui.showToast`).
 * The opencode v2 plugin system (`@opencode-ai/plugin/v2/effect`, imperative
 * `ctx.command.hook("execute.before", …)` + redesigned TUI API) supersedes this surface.
 * TODO(v2): re-migrate this plugin when opencode v2 is released.
 */
export const BtwServerPlugin: Plugin = async ({ client }) => {
  console.warn(BTW_DEPRECATION_NOTICE)

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
        body: { title?: string; message: string; variant?: string; duration?: number }
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
      if (cfg.btw) {
        config = loadConfig(cfg.btw)
      }
    },

    "command.execute.before": async (input: CommandExecuteInput) => {
      if (input.command !== "btw") return

      const question = input.arguments?.trim()
      if (!question) return

      try {
        const btwId = await getOrCreateBtwSession(typedClient as any, input.sessionID, config)
        const answer = await promptBtwSession(typedClient as any, btwId, question, config)

        const truncated = answer.length > 400
        const preview = truncated ? answer.slice(0, 400) + "\n…" : answer
        await typedClient.tui?.showToast({
          body: {
            title: "💡 BTW",
            message: truncated ? `${preview}\n(full answer in the btw:side-questions session)` : preview,
            variant: "info",
            duration: config.toastDuration,
          },
        })
      } catch (err) {
        await log("error", "BTW command failed", { error: err instanceof Error ? err.message : String(err) })
      }
    },
  }
}
