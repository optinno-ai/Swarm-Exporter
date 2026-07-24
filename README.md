# Swarm Exporter

English | [日本語](README.ja.md)

A command-line tool that opens a dedicated browser for signing in to Swarm and exports your complete check-in history to JSON and CSV.

Instead of waiting for a Foursquare data download request, it automatically detects a token for the check-in API from browser traffic after you sign in. You do not need a Developer Console Client ID or Client Secret, nor do you need to copy a token manually.

## Features

- Opens the `ja.swarmapp.com` login page in a dedicated Chrome window
- Accepts only tokens that work with the Foursquare v2 API
- Retrieves venue names, category names, and other data using the OS locale
- Retrieves all check-ins in pages of up to 250
- Produces a combined JSON file while preserving the original API data
- Converts dates, venues, addresses, coordinates, categories, comments, and more to CSV
- Downloads photos attached to check-ins by default
- Writes CSV with a UTF-8 BOM for compatibility with Excel
- Retries temporary network failures and API rate-limit errors

## Requirements

- Python 3.10 or later
- Google Chrome, Microsoft Edge, or Chromium
- A network connection that can access Swarm

If no supported browser is found, you can install Playwright's Chromium:

```sh
python3 -m playwright install chromium
```

## Installation

The standard installation method uses GitHub. The cloned source directory is not retained, and the `swarm-exporter` command remains available after installation.

```sh
python3 -m pip install "git+https://github.com/optinno-ai/Swarm-Exporter.git"
```

To use a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install "git+https://github.com/optinno-ai/Swarm-Exporter.git"
```

Developers who intend to edit the source can use an editable installation and keep the cloned directory:

```sh
git clone https://github.com/optinno-ai/Swarm-Exporter.git
cd Swarm-Exporter
python3 -m pip install -e .
```

If you delete the cloned directory after an editable installation, restore the command with a standard installation:

```sh
python3 -m pip install --force-reinstall --no-deps "git+https://github.com/optinno-ai/Swarm-Exporter.git"
```

## Usage

After installation, run:

```sh
swarm-exporter
```

1. The Swarm login page opens in a dedicated Chrome window.
2. Sign in to your Swarm account.
3. After detecting the login, the tool automatically opens `https://ja.swarmapp.com/history` to trigger API traffic.
4. Once a valid API token is detected, the browser closes automatically.
5. Progress for check-in and photo downloads is displayed in the terminal.
6. JSON, CSV, and photo files are created in `Swarm-Exporter` under the current directory.
   If that directory already exists, the tool uses a numbered name such as `Swarm-Exporter(1)` or `Swarm-Exporter(2)`.

```text
Swarm-Exporter/
├── swarm_checkins.json
├── swarm_checkins.csv
└── photos/
    └── CHECKIN_ID_PHOTO_ID.jpg
```

To export JSON and CSV without downloading photos:

```sh
swarm-exporter --data-only
```

The `photos` directory is created even when there are no photos or `--data-only` is used.

By default, the API display language is detected from the OS locale. To specify it explicitly:

```sh
swarm-exporter --locale ja
```

When Foursquare has no name in the requested language, it selects a fallback representation.

To change the output directory:

```sh
swarm-exporter --output-dir ~/Downloads/swarm-export
```

To see all available options:

```sh
swarm-exporter --help
```

## CSV Columns

| Column | Description |
| --- | --- |
| `id` | Check-in ID |
| `created_at` | Date and time with the check-in location's time zone |
| `created_at_unix` | Unix timestamp |
| `timezone_offset_minutes` | Offset from UTC in minutes |
| `venue_id` / `venue_name` | Venue ID and name |
| `address` / `city` / `state` / `postal_code` / `country` | Address information |
| `latitude` / `longitude` | Coordinates |
| `category` | Primary venue category |
| `shout` | Comment attached to the check-in |
| `photo_count` | Number of attached photos |
| `photo_urls` | Original-size photo URLs |
| `photo_files` | Relative paths to downloaded photos |
| `checkin_url` | Swarm check-in URL |

The JSON file stores the check-in objects returned by the API without modifying them, grouped under an `items` array.

## Security and Privacy

- Your login ID and password are entered directly into Swarm and are never read by this tool.
- Only Swarm/Foursquare traffic inside the temporary browser started by this tool is monitored.
- The token is never written to the screen, logs, JSON, or CSV.
- The token is retained in memory only while the export is running.
- The temporary browser profile is deleted when the process exits.
- Exported JSON and CSV files contain location history. Do not place them in a public repository or shared directory.

The default `Swarm-Exporter/` output directory contains location history and should not be published or shared.

## Supplying a Token Directly

The repository also includes a helper script that can run without a browser when you already have a token:

```sh
FOURSQUARE_OAUTH_TOKEN='your-token' python3 swarm_exporter.py
```

If the environment variable is not set, the script prompts for the token without displaying it:

```sh
python3 swarm_exporter.py
```

## Troubleshooting

### Chrome does not start

Install Playwright's Chromium:

```sh
python3 -m playwright install chromium
```

### Nothing happens after signing in

The tool normally navigates to `https://ja.swarmapp.com/history` automatically. If it does not, open that URL manually in the dedicated browser. The token can be detected once Foursquare API traffic occurs.

### `swarm-exporter: command not found`

Make sure the directory containing scripts installed by pip is included in `PATH`. If you use a virtual environment, activate it first:

```sh
source .venv/bin/activate
```

## Disclaimer

This is an unofficial Swarm/Foursquare tool. Changes to the service's website, cookies, or API may cause it to stop working. Use it only with your own account and data.
