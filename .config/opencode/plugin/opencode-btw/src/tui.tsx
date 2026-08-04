/** @jsxImportSource @opentui/solid */

import type { TuiPlugin } from "@opencode-ai/plugin/tui"

const BTW_TITLE = "btw:side-questions"
const PREVIEW_MAX = 400

/**
 * /btw — ask a quick side question.
 *
 * Runs the question in an isolated child session (`btw:side-questions`) via the TUI
 * plugin's own client, then shows the answer in a dialog panel + toast. The main
 * conversation is never sent a command, so its context stays completely untouched.
 *
 * @deprecated Uses the v1 TUI plugin API (`api.command.register` — the legacy
 * `api.command` bridge is marked "remove in v2"). Re-migrate when opencode v2 ships;
 * see README.md in this plugin directory.
 */
export const tui: TuiPlugin = async (api) => {
  console.warn(
    "[opencode-btw] DEPRECATED: uses the v1 TUI plugin API (api.command). " +
      "Re-migrate when opencode v2 ships. See README.md in this plugin directory.",
  )

  const currentSessionID = (): string | undefined => {
    const route = api.route.current
    return route.name === "session" ? (route.params as { sessionID?: string })?.sessionID : undefined
  }

  const showAnswer = (question: string, answer: string) => {
    const preview = answer.length > PREVIEW_MAX ? answer.slice(0, PREVIEW_MAX) + "\n…" : answer
    api.ui.toast({ title: "💡 BTW", message: preview, variant: "info", duration: 8000 })
    api.ui.dialog.setSize("large")
    api.ui.dialog.replace(
      () => (
        <api.ui.Dialog size="large" onClose={() => api.ui.dialog.clear()}>
          <box width="100%">
            <text wrapMode="word" width="100%" fg={api.theme.current.text}>
              💡 {question}
            </text>
            <text wrapMode="word" width="100%" fg={api.theme.current.text}>
              {answer}
            </text>
            <text wrapMode="word" width="100%" fg={api.theme.current.info}>
              ─ full Q&A also in the `btw:side-questions` session ─
            </text>
          </box>
        </api.ui.Dialog>
      ),
      () => api.ui.dialog.clear(),
    )
  }

  const runBtw = async (raw: string) => {
    const question = raw.trim()
    if (!question) return
    const parentID = currentSessionID()
    api.ui.toast({ title: "💡 BTW", message: "Thinking…", variant: "info", duration: 3000 })
    try {
      const created = await api.client.session.create({
        title: BTW_TITLE,
        ...(parentID ? { parentID } : {}),
      })
      const sideID = created.data?.id
      if (!sideID) throw new Error("failed to create BTW session")

      const result = await api.client.session.prompt({
        sessionID: sideID,
        parts: [{ type: "text", text: question }],
        tools: { todowrite: false, todoread: false },
      })
      const answer =
        result.data?.parts?.findLast((p) => p.type === "text")?.text ?? "(no answer returned)"
      showAnswer(question, answer)
    } catch (err) {
      api.ui.toast({
        title: "BTW error",
        message: err instanceof Error ? err.message : String(err),
        variant: "error",
      })
    }
  }

  const askBtw = () => {
    api.ui.dialog.replace(
      () => (
        <api.ui.DialogPrompt
          title="💡 BTW — side question"
          placeholder="Type your question… (Enter to ask, Esc to cancel)"
          onCancel={() => api.ui.dialog.clear()}
          onConfirm={(value) => {
            api.ui.dialog.clear()
            void runBtw(value)
          }}
        />
      ),
      () => api.ui.dialog.clear(),
    )
  }

  api.command?.register(() => [
    {
      title: "BTW — ask a side question",
      value: "btw",
      description: "Answer in an isolated session, shown in a panel; main context untouched",
      slash: { name: "btw" },
      onSelect: () => askBtw(),
    },
  ])
}

const mod = { id: "opencode-btw", tui }

export default mod
