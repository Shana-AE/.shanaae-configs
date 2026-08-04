import type { BtwConfig } from "./types"
import { DEFAULT_CONFIG } from "./types"

export function loadConfig(raw?: unknown): BtwConfig {
  if (!raw || typeof raw !== "object") return { ...DEFAULT_CONFIG }

  const obj = raw as Record<string, unknown>
  const cfg: BtwConfig = { ...DEFAULT_CONFIG }

  if (obj.model && typeof obj.model === "object") {
    const m = obj.model as { providerID?: string; modelID?: string }
    if (m.providerID && m.modelID) {
      cfg.model = { providerID: m.providerID, modelID: m.modelID }
    }
  }

  if (typeof obj.keybind === "string") cfg.keybind = obj.keybind
  if (typeof obj.showSidebar === "boolean") cfg.showSidebar = obj.showSidebar
  if (typeof obj.keepSession === "boolean") cfg.keepSession = obj.keepSession
  if (typeof obj.toastDuration === "number") cfg.toastDuration = obj.toastDuration

  return cfg
}
