---
name: frontend-visual-verify
description: Use in OpenCode when a frontend task changes or evaluates rendered visual output, including CSS, layout, spacing, responsive behavior, modals, dialogs, visual regressions, UI polish, Figma fidelity, or screenshot matching.
---

# Frontend Visual Verification

## Overview

Render, inspect, compare, and iterate. Never claim a visual change is correct from source code or tests alone.

**REQUIRED SUB-SKILL:** Use `agent-browser` for routine rendered-page inspection. Use `web-devtools` only for deep performance, heap, or network debugging.

Set `<skill-dir>` below to the base directory reported when this skill is loaded. Use the available Python 3 launcher; do not resolve `scripts/` relative to the project. Route resolution requires the current OpenCode model ID. If the ID or capability metadata is unavailable, use the bridge.

## Workflow

1. Resolve the active model's visual route:
   ```bash
   python3 "<skill-dir>/scripts/vision_describe.py" route --model "<provider/model-id>"
   ```
2. **Verify the browser attachment first** (before trusting any snapshot):
   `agent-browser connect <port>` (and even `--cdp <port>` on the default session) can silently spawn its own isolated chromium instead of attaching to the user's real browser (the one they launched for debugging on a CDP port). That isolated browser has no session cookies, so it renders a logged-out page and produces false "not logged in" conclusions.
   - Ground truth: `curl -s --max-time 3 http://127.0.0.1:<port>/json/list | grep -oE '"url": "[^"]*"'` — the CDP tab list shows the user's actual tabs (e.g. a localhost dev tab + a staging/production tab). If your `agent-browser tab` list does **not** match this, you are driving the wrong browser.
   - To attach to the real browser, use a fresh named session: `agent-browser --session <name> --cdp <port> tab`, then confirm the user's tabs appear.
   - Cookies are **origin-scoped and per-profile**: a session on the staging/production domain (or another profile) is invisible to the localhost dev origin. Never report "user is not logged in" from a 登录 link until you have confirmed you are driving the correct browser *and* origin.
3. Open the rendered app with `agent-browser`. Capture a snapshot, computed styles, and bounding boxes for the changed elements.
4. Match the required viewport, theme, data state, fonts, and reduced-motion setting. Capture a screenshot.
5. Follow the resolved route:
   - `native`: read/attach the screenshot directly with the active model.
   - `bridge`: run the balanced visual describer:
     ```bash
     python3 "<skill-dir>/scripts/vision_describe.py" describe "<actual.png>" \
       --reference "<reference.png>" \
       --prompt "Identify concrete visual discrepancies and their likely CSS causes."
     ```
     Omit `--reference` when no expected screenshot exists; request a single-image UI audit instead.
6. Apply the smallest correction, render again, and repeat until the evidence matches. Check desktop and mobile when responsive behavior can change.

For Figma work, get the Figma node screenshot and compare it with the browser screenshot under identical dimensions. A text-only model must use the bridge for image interpretation.

## Routing Contract

| Runtime capability | Route |
| --- | --- |
| `attachment=true` and `input.image=true` | Native vision |
| False, incomplete, missing, or unknown | Bridge |

The balanced bridge uses `qwen/qwen3.5-plus`, then `gemini-2.5-flash-lite`. Use `--profile economy` for `doubao-seed-2.0-mini`. If Qiniu is unavailable, use `zai-mcp-server_ui_diff_check` for a reference comparison or `zai-mcp-server_ui_to_artifact` for one image only when quota permits. Otherwise report that only structural and computed-style verification was possible.

The bridge sends screenshots to Qiniu. Before calling it, crop or redact credentials, personal data, private messages, unreleased designs, and other content that must not leave the machine. If redaction would invalidate the check, use native vision or local geometry inspection instead.

## Common Mistakes

- Waiting for the user to request browser verification leaves visual regressions untested.
- Inferring vision support from a model name bypasses OpenCode's actual image-transport capability.
- Using Kimi K3 as a routine describer wastes roughly 20x the Qwen bridge cost.
- Treating a screenshot as inspectable by a text-only model creates false confidence.
- Stopping after the first screenshot verifies the bug, not the correction.
- Trusting `agent-browser connect <port>` without checking the CDP tab list — it may spawn its own cookie-less chromium, causing false "logged out" conclusions (see Workflow step 2).
