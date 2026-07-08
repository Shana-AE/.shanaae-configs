#!/usr/bin/env python3
"""
Lightweight HTTP server for MaiMemo TTS audio downloads.

Serves MP3 files from the audio directory with a simple file listing page.

Usage:
    python3 maimemo_audio_server.py                    # default port 28888
    python3 maimemo_audio_server.py --port 28888       # custom port
    python3 maimemo_audio_server.py --dir ~/audio      # custom directory
    python3 maimemo_audio_server.py --host 0.0.0.0     # listen on all interfaces (careful!)

Endpoints:
    GET /              - File listing page (HTML)
    GET /list          - JSON file list
    GET /<filename>    - Download file
"""

import os
import sys
import json
import time
import socket
import argparse
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# Defaults
DEFAULT_PORT = 28888
DEFAULT_DIR = os.path.expanduser("~/maimemo-audio")


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_time(timestamp: float) -> str:
    """Format timestamp for display."""
    import datetime
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M")


LISTING_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MaiMemo Audio Library</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
  }}
  h1 {{
    color: #e94560;
    font-size: 1.5em;
    margin-bottom: 8px;
  }}
  .subtitle {{
    color: #888;
    font-size: 0.85em;
    margin-bottom: 24px;
  }}
  .file-list {{
    list-style: none;
  }}
  .file-item {{
    display: flex;
    align-items: center;
    padding: 14px 16px;
    margin-bottom: 8px;
    background: #16213e;
    border-radius: 10px;
    transition: background 0.2s;
  }}
  .file-item:hover {{
    background: #1a2744;
  }}
  .file-icon {{
    font-size: 1.8em;
    margin-right: 14px;
    flex-shrink: 0;
  }}
  .file-info {{
    flex: 1;
    min-width: 0;
  }}
  .file-name {{
    font-weight: 600;
    color: #e0e0e0;
    word-break: break-all;
  }}
  .file-meta {{
    font-size: 0.8em;
    color: #888;
    margin-top: 4px;
  }}
  .download-btn {{
    background: #e94560;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9em;
    text-decoration: none;
    white-space: nowrap;
    flex-shrink: 0;
  }}
  .download-btn:hover {{
    background: #c73652;
  }}
  .empty {{
    text-align: center;
    padding: 60px 20px;
    color: #666;
  }}
  .empty-icon {{
    font-size: 3em;
    display: block;
    margin-bottom: 16px;
  }}
  .refresh {{
    font-size: 0.8em;
    color: #888;
    text-align: center;
    margin-top: 20px;
  }}
  audio {{
    width: 100%;
    margin-top: 4px;
    height: 28px;
  }}
</style>
</head>
<body>
<h1>🎧 MaiMemo Audio Library</h1>
<p class="subtitle">English vocabulary stories read by 艾丽妮 (钉宫理恵 voice) · {count} files · Directory: {dir}</p>
<ul class="file-list">
{items}
</ul>
<p class="refresh">🕐 Generated at {time}</p>
</body>
</html>"""

FILE_ITEM_HTML = """<li class="file-item">
  <span class="file-icon">🎵</span>
  <div class="file-info">
    <div class="file-name">{name}</div>
    <div class="file-meta">{size} · {date}</div>
    <audio controls preload="none">
      <source src="{url}" type="audio/mpeg">
    </audio>
  </div>
  <a class="download-btn" href="{url}" download>⬇ 下载</a>
</li>"""


class AudioServerHandler(SimpleHTTPRequestHandler):
    """Custom handler for serving audio files with a listing page."""

    audio_dir = DEFAULT_DIR
    server_start_time = ""

    def log_message(self, format, *args):
        """Suppress default logging or use custom format."""
        if args[0] != "GET" or "/favicon.ico" not in str(args):
            print(f"[audio-server] {self.client_address[0]} - {format % args}")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)

        # Serve the listing page
        if path == "/" or path == "/index.html":
            self.serve_listing()
            return

        # JSON API
        if path == "/list":
            self.serve_json_list()
            return

        # Serve a file from the audio directory
        if path.startswith("/"):
            filename = path.lstrip("/")
            # Security: prevent directory traversal
            safe_name = os.path.basename(filename)
            filepath = os.path.join(self.audio_dir, safe_name)

            if not os.path.isfile(filepath):
                self.send_error(404, "File not found")
                return

            self.send_response(200)
            if filepath.endswith(".mp3"):
                self.send_header("Content-Type", "audio/mpeg")
            elif filepath.endswith(".wav"):
                self.send_header("Content-Type", "audio/wav")
            elif filepath.endswith(".ogg"):
                self.send_header("Content-Type", "audio/ogg")
            else:
                self.send_header("Content-Type", "application/octet-stream")

            self.send_header("Content-Disposition",
                           f'attachment; filename="{safe_name}"')
            self.send_header("Content-Length", str(os.path.getsize(filepath)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()

            with open(filepath, "rb") as f:
                self.wfile.write(f.read())
            return

        self.send_error(404, "Not found")

    def serve_listing(self):
        """Serve the HTML file listing page."""
        files = self.get_audio_files()
        items_html = ""

        if not files:
            items_html = (
                '<div class="empty">'
                '<span class="empty-icon">📭</span>'
                "<p>还没有音频文件</p>"
                "<p style=\"font-size:0.8em;margin-top:8px;\">No audio files yet — generate one with maimemo_tts.py</p>"
                "</div>"
            )
        else:
            for f in sorted(files, key=lambda x: x["mtime"], reverse=True):
                url = urllib.parse.quote(f["name"])
                items_html += FILE_ITEM_HTML.format(
                    name=f["name"],
                    size=format_size(f["size"]),
                    date=format_time(f["mtime"]),
                    url=url,
                )

        now = format_time(time.time())
        html = LISTING_HTML.format(
            count=len(files),
            dir=self.audio_dir,
            items=items_html,
            time=now,
        )

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def serve_json_list(self):
        """Serve file list as JSON."""
        files = self.get_audio_files()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(files, ensure_ascii=False).encode("utf-8"))

    def get_audio_files(self) -> list[dict]:
        """Get list of audio files in the audio directory."""
        files = []
        try:
            for entry in os.scandir(self.audio_dir):
                if entry.is_file() and entry.name.endswith(('.mp3', '.wav', '.ogg', '.aac')):
                    stat = entry.stat()
                    files.append({
                        "name": entry.name,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                    })
        except FileNotFoundError:
            pass
        return files


def main():
    parser = argparse.ArgumentParser(
        description="MaiMemo Audio Server — lightweight HTTP file server"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to listen on (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--dir", "-d",
        default=DEFAULT_DIR,
        help=f"Audio directory to serve (default: {DEFAULT_DIR})",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1, use 0.0.0.0 for LAN access)",
    )

    args = parser.parse_args()
    audio_dir = os.path.expanduser(args.dir)
    os.makedirs(audio_dir, exist_ok=True)

    AudioServerHandler.audio_dir = audio_dir

    # Use dual-stack IPv6 socket to support both IPv4 and IPv6
    class DualStackServer(HTTPServer):
        address_family = socket.AF_INET6
        
        def server_bind(self):
            # Disable IPV6_V6ONLY to allow IPv4 connections too
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            super().server_bind()

    bind_addr = (args.host, args.port)
    server = DualStackServer(bind_addr, AudioServerHandler)

    print(f"""
╔══════════════════════════════════════════════╗
║     🎧 MaiMemo Audio Server                 ║
╠══════════════════════════════════════════════╣
║  Directory : {audio_dir:<32}║
║  URL       : http://{args.host}:{args.port:<32}║
║  Press Ctrl+C to stop                        ║
╚══════════════════════════════════════════════╝
""")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[audio-server] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
