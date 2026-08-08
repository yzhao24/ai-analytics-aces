"""
Fetch real hourly outdoor temperatures for each facility's city.

Source: Open-Meteo Historical Archive (ERA5 reanalysis). Free, no API key, no
registration — which is why it is used here rather than NOAA CDO, which needs a
token that would have to be stored somewhere.

Writes `weather_real.csv` with one row per facility per hour, and reports how far
the synthetic `temp_f` in the workbook sits from reality.

Usage:
    python fetch_weather.py            # fetch + write + compare
    python fetch_weather.py --compare  # compare only, using the existing CSV
"""

import argparse
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

DATA_FILE = Path(__file__).parent / "dummy_data_set2.xlsx"
OUT_FILE = Path(__file__).parent / "weather_real.csv"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"

# The workbook names the cities but carries no coordinates, so they are pinned
# here. Update if the facility roster changes.
FACILITY_COORDS = {
    "Chicago South DC": (41.8781, -87.6298, "America/Chicago"),
    "Milwaukee Central": (43.0389, -87.9065, "America/Chicago"),
    "Indianapolis East": (39.7684, -86.1581, "America/Indiana/Indianapolis"),
}


def fetch_city(lat, lon, tz, start, end):
    query = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": start,
            "end_date": end,
            "hourly": "temperature_2m",
            "temperature_unit": "fahrenheit",
            "timezone": tz,
        }
    )
    with urllib.request.urlopen(f"{ARCHIVE}?{query}", timeout=60) as r:
        import json

        payload = json.load(r)
    return pd.DataFrame(
        {
            "recorded_at": pd.to_datetime(payload["hourly"]["time"]),
            "temp_f_real": payload["hourly"]["temperature_2m"],
        }
    )


def fetch_all():
    xl = pd.ExcelFile(DATA_FILE)
    readings = xl.parse("energy_readings")
    readings["recorded_at"] = pd.to_datetime(readings.recorded_at)
    facilities = xl.parse("facility_registry")

    start = readings.recorded_at.min().strftime("%Y-%m-%d")
    end = readings.recorded_at.max().strftime("%Y-%m-%d")
    print(f"window: {start} -> {end}")

    frames = []
    for f in facilities.itertuples():
        if f.facility_name not in FACILITY_COORDS:
            print(f"  {f.facility_name}: no coordinates on file, skipped")
            continue
        lat, lon, tz = FACILITY_COORDS[f.facility_name]
        df = fetch_city(lat, lon, tz, start, end)
        df.insert(0, "facility_id", f.facility_id)
        df.insert(1, "facility_name", f.facility_name)
        frames.append(df)
        print(f"  {f.facility_name}: {len(df)} hourly readings, "
              f"{df.temp_f_real.min():.0f}-{df.temp_f_real.max():.0f}F")

    if not frames:
        sys.exit("no facilities resolved to coordinates")
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(OUT_FILE, index=False)
    print(f"\nwrote {len(out)} rows -> {OUT_FILE.name}")
    return out


def compare(real=None):
    """How far is the workbook's synthetic temp_f from what actually happened?"""
    if real is None:
        if not OUT_FILE.exists():
            sys.exit(f"{OUT_FILE.name} not found — run without --compare first.")
        real = pd.read_csv(OUT_FILE, parse_dates=["recorded_at"])

    readings = pd.ExcelFile(DATA_FILE).parse("energy_readings")
    readings["recorded_at"] = pd.to_datetime(readings.recorded_at)

    merged = readings.merge(real, on=["facility_id", "recorded_at"], how="inner")
    merged["error"] = merged.temp_f - merged.temp_f_real

    print(f"\n{'=' * 68}\nSYNTHETIC temp_f  vs  REAL temp_f\n{'=' * 68}")
    print(f"  matched hours        : {len(merged):,}")
    print(f"  mean absolute error  : {merged.error.abs().mean():5.1f} F")
    print(f"  median abs error     : {merged.error.abs().median():5.1f} F")
    print(f"  worst hour           : {merged.error.abs().max():5.1f} F")
    print(f"  synthetic range      : {merged.temp_f.min():.0f} - {merged.temp_f.max():.0f} F")
    print(f"  real range           : {merged.temp_f_real.min():.0f} - {merged.temp_f_real.max():.0f} F")

    print(f"\n  correlation between the two series : {merged.temp_f.corr(merged.temp_f_real):.3f}")
    print("     ^ near 0 means the synthetic weather is unrelated to real weather")

    # The load model matters more than the temperature itself: if kWh was
    # generated from synthetic temp, swapping in real temp breaks the very
    # relationship the weather-adjusted baseline depends on.
    print(f"\n  corr(kWh, synthetic temp) : {merged.kwh.corr(merged.temp_f):+.3f}")
    print(f"  corr(kWh, real temp)      : {merged.kwh.corr(merged.temp_f_real):+.3f}")
    print("     ^ if the first is strong and the second is not, the consumption")
    print("       data was generated from the synthetic weather, and a drop-in")
    print("       swap would destroy the signal rather than make it real.")

    print("\n  per facility, mean abs error:")
    for name, g in merged.groupby("facility_name"):
        print(f"    {name:20} {g.error.abs().mean():5.1f} F   "
              f"corr(kWh, real) = {g.kwh.corr(g.temp_f_real):+.3f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare", action="store_true", help="skip fetching")
    args = ap.parse_args()
    compare() if args.compare else compare(fetch_all())
