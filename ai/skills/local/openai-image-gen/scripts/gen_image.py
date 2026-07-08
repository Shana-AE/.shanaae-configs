#!/usr/bin/env python3
"""Generate images via ChatGPT Plus/Pro OAuth (no API key needed).

Usage:
    python3 gen_image.py --prompt "a cute cat" [--output out.png] [--model gpt-image-2]
    python3 gen_image.py --prompt "edit this" --image input.png
"""
import json, subprocess, base64, argparse, os, sys, time, tempfile

AUTH_FILE = os.path.expanduser("~/.local/share/opencode/auth.json")
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_URL = "https://chatgpt.com/backend-api/codex/responses"


def get_token():
    """Read OAuth credentials from opencode auth store and refresh if needed."""
    with open(AUTH_FILE) as f:
        auth = json.load(f)
    oa = auth.get("openai", {})
    if oa.get("type") != "oauth":
        print("ERROR: No OpenAI OAuth credentials found in auth.json", file=sys.stderr)
        print("Run: opencode auth login  (then select OpenAI)", file=sys.stderr)
        sys.exit(1)

    access = oa["access"]
    expires = oa.get("expires", 0)

    if expires > time.time() * 1000:
        return access, oa["accountId"]

    # Refresh token
    for attempt in range(3):
        result = subprocess.run(
            [
                "curl", "-s", "-X", "POST", TOKEN_URL,
                "-H", "Content-Type: application/x-www-form-urlencoded",
                "--data-urlencode", f"refresh_token={oa['refresh']}",
                "--data-urlencode", "grant_type=refresh_token",
                "--data-urlencode", f"client_id={CLIENT_ID}",
                "--max-time", "15",
            ],
            capture_output=True, text=True, timeout=20,
        )
        if result.stdout and result.stdout.strip():
            tok = json.loads(result.stdout)
            if "access_token" in tok:
                return tok["access_token"], oa["accountId"]
        time.sleep(2)

    print("ERROR: Failed to refresh OpenAI OAuth token after 3 attempts", file=sys.stderr)
    sys.exit(1)


def generate_image(prompt, output_path, model="gpt-5.5", image_inputs=None, quality="auto"):
    """Generate an image via the Codex Responses API."""
    access, account_id = get_token()

    content = [{"type": "input_text", "text": prompt}]
    if image_inputs:
        for img_path in image_inputs:
            with open(img_path, "rb") as f:
                b64_img = base64.b64encode(f.read()).decode()
            ext = os.path.splitext(img_path)[1].lstrip(".") or "png"
            content.append({"type": "input_image", "image_url": f"data:image/{ext};base64,{b64_img}"})

    input_items = [{"type": "message", "role": "user", "content": content}]

    tools = [{"type": "image_generation"}]
    if quality != "auto":
        tools[0]["quality"] = quality

    body = json.dumps({
        "model": model,
        "input": input_items,
        "tools": tools,
        "store": False,
        "stream": True,
    })

    result = subprocess.run(
        [
            "curl", "-s", "-N", "--retry", "2",
            "-X", "POST", CODEX_URL,
            "-H", f"Authorization: Bearer {access}",
            "-H", f"ChatGPT-Account-Id: {account_id}",
            "-H", "Content-Type: application/json",
            "-H", "originator: opencode",
            "-d", body,
            "--max-time", "300",
        ],
        capture_output=True, text=True, timeout=310,
    )

    output = result.stdout
    if not output:
        print("ERROR: Empty response from API", file=sys.stderr)
        sys.exit(1)

    # Parse SSE stream for image data
    # Capture both completed images and partial images (fallback)
    last_partial_b64 = None
    image_saved = False
    error_msg = None

    for line in output.split("\n"):
        if not line.startswith("data: "):
            continue
        try:
            data = json.loads(line[6:])
        except json.JSONDecodeError:
            continue

        evt = data.get("type", "")

        # Capture error
        if evt == "error":
            error_msg = data.get("message", data.get("code", str(data)[:200]))

        # Capture partial images (progressive rendering, each contains full b64 so far)
        if evt == "response.image_generation_call.partial_image":
            item = data.get("item", data)
            b64 = item.get("result", "") if isinstance(item, dict) else ""
            if b64 and len(b64) > 1000:
                last_partial_b64 = b64

        # Final image from output_item.done event (contains complete base64)
        if evt == "response.output_item.done":
            item = data.get("item", {})
            if item.get("type") == "image_generation_call":
                b64 = item.get("result", "")
                if b64:
                    img_bytes = base64.b64decode(b64)
                    with open(output_path, "wb") as f:
                        f.write(img_bytes)
                    print(f"Saved: {output_path} ({len(img_bytes):,} bytes)")
                    image_saved = True

        # Usage info from completed event
        if evt == "response.completed":
            usage = data.get("response", {}).get("usage", {})
            if usage and image_saved:
                img_usage = usage.get("output_tokens_details", {})
                print(f"Tokens: {usage.get('total_tokens', '?')} total"
                      f" ({img_usage.get('image_tokens', '?')} image)")

    # Fallback: use last partial image if completed wasn't received
    if not image_saved and last_partial_b64:
        img_bytes = base64.b64decode(last_partial_b64)
        with open(output_path, "wb") as f:
            f.write(img_bytes)
        print(f"Saved (partial): {output_path} ({len(img_bytes):,} bytes)")
        image_saved = True

    if not image_saved:
        if error_msg:
            print(f"ERROR: {error_msg}", file=sys.stderr)
        else:
            print("ERROR: No image data found in response", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate images via ChatGPT Plus OAuth")
    parser.add_argument("--prompt", "-p", required=True, help="Image prompt")
    parser.add_argument("--output", "-o", default="image.png", help="Output file path")
    parser.add_argument("--model", "-m", default="gpt-5.5", help="Codex model (default: gpt-5.5)")
    parser.add_argument("--image", "-i", action="append", help="Reference image (repeatable for multiple)")
    parser.add_argument("--quality", "-q", default="auto", choices=["auto", "low", "medium", "high"],
                        help="Image quality (default: auto)")
    args = parser.parse_args()

    generate_image(args.prompt, args.output, args.model, args.image, args.quality)
