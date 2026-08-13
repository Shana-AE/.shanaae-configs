#!/usr/bin/env python3

import argparse
import base64
import json
import mimetypes
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


BRIDGE_PROFILES = {
    "balanced": ["qwen/qwen3.5-plus", "gemini-2.5-flash-lite"],
    "economy": ["doubao-seed-2.0-mini", "gemini-2.5-flash-lite"],
}

SYSTEM_PROMPT = """You are a frontend visual QA inspector. Return one JSON object without Markdown fences, using exactly this schema: {"summary":"string","layout_issues":[],"style_issues":[],"responsive_issues":[],"uncertainties":[],"confidence":0.0}. All four issue fields MUST be JSON arrays. Confidence MUST be a JSON number from 0.0 to 1.0. Each issue must name the affected element, observable evidence, severity, and likely CSS cause. Be concise and do not invent details that are not visible."""


def parse_models_verbose(output: str) -> dict[str, dict]:
    records: dict[str, dict] = {}
    lines = output.splitlines()
    decoder = json.JSONDecoder()
    index = 0

    while index + 1 < len(lines):
        model_ref = lines[index].strip()
        if not model_ref or not lines[index + 1].lstrip().startswith("{"):
            index += 1
            continue

        remaining = "\n".join(lines[index + 1 :])
        try:
            model, end = decoder.raw_decode(remaining)
        except json.JSONDecodeError:
            index += 1
            continue

        records[model_ref] = model
        json_lines = remaining[:end].count("\n") + 1
        index += json_lines + 1

    return records


def resolve_route(model_ref: str, records: dict[str, dict]) -> str:
    capabilities = records.get(model_ref, {}).get("capabilities", {})
    image_input = capabilities.get("input", {}).get("image") is True
    attachment = capabilities.get("attachment") is True
    return "native" if attachment and image_input else "bridge"


def build_payload(model: str, images: list[tuple[str, bytes, str]], prompt: str) -> dict:
    content: list[dict] = [{"type": "text", "text": prompt}]
    for label, image_data, mime_type in images:
        image_url = f"data:{mime_type};base64,{base64.b64encode(image_data).decode('ascii')}"
        content.extend(
            [
                {"type": "text", "text": f"{label.title()} image:"},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]
        )

    return {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        "max_tokens": 800,
        "temperature": 0.1,
    }


def load_runtime_models(model_ref: str) -> dict[str, dict]:
    if "/" not in model_ref:
        raise ValueError("Model must include its provider prefix, for example qiniu/z-ai/glm-5.2")

    provider = model_ref.split("/", 1)[0]
    completed = subprocess.run(
        ["opencode", "models", provider, "--verbose"],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_models_verbose(completed.stdout)


def extract_content(response: dict) -> str:
    content = response["choices"][0]["message"]["content"]
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content if isinstance(part, dict)).strip()
    return json.dumps(content, ensure_ascii=False)


def parse_analysis(content: str) -> dict:
    cleaned = content.strip()
    object_start = cleaned.find("{")
    if object_start < 0:
        raise ValueError("Visual analysis does not contain a JSON object")
    analysis, _ = json.JSONDecoder().raw_decode(cleaned[object_start:])
    if not isinstance(analysis, dict):
        raise ValueError("Visual analysis must be a JSON object")

    list_fields = ["layout_issues", "style_issues", "responsive_issues", "uncertainties"]
    if not isinstance(analysis.get("summary"), str):
        raise ValueError("Visual analysis is missing a string summary")
    for field in list_fields:
        analysis.setdefault(field, [])
        if not isinstance(analysis[field], list):
            raise ValueError(f"Visual analysis field {field} must be an array")
    analysis["confidence"] = normalize_confidence(analysis.get("confidence"))
    return analysis


def normalize_confidence(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("Visual analysis confidence cannot be boolean")

    numeric: float | None = None
    if isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str):
        match = re.search(r"\d+(?:\.\d+)?", value)
        if match:
            numeric = float(match.group())
        else:
            labels = {"high": 0.8, "medium": 0.5, "low": 0.2}
            numeric = next((score for label, score in labels.items() if label in value.lower()), None)

    if numeric is None or numeric < 0:
        raise ValueError("Visual analysis confidence is missing or invalid")
    if numeric <= 1:
        return numeric
    if numeric <= 10:
        return numeric / 10
    if numeric <= 100:
        return numeric / 100
    raise ValueError("Visual analysis confidence must represent a value from 0 to 1")


def validate_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    parsed = urllib.parse.urlparse(normalized)
    if parsed.scheme != "https" or parsed.hostname not in {"api.qnaigc.com", "api.modelink.ai"}:
        raise ValueError("QINIU_AI_BASE_URL must be an HTTPS Qiniu AI endpoint")
    return normalized


def request_description(model: str, images: list[tuple[str, bytes, str]], prompt: str) -> str:
    api_key = os.environ.get("QINIU_AI_API_KEY")
    if not api_key:
        raise RuntimeError("QINIU_AI_API_KEY is not set")

    base_url = validate_base_url(os.environ.get("QINIU_AI_BASE_URL", "https://api.qnaigc.com/v1"))
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(build_payload(model, images, prompt)).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return extract_content(json.load(response))


def load_image(label: str, image: Path) -> tuple[str, bytes, str]:
    mime_type = mimetypes.guess_type(image.name)[0]
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError(f"Unsupported image type: {image}")
    return label, image.read_bytes(), mime_type


def describe(image: Path, reference: Path | None, prompt: str, profile: str) -> dict:
    images = [load_image("reference", reference)] if reference else []
    images.append(load_image("actual", image))
    failures: list[str] = []
    for model in BRIDGE_PROFILES[profile]:
        try:
            return {
                "route": "bridge",
                "model": model,
                "analysis": parse_analysis(request_description(model, images, prompt)),
            }
        except (
            IndexError,
            KeyError,
            RuntimeError,
            TimeoutError,
            TypeError,
            ValueError,
            urllib.error.HTTPError,
            urllib.error.URLError,
        ) as error:
            failures.append(f"{model}: {error}")

    raise RuntimeError("All visual bridge models failed: " + "; ".join(failures))


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve native vision or describe a frontend screenshot")
    commands = parser.add_subparsers(dest="command", required=True)

    route = commands.add_parser("route", help="Resolve native versus bridge vision")
    route.add_argument("--model", required=True, help="Active model as provider/model-id")

    describe_command = commands.add_parser("describe", help="Describe an image through the Qiniu vision bridge")
    describe_command.add_argument("image", type=Path)
    describe_command.add_argument("--reference", type=Path, help="Expected or Figma reference image")
    describe_command.add_argument(
        "--prompt",
        default="Identify concrete visual discrepancies and their likely frontend causes.",
    )
    describe_command.add_argument("--profile", choices=BRIDGE_PROFILES, default="balanced")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    try:
        if args.command == "route":
            records = load_runtime_models(args.model)
            print(json.dumps({"model": args.model, "route": resolve_route(args.model, records)}))
            return 0

        print(json.dumps(describe(args.image, args.reference, args.prompt, args.profile), ensure_ascii=False))
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
