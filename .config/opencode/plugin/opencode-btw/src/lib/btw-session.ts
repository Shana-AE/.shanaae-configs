import type { BtwConfig, BtwEntry } from "./types"
import { BTW_TITLE_PREFIX } from "./types"

type OpencodeClient = {
  session: {
    create: (opts: {
      body?: { parentID?: string; title?: string }
      query?: { directory?: string }
    }) => Promise<{ data?: { id: string }; error?: unknown }>
    children: (opts: {
      path: { id: string }
    }) => Promise<{ data?: Array<{ id: string; title?: string }> }>
    prompt: (opts: {
      path: { id: string }
      body: {
        parts: Array<{ type: string; text: string; ignored?: boolean }>
        noReply?: boolean
        agent?: string
        model?: { providerID: string; modelID: string }
        tools?: Record<string, boolean>
      }
    }) => Promise<{
      data?: { info?: unknown; parts?: Array<{ type: string; text?: string }> }
      error?: unknown
    }>
    messages: (opts: {
      path: { id: string }
    }) => Promise<{ data?: Array<{ role?: string; parts?: Array<{ type: string; text?: string }> }> }>
    delete?: (opts: { path: { id: string } }) => Promise<unknown>
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

const btwSessionCache = new Map<string, string>()

export async function getOrCreateBtwSession(
  client: OpencodeClient,
  parentID: string,
  config: BtwConfig,
): Promise<string> {
  const cached = btwSessionCache.get(parentID)
  if (cached && config.keepSession) return cached

  try {
    const children = await client.session.children({ path: { id: parentID } })
    const existing = children.data?.find((s) => s.title === BTW_TITLE_PREFIX)
    if (existing) {
      btwSessionCache.set(parentID, existing.id)
      return existing.id
    }
  } catch {
    // ignore — may not have children endpoint available
  }

  const session = await client.session.create({
    body: { parentID, title: BTW_TITLE_PREFIX },
  })

  if (!session.data?.id) {
    throw new Error("Failed to create BTW session")
  }

  btwSessionCache.set(parentID, session.data.id)
  return session.data.id
}

export async function promptBtwSession(
  client: OpencodeClient,
  btwSessionId: string,
  question: string,
  config: BtwConfig,
): Promise<string> {
  const result = await client.session.prompt({
    path: { id: btwSessionId },
    body: {
      parts: [{ type: "text", text: question }],
      ...(config.model ? { model: config.model } : {}),
      tools: { todowrite: false, todoread: false },
    },
  })

  if (result.error) {
    throw new Error(`BTW prompt failed: ${JSON.stringify(result.error)}`)
  }

  const answer = result.data?.parts?.findLast((p) => p.type === "text")?.text
  return answer ?? "(no answer returned)"
}

export async function saveToTranscript(
  client: OpencodeClient,
  sessionID: string,
  question: string,
  answer: string,
): Promise<void> {
  const text = `💡 BTW: ${question}\n\n${answer}`

  try {
    await client.session.prompt({
      path: { id: sessionID },
      body: {
        noReply: true,
        parts: [{ type: "text", text, ignored: true }],
      },
    })
  } catch (err) {
    client.app?.log({
      body: {
        service: "opencode-btw",
        level: "warn",
        message: "Failed to save BTW to transcript",
        extra: { error: err instanceof Error ? err.message : String(err) },
      },
    })
  }
}

export async function getBtwHistory(
  client: OpencodeClient,
  parentID: string,
): Promise<BtwEntry[]> {
  let btwSessionId: string
  try {
    btwSessionId = btwSessionCache.get(parentID) ?? ""
    if (!btwSessionId) {
      const children = await client.session.children({ path: { id: parentID } })
      const existing = children.data?.find((s) => s.title === BTW_TITLE_PREFIX)
      if (!existing) return []
      btwSessionId = existing.id
      btwSessionCache.set(parentID, btwSessionId)
    }
  } catch {
    return []
  }

  try {
    const messages = await client.session.messages({ path: { id: btwSessionId } })
    if (!messages.data) return []

    const entries: BtwEntry[] = []
    const msgs = messages.data
    for (let i = 0; i < msgs.length; i++) {
      const msg = msgs[i]
      if (msg.role !== "user") continue
      const q = msg.parts?.find((p) => p.type === "text")?.text
      if (!q) continue
      const next = msgs[i + 1]
      const a = next?.parts?.find((p) => p.type === "text")?.text ?? ""
      entries.push({ question: q, answer: a, timestamp: Date.now() - (msgs.length - i) * 1000 })
    }

    return entries.reverse()
  } catch {
    return []
  }
}

export function clearBtwCache(parentID: string): void {
  btwSessionCache.delete(parentID)
}
