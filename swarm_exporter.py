#!/usr/bin/env python3
"""Export all check-ins for the authenticated Swarm/Foursquare user."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import getpass
import json
import locale
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


API_URL = "https://api.foursquare.com/v2/users/self/checkins"
DEFAULT_API_VERSION = "20231010"
PAGE_SIZE = 250
DEFAULT_OUTPUT_DIR_NAME = "Swarm-Exporter"
DEFAULT_LOCALE = "en"
LOCALE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*$")

CSV_COLUMNS = [
    "id",
    "created_at",
    "created_at_unix",
    "timezone_offset_minutes",
    "venue_id",
    "venue_name",
    "address",
    "city",
    "state",
    "postal_code",
    "country",
    "latitude",
    "longitude",
    "category",
    "shout",
    "photo_count",
    "photo_urls",
    "photo_files",
    "checkin_url",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Swarmの全チェックインを結合JSONとCSVへ出力します。"
    )
    parser.add_argument(
        "--output-dir",
        help="出力先 (省略時: カレントディレクトリのSwarm-Exporter、重複時は連番)",
    )
    parser.add_argument("--version", default=DEFAULT_API_VERSION, help="Foursquare API version date")
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE, choices=range(1, 251), metavar="1-250")
    parser.add_argument(
        "--locale",
        type=normalize_locale,
        default=None,
        help="APIの表示言語 (例: ja。省略時はOSのロケール)",
    )
    parser.add_argument("--data-only", action="store_true", help="写真をダウンロードしない")
    return parser.parse_args()


def get_token() -> str:
    token = os.environ.get("FOURSQUARE_OAUTH_TOKEN", "").strip()
    if not token and sys.stdin.isatty():
        token = getpass.getpass("OAuth token: ").strip()
    if not token:
        raise SystemExit("FOURSQUARE_OAUTH_TOKENを設定するか、対話入力でtokenを渡してください。")
    return token


def normalize_locale(value: str) -> str:
    """Convert an OS/API locale to a safe Accept-Language value."""
    candidate = value.strip().split(":", 1)[0].split(".", 1)[0].split("@", 1)[0]
    if not LOCALE_PATTERN.fullmatch(candidate):
        raise argparse.ArgumentTypeError(f"無効なロケールです: {value}")
    # Foursquare v2 documents language codes such as ja and pt, not regional
    # variants such as ja-JP and pt-BR.
    return candidate.replace("_", "-").split("-", 1)[0].lower()


def detect_os_locale() -> str:
    """Return the user's OS locale, ignoring generic C/POSIX process locales."""
    candidates: list[str | None] = []
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleLocale"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                candidates.append(result.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            pass

    current_locale = locale.getlocale()[0]
    candidates.extend(
        [
            current_locale,
            os.environ.get("LC_ALL"),
            os.environ.get("LC_MESSAGES"),
            os.environ.get("LANG"),
        ]
    )
    for candidate in candidates:
        if not candidate or candidate.upper().split(".", 1)[0] in {"C", "POSIX"}:
            continue
        try:
            return normalize_locale(candidate)
        except argparse.ArgumentTypeError:
            continue
    return DEFAULT_LOCALE


def request_page(
    token: str, version: str, limit: int, offset: int, api_locale: str
) -> dict[str, Any]:
    query = urllib.parse.urlencode({"v": version, "limit": limit, "offset": offset})
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={
            "Accept": "application/json",
            "Accept-Language": api_locale,
            "Authorization": f"Bearer {token}",
        },
    )

    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            if error.code == 429 or 500 <= error.code < 600:
                if attempt < 3:
                    time.sleep(2**attempt)
                    continue
            raise RuntimeError(f"API error HTTP {error.code}: {body}") from error
        except urllib.error.URLError as error:
            if attempt < 3:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"Network error: {error.reason}") from error
    raise AssertionError("unreachable")


def fetch_all(
    token: str, version: str, page_size: int, api_locale: str
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    expected_count: int | None = None

    while expected_count is None or len(items) < expected_count:
        payload = request_page(token, version, page_size, len(items), api_locale)
        meta = payload.get("meta", {})
        if meta.get("code") != 200:
            raise RuntimeError(f"API error: {json.dumps(meta, ensure_ascii=False)}")

        checkins = payload.get("response", {}).get("checkins", {})
        page = checkins.get("items", [])
        expected_count = int(checkins.get("count", len(items) + len(page)))
        if not page:
            break
        items.extend(page)
        print(f"取得: {len(items)} / {expected_count}", file=sys.stderr)

    return items


def first_primary_category(venue: dict[str, Any]) -> str:
    categories = venue.get("categories") or []
    category = next((c for c in categories if c.get("primary")), categories[0] if categories else {})
    return str(category.get("name", ""))


def photo_url(photo: dict[str, Any]) -> str:
    prefix = str(photo.get("prefix") or "")
    suffix = str(photo.get("suffix") or "")
    return f"{prefix}original{suffix}" if prefix and suffix else ""


def safe_file_part(value: Any, fallback: str) -> str:
    cleaned = "".join(character for character in str(value or "") if character.isalnum() or character in "-_")
    return cleaned or fallback


def photo_filename(checkin: dict[str, Any], photo: dict[str, Any], index: int) -> str:
    checkin_id = safe_file_part(checkin.get("id"), "checkin")
    photo_id = safe_file_part(photo.get("id"), f"photo-{index + 1}")
    suffix = str(photo.get("suffix") or "")
    extension = Path(urllib.parse.urlparse(suffix).path).suffix.lower()
    if not extension or len(extension) > 10:
        extension = ".jpg"
    return f"{checkin_id}_{photo_id}{extension}"


def checkin_photos(checkin: dict[str, Any]) -> list[dict[str, Any]]:
    return list((checkin.get("photos") or {}).get("items") or [])


def to_csv_row(checkin: dict[str, Any]) -> dict[str, Any]:
    venue = checkin.get("venue") or {}
    location = venue.get("location") or {}
    created_at = checkin.get("createdAt")
    offset = int(checkin.get("timeZoneOffset") or 0)
    local_datetime = ""
    if isinstance(created_at, (int, float)):
        local_datetime = datetime.fromtimestamp(
            created_at, timezone(timedelta(minutes=offset))
        ).isoformat()

    checkin_id = str(checkin.get("id", ""))
    photos = checkin_photos(checkin)
    return {
        "id": checkin_id,
        "created_at": local_datetime,
        "created_at_unix": created_at if created_at is not None else "",
        "timezone_offset_minutes": offset,
        "venue_id": venue.get("id", ""),
        "venue_name": venue.get("name", ""),
        "address": location.get("formattedAddress") and ", ".join(location["formattedAddress"]) or location.get("address", ""),
        "city": location.get("city", ""),
        "state": location.get("state", ""),
        "postal_code": location.get("postalCode", ""),
        "country": location.get("country", ""),
        "latitude": location.get("lat", ""),
        "longitude": location.get("lng", ""),
        "category": first_primary_category(venue),
        "shout": checkin.get("shout", ""),
        "photo_count": (checkin.get("photos") or {}).get("count", len(photos)),
        "photo_urls": " | ".join(filter(None, (photo_url(photo) for photo in photos))),
        "photo_files": " | ".join(
            f"photos/{photo_filename(checkin, photo, index)}"
            for index, photo in enumerate(photos)
        ),
        "checkin_url": f"https://www.swarmapp.com/c/{checkin_id}" if checkin_id else "",
    }


def download_file(url: str, destination: Path) -> str:
    if destination.exists() and destination.stat().st_size > 0:
        return "skipped"

    request = urllib.request.Request(url, headers={"User-Agent": "Swarm-Exporter/0.1"})
    temporary = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as file:
                shutil.copyfileobj(response, file)
            temporary.replace(destination)
            return "downloaded"
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as error:
            temporary.unlink(missing_ok=True)
            if attempt < 3:
                time.sleep(2**attempt)
                continue
            return f"failed: {error}"
    raise AssertionError("unreachable")


def download_photos(items: list[dict[str, Any]], output_dir: Path) -> tuple[int, int]:
    photos_dir = output_dir / "photos"
    jobs: list[tuple[str, Path]] = []
    for checkin in items:
        for index, photo in enumerate(checkin_photos(checkin)):
            url = photo_url(photo)
            if url:
                jobs.append((url, photos_dir / photo_filename(checkin, photo, index)))

    if not jobs:
        print("写真: 0件", file=sys.stderr)
        return 0, 0

    photos_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    failed: list[str] = []
    print(f"写真を取得します: {len(jobs)}件", file=sys.stderr)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(download_file, url, destination): destination
            for url, destination in jobs
        }
        for completed, future in enumerate(concurrent.futures.as_completed(futures), 1):
            result = future.result()
            if result == "downloaded":
                downloaded += 1
            elif result.startswith("failed:"):
                failed.append(f"{futures[future].name}: {result[8:]}")
            if completed % 25 == 0 or completed == len(jobs):
                print(f"写真: {completed} / {len(jobs)}", file=sys.stderr)

    if failed:
        preview = "\n".join(failed[:5])
        raise RuntimeError(f"{len(failed)}件の写真を取得できませんでした。\n{preview}")
    return downloaded, len(jobs) - downloaded


def create_default_output_dir(base_dir: Path | None = None) -> Path:
    """Create and reserve a uniquely named default export directory."""
    base_dir = base_dir or Path.cwd()
    index = 0
    while True:
        suffix = f"({index})" if index else ""
        candidate = base_dir / f"{DEFAULT_OUTPUT_DIR_NAME}{suffix}"
        try:
            candidate.mkdir(parents=False, exist_ok=False)
            return candidate
        except FileExistsError:
            index += 1


def write_outputs(items: list[dict[str, Any]], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "photos").mkdir(exist_ok=True)
    json_path = output_dir / "swarm_checkins.json"
    csv_path = output_dir / "swarm_checkins.csv"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump({"count": len(items), "items": items}, file, ensure_ascii=False, indent=2)
        file.write("\n")

    # utf-8-sig makes Japanese text open correctly in common spreadsheet software.
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(to_csv_row(item) for item in items)

    return json_path, csv_path


def main() -> int:
    args = parse_args()
    api_locale = args.locale or detect_os_locale()
    try:
        print(f"APIロケール: {api_locale}", file=sys.stderr)
        items = fetch_all(get_token(), args.version, args.page_size, api_locale)
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
