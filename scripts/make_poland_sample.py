"""Builds the sample of Polish Raw SBD starts since 2023 (with attempts and bomb-outs) used by team_selection.ipynb.

Run from the repository root:
    uv run python scripts/make_poland_sample.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from powerlifting_metrics import (ATTEMPT_COLUMNS, COLUMNS, POLAND_SAMPLE_CSV, download_openipf,
                                  filter_country_starts, read_openipf_zip)

COUNTRY = "Poland"
SAMPLE_FROM = "2023-01-01"

df = filter_country_starts(read_openipf_zip(download_openipf(), columns=COLUMNS + ATTEMPT_COLUMNS),
                           COUNTRY, SAMPLE_FROM)
df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
POLAND_SAMPLE_CSV.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(POLAND_SAMPLE_CSV, index=False)
print(f"Saved {len(df):,} rows to {POLAND_SAMPLE_CSV} ({POLAND_SAMPLE_CSV.stat().st_size / 1e6:.1f} MB)")
