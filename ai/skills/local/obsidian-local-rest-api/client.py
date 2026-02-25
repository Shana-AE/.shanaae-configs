#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error
import ssl
import argparse

# Configuration
API_KEY = os.environ.get("OBSIDIAN_API_KEY")
BASE_URL = os.environ.get("OBSIDIAN_BASE_URL", "http://127.0.0.1:27123").rstrip("/")
VERIFY_SSL = os.environ.get("OBSIDIAN_VERIFY_SSL", "false").lower() == "true"

if not API_KEY:
    print("Error: OBSIDIAN_API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(1)

# SSL Context
ctx = ssl.create_default_context()
if not VERIFY_SSL:
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

def make_request(method, endpoint, data=None, params=None, headers=None):
    url = f"{BASE_URL}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    
    req_headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json"
    }
    if headers:
        req_headers.update(headers)
    
    encoded_data = None
    if data is not None:
        if isinstance(data, (dict, list)):
            encoded_data = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        else:
            encoded_data = data.encode("utf-8")
            if "Content-Type" not in req_headers:
                req_headers["Content-Type"] = "text/markdown"

    req = urllib.request.Request(url, data=encoded_data, headers=req_headers, method=method)
    
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            status = response.getcode()
            content = response.read().decode("utf-8")
            
            # Try to parse JSON if content-type says so, or if it looks like JSON
            content_type = response.headers.get("Content-Type", "")
            if "json" in content_type:
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    pass
            return content
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        try:
            err_body = e.read().decode("utf-8")
            print(f"Response: {err_body}", file=sys.stderr)
        except:
            pass
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}", file=sys.stderr)
        sys.exit(1)

def encode_path(path):
    # Obsidian API expects path components to be encoded
    # e.g. "folder/file.md" -> "folder/file.md" (if slashes allowed)
    # The MCP server splits by / and encodes each component.
    # We should probably do the same.
    return "/".join([urllib.parse.quote(part) for part in path.split("/")])

def read_note(path):
    encoded = encode_path(path)
    content = make_request("GET", f"/vault/{encoded}", headers={"Accept": "text/markdown"})
    print(content)

def list_notes(path):
    # Ensure path ends with / for directory listing
    path = path.strip("/")
    if path:
        encoded = encode_path(path)
        endpoint = f"/vault/{encoded}/"
    else:
        endpoint = "/vault/"
        
    result = make_request("GET", endpoint)
    if isinstance(result, dict) and "files" in result:
        for file in result["files"]:
            print(file)
    else:
        print(json.dumps(result, indent=2))

def update_note(path, content, mode="overwrite"):
    encoded = encode_path(path)
    if mode == "append":
        make_request("POST", f"/vault/{encoded}", data=content)
    elif mode == "prepend":
        # Prepend requires reading first then writing, or using PATCH if supported.
        # MCP server does read -> modify -> write for prepend.
        # For simplicity, let's just support append and overwrite (PUT) natively.
        print("Prepend not natively supported in this simple client. Use overwrite.", file=sys.stderr)
        sys.exit(1)
    else: # overwrite
        make_request("PUT", f"/vault/{encoded}", data=content)
    print(f"Successfully updated {path}")

def delete_note(path):
    encoded = encode_path(path)
    make_request("DELETE", f"/vault/{encoded}")
    print(f"Successfully deleted {path}")

def search_notes(query, context_length=100):
    # simple search
    result = make_request("POST", "/search/simple/", params={"query": query, "contextLength": context_length})
    print(json.dumps(result, indent=2))

def daily_note(action, content=None):
    # /periodic/daily/
    if action == "read":
        result = make_request("GET", "/periodic/daily/", headers={"Accept": "text/markdown"})
        print(result)
    elif action == "append":
        if content is None:
            print("Error: content required for append", file=sys.stderr)
            sys.exit(1)
        make_request("POST", "/periodic/daily/", data=content)
        print("Appended to daily note")
    elif action == "overwrite":
        if content is None:
            print("Error: content required for overwrite", file=sys.stderr)
            sys.exit(1)
        make_request("PUT", "/periodic/daily/", data=content)
        print("Updated daily note")

def main():
    parser = argparse.ArgumentParser(description="Obsidian Local REST API Client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Read
    read_parser = subparsers.add_parser("read", help="Read a note")
    read_parser.add_argument("path", help="Path to the note")

    # List
    list_parser = subparsers.add_parser("list", help="List notes in a folder")
    list_parser.add_argument("path", nargs="?", default="/", help="Folder path (default: root)")

    # Update (Write/Append)
    update_parser = subparsers.add_parser("update", help="Update a note")
    update_parser.add_argument("path", help="Path to the note")
    update_parser.add_argument("content", help="Content to write")
    update_parser.add_argument("--mode", choices=["overwrite", "append"], default="overwrite", help="Write mode")

    # Delete
    delete_parser = subparsers.add_parser("delete", help="Delete a note")
    delete_parser.add_argument("path", help="Path to the note")

    # Search
    search_parser = subparsers.add_parser("search", help="Search notes")
    search_parser.add_argument("query", help="Search query")

    # Daily Note
    daily_parser = subparsers.add_parser("daily", help="Interact with daily note")
    daily_parser.add_argument("action", choices=["read", "append", "overwrite"], help="Action to perform")
    daily_parser.add_argument("content", nargs="?", help="Content for append/overwrite")

    args = parser.parse_args()

    if args.command == "read":
        read_note(args.path)
    elif args.command == "list":
        list_notes(args.path)
    elif args.command == "update":
        update_note(args.path, args.content, args.mode)
    elif args.command == "delete":
        delete_note(args.path)
    elif args.command == "search":
        search_notes(args.query)
    elif args.command == "daily":
        daily_note(args.action, args.content)

if __name__ == "__main__":
    main()
