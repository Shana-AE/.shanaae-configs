/** @jsxImportSource @opentui/solid */

import type { JSX } from "@opentui/solid"
import { createSignal } from "solid-js"
import type { TuiPlugin } from "@opencode-ai/plugin/tui"

const BTW_TITLE = "btw:side-questions"
const PREVIEW_MAX = 500

/**
 * /btw — sidebar panel.
 *
 * The SERVER plugin (src/plugin.ts) runs `/btw <question>` in an isolated
 * `btw:side-questions` child session and shows a toast. This TUI plugin
 * subscribes to that toast event, reads the child session's full answer, and
 * renders it in a persistent sidebar panel (via api.slots — the same mechanism
 * subagent-magazine uses). No dialogs / textarea, so nothing to get stuck.
 *
 * @deprecated Uses the v1 TUI plugin API (api.slots / api.event). Re-migrate
 * when opencode v2 ships; see README.md in this plugin directory.
 */
export const tui: TuiPlugin = async (api) => {
  const [btw, setBtw] = createSignal<{ question: string; answer: string } | null>(null)

  const trace = (msg: string) => console.warn(`[opencode-btw] ${msg}`)

  const currentSessionID = (): string | undefined => {
    const route = api.route.current
    return route.name === "session" ? (route.params as { sessionID?: string })?.sessionID : undefined
  }

  const textOf = (parts: Array<{ type: string; text?: string }> | undefined): string =>
    parts?.findLast((p) => p.type === "text")?.text ?? ""

  const loadAnswer = async () => {
    const parentID = currentSessionID()
    if (!parentID) return
    try {
      const children = await api.client.session.children({ sessionID: parentID })
      const btwChild = children.data?.find((s) => s.title === BTW_TITLE)
      if (!btwChild) {
        trace("no btw child session")
        return
      }
      const msgs = await api.client.session.messages({ sessionID: btwChild.id })
      const list = msgs.data ?? []
      const question = textOf(list.find((m) => m.info.role === "user")?.parts)
      let answer = ""
      for (let i = list.length - 1; i >= 0; i--) {
        const m = list[i]
        if (m.info.role !== "assistant") continue
        const text = textOf(m.parts)
        if (text) {
          answer = text
          break
        }
      }
      if (!answer) {
        trace("no answer text yet")
        return
      }
      setBtw({ question, answer })
      trace(`panel updated (${answer.length} chars)`)
    } catch (err) {
      trace(`loadAnswer error: ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  const BtwPanel = (): JSX.Element => {
    const item = btw()
    const { theme } = api
    if (!item) {
      return (
        <box width="100%" paddingTop={1} paddingBottom={1}>
          <text fg={theme.current.textMuted}>💡 /btw — ask a side question</text>
        </box>
      )
    }
    const preview =
      item.answer.length > PREVIEW_MAX ? item.answer.slice(0, PREVIEW_MAX) + "\n…" : item.answer
    return (
      <box width="100%" paddingTop={1} paddingBottom={1}>
        <text wrapMode="word" width="100%" fg={theme.current.text}>
          💡 {item.question || "BTW"}
        </text>
        <text wrapMode="word" width="100%" fg={theme.current.text}>
          {preview}
        </text>
        <text wrapMode="word" width="100%" fg={theme.current.textMuted}>
          ─ full answer in the `btw:side-questions` session ─
        </text>
      </box>
    )
  }

  api.slots.register({
    slots: {
      sidebar_content: () => <BtwPanel />,
    },
  })
  trace("sidebar slot registered")

  api.event.on("tui.toast.show", (evt) => {
    if (evt.properties?.title !== "💡 BTW") return
    trace("toast event → load answer")
    void loadAnswer()
  })
}

const mod = { id: "opencode-btw", tui }

export default mod
