#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build_venv="$project_dir/.build-venv"

python3 -m venv "$build_venv"
"$build_venv/bin/python" -m pip install --upgrade pip
"$build_venv/bin/python" -m pip install \
  -r "$project_dir/requirements.txt" \
  -r "$project_dir/requirements-build.txt"

cd "$project_dir"
"$build_venv/bin/pyinstaller" \
  --noconfirm \
  --clean \
  --windowed \
  --name "Swarm-Exporter" \
  --osx-bundle-identifier "ai.optinno.swarm-exporter" \
  --collect-all playwright \
  --hidden-import playwright.sync_api \
  swarm_exporter_macos.py

/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString 0.2.0" \
  "$project_dir/dist/Swarm-Exporter.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleVersion string 0.2.0" \
  "$project_dir/dist/Swarm-Exporter.app/Contents/Info.plist"
codesign --force --deep --sign - "$project_dir/dist/Swarm-Exporter.app"

ditto -c -k --keepParent \
  "$project_dir/dist/Swarm-Exporter.app" \
  "$project_dir/dist/Swarm-Exporter-macOS-$(uname -m).zip"

printf 'Created: %s\n' "$project_dir/dist/Swarm-Exporter-macOS-$(uname -m).zip"
