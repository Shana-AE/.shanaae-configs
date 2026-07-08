#!/usr/bin/env python3
"""
MaiMemo TTS Generator
Extracts English text from MaiMemo daily story articles and generates
audio using GPT-SoVITS (钉宫理恵 voice).

Usage:
    python3 maimemo_tts.py --file /tmp/article.md
    python3 maimemo_tts.py --file /tmp/article.md --output ~/maimemo-audio/
    python3 maimemo_tts.py --text "Hello world" --title "test"

Output: MP3 file saved to ~/maimemo-audio/ with filename matching article title.
"""

import os
import re
import sys
import json
import argparse
import tempfile
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

# Configuration
TTS_API_URL = os.environ.get("MAIMEMO_TTS_API", "http://127.0.0.1:9880/")
TTS_REF_AUDIO = os.environ.get(
    "MAIMEMO_TTS_REF_AUDIO",
    "/Users/shanaae/GPT-SoVITS/reference_audios/ailini_ref.wav",
)
TTS_PROMPT_TEXT = os.environ.get("MAIMEMO_TTS_PROMPT_TEXT", "こんにちは、私はアリーニです。")
TTS_PROMPT_LANG = os.environ.get("MAIMEMO_TTS_PROMPT_LANG", "ja")
AUDIO_OUTPUT_DIR = os.path.expanduser(
    os.environ.get("MAIMEMO_AUDIO_DIR", "~/maimemo-audio")
)

# Characters per TTS chunk — English text is shorter after synthesis,
# but we chunk conservatively for API stability
CHUNK_SIZE = int(os.environ.get("MAIMEMO_TTS_CHUNK_SIZE", "500"))


def extract_english_paragraphs(markdown_text: str) -> str:
    """
    Extract English-only story paragraphs from a MaiMemo article.
    Skips frontmatter, callout blocks, word notes, review sections, tables.
    """
    lines = markdown_text.split("\n")
    result = []
    in_frontmatter = False
    in_callout = False
    in_table = False
    frontmatter_dashes = 0

    for line in lines:
        stripped = line.strip()

        # Handle YAML frontmatter
        if stripped == "---":
            if not in_frontmatter:
                in_frontmatter = True
                frontmatter_dashes += 1
                continue
            elif in_frontmatter:
                frontmatter_dashes += 1
                if frontmatter_dashes >= 2:
                    in_frontmatter = False
                continue

        if in_frontmatter:
            continue

        # Handle callout blocks (> [!...])
        if stripped.startswith("> ["):
            in_callout = True
            continue

        if in_callout:
            if stripped == "":
                # Empty line might end callout or be inside
                continue
            if not stripped.startswith(">"):
                # Non-quote line — callout ended
                in_callout = False
            else:
                continue

        # Skip table rows
        if stripped.startswith("|"):
            in_table = True
            continue
        if in_table and not stripped.startswith("|"):
            in_table = False

        # Skip markdown headers (but keep section titles)
        if stripped.startswith("#"):
            # Keep ## Part N: titles as section breaks
            if stripped.startswith("## "):
                result.append("")  # paragraph break
            continue

        # Skip empty lines
        if stripped == "":
            continue

        # Skip tag lines, metadata
        if stripped.startswith("tags:") or stripped.startswith("date:"):
            continue

        # Skip lines that are purely Chinese or Japanese
        if re.match(r"^[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+", stripped):
            continue

        # This is likely an English paragraph
        result.append(stripped)

    # Join and clean up
    text = " ".join(result)
    # Remove markdown bold markers for TTS
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # Remove 🗑️ emoji markers
    text = text.replace("🗑️", "")
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text


def split_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Split text into chunks at sentence boundaries."""
    if len(text) <= chunk_size:
        return [text]

    # Split by sentence-ending punctuation
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= chunk_size:
            if current:
                current += " " + sentence
            else:
                current = sentence
        else:
            if current:
                chunks.append(current)
            # If a single sentence is longer than chunk_size, split it
            if len(sentence) > chunk_size:
                # Force split at word boundaries
                words = sentence.split()
                sub_chunk = ""
                for word in words:
                    if len(sub_chunk) + len(word) + 1 <= chunk_size:
                        if sub_chunk:
                            sub_chunk += " " + word
                        else:
                            sub_chunk = word
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                        sub_chunk = word
                if sub_chunk:
                    current = sub_chunk
                else:
                    current = ""
            else:
                current = sentence

    if current:
        chunks.append(current)

    return chunks


def call_tts_api(text: str, text_language: str = "en") -> bytes:
    """Call GPT-SoVITS TTS API and return WAV audio bytes."""
    payload = {
        "text": text,
        "text_language": text_language,
        "refer_wav_path": TTS_REF_AUDIO,
        "prompt_text": TTS_PROMPT_TEXT,
        "prompt_language": TTS_PROMPT_LANG,
    }

    data = json.dumps(payload).encode("utf-8")
    req = Request(
        TTS_API_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=120) as resp:
            if resp.status == 200:
                return resp.read()
            else:
                error_body = resp.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"TTS API error {resp.status}: {error_body}")
    except URLError as e:
        raise RuntimeError(f"TTS API request failed: {e}")


def concat_wav_files(wav_data_list: list[bytes]) -> bytes:
    """Concatenate multiple WAV audio chunks into a single WAV file."""
    if len(wav_data_list) == 1:
        return wav_data_list[0]

    import struct
    import io

    # Parse first WAV for header info
    first = wav_data_list[0]
    # WAV header is 44 bytes for standard PCM
    header = first[:44]
    sample_rate = struct.unpack_from("<I", header, 24)[0]
    bits_per_sample = struct.unpack_from("<H", header, 34)[0]
    num_channels = struct.unpack_from("<H", header, 22)[0]

    # Collect PCM data from all chunks (skip headers)
    pcm_chunks = []
    total_samples = 0

    for wav_data in wav_data_list:
        # Find the data chunk marker
        data_start = wav_data.find(b"data")
        if data_start == -1:
            # If no "data" marker, assume 44-byte header
            data_start = 44
        else:
            data_start += 8  # "data" (4) + size (4)

        pcm_data = wav_data[data_start:]
        pcm_chunks.append(pcm_data)
        total_samples += len(pcm_data) // (bits_per_sample // 8 * num_channels)

    combined_pcm = b"".join(pcm_chunks)

    # Build new WAV header
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = len(combined_pcm)
    file_size = 36 + data_size

    output = io.BytesIO()
    output.write(b"RIFF")
    output.write(struct.pack("<I", file_size))
    output.write(b"WAVE")
    output.write(b"fmt ")
    output.write(struct.pack("<I", 16))  # chunk size
    output.write(struct.pack("<H", 1))  # PCM
    output.write(struct.pack("<H", num_channels))
    output.write(struct.pack("<I", sample_rate))
    output.write(struct.pack("<I", byte_rate))
    output.write(struct.pack("<H", block_align))
    output.write(struct.pack("<H", bits_per_sample))
    output.write(b"data")
    output.write(struct.pack("<I", data_size))
    output.write(combined_pcm)

    return output.getvalue()


def wav_to_mp3(wav_data: bytes) -> bytes:
    """Convert WAV audio to MP3 using ffmpeg."""
    proc = subprocess.run(
        [
            "ffmpeg",
            "-f", "wav",
            "-i", "pipe:0",
            "-codec:a", "libmp3lame",
            "-b:a", "128k",
            "-f", "mp3",
            "pipe:1",
        ],
        input=wav_data,
        capture_output=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {proc.stderr.decode()}")
    return proc.stdout


def generate_audio(
    text: str,
    title: str = "untitled",
    text_language: str = "en",
    output_dir: str = None,
) -> str:
    """
    Generate TTS audio from text and save as MP3.

    Args:
        text: English text to synthesize
        title: Base filename (without extension)
        text_language: Language code for TTS
        output_dir: Output directory (default: AUDIO_OUTPUT_DIR)

    Returns:
        Path to the generated MP3 file
    """
    if output_dir is None:
        output_dir = AUDIO_OUTPUT_DIR

    os.makedirs(output_dir, exist_ok=True)

    # Extract English paragraphs if input looks like a full markdown article
    if text.strip().startswith("---") or "## Part" in text or "## 🗑️" in text:
        print("[maimemo_tts] Detected markdown article, extracting English paragraphs...")
        text = extract_english_paragraphs(text)

    if not text.strip():
        raise ValueError("No English text found to synthesize")

    print(f"[maimemo_tts] Text length: {len(text)} chars")

    # Split into chunks
    chunks = split_text(text)
    print(f"[maimemo_tts] Split into {len(chunks)} chunk(s)")

    # Generate audio for each chunk
    wav_chunks = []
    for i, chunk in enumerate(chunks, 1):
        print(f"[maimemo_tts] Processing chunk {i}/{len(chunks)} ({len(chunk)} chars)...")
        wav_data = call_tts_api(chunk, text_language)
        wav_chunks.append(wav_data)
        print(f"[maimemo_tts] Chunk {i}/{len(chunks)} done ({len(wav_data)} bytes)")

    # Concatenate
    print("[maimemo_tts] Concatenating audio...")
    combined_wav = concat_wav_files(wav_chunks)

    # Convert to MP3
    print("[maimemo_tts] Converting to MP3...")
    mp3_data = wav_to_mp3(combined_wav)

    # Sanitize filename
    safe_title = re.sub(r"[^\w\s\-]", "", title).strip()
    safe_title = re.sub(r"\s+", "_", safe_title)
    if not safe_title:
        safe_title = "untitled"

    output_path = os.path.join(output_dir, f"{safe_title}.mp3")

    with open(output_path, "wb") as f:
        f.write(mp3_data)

    size_kb = len(mp3_data) / 1024
    print(f"[maimemo_tts] Saved: {output_path} ({size_kb:.1f} KB)")
    return output_path


def generate_from_file(
    file_path: str,
    title: str = None,
    output_dir: str = None,
) -> str:
    """Generate TTS audio from a markdown file."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if title is None:
        # Extract title from filename
        basename = os.path.splitext(os.path.basename(file_path))[0]
        title = basename

    return generate_audio(content, title=title, output_dir=output_dir)


def main():
    parser = argparse.ArgumentParser(
        description="MaiMemo TTS Generator — English text to 钉宫理恵 voice audio"
    )
    parser.add_argument(
        "--file", "-f",
        help="Path to markdown article file",
    )
    parser.add_argument(
        "--text", "-t",
        help="Direct text to synthesize",
    )
    parser.add_argument(
        "--title",
        help="Output filename (without extension)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output directory (default: ~/maimemo-audio/)",
    )
    parser.add_argument(
        "--language", "-l",
        default="en",
        help="Text language code (default: en)",
    )

    args = parser.parse_args()

    if args.file:
        output = generate_from_file(
            args.file,
            title=args.title,
            output_dir=args.output,
        )
    elif args.text:
        output = generate_audio(
            args.text,
            title=args.title or "custom",
            output_dir=args.output,
            text_language=args.language,
        )
    else:
        parser.error("Either --file or --text is required")

    print(output)  # Print path for scripting


if __name__ == "__main__":
    main()
