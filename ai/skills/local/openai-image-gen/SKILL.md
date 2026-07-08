---
name: openai-image-gen
description: Generate images using gpt-image-2 via ChatGPT Plus/Pro OAuth subscription (no API key, no API costs). Use when the user asks to create/generate/draw/paint images using their ChatGPT subscription, or when they mention GPT Image, openai image gen, or free image generation. Triggers on generate image with chatgpt, draw with gpt, 生成图片, 画图 (when Qiniu is not preferred).
---

# OpenAI Image Generation via ChatGPT Plus OAuth

Generate images using `gpt-image-2` through your **ChatGPT Plus/Pro subscription** — zero API costs, billed against your subscription's image generation quota.

## Prerequisites

- ChatGPT Plus or Pro subscription
- OpenAI OAuth configured in opencode (`opencode auth login` → select OpenAI)
- Credentials stored at `~/.local/share/opencode/auth.json`

## Quick Start

```bash
python3 ~/.shanaae/configs/ai/skills/local/openai-image-gen/scripts/gen_image.py \
  --prompt "a cute pixel art cat" \
  --output /tmp/image.png
```

## How It Works

This skill uses the **Codex Responses API** (`chatgpt.com/backend-api/codex/responses`) — the same backend that opencode uses for chat models. Image generation is triggered by the built-in `image_generation` tool within the Responses API.

1. Reads OAuth token from opencode's auth store
2. Refreshes the token if expired (via `auth.openai.com/oauth/token`)
3. Sends a streaming Responses API request with `tools: [{"type": "image_generation"}]`
4. Parses the SSE stream and extracts the base64 image from `response.completed`

## Usage Examples

### Basic generation

```bash
python3 scripts/gen_image.py -p "sunset over mountains, oil painting style" -o painting.png
```

### Image editing (image-to-image)

```bash
python3 scripts/gen_image.py -p "make the background a beach" -i input.png -o edited.png
```

### In-context (agent calling the skill)

When you (the agent) need to generate an image, run:

```bash
source ~/.secrets
OUT="${OPENAI_IMAGE_OUTPUT_DIR:-/tmp/openai-images}"
mkdir -p "$OUT"

python3 ~/.shanaae/configs/ai/skills/local/openai-image-gen/scripts/gen_image.py \
  --prompt "DESCRIPTION" \
  --output "$OUT/image.png"
```

## Parameters

| Parameter    | Flag        | Default     | Description                          |
| ------------ | ----------- | ----------- | ------------------------------------ |
| `prompt`     | `-p`        | Required    | Text description of the image        |
| `output`     | `-o`        | `image.png` | Output file path                     |
| `model`      | `-m`        | `gpt-5.5`   | Codex model (must be Codex-supported)|
| `image`      | `-i`        | None        | Reference image for editing mode     |

## Comparison with Qiniu

| Feature             | ChatGPT Plus OAuth (this skill)     | Qiniu API (`qiniu-media-gen` skill) |
| ------------------- | ----------------------------------- | ----------------------------------- |
| Cost                | **Free** (subscription quota)       | ~$0.03/image                        |
| Model               | gpt-image-2                         | gpt-image-2, Kling, Gemini           |
| Speed               | ~10-30s                             | ~2-10s (sync models)                 |
| Rate limits         | ChatGPT Plus limits (~50/day)       | Pay-per-use, no limit                |
| Image editing       | Supported (reference image)         | Not supported via API                |
| Async polling       | No (streaming)                      | Yes (Kling models)                   |

## Troubleshooting

- **"No OpenAI OAuth credentials"**: Run `opencode auth login`, select OpenAI, complete browser login
- **"Failed to refresh token"**: The refresh token may have expired. Run `opencode auth login` again
- **Empty response / timeout**: The Codex backend may be overloaded. Retry or use Qiniu as fallback
- **Rate limit**: ChatGPT Plus has daily image generation limits. Check chatgpt.com for quota status
