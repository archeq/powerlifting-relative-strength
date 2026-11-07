"""IPF GL Points metric and loading of the OpenIPF (OpenPowerlifting) dataset."""

import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OPENIPF_URL = "https://openpowerlifting.gitlab.io/opl-csv/files/openipf-latest.zip"
RAW_ZIP = ROOT / "data" / "raw" / "openipf-latest.zip"
SAMPLE_CSV = ROOT / "data" / "sample" / "openipf_sbd_2024plus.csv.gz"
POLAND_SAMPLE_CSV = ROOT / "data" / "sample" / "poland_raw_sbd_2023plus.csv"

COLUMNS = [
    "Name", "Sex", "Event", "Equipment", "Age", "Division", "BodyweightKg",
    "WeightClassKg", "Best3SquatKg", "Best3BenchKg", "Best3DeadliftKg",
    "TotalKg", "Place", "Dots", "Wilks", "Goodlift", "Country",
    "Federation", "Date", "MeetName",
]

LIFTS = ["Squat", "Bench", "Deadlift"]
# Individual attempts: positive = made, negative = missed, empty = not taken
ATTEMPT_COLUMNS = [f"{lift}{i}Kg" for lift in LIFTS for i in (1, 2, 3)]

# IPF GL coefficients for full powerlifting (SBD), in force since 1 May 2020.
# Key: (sex, equipment) -> (A, B, C)
GL_COEFFICIENTS = {
    ("M", "Raw"): (1199.72839, 1025.18162, 0.00921),
    ("F", "Raw"): (610.32796, 1045.59282, 0.03048),
    ("M", "Single-ply"): (1236.25115, 1449.21864, 0.01644),
    ("F", "Single-ply"): (758.63878, 949.31382, 0.02435),
}

# Current IPF senior weight classes (without the youth-only 53 / 43 kg classes)
IPF_WEIGHT_CLASSES = {
    "M": ["59", "66", "74", "83", "93", "105", "120", "120+"],
    "F": ["47", "52", "57", "63", "69", "76", "84", "84+"],
}


def ipf_gl(total_kg, bodyweight_kg, sex, equipment="Raw"):
    """IPF GL Points = Total * 100 / (A - B * e^(-C * bodyweight)).

    Works on scalars as well as on columns / arrays
    (sex and equipment must then be the same for the whole array).
    """
    a, b, c = GL_COEFFICIENTS[(sex, equipment)]
    return total_kg * 100 / (a - b * np.exp(-c * bodyweight_kg))


def ipf_gl_column(df):
    """Computes GL for every row of a DataFrame with Sex, Equipment, TotalKg and BodyweightKg columns."""
    out = pd.Series(np.nan, index=df.index)
    for (sex, equipment), group in df.groupby(["Sex", "Equipment"]):
        if (sex, equipment) in GL_COEFFICIENTS:
            out[group.index] = ipf_gl(group["TotalKg"], group["BodyweightKg"], sex, equipment)
    return out


def download_openipf(path=RAW_ZIP):
    """Downloads the full OpenIPF dataset (~70 MB) unless it is already on disk."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {OPENIPF_URL} ...")
        urllib.request.urlretrieve(OPENIPF_URL, path)
    return path


def read_openipf_zip(path=RAW_ZIP, columns=COLUMNS):
    with zipfile.ZipFile(path) as z:
        csv_name = next(n for n in z.namelist() if n.endswith(".csv"))
        with z.open(csv_name) as f:
            return pd.read_csv(f, usecols=columns, low_memory=False)


def filter_sbd(df, date_from):
    """Keeps only valid full-power (SBD) results from the given date onwards."""
    df = df[
        (df["Event"] == "SBD")
        & df["TotalKg"].notna()
        & df["BodyweightKg"].notna()
        & df["Sex"].isin(["M", "F"])
        & df["Equipment"].isin(["Raw", "Single-ply"])
        & (df["Date"] >= date_from)
    ].copy()
    # A lifter entered in several divisions at once (e.g. Junior and Open) appears in several
    # rows with the same result — keep one row per lifter, meet and equipment.
    df = df.sort_values("TotalKg", ascending=False).drop_duplicates(["Name", "Date", "MeetName", "Equipment"])
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values(["Date", "MeetName", "Name"]).reset_index(drop=True)


def load_openipf(use_sample=False, date_from="2019-01-01"):
    """Returns SBD results from the OpenIPF dataset.

    use_sample=True reads the small sample bundled with the repository (results since 2024) and works offline.
    Otherwise downloads the full dataset and filters it from `date_from`.
    """
    if use_sample:
        df = pd.read_csv(SAMPLE_CSV, low_memory=False)
    else:
        df = read_openipf_zip(download_openipf())
    return filter_sbd(df, date_from)


def filter_country_starts(df, country, date_from):
    """Keeps all Raw SBD starts of one country's lifters, including bomb-outs (DQ, no total).

    No-shows (NS) and doping disqualifications (DD) are dropped.
    """
    df = df[
        (df["Event"] == "SBD")
        & (df["Equipment"] == "Raw")
        & (df["Country"] == country)
        & (df["Date"] >= date_from)
        & (df["TotalKg"].notna() | (df["Place"] == "DQ"))
    ].copy()
    # Same duplicate rule as in filter_sbd; a valid total wins over a bomb-out row
    df = (df.sort_values("TotalKg", ascending=False, na_position="last")
            .drop_duplicates(["Name", "Date", "MeetName"]))
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values(["Date", "MeetName", "Name"]).reset_index(drop=True)


def load_country_starts(country="Poland", use_sample=False, date_from="2023-01-01"):
    """Returns Raw SBD starts (with individual attempts and bomb-outs) of one country's lifters.

    use_sample=True reads the bundled sample of Polish lifters since 2023 and works offline.
    """
    if use_sample:
        df = pd.read_csv(POLAND_SAMPLE_CSV, low_memory=False)
    else:
        df = read_openipf_zip(download_openipf(), columns=COLUMNS + ATTEMPT_COLUMNS)
    return filter_country_starts(df, country, date_from)


def attempt_counts(df):
    """Counts made and attempted attempts per start, for each lift and in total (max 9)."""
    out = pd.DataFrame(index=df.index)
    for lift in LIFTS:
        attempts = df[[f"{lift}{i}Kg" for i in (1, 2, 3)]]
        out[f"{lift}Made"] = (attempts > 0).sum(axis=1)
        out[f"{lift}Attempted"] = attempts.notna().sum(axis=1)
    out["Made"] = out[[f"{lift}Made" for lift in LIFTS]].sum(axis=1)
    out["Attempted"] = out[[f"{lift}Attempted" for lift in LIFTS]].sum(axis=1)
    return out
