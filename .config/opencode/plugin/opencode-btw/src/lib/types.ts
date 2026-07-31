export type BtwConfig = {
  model: { providerID: string; modelID: string } | null
  keybind: string
  showSidebar: boolean
  keepSession: boolean
  toastDuration: number
}

export const DEFAULT_CONFIG: BtwConfig = {
  model: null,
  keybind: "ctrl+b",
  showSidebar: true,
  keepSession: true,
  toastDuration: 10000,
}

export type BtwEntry = {
  question: string
  answer: string
  timestamp: number
}

export const BTW_TITLE_PREFIX = "btw:side-questions"
