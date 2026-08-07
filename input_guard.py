"""
Input sanity checks for incoming meter data.

The product already tells a manager when one *reading* is implausible. It said
nothing when an entire *feed* was wrong — a file in watts instead of kilowatts,
a meter that stopped reporting halfway through, a facility code that does not
exist. Those failures are silent: the dashboard renders, the numbers look
plausible, and every classification downstream is wrong.

This profiles a new batch against the established database and returns findings
ordered by severity. It is deliberately conservative: a finding means "a human
should look", never "the data is rejected".

    from input_guard import baseline_profile, check_readings
    findings = check_readings(new_df, baseline_profile(existing_df), registries)
"""

from dataclasses import dataclass

import pandas as pd

BLOCKER, WARNING, NOTE = "blocker", "warning", "note"
SEVERITY_ORDER = {BLOCKER: 0, WARNING: 1, NOTE: 2}

# A feed this far from the established median is almost always a unit mistake
# rather than a real change in consumption.
UNIT_SCALE_FACTOR = 20
# Physically implausible outdoor temperatures for a US distribution centre.
TEMP_MIN_F, TEMP_MAX_F = -40.0, 130.0


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    detail: str = ""

    def __post_init__(self):
        assert self.severity in SEVERITY_ORDER


def baseline_profile(readings):
    """What the established database looks like, per sub-system where possible."""
    kwh = readings.kwh.dropna()
    prof = {
        "n": len(readings),
        "median": float(kwh.median()) if len(kwh) else float("nan"),
        "p01": float(kwh.quantile(0.01)) if len(kwh) else float("nan"),
        "p99": float(kwh.quantile(0.99)) if len(kwh) else float("nan"),
        "max": float(kwh.max()) if len(kwh) else float("nan"),
        "systems": set(readings.system_id.dropna().unique()),
        "facilities": set(readings.facility_id.dropna().unique()),
        "last_at": pd.to_datetime(readings.recorded_at).max(),
        "temp_median": (float(readings.temp_f.median())
                        if "temp_f" in readings else float("nan")),
        "temp_lo": (float(readings.temp_f.quantile(0.01))
                    if "temp_f" in readings else float("nan")),
        "temp_hi": (float(readings.temp_f.quantile(0.99))
                    if "temp_f" in readings else float("nan")),
    }
    by_sys = readings.groupby("system_id").kwh.agg(["median", "max"])
    prof["by_system"] = by_sys.to_dict("index")
    return prof


def check_readings(new, profile, registries=None):
    """Compare a new batch against the profile. Returns findings, worst first."""
    f = []
    if new is None or new.empty:
        return [Finding(BLOCKER, "empty", "The file contains no readings.")]

    missing = {"facility_id", "system_id", "recorded_at", "kwh"} - set(new.columns)
    if missing:
        return [Finding(BLOCKER, "schema",
                        f"Missing required column(s): {', '.join(sorted(missing))}.",
                        "Expected facility_id, system_id, recorded_at, kwh.")]

    new = new.copy()
    new["recorded_at"] = pd.to_datetime(new.recorded_at, errors="coerce")
    kwh = pd.to_numeric(new.kwh, errors="coerce")

    # ── values ──────────────────────────────────────────────────────────────
    unparsed = int(kwh.isna().sum())
    if unparsed:
        f.append(Finding(BLOCKER, "non_numeric",
                         f"{unparsed:,} reading(s) are not numbers.",
                         "Check for text, commas as decimal separators, or blank cells."))
    good = kwh.dropna()
    if good.empty:
        return sorted(f, key=lambda x: SEVERITY_ORDER[x.severity])

    if (good < 0).any():
        f.append(Finding(BLOCKER, "negative",
                         f"{int((good < 0).sum()):,} reading(s) are negative.",
                         "Consumption cannot be below zero — likely a meter rollover or an "
                         "export channel mixed into the import feed."))

    # Unit mismatch is the single most common import error and the most
    # dangerous, because every value stays internally consistent.
    med, base_med = float(good.median()), profile["median"]
    if base_med and med > 0:
        ratio = med / base_med
        if ratio > UNIT_SCALE_FACTOR or ratio < 1 / UNIT_SCALE_FACTOR:
            direction = "higher" if ratio > 1 else "lower"
            guess = ("Readings may be in watts rather than kilowatts."
                     if ratio > 1 else
                     "Readings may be in megawatt-hours, or already averaged.")
            f.append(Finding(BLOCKER, "unit_scale",
                             f"Typical reading is {ratio:,.0f}× {direction} than this "
                             f"database ({med:,.1f} vs {base_med:,.1f} kWh).", guess))

    out_hi = int((good > profile["max"] * 3).sum()) if profile["max"] else 0
    if out_hi:
        f.append(Finding(WARNING, "extreme_high",
                         f"{out_hi:,} reading(s) exceed three times the highest value ever "
                         f"recorded ({profile['max']:,.0f} kWh).",
                         "Genuine, or a sensor fault worth confirming before it drives a "
                         "dispatch."))

    zero_run = int((good == 0).sum())
    if zero_run > max(3, 0.02 * len(good)):
        f.append(Finding(WARNING, "zeros",
                         f"{zero_run:,} reading(s) are exactly zero "
                         f"({zero_run / len(good):.0%} of the file).",
                         "A meter that stopped reporting usually reads zero rather than "
                         "going missing."))

    # ── coverage ────────────────────────────────────────────────────────────
    dupes = int(new.duplicated(["system_id", "recorded_at"]).sum())
    if dupes:
        f.append(Finding(WARNING, "duplicates",
                         f"{dupes:,} duplicate sub-system/timestamp pair(s).",
                         "Duplicates double-count consumption and shift every baseline."))

    for sid, g in new.groupby("system_id"):
        t = g.recorded_at.dropna().sort_values()
        if len(t) < 3:
            continue
        gaps = t.diff().dropna()
        hourly = pd.Timedelta(hours=1)
        if (gaps > hourly).any():
            worst = gaps.max()
            n_gaps = int((gaps > hourly).sum())
            f.append(Finding(WARNING, "gaps",
                             f"{sid} has {n_gaps} gap(s) in hourly coverage, "
                             f"longest {worst.total_seconds() / 3600:.0f} hours.",
                             "Missing hours are excluded from baselines rather than "
                             "treated as zero, so a long gap weakens every comparison."))
            break     # one example is enough; the file-level point is made

    # ── identifiers ─────────────────────────────────────────────────────────
    known_sys = profile["systems"] | (
        set(registries["system_registry"].system_id) if registries else set())
    unknown = sorted(set(new.system_id.dropna()) - known_sys)
    if unknown:
        f.append(Finding(BLOCKER, "unknown_system",
                         f"{len(unknown)} sub-system code(s) not in the registry: "
                         f"{', '.join(map(str, unknown[:4]))}"
                         f"{'…' if len(unknown) > 4 else ''}.",
                         "Readings on an unregistered meter cannot be classified — the "
                         "system type and its fault catalogue are unknown."))

    # ── time ────────────────────────────────────────────────────────────────
    bad_ts = int(new.recorded_at.isna().sum())
    if bad_ts:
        f.append(Finding(BLOCKER, "bad_timestamp",
                         f"{bad_ts:,} timestamp(s) could not be read.",
                         "Expected an ISO-style date and time, e.g. 2026-07-17 14:00."))

    ts = new.recorded_at.dropna()
    if not ts.empty:
        now = pd.Timestamp.now()
        ahead = int((ts > now + pd.Timedelta(days=1)).sum())
        if ahead:
            f.append(Finding(WARNING, "future",
                             f"{ahead:,} reading(s) are dated in the future.",
                             "Usually a timezone or date-format mix-up (US vs EU ordering)."))
        if profile["last_at"] is not pd.NaT and ts.min() <= profile["last_at"]:
            overlap = int((ts <= profile["last_at"]).sum())
            f.append(Finding(NOTE, "overlap",
                             f"{overlap:,} reading(s) predate the newest reading already "
                             f"held ({profile['last_at']:%Y-%m-%d %H:%M}).",
                             "Re-importing an overlapping period double-counts unless the "
                             "existing rows are replaced."))

    if "temp_f" in new.columns:
        temp = pd.to_numeric(new.temp_f, errors="coerce").dropna()
        odd = int(((temp < TEMP_MIN_F) | (temp > TEMP_MAX_F)).sum())
        if odd:
            f.append(Finding(WARNING, "temperature",
                             f"{odd:,} outdoor temperature(s) outside "
                             f"{TEMP_MIN_F:.0f}–{TEMP_MAX_F:.0f}°F.",
                             "Check the column is Fahrenheit and not a sensor fault."))

        # Celsius survives a plausible-range check — 70F becomes 21, which is a
        # perfectly reasonable Fahrenheit reading. Only a comparison against the
        # temperatures this database already holds catches it.
        base_t = profile.get("temp_median", float("nan"))
        lo, hi = profile.get("temp_lo", float("nan")), profile.get("temp_hi", float("nan"))
        if len(temp) and pd.notna(base_t) and float(temp.median()) < base_t - 20:
            as_f = float(temp.median()) * 9 / 5 + 32
            # Converted, does it land inside the range this database has actually
            # seen? Comparing against the annual median would fail on any file
            # drawn from a single season.
            if pd.notna(lo) and lo <= as_f <= hi:
                f.append(Finding(WARNING, "temp_units",
                                 f"Typical temperature is {float(temp.median()):.0f}°, well below "
                                 f"the {base_t:.0f}°F this database holds.",
                                 f"Reads as Celsius: converted, it becomes {as_f:.0f}°F, which "
                                 "matches. The weather-adjusted baseline would be wrong."))

    return sorted(f, key=lambda x: SEVERITY_ORDER[x.severity])


def worst_severity(findings):
    return min((x.severity for x in findings),
               key=lambda s: SEVERITY_ORDER[s]) if findings else None
