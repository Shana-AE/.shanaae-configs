import type { Plugin } from "@opencode-ai/plugin"

// Root cause (2026-09-07, fe-infra session ses_f94348851ffeD3e32uaAS0cjzM):
// When a tool returns an image attachment with empty text output (e.g.
// Figma-Desktop_get_screenshot), opencode builds a message part containing
// [{type:"text",text:""}, {type:"image_url",...}] on the wire. The GLM
// upstream (Zhipu) rejects empty text blocks in multimodal content, and Qiniu
// surfaces it as the opaque 400:
//   "API 调用参数有误，请检查文档。 (type: upstream_error)"
// Every retry replays the identical payload, bricking the session turn.
//
// Fix: give empty tool outputs a placeholder so the text part is never empty.
// Verified against api.qnaigc.com/v1 (z-ai/glm-5.3-flash):
//   [{text:""}, image]          -> 400
//   [{text:"(no output)"}, image] -> 200
// Generic across providers: "(no output)" is what opencode's TUI already
// displays for empty tool results, so semantics are unchanged for models.

const PLACEHOLDER = "(no output)"

export const FixEmptyToolOutputPlugin: Plugin = async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (typeof output.output === "string" && output.output.trim() === "") {
        output.output = PLACEHOLDER
      }
    },
  }
}
