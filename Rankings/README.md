# SERP Relative Positioning Reports

This repository houses day-by-day SERP snapshots per client (Markdown files) and generates:

- A relative positioning report (Markdown) showing First vs. Last ranks and deltas for each keyword.
- Optional PNG charts per keyword visualizing your client’s rank over the selected window.

The generator is implemented in `scripts/serp_report.py`.

## Prerequisites

- Python 3.11+ installed (pillow 13, a security fix, requires it)
  - Windows: https://www.python.org/downloads/windows/
  - macOS: https://www.python.org/downloads/macos/
  - Linux: use your package manager or pyenv
- Optional (for PNG charts): `matplotlib`

To verify Python:

- Windows PowerShell: `py --version` (or `python --version`)
- macOS/Linux (or WSL): `python3 --version`

## Directory Layout

The script expects the following structure at the repository root (the defaults can be changed by editing `CLIENTS` in `scripts/serp_report.py`):

- `Bavarian Ranking/` — daily files named like `9-29-25.md`
- `OrthoEdge Ranking/` — daily files named like `9-29-25.md`
- `Shafer Law Ranking/` — daily files named like `9-29-25.md`
- `999 Ranking Templates/` — seed templates used when data is missing
  - `Bavarian.md`
  - `OrthoEdge.md`
  - `Shafer Law.md`
- `reporting/` — output folder (subfolders are created automatically)
  - `bavarian_rennsport/`
  - `orthoedge/`
  - `Shafer_law/`

Each daily Markdown snapshot is grouped by section (e.g., `## BMW`, `## Audi`, etc.) and each section contains a Markdown table with columns:

`| Keyword | P1 | P2 | P3 | Notes |`

Notes column is used to record an out-of-top-3 rank for the client (e.g., "Bavarian is rank 6").

## Installation (Dependencies)

Dependencies are minimal and optional:

- Base functionality (Markdown reports): no extra packages required.
- Charts (PNG time series): `matplotlib` is required.

Install `matplotlib` if you want charts:

- Windows PowerShell:
  - `py -m pip install --upgrade pip`
  - `py -m pip install matplotlib`
- macOS/Linux/WSL:
  - `python3 -m pip install --upgrade pip`
  - `python3 -m pip install matplotlib`

Alternatively, from this repo root:

`python3 -m pip install -r requirements.txt`  (or `py -m pip install -r requirements.txt` on Windows)

> Note: `requirements.txt` only includes `matplotlib` because the rest is part of Python’s standard library.

## Running the Generator

Run from the repo root (e.g., `C:\Users\sheld\Desktop\Rankings`).

- Windows PowerShell:
  - With synthesis (fills missing days):
    - `py .\scripts\serp_report.py --synthesize --days 10`
  - Without synthesis (uses only existing files):
    - `py .\scripts\serp_report.py --days 10`

- macOS/Linux/WSL:
  - With synthesis:
    - `python3 scripts/serp_report.py --synthesize --days 10`
  - Without synthesis:
    - `python3 scripts/serp_report.py --days 10`

Flags:

- `--days N` — Number of days in the window (default 10). The script selects the last N dated files per client.
- `--synthesize` — If provided, creates missing daily files within the window by applying small, deterministic variations to existing data (or templates when no data exists).
- `--root PATH` — Only needed if you run the script from outside the repo root.

## Outputs

- Markdown reports:
  - `reporting/bavarian_rennsport/relative_positions_YYYY-MM-DD_to_YYYY-MM-DD.md`
  - `reporting/orthoedge/relative_positions_YYYY-MM-DD_to_YYYY-MM-DD.md`
  - `reporting/Shafer_law/relative_positions_YYYY-MM-DD_to_YYYY-MM-DD.md`

  Each report contains:
  - A window header (First date → Last date).
  - For each keyword: client row plus the last day’s top-3 competitor sites.
  - Columns: `First`, `Last`, `Delta` (computed as Last − First).
  - Verification summary confirming the deltas were computed consistently.

- Charts (if `matplotlib` installed):
  - PNG files per keyword under each client’s `charts/` folder, e.g.:
    - `reporting/bavarian_rennsport/charts/SECTION__KEYWORD__YYYYMMDD_to_YYYYMMDD.png`
  - Shows client rank over the window (Y-axis inverted so 1 is at the top).

## Data Assumptions

- Filenames: `M-D-YY.md` (single-digit months/days are OK, e.g., `9-3-25.md`).
- Table parsing: the script reads `P1`, `P2`, `P3` as site names; bold/italics are stripped during parsing.
- Client rank inference:
  - If client appears in `P1`–`P3`, that position is used.
  - Otherwise, if `Notes` contains phrases like "<Client> is rank 6" or "<Client> is number 6", that number is used.

## Adding a New Client

1. Create a new ranking folder (e.g., `NewClient Ranking/`).
2. Add a template to `999 Ranking Templates/` (optional) to seed synthetic data.
3. Create a reporting subfolder path under `reporting/` (script will create it automatically when writing reports).
4. Edit `CLIENTS` in `scripts/serp_report.py` to map:
   - Ranking dir name → (Display label, Reporting dir path, Canonical client name string used in tables)

Example:

```
CLIENTS = {
  "Bavarian Ranking": ("Bavarian Rennsport", "reporting/bavarian_rennsport", "Bavarian"),
  "OrthoEdge Ranking": ("OrthoEdge", "reporting/orthoedge", "OrthoEdge"),
  "Shafer Law Ranking": ("Shafer Law", "reporting/Shafer_law", "Shafer Law"),
  "NewClient Ranking": ("NewClient", "reporting/newclient", "NewClient"),
}
```

## Troubleshooting

- `py: command not found` (Windows): Use `python` instead of `py`, or ensure Python’s launcher is installed.
- `pip: command not found`: Use `py -m pip ...` (Windows) or `python3 -m pip ...` (macOS/Linux/WSL).
- Charts not generated: Install `matplotlib`. The script will still generate Markdown reports if plotting isn’t available.
- No ranking files found: Ensure your daily `.md` files are inside the `* Ranking` folders with names like `9-29-25.md`.

## License

Internal use. No license header added.

