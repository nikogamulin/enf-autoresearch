#!/usr/bin/env python3
"""
Download ENF reference data — either from Google Drive (pre-packaged)
or directly from Netztransparenz.de (original source).

Usage:
    # From Google Drive (recommended — faster, pre-validated)
    python scripts/download_enf_reference.py

    # From Netztransparenz.de (original source, month by month)
    python scripts/download_enf_reference.py --source netztransparenz --start 2023-02 --end 2026-03

Original data source:
    https://www.netztransparenz.de/de-de/Regelenergie/Daten-Regelreserve/Sekündliche-Daten
    Per-second grid frequency measurements for Continental Europe (ENTSO-E CE synchronous area).
    Public data, free for research use.

Data format: CSV with columns DATE;TIME;FREQUENCY_[HZ] (semicolon-separated)
    - DATE: DD.MM.YYYY
    - TIME: HH:MM:SS
    - FREQUENCY: decimal with comma (e.g., 50,031)

Coverage in this project: February 2023 through March 2026 (38 monthly files, ~2.6 GB total).
"""

import os
import sys
import argparse
import subprocess
import urllib.request
from pathlib import Path
import calendar

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data" / "reference"

# Google Drive folder containing pre-packaged ENF reference CSVs
GDRIVE_FOLDER_ID = "1IO3Mo4XCO9bwyjSfkARzOk_OJ_Do3_cE"
GDRIVE_FOLDER_URL = f"https://drive.google.com/drive/folders/{GDRIVE_FOLDER_ID}"


def download_from_gdrive():
    """Download all reference CSVs from Google Drive using gdown."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    try:
        import gdown
    except ImportError:
        print("Installing gdown...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown"])
        import gdown

    print(f"Downloading ENF reference data from Google Drive...")
    print(f"Source: {GDRIVE_FOLDER_URL}")
    print(f"Target: {DATA_DIR}\n")

    gdown.download_folder(
        url=GDRIVE_FOLDER_URL,
        output=str(DATA_DIR),
        quiet=False,
        remaining_ok=True,
    )

    csvs = sorted(DATA_DIR.glob("Frequenz_*.csv"))
    print(f"\nDownloaded {len(csvs)} reference files")
    total_mb = sum(f.stat().st_size for f in csvs) / 1e6
    print(f"Total size: {total_mb:.0f} MB")


def download_from_netztransparenz(start_str, end_str):
    """Download month by month from Netztransparenz.de (original source)."""
    from datetime import datetime
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    start = datetime.strptime(start_str, "%Y-%m")
    end = datetime.strptime(end_str, "%Y-%m")

    print(f"Downloading from Netztransparenz.de: {start_str} to {end_str}")
    print(f"Original source: https://www.netztransparenz.de/de-de/Regelenergie/Daten-Regelreserve/Sekündliche-Daten")
    print(f"Target: {DATA_DIR}\n")

    current = start
    success, failed = 0, 0

    while current <= end:
        y, m = current.year, current.month
        end_day = calendar.monthrange(y, m)[1]
        fname = f"Frequenz_{y}{m:02d}01_{y}{m:02d}{end_day:02d}.csv"
        outpath = DATA_DIR / fname

        if outpath.exists():
            sz = outpath.stat().st_size / 1e6
            print(f"  EXISTS: {fname} ({sz:.1f} MB)")
            success += 1
        else:
            url = f"https://www.netztransparenz.de/portals/1/{fname}"
            print(f"  Downloading: {fname}...", end="", flush=True)
            try:
                urllib.request.urlretrieve(url, str(outpath))
                sz = outpath.stat().st_size / 1e6
                print(f" OK ({sz:.1f} MB)")
                success += 1
            except Exception as e:
                print(f" FAILED: {e}")
                failed += 1

        if m == 12:
            current = current.replace(year=y + 1, month=1)
        else:
            current = current.replace(month=m + 1)

    print(f"\nDone: {success} downloaded, {failed} failed")
    if failed:
        print("For failed downloads, try the Google Drive option instead:")
        print(f"  python scripts/download_enf_reference.py")


def main():
    parser = argparse.ArgumentParser(
        description="Download ENF reference data for forensic audio dating"
    )
    parser.add_argument("--source", choices=["gdrive", "netztransparenz"],
                        default="gdrive",
                        help="Download source (default: gdrive)")
    parser.add_argument("--start", default="2023-02",
                        help="Start month for netztransparenz (YYYY-MM)")
    parser.add_argument("--end", default="2026-03",
                        help="End month for netztransparenz (YYYY-MM)")
    args = parser.parse_args()

    if args.source == "gdrive":
        download_from_gdrive()
    else:
        download_from_netztransparenz(args.start, args.end)


if __name__ == "__main__":
    main()
