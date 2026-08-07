"""
Synthetic dataset generator for the Energy Anomaly Explainer.

The workbook shipped without the script that produced it, so the dataset could
not be extended, re-driven from real weather, or given harder cases. This
rebuilds it end to end and is the file to edit when the data needs to change.

What it does differently from the original v1 workbook:

  * Consumption is driven by REAL hourly temperatures (Open-Meteo archive), not
    an invented temperature series. Weather adjustment is therefore testable
    rather than circular.
  * Any window, not 30 days. The team spec asks for 12 months.
  * Anomalies are INJECTED, then DETECTED by a real detector. detected_at,
    spike_kwh, and baseline_kwh are measured off the series, not asserted. An
    injection the detector misses is reported as a detection miss rather than
    silently becoming a test case.
  * One ground-truth source. The old workbook carried two that disagreed:
    test_set_15_cases (15 rows) and manager_actions.actual_top_level_class
    (4 rows). Scoring the second way excluded every abstention and reported
    100% recall on a quarter of the set.
  * Optional strata for the experiments the adversarial reviews call for:
    co-occurring causes in one hour, and spikes below statistical significance.
  * The classifications sheet is emitted EMPTY. It is meant to hold AI output;
    shipping pre-written labels in it is what let the product look finished
    without a classifier. Run classifier.py to populate it.

Usage:
    python generate_dataset.py                            # 12 months, 15 cases
    python generate_dataset.py --months 3 --out demo.xlsx # faster to load
    python generate_dataset.py --co-occurring 8 --sub-threshold 5
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
SOURCE_WORKBOOK = HERE / "registries.xlsx"        # facilities, systems, classifications
WEATHER_CACHE = HERE / "weather_cache.csv"

# ── Load model ────────────────────────────────────────────────────────────────
# Per sub-system type. Everything is kW for one hour, i.e. kWh.

BASE_KW = {"refrigeration": 55.0, "hvac": 24.0, "lighting": 12.0, "other": 18.0}

# Cooling load above a 65F balance point, kW per degree F. Refrigeration also
# works harder when it is hot outside, but less sharply than air conditioning.
TEMP_COEF = {"refrigeration": 1.15, "hvac": 2.10, "lighting": 0.0, "other": 0.15}

# Day shift 06:00-14:00, night shift 22:00-06:00 (spec section 12).
DAY_SHIFT = range(6, 14)
NIGHT_SHIFT = list(range(22, 24)) + list(range(0, 6))
SHIFT_KW = {"refrigeration": 6.0, "hvac": 11.0, "lighting": 15.0, "other": 22.0}

COMPRESSOR_CYCLE_HOURS = 4       # refrigeration duty cycle
COMPRESSOR_AMPLITUDE_KW = 17.0

FORKLIFT_HOURS = (14, 15)        # fleet charges right after day shift
FORKLIFT_KW = 30.0

WEEKEND_SCALE = 0.72             # throughput drops Sat/Sun
WARMUP_DAYS = 90                 # baseline history required before monitoring starts
NOISE_FRACTION = 0.045           # multiplicative jitter
NOISE_FLOOR_KW = 1.2

# ── Anomaly catalogue ────────────────────────────────────────────────────────
# Keyed by classification_id from classification_registry. `shape` is applied to
# the clean series; `systems` restricts which sub-system types can host it.

CATALOGUE = {
    # equipment_fault
    "CT-001": dict(systems=["refrigeration"], hours=3, note="Compressor cycling continuously; rapid rise, plateau, no recovery"),
    "CT-002": dict(systems=["refrigeration"], hours=4, note="Gradual rise over several hours; refrigerant loss pattern"),
    "CT-003": dict(systems=["hvac"], hours=3, note="Intermittent spikes; fan motor inconsistency"),
    "CT-004": dict(systems=["hvac"], hours=4, note="Sustained elevated draw; filter restriction"),
    "CT-005": dict(systems=["lighting"], hours=1, note="Single-interval spike; controller reset"),
    "CT-006": dict(systems=["refrigeration"], hours=3, note="Off-hours slow rise; door seal ingress"),
    "CT-007": dict(systems=["hvac", "lighting"], hours=1, note="Brief high-magnitude draw; power surge"),
    # operational_variation
    "CT-008": dict(systems=["refrigeration", "hvac", "other"], hours=8, note="All systems elevated; peak shipping day"),
    "CT-009": dict(systems=["hvac", "lighting", "other"], hours=6, note="Shift-window match for extended operations"),
    "CT-010": dict(systems=["hvac"], hours=4, note="Spike proportional to temperature deviation; no fault signature"),
    "CT-011": dict(systems=["other", "hvac"], hours=5, note="Unfamiliar load profile; rental unit on site"),
    # data_anomaly
    "CT-012": dict(systems=["refrigeration", "hvac", "lighting"], hours=2, note="Near-zero then compensatory spike; meter loss"),
    "CT-013": dict(systems=["refrigeration", "hvac", "lighting"], hours=1, note="Physically implausible single reading; sensor noise"),
    "CT-014": dict(systems=["refrigeration", "hvac", "lighting"], hours=1, note="Reading many times historical max; transmission error"),
}


def apply_shape(series, idx, ct_id, magnitude, temps):
    """Write one anomaly into `series` starting at `idx`. Returns hours affected."""
    spec = CATALOGUE[ct_id]
    n = spec["hours"]
    baseline = series[idx]

    if ct_id == "CT-001":                       # rapid rise, sustained plateau
        series[idx:idx + n] += magnitude
    elif ct_id == "CT-002":                     # gradual climb, no recovery
        series[idx:idx + n] += np.linspace(magnitude * 0.35, magnitude, n)
    elif ct_id == "CT-003":                     # intermittent — alternating hours
        series[idx:idx + n:2] += magnitude
    elif ct_id == "CT-004":                     # sustained, modest
        series[idx:idx + n] += magnitude * 0.8
    elif ct_id in ("CT-005", "CT-007"):         # single-interval
        series[idx] += magnitude
    elif ct_id == "CT-006":                     # slow rise, off-hours
        series[idx:idx + n] += np.linspace(magnitude * 0.4, magnitude, n)
    elif ct_id == "CT-008":                     # peak throughput, long and flat
        series[idx:idx + n] += magnitude * 0.55
    elif ct_id == "CT-009":                     # overtime — looks like a shift
        series[idx:idx + n] += magnitude * 0.6
    elif ct_id == "CT-010":                     # scales with how hot it is
        excess = np.clip(temps[idx:idx + n] - 78.0, 0, None)
        series[idx:idx + n] += magnitude * 0.10 * excess
    elif ct_id == "CT-011":                     # steady unfamiliar block
        series[idx:idx + n] += magnitude * 0.5
    elif ct_id == "CT-012":                     # dropout then catch-up
        series[idx] = 0.4
        series[idx + 1] = baseline * 2 + magnitude
    elif ct_id == "CT-013":                     # implausible single reading
        series[idx] = baseline + magnitude * 3
    elif ct_id == "CT-014":                     # >5x historical max
        series[idx] = baseline * 6 + magnitude
    return n


# ── Weather ──────────────────────────────────────────────────────────────────


def load_weather(facilities, start, end):
    """Real hourly temperatures per facility, cached so reruns are offline."""
    if WEATHER_CACHE.exists():
        cached = pd.read_csv(WEATHER_CACHE, parse_dates=["recorded_at"])
        covered = cached.groupby("facility_id").recorded_at.agg(["min", "max"])
        if (
            set(covered.index) >= set(facilities.facility_id)
            and covered["min"].max() <= start
            and covered["max"].min() >= end
        ):
            print(f"weather: cache hit ({len(cached):,} rows)")
            return cached

    try:
        from fetch_weather import FACILITY_COORDS, fetch_city
    except ImportError:
        sys.exit("fetch_weather.py not found — it supplies the temperature source.")

    print(f"weather: fetching {start:%Y-%m-%d} -> {end:%Y-%m-%d}")
    frames = []
    for f in facilities.itertuples():
        if f.facility_name not in FACILITY_COORDS:
            sys.exit(f"no coordinates for {f.facility_name} — add them to fetch_weather.py")
        lat, lon, tz = FACILITY_COORDS[f.facility_name]
        df = fetch_city(lat, lon, tz, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        df.insert(0, "facility_id", f.facility_id)
        frames.append(df.rename(columns={"temp_f_real": "temp_f"}))
        print(f"  {f.facility_name}: {len(df):,} hours")
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(WEATHER_CACHE, index=False)
    return out


# ── Clean series ─────────────────────────────────────────────────────────────


def clean_series(system, hours, temps, rng):
    """Consumption with no anomalies: base + shift + weather + duty cycle + noise."""
    t = system.system_type
    hour_of_day = hours.hour.to_numpy()
    weekday = hours.dayofweek.to_numpy()

    level = np.full(len(hours), BASE_KW.get(t, BASE_KW["other"]))

    on_shift = np.isin(hour_of_day, list(DAY_SHIFT)) | np.isin(hour_of_day, NIGHT_SHIFT)
    level += on_shift * SHIFT_KW.get(t, 0.0)

    level += np.clip(temps - 65.0, 0, None) * TEMP_COEF.get(t, 0.0)

    if t == "refrigeration":
        phase = hash(system.system_id) % COMPRESSOR_CYCLE_HOURS
        level += ((hour_of_day % COMPRESSOR_CYCLE_HOURS) == phase) * COMPRESSOR_AMPLITUDE_KW
    if t in ("other", "lighting"):
        level += np.isin(hour_of_day, FORKLIFT_HOURS) * FORKLIFT_KW

    level *= np.where(weekday >= 5, WEEKEND_SCALE, 1.0)
    level += rng.normal(0, NOISE_FRACTION * level + NOISE_FLOOR_KW)
    return np.clip(level, 0.5, None)


# ── Detector ─────────────────────────────────────────────────────────────────


def rolling_baseline(frame, neighbours=12, lookback_days=90, min_samples=5,
                     weather_aware=True):
    """Rolling median at the same hour, weekday, and temperature band.

    Mirrors the schema's definition, with one deliberate change: the lookback is
    90 days, not the schema's 28. At 28 days a same-hour, same-weekday, same-
    temperature cell holds four readings — below any sane minimum — so the match
    degrades to same-hour-any-temperature and the baseline stops tracking
    weather. On a temperature-driven load that leaves a residual far larger than
    the 20 kWh alert threshold, and the detector fires on ordinary hot
    afternoons. Temperature is also matched before weekday, since cooling load
    cares more about degrees than about which day it is.
    """
    kwh = frame.kwh.to_numpy()
    temps = frame.temp_f.to_numpy()
    hours = frame.recorded_at.dt.hour.to_numpy()
    dows = frame.recorded_at.dt.dayofweek.to_numpy()
    weekend = dows >= 5
    times = frame.recorded_at.to_numpy()
    window = np.timedelta64(lookback_days, "D")

    out = np.empty(len(frame))
    for i in range(len(frame)):
        prior = (times < times[i]) & (times >= times[i] - window)
        if prior.sum() < min_samples:
            out[i] = kwh[i]
            continue
        same_hour = prior & (hours == hours[i])
        # Weekend class is matched before anything else. Throughput drops
        # sharply at weekends, so a comparison set that mixes the two carries an
        # offset of roughly the alert threshold itself.
        candidates = same_hour & (weekend == weekend[i])
        if candidates.sum() < min_samples:
            candidates = same_hour
        if candidates.sum() < min_samples:
            out[i] = np.median(kwh[prior])
            continue

        pool = np.flatnonzero(candidates)
        if not weather_aware:
            # The alarm a manager already receives is a plain threshold on a
            # simple baseline; it has no idea what the weather is doing. Leaving
            # temperature out here is what gives the agent something to correct
            # for downstream — a hot-afternoon surge trips this and is then
            # cleared once Tool 2 conditions on temperature.
            out[i] = np.median(kwh[pool])
            continue
        # Take the readings nearest in temperature rather than those inside a
        # fixed band. A fixed band is empty during seasonal transitions — on the
        # first warm day of spring nothing in the prior 90 days is within 5F —
        # and the match then silently drops temperature altogether, leaving a
        # winter baseline against a summer reading. Nearest-neighbour always
        # conditions on temperature as far as the history allows.
        nearest = pool[np.argsort(np.abs(temps[pool] - temps[i]))[:neighbours]]
        out[i] = np.median(kwh[nearest])
    return out


def detect(frame, kwh_threshold, duration_min, active=None):
    """Runs of consecutive hours exceeding baseline + threshold.

    `active` masks off hours that are not being monitored yet; positions in the
    returned runs index `frame` directly.
    """
    over = (frame.kwh - frame.baseline_kwh) > kwh_threshold
    if active is not None:
        over &= active
    events, run = [], []
    for i, flag in enumerate(over.to_numpy()):
        if flag:
            run.append(i)
        elif run:
            events.append(run)
            run = []
    if run:
        events.append(run)
    return [e for e in events if len(e) * 60 >= duration_min]


# ── Generation ───────────────────────────────────────────────────────────────


def build(months, n_core, n_co, n_sub, seed, out_path):
    rng = np.random.default_rng(seed)
    src = pd.ExcelFile(SOURCE_WORKBOOK)
    facilities = src.parse("facility_registry")
    systems = src.parse("system_registry")
    registry = src.parse("classification_registry")

    end = pd.Timestamp.now("UTC").tz_localize(None).normalize() - pd.Timedelta(days=6)
    start = (end - pd.DateOffset(months=months)).normalize()
    hours = pd.date_range(start, end, freq="h", inclusive="left")
    print(f"window: {start:%Y-%m-%d} -> {end:%Y-%m-%d}  ({len(hours):,} hours)")

    weather = load_weather(facilities, start, end)
    wide = {
        fid: g.set_index("recorded_at").temp_f.reindex(hours).interpolate().bfill().ffill().to_numpy()
        for fid, g in weather.groupby("facility_id")
    }

    # 1. clean consumption per system
    series = {}
    for s in systems.itertuples():
        series[s.system_id] = clean_series(s, hours, wide[s.facility_id], rng)

    thresholds = facilities.set_index("facility_id")

    # 2. plan injections
    by_class = registry.groupby("top_level_class").classification_id.apply(list).to_dict()
    plan = []

    def pick_ct(pool):
        return str(rng.choice(pool))

    # Every classification the product can emit must appear at least once, or the
    # test set silently fails to exercise it. Random draws missed CT-010, the
    # weather-driven surge — the one case built to separate Theory A from
    # Theory B — leaving the weather machinery untested.
    n_fault = round(n_core * 0.60)
    n_oper = round(n_core * 0.27)
    quota = {"equipment_fault": n_fault, "operational_variation": n_oper,
             "data_anomaly": n_core - n_fault - n_oper}
    core_ids = []
    for cls, want in quota.items():
        pool = by_class[cls]
        core_ids += pool[:want]                      # one of each, in order
        core_ids += [pick_ct(pool) for _ in range(max(0, want - len(pool)))]
    core_ids = core_ids[:n_core]
    missing = [c for c in CATALOGUE if c not in core_ids]
    if missing:
        print(f"  note: {len(missing)} classification(s) not in core stratum: {missing}")
    for ct in core_ids:
        plan.append(("core", [ct]))
    for _ in range(n_co):
        # A fault hiding underneath an operational surge — the case the
        # three-class scheme assumes cannot happen.
        plan.append(("co_occurring", [pick_ct(by_class["equipment_fault"]),
                                      pick_ct(by_class["operational_variation"])]))
    for _ in range(n_sub):
        plan.append(("sub_threshold", [pick_ct(by_class["equipment_fault"])]))

    # 3. inject
    usable = hours[(hours >= start + pd.Timedelta(days=95)) & (hours < end - pd.Timedelta(days=2))]
    injections, taken = [], {s: set() for s in series}

    for stratum, ct_ids in plan:
        hosts = [
            s for s in systems.itertuples()
            if all(s.system_type in CATALOGUE[c]["systems"] for c in ct_ids)
        ]
        if not hosts:
            continue
        host = hosts[rng.integers(len(hosts))]
        arr = series[host.system_id]

        # A weather-driven surge only exists when it is hot. Placing one on a mild
        # hour produces no excursion at all, which is how CT-010 — the case that
        # separates Theory A from Theory B — kept vanishing from the test set.
        needs_heat = "CT-010" in ct_ids
        temps_here = wide[host.facility_id]
        hot = np.percentile(temps_here, 85)

        for _ in range(200):
            at = usable[rng.integers(len(usable))]
            idx = hours.get_loc(at)
            span = max(CATALOGUE[c]["hours"] for c in ct_ids)
            if taken[host.system_id] & set(range(idx - 6, idx + span + 6)):
                continue
            if needs_heat and temps_here[idx] < hot:
                continue
            break
        else:
            continue

        level = float(np.median(arr[max(0, idx - 336):idx]))
        scale = {"core": (1.6, 3.4), "co_occurring": (1.5, 3.0), "sub_threshold": (0.42, 0.62)}[stratum]
        magnitude = level * float(rng.uniform(*scale))

        # Several shapes apply only a fraction of the magnitude, so a spike sized
        # off a low-consumption meter can land under the alert threshold and never
        # be detected. Floor it so the case reaches the test set — except in the
        # sub-threshold stratum, where being marginal is the whole point.
        if stratum != "sub_threshold":
            magnitude = max(magnitude, 3.0 * float(thresholds.loc[host.facility_id]
                                                   .spike_kwh_threshold))

        span = 0
        for ct in ct_ids:
            span = max(span, apply_shape(arr, idx, ct, magnitude, wide[host.facility_id]))
        taken[host.system_id] |= set(range(idx, idx + span))

        injections.append(
            dict(stratum=stratum, system_id=host.system_id, facility_id=host.facility_id,
                 at=at, ct_ids=ct_ids, magnitude=magnitude)
        )

    # 4. readings table
    readings = pd.concat(
        [
            pd.DataFrame(
                dict(
                    reading_id=[f"RD-{s.system_id}-{i:06d}" for i in range(len(hours))],
                    facility_id=s.facility_id, system_id=s.system_id,
                    recorded_at=hours, kwh=np.round(series[s.system_id], 2),
                    temp_f=np.round(wide[s.facility_id], 1),
                )
            )
            for s in systems.itertuples()
        ],
        ignore_index=True,
    )

    # 5. detect
    print("detecting spikes …")
    detected = []
    for sid, g in readings.groupby("system_id", sort=False):
        g = g.sort_values("recorded_at").reset_index(drop=True)
        g["baseline_kwh"] = rolling_baseline(g, weather_aware=False)
        cfg = thresholds.loc[g.facility_id.iloc[0]]
        # Nothing is monitored until a full lookback of history exists — before
        # that the baseline is built from too few readings and flags ordinary
        # load. Real deployments have the same blind spot on day one.
        warm = g.recorded_at >= g.recorded_at.min() + pd.Timedelta(days=WARMUP_DAYS)
        for run in detect(g, cfg.spike_kwh_threshold,
                          cfg.spike_duration_threshold_min, active=warm):
            peak = g.loc[run].assign(delta=lambda d: d.kwh - d.baseline_kwh).delta.idxmax()
            detected.append(
                dict(system_id=sid, facility_id=g.facility_id.iloc[0],
                     detected_at=g.recorded_at[run[0]],
                     peak_at=g.recorded_at[peak],
                     spike_kwh=round(float(g.kwh[peak] - g.baseline_kwh[peak]), 2),
                     baseline_kwh=round(float(g.baseline_kwh[peak]), 2),
                     duration_minutes=len(run) * 60,
                     temp_f_at_detection=round(float(g.temp_f[run[0]]), 1))
            )
    det = pd.DataFrame(detected)
    print(f"  {len(det)} spikes detected from {len(injections)} injections")

    # 6. match detections back to injections
    rows, truth_rows, missed = [], [], []
    reg = registry.set_index("classification_id")
    for n, inj in enumerate(injections):
        hit = det[
            (det.system_id == inj["system_id"])
            & (det.detected_at >= inj["at"] - pd.Timedelta(hours=1))
            & (det.detected_at <= inj["at"] + pd.Timedelta(hours=3))
        ]
        if hit.empty:
            missed.append(inj)
            continue
        d = hit.iloc[0]
        aid = f"ANO-{2000 + len(rows)}"
        rows.append(
            dict(anomaly_id=aid, facility_id=inj["facility_id"], system_id=inj["system_id"],
                 detected_at=d.detected_at, spike_kwh=d.spike_kwh,
                 duration_minutes=d.duration_minutes, baseline_kwh=d.baseline_kwh,
                 temp_f_at_detection=d.temp_f_at_detection, status="unclassified",
                 classified_at=pd.NaT, classification_minutes=np.nan)
        )
        primary = inj["ct_ids"][0]
        truth_rows.append(
            dict(case_id=f"TC-{len(truth_rows) + 1:02d}", anomaly_id=aid,
                 stratum=inj["stratum"],
                 true_top_level_class=reg.loc[primary].top_level_class,
                 true_classification_id=primary,
                 true_subtype_label=reg.loc[primary].subtype_label,
                 co_occurring_with=inj["ct_ids"][1] if len(inj["ct_ids"]) > 1 else None,
                 spike_kwh=d.spike_kwh, baseline_kwh=d.baseline_kwh,
                 temp_f=d.temp_f_at_detection, duration_hours=d.duration_minutes // 60,
                 hour_of_day=d.detected_at.hour,
                 day_of_week=d.detected_at.day_name(),
                 notes=CATALOGUE[primary]["note"])
        )
    anomalies = pd.DataFrame(rows)
    truth = pd.DataFrame(truth_rows)
    print(f"  {len(anomalies)} matched to injections, {len(missed)} injections undetected")

    # 7. manager actions — ground truth is recorded for every acted case, so the
    #    two scoring paths in the old workbook can no longer diverge.
    acts = []
    for i, t in enumerate(truth.itertuples()):
        if rng.random() > 0.73:
            continue
        rec = reg.loc[t.true_classification_id].recommended_action
        acts.append(
            dict(action_id=f"ACT-{i:04d}", classification_id=None, anomaly_id=t.anomaly_id,
                 # One verb per outcome, matching what the agent recommends. The
                 # old scheme collapsed dispatch and monitor into "accepted", so
                 # once an action was logged you could no longer tell from the
                 # data whether a technician was actually sent.
                 action_taken={"dispatch": "dispatched", "monitor": "monitoring",
                               "dismiss": "dismissed"}[rec],
                 acted_at=anomalies.set_index("anomaly_id").loc[t.anomaly_id].detected_at
                 + pd.Timedelta(minutes=float(rng.uniform(6, 40))),
                 resolution_minutes=round(float(rng.uniform(6, 40)), 1),
                 engineer_called=bool(rng.random() < 0.25),
                 actual_top_level_class=t.true_top_level_class,
                 actual_classification_id=t.true_classification_id)
        )
    actions = pd.DataFrame(acts)

    # 8. empty classifications — classifier.py fills this
    classifications = pd.DataFrame(
        columns=["classification_id", "anomaly_id", "top_level_class",
                 "classification_type_id", "confidence_score", "explanation_text",
                 "created_at", "review_recommended", "weather_adjusted"]
    )

    readme = pd.DataFrame({"Energy Anomaly Explainer — generated dataset": [
        f"Generated by generate_dataset.py, seed {seed}",
        f"Window {start:%Y-%m-%d} to {end:%Y-%m-%d} ({months} months, {len(hours):,} hours)",
        "",
        "Temperatures are REAL (Open-Meteo ERA5 archive), not synthetic. Consumption",
        "is generated from them, so weather adjustment can be tested rather than assumed.",
        "",
        "GROUND TRUTH lives in test_set_15_cases and nowhere else.",
        "manager_actions.actual_top_level_class is copied from it for every acted case,",
        "so the two can never disagree. Score on the full sheet, not on acted cases only:",
        "filtering to acted cases silently drops every abstention.",
        "",
        "STRATA (column `stratum` in test_set_15_cases):",
        "  core          single cause, above detection threshold — the spec's success bar",
        "  co_occurring  two causes in the same hour; score separately",
        "  sub_threshold deliberately weak; should fall below z=2.0",
        "",
        "classifications is EMPTY by design — run classifier.py to populate it.",
    ]})

    with pd.ExcelWriter(out_path, engine="openpyxl") as w:
        facilities.to_excel(w, sheet_name="facility_registry", index=False)
        systems.to_excel(w, sheet_name="system_registry", index=False)
        registry.to_excel(w, sheet_name="classification_registry", index=False)
        readings.to_excel(w, sheet_name="energy_readings", index=False)
        anomalies.to_excel(w, sheet_name="anomalies", index=False)
        classifications.to_excel(w, sheet_name="classifications", index=False)
        actions.to_excel(w, sheet_name="manager_actions", index=False)
        truth.to_excel(w, sheet_name="test_set_15_cases", index=False)
        readme.to_excel(w, sheet_name="README", index=False)

    print(f"\nwrote {out_path.name}  ({out_path.stat().st_size / 1e6:.1f} MB)")
    print(f"  energy_readings {len(readings):,} · anomalies {len(anomalies)} · "
          f"actions {len(actions)} · classifications 0 (run classifier.py)")
    print("\nby stratum:")
    for name, g in truth.groupby("stratum"):
        print(f"  {name:14} {len(g):3}   " +
              "  ".join(f"{k}={v}" for k, v in g.true_top_level_class.value_counts().items()))
    if missed:
        print(f"\ndetection misses ({len(missed)}): " +
              ", ".join(f"{m['ct_ids'][0]}@{m['stratum']}" for m in missed))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--cases", type=int, default=15, help="core stratum size")
    ap.add_argument("--co-occurring", type=int, default=0)
    ap.add_argument("--sub-threshold", type=int, default=0)
    ap.add_argument("--seed", type=int, default=43800)
    ap.add_argument("--out", type=Path, default=HERE / "dummy_data_set2.xlsx")
    a = ap.parse_args()
    build(a.months, a.cases, a.co_occurring, a.sub_threshold, a.seed, a.out)
