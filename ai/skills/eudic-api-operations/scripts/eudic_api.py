#!/usr/bin/env python3
import os
import sys
import json
import argparse
import requests
import http.client

def get_token():
    token = os.environ.get('EUDIC_TOKEN')
    if not token:
        print(json.dumps({"error": "EUDIC_TOKEN environment variable not set. Please set it to your Eudic API token."}))
        sys.exit(1)
    return token

def get_headers(token):
    return {
        'User-Agent': 'Mozilla/5.0',
        'Authorization': token,
        'Content-Type': 'application/json'
    }

BASE_URL = "https://api.frdic.com/api/open/v1/studylist"

def handle_response(response):
    try:
        if response.status_code == 204:
            print(json.dumps({"success": True, "message": "Operation successful (No Content)"}))
            return

        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except json.JSONDecodeError:
        print(json.dumps({
            "error": "Failed to decode JSON response",
            "status_code": response.status_code,
            "text": response.text
        }, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

def get_categories(args):
    token = get_token()
    url = f"{BASE_URL}/category"
    params = {'language': args.language}
    response = requests.get(url, headers=get_headers(token), params=params)
    handle_response(response)

def add_category(args):
    token = get_token()
    url = f"{BASE_URL}/category"
    payload = {
        "language": args.language,
        "name": args.name
    }
    response = requests.post(url, headers=get_headers(token), json=payload)
    handle_response(response)

def rename_category(args):
    token = get_token()
    url = f"{BASE_URL}/category"
    payload = {
        "id": args.id,
        "language": args.language,
        "name": args.name
    }
    response = requests.patch(url, headers=get_headers(token), json=payload)
    handle_response(response)

def delete_category(args):
    token = get_token()
    url = f"{BASE_URL}/category"
    payload = {
        "id": args.id,
        "language": args.language,
        "name": args.name if args.name else "" # Name might be required or optional, safer to pass empty if not provided but API doc says name is required in body? Wait, delete usually just needs ID. But API doc says "value" object with id, language, name. I'll pass name if user provides, or try empty string.
    }
    # Note: requests.delete with json payload
    response = requests.request("DELETE", url, headers=get_headers(token), json=payload)
    handle_response(response)

def get_words(args):
    token = get_token()
    url = f"{BASE_URL}/words"
    params = {
        "language": args.language,
        "category_id": args.category_id,
        "page": args.page,
        "page_size": args.page_size
    }
    response = requests.get(url, headers=get_headers(token), params=params)
    handle_response(response)

def add_words(args):
    token = get_token()
    url = f"{BASE_URL}/words"
    payload = {
        "language": args.language,
        "category_id": args.category_id,
        "words": args.words
    }
    response = requests.post(url, headers=get_headers(token), json=payload)
    handle_response(response)

def delete_words(args):
    token = get_token()
    url = f"{BASE_URL}/words"
    payload = {
        "language": args.language,
        "category_id": args.category_id,
        "words": args.words
    }
    response = requests.request("DELETE", url, headers=get_headers(token), json=payload)
    handle_response(response)

def add_word(args):
    token = get_token()
    url = f"{BASE_URL}/word"
    payload = {
        "language": args.language,
        "word": args.word,
        "star": args.star,
        "context_line": args.context_line,
        "category_ids": args.category_ids
    }
    response = requests.post(url, headers=get_headers(token), json=payload)
    handle_response(response)

def get_word(args):
    token = get_token()
    url = f"{BASE_URL}/word"
    params = {
        "language": args.language,
        "word": args.word
    }
    response = requests.get(url, headers=get_headers(token), params=params)
    handle_response(response)

def main():
    parser = argparse.ArgumentParser(description="Eudic API CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # 1. Get Categories
    p_get_cat = subparsers.add_parser("get-categories", help="Get all categories")
    p_get_cat.add_argument("--language", default="en", help="Language (default: en)")
    p_get_cat.set_defaults(func=get_categories)

    # 2. Add Category
    p_add_cat = subparsers.add_parser("add-category", help="Add a new category")
    p_add_cat.add_argument("--name", required=True, help="Category name")
    p_add_cat.add_argument("--language", default="en", help="Language (default: en)")
    p_add_cat.set_defaults(func=add_category)

    # 3. Rename Category
    p_rename_cat = subparsers.add_parser("rename-category", help="Rename a category")
    p_rename_cat.add_argument("--id", required=True, help="Category ID")
    p_rename_cat.add_argument("--name", required=True, help="New name")
    p_rename_cat.add_argument("--language", default="en", help="Language (default: en)")
    p_rename_cat.set_defaults(func=rename_category)

    # 4. Delete Category
    p_del_cat = subparsers.add_parser("delete-category", help="Delete a category")
    p_del_cat.add_argument("--id", required=True, help="Category ID")
    p_del_cat.add_argument("--name", default="", help="Category name (required by API?)")
    p_del_cat.add_argument("--language", default="en", help="Language (default: en)")
    p_del_cat.set_defaults(func=delete_category)

    # 5. Get Words
    p_get_words = subparsers.add_parser("get-words", help="Get words from a category")
    p_get_words.add_argument("--category-id", default="0", help="Category ID (default: 0)")
    p_get_words.add_argument("--language", default="en", help="Language (default: en)")
    p_get_words.add_argument("--page", type=int, default=1, help="Page number")
    p_get_words.add_argument("--page-size", type=int, default=100, help="Page size")
    p_get_words.set_defaults(func=get_words)

    # 6. Add Words (Batch)
    p_add_words = subparsers.add_parser("add-words", help="Add words to a category")
    p_add_words.add_argument("--category-id", default="0", help="Category ID (default: 0)")
    p_add_words.add_argument("--language", default="en", help="Language (default: en)")
    p_add_words.add_argument("words", nargs="+", help="List of words to add")
    p_add_words.set_defaults(func=add_words)

    # 7. Delete Words
    p_del_words = subparsers.add_parser("delete-words", help="Delete words from a category")
    p_del_words.add_argument("--category-id", default="0", help="Category ID (default: 0)")
    p_del_words.add_argument("--language", default="en", help="Language (default: en)")
    p_del_words.add_argument("words", nargs="+", help="List of words to delete")
    p_del_words.set_defaults(func=delete_words)

    # 8. Add Word (Single)
    p_add_word = subparsers.add_parser("add-word", help="Add a single word with details")
    p_add_word.add_argument("--word", required=True, help="Word to add")
    p_add_word.add_argument("--language", default="en", help="Language (default: en)")
    p_add_word.add_argument("--star", type=int, default=0, help="Star rating (0-5)")
    p_add_word.add_argument("--context-line", help="Context sentence")
    p_add_word.add_argument("--category-ids", type=int, nargs="*", default=[0], help="Category IDs")
    p_add_word.set_defaults(func=add_word)

    # 9. Get Word
    p_get_word = subparsers.add_parser("get-word", help="Get details of a single word")
    p_get_word.add_argument("--word", required=True, help="Word to query")
    p_get_word.add_argument("--language", default="en", help="Language (default: en)")
    p_get_word.set_defaults(func=get_word)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
