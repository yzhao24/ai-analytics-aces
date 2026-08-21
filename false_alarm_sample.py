"""
Test the classifier against the detector alarms it has never been scored on.

The detector raises 562 alarms across the year; only the 25 that match an
injected anomaly reach the test set. The other 537 are false alarms, and the
product has never been asked to classify one. That matters more than "our test
set is easy": with 20 real faults among 25 scored cases, the most any policy can
save against blanket dispatch is $1,500 while one missed fault costs $2,000, so
no policy that ever withholds a dispatch can win. The test set cannot show the
product working even in principle.

Ground truth here is free. A detection that matches no injected anomaly is, by
construction, not an equipment fault -- so the correct action on every one of
these is "do not send anyone".

    python3 false_alarm_sample.py --build            # rebuild alarms, no API calls
    python3 false_alarm_sample.py --classify -n 100  # sample and classify (~$2.40)
    python3 false_alarm_sample.py --score            # score whatever has been run

Sampling is deliberate. 100 of 537 costs about $2.40 and is enough to tell a
classifier that calls 10% of false alarms faults from one that calls 60% -- the
difference between a product worth deploying and one that would flood the queue.
Run the full set only if the sample looks worth the $13.
"""

import argparse
import importlib.util
import json
import random
import sys
import time
from pathlib import Path

import pandas as pd

import classifier

HERE = Path(__file__).parent
ALARMS = HERE / "false_alarms.json"
RESULTS = HERE / "false_alarm_results.json"
SEED = 43800


def _load_generator():
    spec = importlib.util.spec_from_file_location("gd", HERE / "generate_dataset.py")
    gd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gd)
    return gd


def build():
    """Re-run the detector and keep every alarm that is not an injected anomaly."""
    gd = _load_generator()
    xl = pd.ExcelFile(classifier.DATA_FILE)
    readings = xl.parse("energy_readings")
    readings["recorded_at"] = pd.to_datetime(readings.recorded_at)
    facs = xl.parse("facility_registry").set_index("facility_id")
    injected = xl.parse("anomalies")
    injected["detected_at"] = pd.to_datetime(injected.detected_at)

    # An alarm is "real" if an injected anomaly starts on the same meter within
    # the same hour; everything else is a false alarm.
    claimed = {(r.system_id, pd.Timestamp(r.detected_at).floor("h"))
               for r in injected.itertuples()}

    rows, n_alarms = [], 0
    for sid, g in readings.groupby("system_id"):
        g = g.sort_values("recorded_at").reset_index(drop=True)
        fac = g.facility_id.iloc[0]
        g = g.assign(baseline_kwh=gd.rolling_baseline(g, weather_aware=False))
        warm = g.recorded_at >= g.recorded_at.min() + pd.Timedelta(days=gd.WARMUP_DAYS)
        events = gd.detect(g, float(facs.loc[fac].spike_kwh_threshold),
                           int(facs.loc[fac].spike_duration_threshold_min), active=warm)
        n_alarms += len(events)
        for ev in events:
            peak_i = max(ev, key=lambda i: g.kwh.iloc[i] - g.baseline_kwh.iloc[i])
            start = g.recorded_at.iloc[ev[0]]
            if (sid, pd.Timestamp(start).floor("h")) in claimed:
                continue
            rows.append({
                "anomaly_id": f"FA-{len(rows):04d}",
                "facility_id": fac,
                "system_id": sid,
                "detected_at": start.isoformat(),
                "spike_kwh": round(float(g.kwh.iloc[peak_i] - g.baseline_kwh.iloc[peak_i]), 2),
                "baseline_kwh": round(float(g.baseline_kwh.iloc[peak_i]), 2),
                "duration_minutes": len(ev) * 60,
                "temp_f_at_detection": round(float(g.temp_f.iloc[peak_i]), 1),
            })
    ALARMS.write_text(json.dumps(rows, indent=1))
    print(f"  detector alarms       {n_alarms}")
    print(f"  matched an injection  {n_alarms - len(rows)}")
    print(f"  false alarms kept     {len(rows)}  -> {ALARMS.name}")
    return rows


class _Row:
    """Quacks like the namedtuple classifier.build_prompt expects."""
    def __init__(self, d):
        self.__dict__.update(d)
        self.detected_at = pd.Timestamp(d["detected_at"])


def classify(n):
    import anthropic

    rows = json.loads(ALARMS.read_text()) if ALARMS.exists() else build()
    random.Random(SEED).shuffle(rows)
    sample = rows[:n]

    data = classifier.load_inputs()
    sysr = data["system_registry"]
    client = anthropic.Anthropic()
    out = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}

    est = n * 0.024
    print(f"  classifying {n} of {len(rows)} false alarms  (~${est:.2f})\n")
    for i, d in enumerate(sample, 1):
        if d["anomaly_id"] in out:
            continue
        a = _Row(d)
        srow = sysr[sysr.system_id == a.system_id]
        system = srow.iloc[0] if not srow.empty else None
        t0 = time.monotonic()
        try:
            resp = client.messages.create(
                model=classifier.MODEL, max_tokens=8000,
                system=classifier.SYSTEM_PROMPT,
                output_config={"effort": "low",
                               "format": {"type": "json_schema",
                                          "schema": classifier.SCHEMA}},
                messages=[{"role": "user",
                           "content": classifier.build_prompt(data, a, system)}],
            )
        except anthropic.AuthenticationError:
            sys.exit(classifier.NO_CREDS)
        rec = json.loads(next(b.text for b in resp.content if b.type == "text"))
        rec["latency_seconds"] = round(time.monotonic() - t0, 2)
        out[d["anomaly_id"]] = rec
        RESULTS.write_text(json.dumps(out, indent=1))
        if i % 10 == 0 or i == len(sample):
            print(f"    {i}/{len(sample)}", flush=True)
    print(f"\n  wrote {RESULTS.name}")


def score():
    from costs import COMMIT_THRESHOLD_DEFAULT as GATE, DISPATCH_COST as D, MISS_COST as M

    if not RESULTS.exists():
        sys.exit("  nothing classified yet — run --classify first")
    res = json.loads(RESULTS.read_text())
    # The alarm list is regenerated rather than tracked — the detector is
    # deterministic, so rebuilding costs ~10s and keeps a 537-row file out of
    # git. Scoring must not assume a previous --build in this working copy.
    if not ALARMS.exists():
        print("  false_alarms.json not present — rebuilding it (no API calls)")
        build()
        print()
    alarms = {r["anomaly_id"]: r for r in json.loads(ALARMS.read_text())}
    reg = pd.ExcelFile(classifier.DATA_FILE).parse("classification_registry") \
            .set_index("classification_id")
    RANK = {"dismiss": 0, "monitor": 1, "dispatch": 2}

    n = len(res)
    as_fault = sum(1 for p in res.values() if p["top_level_class"] == "equipment_fault")

    def decision(p, gate):
        cap = reg.loc[p["classification_type_id"]].recommended_action
        g = "dispatch" if p["confidence_score"] >= gate else "monitor"
        return min(g, cap, key=lambda k: RANK[k])

    sent_gate = sum(1 for p in res.values() if decision(p, GATE) == "dispatch")
    sent_class = as_fault          # the rule that scored best on the real test set

    print(f"\n{'='*70}\nFALSE ALARMS — the classifier has never been scored on these\n{'='*70}")
    print(f"  sampled                       {n} of {len(alarms)}")
    print(f"  called equipment_fault        {as_fault}  ({as_fault/n:.0%})")
    print(f"  every one of these is a false alarm, so that is the false-positive rate\n")
    print(f"  would dispatch, gate {GATE:.2f}      {sent_gate}  ({sent_gate/n:.0%})")
    print(f"  would dispatch, class rule    {sent_class}  ({sent_class/n:.0%})")

    by_class = {}
    for p in res.values():
        by_class[p["top_level_class"]] = by_class.get(p["top_level_class"], 0) + 1
    print(f"\n  what it called them:")
    for k, v in sorted(by_class.items(), key=lambda kv: -kv[1]):
        print(f"    {k:24} {v:4}  ({v/n:.0%})")

    # Extrapolate to the full year, adding back the 20 real faults.
    total_fa = len(alarms)
    print(f"\n{'='*70}\nEXTRAPOLATED TO ALL {total_fa} FALSE ALARMS + 20 REAL FAULTS\n{'='*70}")
    for label, rate, caught in [
        (f"follow the tool, gate {GATE:.2f}", sent_gate / n, 3),
        ("follow the tool, class rule", sent_class / n, 19),
    ]:
        sent = rate * total_fa + caught
        cost = sent * D + (20 - caught) * M
        print(f"  {label:32} sends ~{sent:6.0f}   costs ~${cost:,.0f}")
    print(f"  {'dispatch on every alarm':32} sends  {total_fa + 25:6.0f}   "
          f"costs ~${(total_fa + 25) * D:,.0f}")
    print(f"  {'perfect classifier':32} sends  {20:6.0f}   costs ~${20 * D:,.0f}")
    print("\n  Extrapolation assumes the sample is representative; it is random with a\n"
          f"  fixed seed, and at n={n} the false-positive rate carries roughly "
          f"±{100 * (0.25 / n) ** 0.5:.0f} points.\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--classify", action="store_true")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("-n", type=int, default=100)
    a = ap.parse_args()
    if a.build:
        build()
    if a.classify:
        classify(a.n)
    if a.score or not (a.build or a.classify):
        score()
