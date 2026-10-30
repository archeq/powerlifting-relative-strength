"""Builds the small data sample (SBD results since 2024) committed to the repository.

Run from the repository root:
    uv run python scripts/make_sample.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from powerlifting_metrics import SAMPLE_CSV, download_openipf, filter_sbd, read_openipf_zip

SAMPLE_FROM = "2024-01-01"

df = filter_sbd(read_openipf_zip(download_openipf()), SAMPLE_FROM)
df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
SAMPLE_CSV.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(SAMPLE_CSV, index=False, compression="gzip")
print(f"Saved {len(df):,} rows to {SAMPLE_CSV} ({SAMPLE_CSV.stat().st_size / 1e6:.1f} MB)")
