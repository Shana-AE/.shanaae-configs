# Figma MCP Usage Rules

Applies to every Figma-driven design-to-code or UI-revision task, on either the
remote `figma` server (`https://mcp.figma.com/mcp`) or the desktop `Figma-Desktop`
fallback (`http://127.0.0.1:3845/mcp`).

## Required flow (do not skip)

1. Fetch structured design context for the exact node(s) first — `get_code`
   (remote server) or `get_design_context` (desktop server). The Figma URL's
   `node-id` query param identifies the node; never guess node IDs.
2. If the response is too large or truncated: run `get_metadata` for the
   high-level node map, then re-fetch ONLY the required node(s).
3. Run `get_screenshot` for a visual reference of the exact variant being
   implemented.
4. Only after you have both design context and screenshot: download needed
   assets, then start implementation.
5. Treat MCP output (a React + Tailwind representation) as a description of
   design and behavior — NOT as final code style.
6. Validate against Figma for 1:1 look and behavior before marking the task
   complete (screenshot comparison per the frontend-visual-verify skill).

## Implementation rules

- Translate into THIS project's conventions: Vue 3 `<script setup lang="ts">`,
  and the project's styling system (UnoCSS / Element Plus / Reka UI tokens) —
  replace Tailwind utility classes with project equivalents.
- Reuse existing components (buttons, inputs, typography, icon wrappers)
  instead of duplicating functionality.
- Use the project's color system, typography scale, and spacing tokens
  consistently. Pull Figma variables via `get_variable_defs` (remote) when
  available; never hardcode values that exist as tokens.
- Respect existing routing, state management (Pinia), and data-fetching
  patterns already adopted in the repo.
- Strive for 1:1 visual parity. On conflict, prefer design-system tokens and
  adjust spacing/sizes minimally to match the visuals.

## Assets

- The Figma MCP server provides an assets endpoint that serves image and SVG
  assets.
- IMPORTANT: if the response returns a `localhost` source for an image or SVG,
  use that source directly.
- IMPORTANT: do NOT import or add new icon packages — all assets should come
  from the Figma payload.
- IMPORTANT: do NOT use or create placeholders when a real asset source is
  provided.
