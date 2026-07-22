#!/usr/bin/env python3
"""Native macOS app entry point for Swarm Exporter."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from swarm_exporter import (
    DEFAULT_API_VERSION,
    PAGE_SIZE,
    create_default_output_dir,
    download_photos,
    fetch_all,
    write_outputs,
)
from swarm_exporter_cli import acquire_token


APP_TITLE = "Swarm Exporter"


def choose_save_location() -> Path | None:
    downloads = Path.home() / "Downloads"
    default_location = downloads if downloads.is_dir() else Path.home()
    script = """
on run argv
    try
        set defaultFolder to POSIX file (item 1 of argv) as alias
        set selectedFolder to choose folder ¬
            with prompt "Swarmデータの保存先を選択してください。" ¬
            default location defaultFolder
        return POSIX path of selectedFolder
    on error number -128
        return ""
    end try
end run
"""
    result = subprocess.run(
        ["osascript", "-e", script, "--", str(default_location)],
        check=True,
        capture_output=True,
        text=True,
    )
    selected = result.stdout.strip()
    return Path(selected) if selected else None


def show_dialog(message: str, *, is_error: bool = False) -> None:
    icon = "stop" if is_error else "note"
    script = f"""
on run argv
    display dialog (item 1 of argv) ¬
        with title "{APP_TITLE}" ¬
        buttons {{"OK"}} default button "OK" ¬
        with icon {icon}
end run
"""
    subprocess.run(
        ["osascript", "-e", script, "--", message],
        check=False,
        capture_output=True,
        text=True,
    )


def main() -> int:
    if "--self-test" in sys.argv:
        from playwright.sync_api import sync_playwright

        assert callable(sync_playwright)
        assert (Path.home() / "Downloads").is_absolute()
        return 0

    try:
        save_location = choose_save_location()
        if save_location is None:
            return 0

        show_dialog(
            "続いてSwarmのログイン画面を開きます。\n"
            "ログイン後、データ取得が完了するまでブラウザを閉じないでください。"
        )
        token = acquire_token(600, DEFAULT_API_VERSION)
        items = fetch_all(token, DEFAULT_API_VERSION, PAGE_SIZE)
        output_dir = create_default_output_dir(save_location)
        write_outputs(items, output_dir)
        download_photos(items, output_dir)
    except Exception as error:
        show_dialog(f"データを取得できませんでした。\n\n{error}", is_error=True)
        return 1

    show_dialog(
        f"{len(items)}件のチェックインを保存しました。\n\n保存先:\n{output_dir}"
    )
    subprocess.run(["open", str(output_dir)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
