"""
Reproduces the review's figures. NOTE: the review was written against v1;
this now reads v2, so the "review cites" markers no longer match. Kept for the
method, not the numbers.

Run with:  ./.venv/bin/python verify_review_numbers.py

Reimplements the dashboard's four agent tools rather than importing them, so the
numbers are checked independently of the app rather than inherited from it.
"""

import math
import pandas as pd

DISPATCH_COST = 300.0        # spec: "one technician dispatch costs approximately $300"
MISS_COST_LOW = 2000.0       # spec: "$2,000-$8,000 in excess electricity cost"
MISS_COST_HIGH = 8000.0
COST_RATIO = 167.0           # spec: "ratio of miss cost to false-alarm cost is 167:1 to 800:1"

xl = pd.ExcelFile("dummy_data_set2.xlsx")
readings = xl.parse("energy_readings")
anomalies = xl.parse("anomalies")
classifications = xl.parse("classifications")
registry = xl.parse("classification_registry")
test_set = xl.parse("test_set_15_cases")

readings["recorded_at"] = pd.to_datetime(readings.recorded_at)
anomalies["detected_at"] = pd.to_datetime(anomalies.detected_at)


def baseline_std(anomaly):
    """Tool 2 — the dashboard's progressive fallback ladder for the baseline std."""
    t, temp = anomaly.detected_at, anomaly.temp_f_at_detection
    meter = readings[
        (readings.facility_id == anomaly.facility_id)
        & (readings.system_id == anomaly.system_id)
    ]
    lookback = meter[
        (meter.recorded_at < t) & (meter.recorded_at >= t - pd.Timedelta(days=28))
    ].copy()
    if lookback.empty:
        return max(anomaly.baseline_kwh * 0.12, 1.0)

    lookback["hour"] = lookback.recorded_at.dt.hour
    lookback["dow"] = lookback.recorded_at.dt.dayofweek
    slot = lookback[(lookback.hour == t.hour) & (lookback.dow == t.dayofweek)]
    hour = lookback[lookback.hour == t.hour]

    for sample in [
        slot[slot.temp_f.between(temp - 5, temp + 5)],
        hour[hour.temp_f.between(temp - 5, temp + 5)],
        slot,
        hour,
        lookback,
    ]:
        if len(sample) < 5:
            continue
        s = sample.kwh.std()
        if pd.notna(s) and s > 0:
            return float(s)
    return max(anomaly.baseline_kwh * 0.12, 1.0)


RANK = {"dismiss": 0, "monitor": 1, "dispatch": 2}


def agent_decision(anomaly):
    """Tools 3-4 — statistical gate, then the semantic cap from the registry."""
    z = anomaly.spike_kwh / baseline_std(anomaly)
    if z < 2.0:
        return z, None, "dismiss"

    rows = classifications[classifications.anomaly_id == anomaly.anomaly_id]
    conf = float(rows.iloc[0].confidence_score) if not rows.empty else None
    decision = "dispatch" if (z >= 3.0 and conf is not None and conf >= 0.75) else "monitor"

    if not rows.empty:
        match = registry[registry.classification_id == rows.iloc[0].classification_type_id]
        if not match.empty:
            ceiling = match.iloc[0].recommended_action
            if RANK[ceiling] < RANK[decision]:
                decision = ceiling
    return z, conf, decision


# ── 1. Primary success bar ────────────────────────────────────────────────────

scored = test_set.merge(
    classifications[["anomaly_id", "top_level_class", "confidence_score"]],
    on="anomaly_id", how="left",
)
scored["pred"] = scored.top_level_class.fillna("(abstained)")

TP = ((scored.pred == "equipment_fault") & (scored.true_top_level_class == "equipment_fault")).sum()
FP = ((scored.pred == "equipment_fault") & (scored.true_top_level_class != "equipment_fault")).sum()
FN = ((scored.pred != "equipment_fault") & (scored.true_top_level_class == "equipment_fault")).sum()
n_faults = (scored.true_top_level_class == "equipment_fault").sum()

precision, recall = TP / (TP + FP), TP / (TP + FN)

print("=" * 72)
print("[1] PRIMARY SUCCESS BAR  — equipment_fault, 15-case held-out set")
print("=" * 72)
print(f"  true equipment faults in test set : {n_faults}          <- review cites 9")
print(f"  TP={TP}  FP={FP}  FN={FN}")
print(f"  Precision = {TP}/{TP+FP} = {precision:.1%}   (bar >=75%)  {'PASS' if precision >= .75 else 'FAIL'}"
      f"          <- review cites 100%")
print(f"  Recall    = {TP}/{TP+FN} = {recall:.1%}   (bar >=70%)  {'PASS' if recall >= .70 else 'FAIL'}"
      f"          <- review cites 66.7%")

# ── 2. Agent decision mix ─────────────────────────────────────────────────────

rows = []
for a in anomalies.itertuples():
    z, conf, decision = agent_decision(a)
    truth = test_set[test_set.anomaly_id == a.anomaly_id].iloc[0].true_top_level_class
    rows.append(dict(anomaly=a.anomaly_id, z=round(z, 1), confidence=conf,
                     decision=decision, truth=truth))
d = pd.DataFrame(rows)
mix = d.decision.value_counts().to_dict()

print()
print("=" * 72)
print("[2] AGENT DECISION MIX")
print("=" * 72)
print(f"  dispatch={mix.get('dispatch', 0)}  monitor={mix.get('monitor', 0)}  "
      f"dismiss={mix.get('dismiss', 0)}          <- review cites 2 / 8 / 5")
print(f"  spikes with z >= 2.0 : {(d.z >= 2).sum()} of {len(d)}   (max z = {d.z.max()})")
print("     ^ the 'NOT SIGNIFICANT' path is unreachable on this dataset")

# ── 3. Decision-flip audit vs. the trivial policy ─────────────────────────────

faults = d[d.truth == "equipment_fault"]
caught = (faults.decision == "dispatch").sum()
missed = len(faults) - caught
tool_dispatch_spend = (d.decision == "dispatch").sum() * DISPATCH_COST
blanket_spend = len(d) * DISPATCH_COST

print()
print("=" * 72)
print("[3] DECISION-FLIP AUDIT  — tool vs. 'dispatch on every flagged spike'")
print("=" * 72)
print(f"  real equipment faults          : {len(faults)}")
print(f"  faults the tool dispatches to  : {caught}          <- review cites 2 of 9")
print(f"  faults left uninvestigated     : {missed}          <- review cites 7")
print()
print(f"  blanket dispatch : {len(d)} x ${DISPATCH_COST:,.0f} = ${blanket_spend:,.0f}, misses 0"
      f"          <- review cites $4,500")
print(f"  tool             : {int(tool_dispatch_spend / DISPATCH_COST)} x ${DISPATCH_COST:,.0f} "
      f"= ${tool_dispatch_spend:,.0f}, plus {missed} missed faults")
print(f"                     exposure = ${missed * MISS_COST_LOW:,.0f} - "
      f"${missed * MISS_COST_HIGH:,.0f}          <- review cites $14,000-$56,000")

# ── 4. Confidence threshold demotions ────────────────────────────────────────

demoted = d[(d.truth == "equipment_fault") & (d.decision == "monitor")
            & d.confidence.notna() & (d.confidence < 0.75)]

print()
print("=" * 72)
print("[4] CONFIDENCE-THRESHOLD DEMOTIONS  (auto-classify bar = 0.75)")
print("=" * 72)
print(f"  break-even p at cost ratio {COST_RATIO:.0f}:1 = 1/(1+{COST_RATIO:.0f}) = "
      f"{1 / (1 + COST_RATIO):.2%}          <- review cites 0.6%")
for r in demoted.itertuples():
    print(f"  {r.anomaly}: true equipment fault, confidence {r.confidence:.2f} "
          f"-> demoted to MONITOR (gap {0.75 - r.confidence:.2f})")
print("     ^ review cites gaps of 0.01 and 0.02")

# ── 5. Arithmetic taken from the specification (verify against the proposal) ──

print()
print("=" * 72)
print("[5] SPEC ARITHMETIC  — check these against the proposal text, not the data")
print("=" * 72)
print(f"  3-5 anomalies/month  -> {3*12}-{5*12} per facility-year")
print(f"  blanket dispatch     -> ${3*12*DISPATCH_COST:,.0f}-${5*12*DISPATCH_COST:,.0f} "
      f"per facility-year          <- review cites $10,800-$18,000")
print(f"  $60k-$240k / 10 facilities -> $6,000-$24,000 per facility-year")
print("     ^ the two ranges overlap: that is the review's section 1 argument")
print()
print("Per-anomaly detail:")
print(d.to_string(index=False))
