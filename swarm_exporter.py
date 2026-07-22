#!/usr/bin/env python3
"""Export all check-ins for the authenticated Swarm/Foursquare user."""

from __future__ import annotations

import argparse
import csv
import getpass
import json
import os
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
    "checkin_url",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Swarmの全チェックインを結合JSONとCSVへ出力します。"
    )
    parser.add_argument("--output-dir", default="output", help="出力先 (default: output)")
    parser.add_argument("--version", default=DEFAULT_API_VERSION, help="Foursquare API version date")
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE, choices=range(1, 251), metavar="1-250")
    return parser.parse_args()


def get_token() -> str:
    token = os.environ.get("FOURSQUARE_OAUTH_TOKEN", "").strip()
    if not token and sys.stdin.isatty():
        token = getpass.getpass("OAuth token: ").strip()
    if not token:
        raise SystemExit("FOURSQUARE_OAUTH_TOKENを設定するか、対話入力でtokenを渡してください。")
    return token


def request_page(token: str, version: str, limit: int, offset: int) -> dict[str, Any]:
    query = urllib.parse.urlencode({"v": version, "limit": limit, "offset": offset})
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
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


def fetch_all(token: str, version: str, page_size: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    expected_count: int | None = None

    while expected_count is None or len(items) < expected_count:
        payload = request_page(token, version, page_size, len(items))
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
        "checkin_url": f"https://www.swarmapp.com/c/{checkin_id}" if checkin_id else "",
    }


def write_outputs(items: list[dict[str, Any]], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
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
    try:
        items = fetch_all(get_token(), args.version, args.page_size)
        json_path, csv_path = write_outputs(items, Path(args.output_dir))
    except (RuntimeError, ValueError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1

    print(f"完了: {len(items)}件", file=sys.stderr)
    print(json_path)
    print(csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
