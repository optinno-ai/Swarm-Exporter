#!/usr/bin/env python3
"""Command-line entry point for Swarm Exporter."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from swarm_exporter import (
    DEFAULT_API_VERSION,
    PAGE_SIZE,
    create_default_output_dir,
    download_photos,
    fetch_all,
    request_page,
    write_outputs,
)


LOGIN_URL = "https://ja.swarmapp.com/login"
HISTORY_URL = "https://ja.swarmapp.com/history"
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,256}$")
ALLOWED_COOKIE_DOMAINS = ("swarmapp.com", "foursquare.com")
ALLOWED_API_HOSTS = ("api.foursquare.com",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="専用ブラウザでSwarmへログインし、全チェックインをJSON/CSVへ出力します。"
    )
    parser.add_argument(
        "--output-dir",
        help="出力先 (省略時: カレントディレクトリのSwarm-Exporter、重複時は連番)",
    )
    parser.add_argument("--version", default=DEFAULT_API_VERSION)
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE, choices=range(1, 251), metavar="1-250")
    parser.add_argument("--timeout", type=int, default=600, help="ログイン待機秒数 (default: 600)")
    parser.add_argument("--data-only", action="store_true", help="JSONとCSVだけを取得し、写真を保存しない")
    return parser.parse_args()


def valid_token(value: str | None) -> str | None:
    value = (value or "").strip()
    return value if TOKEN_PATTERN.fullmatch(value) else None


def token_from_request(request: Any) -> str | None:
    parsed = urlparse(request.url)
    if parsed.hostname not in ALLOWED_API_HOSTS or not parsed.path.startswith("/v2/"):
        return None

    token = valid_token((parse_qs(parsed.query).get("oauth_token") or [None])[0])
    if token:
        return token

    try:
        headers = request.all_headers()
    except Exception:
        headers = request.headers
    authorization = headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return valid_token(authorization[7:])
    return None


def is_checkin_token(token: str, version: str) -> bool:
    try:
        payload = request_page(token, version, 1, 0)
    except RuntimeError:
        return False
    return payload.get("meta", {}).get("code") == 200


def open_history_page(page: Any) -> bool:
    """Open history to trigger the v2 API request containing the usable token."""
    try:
        page.goto(HISTORY_URL, wait_until="domcontentloaded", timeout=60_000)
    except Exception:
        return False
    return True


def token_from_cookies(context: Any) -> str | None:
    for cookie in context.cookies():
        domain = cookie.get("domain", "").lstrip(".").lower()
        if (
            cookie.get("name") == "oauth_token"
            and any(domain == allowed or domain.endswith("." + allowed) for allowed in ALLOWED_COOKIE_DOMAINS)
        ):
            token = valid_token(cookie.get("value"))
            if token:
                return token
    return None


def find_chromium() -> str | None:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        str(Path.home() / "Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        str(Path.home() / "Applications/Chromium.app/Contents/MacOS/Chromium"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    return next((path for path in candidates if path and Path(path).exists()), None)


def acquire_token(timeout: int, version: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError(
            "Playwrightがありません。`python3 -m pip install -r requirements.txt`を実行してください。"
        ) from error

    captured: list[str] = []
    rejected: set[str] = set()
    history_open_attempted = False
    with tempfile.TemporaryDirectory(prefix="swarm-exporter-browser-") as profile_dir:
        with sync_playwright() as playwright:
            launch_options: dict[str, Any] = {
                "user_data_dir": profile_dir,
                "headless": False,
                "args": ["--no-first-run", "--no-default-browser-check"],
            }
            executable = find_chromium()
            if executable:
                launch_options["executable_path"] = executable

            try:
                context = playwright.chromium.launch_persistent_context(**launch_options)
            except Exception as error:
                raise RuntimeError(
                    "Chrome/Chromiumを起動できません。Google Chrome、Microsoft Edge、"
                    "Chromiumのいずれかをインストールしてください。"
                ) from error

            def inspect_request(request: Any) -> None:
                token = token_from_request(request)
                if token:
                    captured.append(token)

            context.on("request", inspect_request)
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
            print("専用ブラウザでSwarmへログインしてください。", file=sys.stderr)
            print("tokenを検出するとブラウザは自動で閉じます。", file=sys.stderr)

            deadline = time.monotonic() + timeout
            try:
                while time.monotonic() < deadline:
                    candidates = list(captured)
                    cookie_token = token_from_cookies(context)
                    if cookie_token:
                        candidates.append(cookie_token)
                    for candidate in candidates:
                        if candidate in rejected:
                            continue
                        if is_checkin_token(candidate, version):
                            return candidate
                        rejected.add(candidate)
                        print(
                            "API用ではないtoken候補を除外し、通信の監視を続けます。",
                            file=sys.stderr,
                        )
                        if not history_open_attempted:
                            history_open_attempted = True
                            if open_history_page(page):
                                print(
                                    "ログインを確認し、履歴ページを自動で開きます。",
                                    file=sys.stderr,
                                )
                            else:
                                print(
                                    f"履歴ページを自動で開けませんでした。{HISTORY_URL}を開いてください。",
                                    file=sys.stderr,
                                )
                    if not context.pages:
                        raise RuntimeError("tokenを検出する前にブラウザが閉じられました。")
                    page.wait_for_timeout(500)
            finally:
                context.close()

    raise RuntimeError(f"{timeout}秒以内にtokenを検出できませんでした。")


def main() -> int:
    args = parse_args()
    try:
        token = acquire_token(args.timeout, args.version)
        print("ログインを確認しました。チェックインを取得します。", file=sys.stderr)
        items = fetch_all(token, args.version, args.page_size)
        output_dir = Path(args.output_dir) if args.output_dir else create_default_output_dir()
        json_path, csv_path = write_outputs(items, output_dir)
        if not args.data_only:
            download_photos(items, output_dir)
    except (RuntimeError, ValueError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1

    print(f"完了: {len(items)}件", file=sys.stderr)
    print(json_path)
    print(csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
