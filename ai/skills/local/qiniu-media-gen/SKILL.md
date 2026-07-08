---
name: qiniu-media-gen
description: Generate images and videos via Qiniu AI (Sufy) API. Use when the user asks to create/generate/draw/paint images or videos using AI models like GPT-Image-2, Gemini, Kling, or Veo. Triggers on generate image, create image, 生成图片, 画图, generate video, create video, 生成视频.
---

# Qiniu Media Generation

Generate images and videos through the Qiniu/Sufy AI inference API (`api.qnaigc.com`).

## Prerequisites

- `QINIU_AI_API_KEY` environment variable (loaded from `~/.secrets`)
- Output directory: `${QINIU_MEDIA_OUTPUT_DIR:-/tmp/qiniu-media}`

## Available Models

### Image Generation

| Model ID                       | Type | Notes                          |
| ------------------------------ | ---- | ------------------------------ |
| `openai/gpt-image-2`           | Sync | Sizes: `1024x1024`, `1792x1024`, `1024x1792`, `auto` |
| `gemini-2.5-flash-image`       | Sync | Fast, cheap                    |
| `gemini-3.0-pro-image-preview` | Sync | Higher quality                 |
| `kling-v2`                     | Async| Supports `aspect_ratio`        |
| `kling-v2-1`                   | Async| Image + video capable          |
| `kling-v1-5`                   | Async| Cheaper Kling                  |
| `kling-v1`                     | Async| Cheapest Kling                 |

### Video Generation (Veo only via API)

| Model ID                       | Notes                                   |
| ------------------------------ | --------------------------------------- |
| `veo-3.1-generate-001`         | Highest quality, supports audio         |
| `veo-3.1-fast-generate-001`    | Faster, supports audio                  |
| `veo-3.0-generate-001`         | Previous gen                            |
| `veo-3.0-fast-generate-001`    | Previous gen fast                       |
| `veo-2.0-generate-001`         | Legacy                                  |

> **Note**: Kling video (kling-v3, kling-v2-6, etc.), Vidu, Sora-2, and Doubao Seedance are listed on sufy.com but are NOT available via the API — only through the web console at <https://sufy.com/zh-CN/services/ai-inference/models>.

## API Reference

Base URL: `https://api.qnaigc.com/v1`
Auth header: `Authorization: Bearer $QINIU_AI_API_KEY`

### 1. Image Generation — Sync (OpenAI models)

Returns base64-encoded image immediately.

```bash
source ~/.secrets
OUT="${QINIU_MEDIA_OUTPUT_DIR:-/tmp/qiniu-media}"
mkdir -p "$OUT"

curl -s "https://api.qnaigc.com/v1/images/generations" \
  -H "Authorization: Bearer $QINIU_AI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-image-2",
    "prompt": "DESCRIPTION HERE",
    "n": 1,
    "size": "1024x1024"
  }' | python3 -c "
import json,sys,base64
d=json.load(sys.stdin)
if 'error' in d:
    print('ERROR:', d['error']['message']); sys.exit(1)
for i,item in enumerate(d['data']):
    path=f'$OUT/image_{i}.png'
    with open(path,'wb') as f: f.write(base64.b64decode(item['b64_json']))
    print(f'Saved: {path}')
"
```

### 2. Image Generation — Async (Kling models)

Returns a `task_id`; poll until complete, then download the URL.

```bash
source ~/.secrets
OUT="${QINIU_MEDIA_OUTPUT_DIR:-/tmp/qiniu-media}"
mkdir -p "$OUT"

# Step 1: Submit task
TASK_ID=$(curl -s "https://api.qnaigc.com/v1/images/generations" \
  -H "Authorization: Bearer $QINIU_AI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kling-v2",
    "prompt": "DESCRIPTION HERE",
    "n": 1,
    "aspect_ratio": "16:9"
  }' | python3 -c "import json,sys; print(json.load(sys.stdin).get('task_id',''))")

echo "Task: $TASK_ID"

# Step 2: Poll until done (usually 10-30s)
while true; do
  RESP=$(curl -s "https://api.qnaigc.com/v1/images/tasks/$TASK_ID" \
    -H "Authorization: Bearer $QINIU_AI_API_KEY")
  STATUS=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))")
  echo "  Status: $STATUS"
  [ "$STATUS" = "succeed" ] && break
  [ "$STATUS" = "failed" ] && { echo "FAILED"; echo "$RESP"; exit 1; }
  sleep 5
done

# Step 3: Download result
echo "$RESP" | python3 -c "
import json,sys,urllib.request
d=json.load(sys.stdin)
for i,item in enumerate(d.get('data',[])):
    url=item.get('url','')
    if not url: continue
    path=f'$OUT/image_{i}.png'
    urllib.request.urlretrieve(url, path)
    print(f'Saved: {path}')
"
```

### 3. Video Generation — Async (Veo models)

Returns a task `id`; poll until complete. Videos take 1-5 minutes.

```bash
source ~/.secrets
OUT="${QINIU_MEDIA_OUTPUT_DIR:-/tmp/qiniu-media}"
mkdir -p "$OUT"

# Step 1: Submit task
TASK_ID=$(curl -s "https://api.qnaigc.com/v1/videos/generations" \
  -H "Authorization: Bearer $QINIU_AI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "veo-3.1-fast-generate-001",
    "instances": [{
      "prompt": "DESCRIPTION HERE",
      "generate_audio": true
    }]
  }' | python3 -c "import json,sys; print(json.load(sys.stdin).get('id',''))")

echo "Task: $TASK_ID"

# Step 2: Poll until done (videos take 1-5 min)
while true; do
  RESP=$(curl -s "https://api.qnaigc.com/v1/videos/generations/$TASK_ID" \
    -H "Authorization: Bearer $QINIU_AI_API_KEY")
  STATUS=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))")
  echo "  Status: $STATUS"
  [ "$STATUS" = "succeed" ] && break
  [ "$STATUS" = "failed" ] && { echo "FAILED"; echo "$RESP"; exit 1; }
  sleep 10
done

# Step 3: Download result
echo "$RESP" | python3 -c "
import json,sys,urllib.request
d=json.load(sys.stdin)
videos=d.get('data',{}).get('videos',[])
for i,v in enumerate(videos):
    url=v if isinstance(v,str) else v.get('url','')
    if not url: continue
    ext='mp4'
    path=f'$OUT/video_{i}.{ext}'
    urllib.request.urlretrieve(url, path)
    print(f'Saved: {path}')
"
```

## Parameter Reference

### Image Generation Parameters

| Parameter      | Sync models       | Async (Kling) models | Description                    |
| -------------- | ----------------- | -------------------- | ------------------------------ |
| `model`        | Required          | Required             | Model ID from table above       |
| `prompt`       | Required          | Required             | Text description of the image   |
| `n`            | Optional (1)      | Optional (1)         | Number of images                |
| `size`         | `1024x1024` etc.  | —                    | Image dimensions (sync only)    |
| `aspect_ratio` | —                 | `1:1`, `16:9`, `9:16`, `4:3`, `3:2`, `21:9` | Aspect ratio (Kling only) |

### Video Generation Parameters

| Parameter                  | Description                              |
| -------------------------- | ---------------------------------------- |
| `model`                    | Required — Veo model ID                  |
| `instances`                | Required — array with `prompt` object    |
| `instances[].prompt`       | Required — video description             |
| `instances[].generate_audio` | `true` for videos with sound           |

## Tips

- **Sync image gen** is instant (2-5s). Use for quick iterations.
- **Async image gen** takes 10-30s. Kling models often produce better artistic results.
- **Video gen** takes 1-5 minutes. Use `veo-3.1-fast-generate-001` for speed, `veo-3.1-generate-001` for quality.
- For **image-to-image** or **image-to-video**, check the sufy.com docs for additional `image` field in the request.
- Costs: image gen ~$0.003-$0.03/image, video gen ~$0.10-$0.40/second.
