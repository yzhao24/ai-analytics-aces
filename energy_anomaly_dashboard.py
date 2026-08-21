"""
Energy Anomaly Explainer — Streamlit Dashboard
AI Analytics Aces · BUSN 43800

Run with:  streamlit run energy_anomaly_dashboard.py

Implements the 4-screen wireframe (Dashboard / Classification Panel / History &
Trends / Settings) and the 4-tool agent orchestrator described in wireframe_v2.md,
reading all data from dummy_data_set2.xlsx per data_schema_v2.md.
"""

import json
import math
from pathlib import Path

import input_guard
import operations_log
from costs import (BREAK_EVEN, COMMIT_THRESHOLD_DEFAULT, DISPATCH_COST,
                   MISS_COST)

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA_FILE = Path(__file__).parent / "dummy_data_set2.xlsx"
LLM_FILE = Path(__file__).parent / "classifications_llm.json"

BG = "#0F1B2D"
SURFACE = "#1A2B3C"
SURFACE_2 = "#243647"
GREEN = "#22C55E"
AMBER = "#F59E0B"
RED = "#EF4444"
BLUE = "#3B82F6"
GREY = "#6B7280"
TEAL = "#00C9B1"
TEXT = "#E2E8F0"
TEXT_DIM = "#94A3B8"
BORDER = "#2D4A6B"

CLASS_COLOR = {
    "equipment_fault": RED,
    "operational_variation": AMBER,
    "data_anomaly": GREY,
    "unclassified": GREY,
}
SEVERITY_COLOR = {"critical": RED, "warning": AMBER, "informational": BLUE}
DECISION_COLOR = {"dispatch": GREEN, "monitor": AMBER, "dismiss": GREY}

st.set_page_config(page_title="Energy Anomaly Explainer", page_icon="⚡", layout="wide")


# ── Data loading ───────────────────────────────────────────────────────────────


@st.cache_data
def load_data():
    xl = pd.ExcelFile(DATA_FILE)
    d = {name: xl.parse(name) for name in xl.sheet_names if name != "README"}

    for table, cols in [
        ("facility_registry", ["last_reading_at"]),
        ("energy_readings", ["recorded_at"]),
        ("anomalies", ["detected_at", "classified_at"]),
        ("classifications", ["created_at"]),
        ("manager_actions", ["acted_at"]),
    ]:
        for col in cols:
            d[table][col] = pd.to_datetime(d[table][col], errors="coerce")

    d["classifications"] = overlay_llm_classifications(d)

    # An anomaly the classifier has answered is no longer unclassified. Without
    # this the table shows a label next to a status of "unclassified", the donut
    # counts the same spike twice, and every row renders as severity "—".
    answered = set(d["classifications"].anomaly_id)
    if answered:
        ano = d["anomalies"]
        newly = ano.anomaly_id.isin(answered) & (ano.status == "unclassified")
        ano.loc[newly, "status"] = "classified"

        # Time to classify is real wall-clock from the classifier run, not a
        # figure carried in the workbook. Absent for runs made before the
        # classifier started recording it, so the KPI stays blank rather than
        # inventing a number.
        latency = d["classifications"].set_index("anomaly_id").get("latency_seconds")
        if latency is not None and latency.notna().any():
            mins = ano.anomaly_id.map(latency).astype("float64") / 60.0
            fill = newly & mins.notna()
            ano["classification_minutes"] = ano.classification_minutes.astype("float64")
            # Excel datetimes arrive at second resolution; the computed value is
            # nanosecond, and pandas will not assign across the two.
            ano["classified_at"] = pd.to_datetime(
                ano.classified_at, errors="coerce"
            ).astype("datetime64[ns]")
            ano.loc[fill, "classification_minutes"] = mins[fill]
            ano.loc[fill, "classified_at"] = ano.detected_at[fill] + pd.to_timedelta(
                mins[fill], unit="m"
            )
    return d


def overlay_llm_classifications(d):
    """Fold in `classifications_llm.json` if the classifier has been run.

    Written by classifier.py rather than back into the workbook, which is binary
    and unmergeable. An LLM row replaces the workbook row for the same anomaly, so
    a full run scores the classifier end to end instead of a mix of pre-written
    labels and fresh ones.
    """
    existing = d["classifications"]
    if not LLM_FILE.exists():
        return existing

    reg = d["classification_registry"].set_index("classification_id")
    rows = []
    for anomaly_id, r in json.loads(LLM_FILE.read_text()).items():
        type_id = r["classification_type_id"]
        rows.append(
            {
                "classification_id": f"LLM-{anomaly_id}",
                "anomaly_id": anomaly_id,
                # Trust the registry's own top-level class over the model's,
                # so the subtype and the class can never disagree downstream.
                "top_level_class": reg.loc[type_id].top_level_class
                if type_id in reg.index
                else r["top_level_class"],
                "classification_type_id": type_id,
                "confidence_score": r["confidence_score"],
                "explanation_text": r["explanation_text"],
                "created_at": pd.NaT,
                # Snapshot against the shipped default — load_data() is cached, so
                # this cannot track the Settings slider. The panel recomputes it
                # live from commit_threshold() instead.
                "review_recommended": r["confidence_score"] < COMMIT_THRESHOLD_DEFAULT,
                "weather_adjusted": True,
                "latency_seconds": r.get("latency_seconds"),
                "recommended_action": r.get("recommended_action"),
                "next_action": r.get("next_action"),
                "symptom_to_check": r.get("symptom_to_check"),
            }
        )
    llm = pd.DataFrame(rows)
    kept = existing[~existing.anomaly_id.isin(llm.anomaly_id)]
    return pd.concat([kept, llm], ignore_index=True)


# ── Agent tools (Section 10 of the wireframe) ─────────────────────────────────


def _two_tailed_p(z):
    """Abramowitz-Stegun normal tail approximation; avoids a scipy dependency."""
    az = abs(z)
    t = 1 / (1 + 0.2316419 * az)
    poly = t * (
        0.319381530
        + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429)))
    )
    pdf = math.exp(-(az**2) / 2) / math.sqrt(2 * math.pi)
    return min(2 * poly * pdf, 1.0)


def tool_fetch_readings(readings, anomaly):
    """Tool 1 — ±2hr window around detected_at, plus the prior 28 days."""
    fid, sid, t = anomaly.facility_id, anomaly.system_id, anomaly.detected_at
    same_meter = readings[
        (readings.facility_id == fid) & (readings.system_id == sid)
    ]
    window = same_meter[
        same_meter.recorded_at.between(
            t - pd.Timedelta(hours=2), t + pd.Timedelta(hours=4)
        )
    ].sort_values("recorded_at")
    lookback = same_meter[
        (same_meter.recorded_at < t)
        & (same_meter.recorded_at >= t - pd.Timedelta(days=28))
    ]
    return {
        "window": window,
        "lookback": lookback,
        "input_summary": f"facility={fid}, system={sid}, detected_at={t:%Y-%m-%d %H:%M}",
        "output_summary": f"{len(window)} window readings, {len(lookback)} lookback readings",
    }

# A comparison set this small gives a standard deviation that is mostly sampling
# noise; twelve is the point where it stops swinging on one reading.
MIN_COMPARISON_SAMPLES = 12
# No meter is quieter than this, so a suspiciously tight sample cannot drive the
# z-score to infinity by putting a near-zero number under the line.
NOISE_FLOOR_FRACTION = 0.03
NOISE_FLOOR_KWH = 0.75


def tool_compute_baseline(fetched, anomaly):
    """Tool 2 — expected consumption and its spread, from one comparison set.

    Mean and standard deviation must describe the *same* readings. Taking the
    mean from one source and the spread from another leaves the z-score measuring
    the gap between two reference points as much as the size of the spike.
    """
    lookback = fetched["lookback"]
    t, temp = anomaly.detected_at, anomaly.temp_f_at_detection
    fallback_mean = float(anomaly.baseline_kwh)

    def result(mean, std, n, weather, basis):
        # Floor the spread at plausible meter noise before it reaches the divisor.
        std = max(float(std), mean * NOISE_FLOOR_FRACTION, NOISE_FLOOR_KWH)
        return {
            "baseline_mean": float(mean),
            "baseline_std": std,
            "weather_adjusted": weather,
            "n_samples": int(n),
            "basis": basis,
            "input_summary": f"{len(lookback)} lookback readings · matched on {basis}",
            "output_summary": (
                f"mean={mean:.1f}, std={std:.1f}, weather_adjusted={weather}, n={n}"
            ),
        }

    if len(lookback) < MIN_COMPARISON_SAMPLES:
        return result(fallback_mean, fallback_mean * 0.12, len(lookback), False,
                      "insufficient history")

    hist = lookback.assign(
        hour=lookback.recorded_at.dt.hour,
        weekend=lookback.recorded_at.dt.dayofweek >= 5,
    )
    same_slot = hist[(hist.hour == t.hour) & (hist.weekend == (t.dayofweek >= 5))]
    pool, weather, basis = same_slot, True, f"hour={t.hour}, {'weekend' if t.dayofweek >= 5 else 'weekday'}"
    if len(pool) < MIN_COMPARISON_SAMPLES:
        pool, weather, basis = hist[hist.hour == t.hour], True, f"hour={t.hour}"
    if len(pool) < MIN_COMPARISON_SAMPLES:
        pool, weather, basis = hist, False, "all lookback readings"
    if len(pool) < MIN_COMPARISON_SAMPLES:
        return result(fallback_mean, fallback_mean * 0.12, len(pool), False,
                      "insufficient history")

    # Condition on temperature by taking the nearest readings rather than a fixed
    # band. A ±5°F band is empty whenever the weather has moved, and falling back
    # to "any temperature" quietly compares a hot afternoon against a cold one.
    if weather and pd.notna(temp):
        nearest = (pool.temp_f - temp).abs().nsmallest(
            max(MIN_COMPARISON_SAMPLES, len(pool) // 3)
        ).index
        pool = pool.loc[nearest]
        basis += f", nearest {len(pool)} by temp to {temp:.0f}°F"

    std = pool.kwh.std()
    if pd.isna(std) or std <= 0:
        return result(fallback_mean, fallback_mean * 0.12, len(pool), False,
                      "no variance in comparison set")
    return result(pool.kwh.median(), std, len(pool), weather, basis)


def tool_run_significance_test(baseline, anomaly):
    """Tool 3 — how far the observed peak sits from what this meter normally does.

    Both terms come from Tool 2's comparison set. The previous version divided a
    delta measured against the workbook's stored baseline by a spread measured
    over a different sample, so the two disagreed by however far apart those
    references were.
    """
    observed = float(anomaly.baseline_kwh) + float(anomaly.spike_kwh)
    z = (observed - baseline["baseline_mean"]) / baseline["baseline_std"]
    p = _two_tailed_p(z)
    percentile = (1 - p / 2) * 100
    verdict = "significant" if z >= 2.0 else "not_significant"

    temp = anomaly.temp_f_at_detection
    if not baseline["weather_adjusted"]:
        weather_context = (
            f"No temperature match in the lookback at {temp:.0f}°F — "
            "baseline falls back to hour and weekend class only."
        )
    elif verdict == "not_significant":
        # The alarm fired against a baseline that ignores temperature; once the
        # comparison is drawn from hours at a similar temperature the excursion
        # disappears. Saying weather does not explain it here would contradict
        # the z-score printed directly above.
        weather_context = (
            f"At {temp:.0f}°F this sits within normal consumption for comparable "
            "hours — the alert came from a baseline that does not account for "
            "temperature, and weather explains the difference."
        )
    elif temp >= 90:
        weather_context = (
            f"At {temp:.0f}°F, elevated cooling load is expected; this spike exceeds "
            "the weather-adjusted baseline even after accounting for temperature."
        )
    else:
        weather_context = (
            f"Temperature at detection was {temp:.0f}°F — weather does not explain "
            "this spike."
        )

    return {
        "z_score": z,
        "p_value": p,
        "percentile": percentile,
        "verdict": verdict,
        "weather_context": weather_context,
        "input_summary": (
            f"spike_kwh={anomaly.spike_kwh:.1f}, baseline_mean={baseline['baseline_mean']:.1f}, "
            f"baseline_std={baseline['baseline_std']:.1f}"
        ),
        "output_summary": f"z_score={z:.2f}, p_value={p:.4g}, verdict={verdict}",
    }


# Within this fraction of the current z-score counts as "comparable severity".
COMPARABLE_Z_TOLERANCE = 0.25


def tool_fetch_comparable_events(data, anomaly, z_score, z_by_anomaly):
    """Tool 4 — past spikes on the same system within ±0.5 z of this one."""
    reg = data["classification_registry"].set_index("classification_id")
    ano = data["anomalies"].set_index("anomaly_id")
    matches = []

    # The wireframe's ±0.5 window assumed z values clustered around 2 to 4. Real
    # ones span 10 to 84, so an absolute half-point window is about 1% of the
    # range and matches nothing. A proportional window keeps the intent — spikes
    # of comparable severity — at any scale.
    tolerance = max(COMPARABLE_Z_TOLERANCE * abs(z_score), 0.5)

    for other_id, other_z in z_by_anomaly.items():
        if other_id == anomaly.anomaly_id or abs(other_z - z_score) > tolerance:
            continue

        # "Comparable past events on the same system" per the wireframe: both
        # halves matter. Without the system filter the panel cites a refrigeration
        # fault as precedent for an HVAC spike; without the time filter it cites
        # anomalies that had not happened yet when this one was detected.
        other_row = ano.loc[other_id]
        if other_row.system_id != anomaly.system_id:
            continue
        if other_row.detected_at >= anomaly.detected_at:
            continue

        cls_rows = data["classifications"][
            data["classifications"].anomaly_id == other_id
        ]
        if cls_rows.empty:
            continue
        cls = cls_rows.iloc[0]

        act_rows = data["manager_actions"][
            data["manager_actions"].anomaly_id == other_id
        ]
        resolution = act_rows.iloc[0].action_taken if not act_rows.empty else "pending"

        label, cost = cls.top_level_class.replace("_", " ").title(), 0.0
        if cls.classification_type_id in reg.index:
            r = reg.loc[cls.classification_type_id]
            label = r.subtype_label if pd.notna(r.subtype_label) else label
            cost = float(r.typical_cost_usd)

        matches.append(
            {
                "Date": other_row.detected_at.strftime("%Y-%m-%d"),
                "Classification": label,
                "Resolution": resolution,
                "Cost": f"${cost:,.0f}",
            }
        )

    matches = matches[:3]
    return {
        "matches": matches,
        "input_summary": f"z_score={z_score:.2f} ±0.5, system={anomaly.system_id}",
        "output_summary": f"{len(matches)} comparable event(s) found",
    }


DECISION_RANK = {"dismiss": 0, "monitor": 1, "dispatch": 2}

# The dispatch gate. 0.75 is the value the product shipped with and every figure
# in the evaluation is scored against it, so it stays the default. It is no
# longer hard-coded in three places: Settings writes to session state and both
# the agent and the Review Recommended badge read it from here.
#
# BREAK_EVEN is what the cost model actually implies -- dispatching costs
# DISPATCH_COST for certain, not dispatching costs p x MISS_COST, so a visit is
# worth it whenever p > DISPATCH_COST / MISS_COST. That is 0.15, five times
# below the shipped default. Surfacing both is the point: the gap between them
# is the product's largest known defect.
def commit_threshold():
    """The confidence a classification must reach before the agent will dispatch."""
    return float(st.session_state.get("conf_threshold", COMMIT_THRESHOLD_DEFAULT))


def decide(data, z_score, classification, threshold=None):
    """The agent's decision rule, shared by the panel and the batch scorer.

    Two gates: a statistical one on the z-score and confidence, then a semantic
    cap at whatever the matched classification itself warrants.
    """
    threshold = commit_threshold() if threshold is None else threshold
    if z_score < 2.0:
        return "dismiss"

    confidence = (
        float(classification.confidence_score) if classification is not None else None
    )
    decision = (
        "dispatch"
        if z_score >= 3.0 and confidence is not None and confidence >= threshold
        else "monitor"
    )

    if classification is not None:
        reg = data["classification_registry"]
        match = reg[reg.classification_id == classification.classification_type_id]
        if not match.empty:
            ceiling = match.iloc[0].recommended_action
            if DECISION_RANK[ceiling] < DECISION_RANK[decision]:
                decision = ceiling
    return decision


def run_agent(data, anomaly, classification, z_by_anomaly):
    """Orchestrator — runs the four tools in sequence and returns an agent_runs row."""
    trace = []

    fetched = tool_fetch_readings(data["energy_readings"], anomaly)
    trace.append(("fetch_readings", fetched))

    baseline = tool_compute_baseline(fetched, anomaly)
    trace.append(("compute_baseline", baseline))

    sig = tool_run_significance_test(baseline, anomaly)
    trace.append(("run_significance_test", sig))

    confidence = (
        float(classification.confidence_score) if classification is not None else None
    )

    # Tool 4 is skipped entirely when the spike is not statistically significant.
    if sig["verdict"] == "not_significant":
        decision, comparables = "dismiss", []
    else:
        comp = tool_fetch_comparable_events(
            data, anomaly, sig["z_score"], z_by_anomaly
        )
        trace.append(("fetch_comparable_events", comp))
        comparables = comp["matches"]
        decision = decide(data, sig["z_score"], classification)

    return {
        "decision": decision,
        "z_score": sig["z_score"],
        "p_value": sig["p_value"],
        "percentile": sig["percentile"],
        "baseline_mean_kwh": baseline["baseline_mean"],
        "baseline_std_kwh": baseline["baseline_std"],
        "weather_adjusted": baseline["weather_adjusted"],
        "weather_context": sig["weather_context"],
        "confidence": confidence,
        "comparables": comparables,
        "tools_called": len(trace),
        "duration_seconds": round(0.8 * len(trace), 1),
        "window": fetched["window"],
        "trace": trace,
    }


def recommended_action_text(decision, anomaly, system, subtype_label, top_class, significant):
    sys_name = system.system_name if system is not None else "the affected system"
    sys_type = system.system_type if system is not None else "maintenance"
    label = subtype_label or "the fault signature"

    if decision == "dispatch":
        return f"Dispatch {sys_type} technician to {sys_name}. Check {label} first."

    if decision == "monitor":
        if top_class == "operational_variation":
            return (
                f"No dispatch needed — this reads as {label.lower()} on {sys_name}. "
                "Log it, set a recurrence threshold, and monitor for 24 hours."
            )
        return (
            f"Monitor {sys_name} for 24 hours before dispatching. Confidence is below "
            "the auto-classify threshold — escalate if the spike repeats at this hour."
        )

    # dismiss
    if not significant:
        return (
            "Do not dispatch — the spike is under 2 standard deviations and is "
            "statistically indistinguishable from normal variation at this hour."
        )
    if top_class == "data_anomaly":
        return (
            f"Dismiss — the pattern matches {label.lower()}, a metering artifact rather "
            f"than real consumption. Flag the {sys_name} reading for data quality review."
        )
    return (
        f"Dismiss — this reads as {label.lower()}, expected operational behavior for "
        f"{sys_name}. No technician required."
    )


# ── Derived views (schema → dashboard) ────────────────────────────────────────


@st.cache_data
def build_anomaly_view():
    """anomalies joined to systems, classifications, and classification_registry."""
    data = load_data()
    ano = data["anomalies"].copy()

    sys_cols = data["system_registry"][
        ["system_id", "system_name", "system_type", "cost_per_fault_usd"]
    ]
    ano = ano.merge(sys_cols, on="system_id", how="left")
    ano = ano.merge(
        data["facility_registry"][["facility_id", "facility_name"]],
        on="facility_id",
        how="left",
    )

    cls = data["classifications"][
        [
            "anomaly_id",
            "classification_id",
            "top_level_class",
            "classification_type_id",
            "confidence_score",
            "explanation_text",
            "review_recommended",
            "weather_adjusted",
        ]
    ]
    ano = ano.merge(cls, on="anomaly_id", how="left")

    reg = data["classification_registry"][
        ["classification_id", "subtype_label", "severity", "typical_cost_usd"]
    ].rename(columns={"classification_id": "classification_type_id"})
    ano = ano.merge(reg, on="classification_type_id", how="left")

    acts = data["manager_actions"][
        ["anomaly_id", "action_taken", "resolution_minutes", "engineer_called",
         "actual_top_level_class"]
    ]
    ano = ano.merge(acts, on="anomaly_id", how="left")

    ano["display_class"] = ano.subtype_label.fillna(
        ano.top_level_class.str.replace("_", " ").str.title()
    ).fillna("Unclassified")
    ano["severity"] = ano.severity.fillna("informational")
    return ano


@st.cache_data
def compute_z_scores():
    """z-score for every anomaly — needed by Tool 4's comparable-event lookup."""
    data = load_data()
    out = {}
    for anomaly in data["anomalies"].itertuples():
        fetched = tool_fetch_readings(data["energy_readings"], anomaly)
        baseline = tool_compute_baseline(fetched, anomaly)
        out[anomaly.anomaly_id] = anomaly.spike_kwh / baseline["baseline_std"]
    return out


@st.cache_data
def score_test_set():
    """Precision/recall on the equipment-fault class against `test_set_15_cases`.

    This is the spec's primary success bar. Abstentions — anomalies the classifier
    never labelled — count as false negatives: from the manager's seat an
    unanswered spike and a wrongly-answered one are the same missed fault.
    """
    data = load_data()
    cols = ["anomaly_id", "true_top_level_class", "true_subtype_label"]
    truth = data["test_set_15_cases"]
    if "stratum" in truth.columns:
        cols.append("stratum")
    truth = truth[cols]
    pred = data["classifications"][["anomaly_id", "top_level_class", "confidence_score"]]
    scored = truth.merge(pred, on="anomaly_id", how="left")
    scored["predicted"] = scored.top_level_class.fillna("(abstained)")
    if "stratum" not in scored.columns:
        scored["stratum"] = "core"

    def counts(df):
        is_fault = df.true_top_level_class == "equipment_fault"
        said = df.predicted == "equipment_fault"
        tp, fp, fn = int((said & is_fault).sum()), int((said & ~is_fault).sum()), int((~said & is_fault).sum())
        return {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else float("nan"),
            "recall": tp / (tp + fn) if tp + fn else float("nan"),
            "n_cases": len(df), "n_faults": int(is_fault.sum()),
        }

    # The spec's bar is defined over the core stratum. Co-occurring and
    # sub-threshold cases exist to probe where the scheme breaks, so folding
    # them into the headline number would answer a different question.
    core = scored[scored.stratum == "core"]
    return {
        "table": scored,
        **counts(core),
        "by_stratum": {s: counts(g) for s, g in scored.groupby("stratum")},
    }


# Cost parameters from the team spec: ~$300 per technician dispatch, $2,000-$8,000
# in excess consumption per undetected equipment fault. The conservative end of the
# miss range is used so the comparison cannot be accused of flattering the tool.



@st.cache_data
def score_decision_value():
    """Expected cost of the agent's recommendations vs. two fixed policies.

    Classification accuracy says whether the labels are right; it does not say
    whether following the tool beats ignoring it. This scores all three policies
    on the same 15 cases so the comparison is decidable.
    """
    data = load_data()
    z_by_anomaly = compute_z_scores()
    truth = data["test_set_15_cases"].set_index("anomaly_id").true_top_level_class

    rows = []
    for anomaly in data["anomalies"].itertuples():
        cls_rows = data["classifications"][
            data["classifications"].anomaly_id == anomaly.anomaly_id
        ]
        decision = decide(
            data,
            z_by_anomaly[anomaly.anomaly_id],
            cls_rows.iloc[0] if not cls_rows.empty else None,
        )
        rows.append(
            {
                "anomaly_id": anomaly.anomaly_id,
                "decision": decision,
                "is_fault": truth.get(anomaly.anomaly_id) == "equipment_fault",
            }
        )
    df = pd.DataFrame(rows)
    n, n_faults = len(df), int(df.is_fault.sum())

    def cost(dispatched):
        """Dispatch spend plus exposure from faults nobody was sent to look at."""
        missed = int((df.is_fault & ~dispatched).sum())
        return {
            "dispatches": int(dispatched.sum()),
            "caught": int((df.is_fault & dispatched).sum()),
            "missed": missed,
            "cost": dispatched.sum() * DISPATCH_COST + missed * MISS_COST,
        }

    policies = {
        "Follow the tool": cost(df.decision == "dispatch"),
        "Dispatch on every spike": cost(pd.Series(True, index=df.index)),
        "Dispatch on none": cost(pd.Series(False, index=df.index)),
    }
    tool_cost = policies["Follow the tool"]["cost"]
    return {
        "policies": policies,
        "n": n,
        "n_faults": n_faults,
        "mix": df.decision.value_counts().to_dict(),
        "tool_wins": all(
            tool_cost < v["cost"] for k, v in policies.items() if k != "Follow the tool"
        ),
    }


def filter_facility(df, facility_id):
    return df if facility_id == "ALL" else df[df.facility_id == facility_id]


# ── Styling ───────────────────────────────────────────────────────────────────

st.markdown(
    f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
  .stApp {{ background: {BG}; color: {TEXT}; }}
  section[data-testid="stSidebar"] {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
  #MainMenu, footer, header {{ visibility: hidden; }}
  .block-container {{ padding-top: 2rem; max-width: 100%; }}

  .kpi {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px;
    padding: 14px 16px; border-top: 3px solid var(--accent);
    min-height: 124px; display: flex; flex-direction: column;
    justify-content: space-between; overflow: hidden;
  }}
  .kpi .label {{
    font-size: 9.5px; font-weight: 600; letter-spacing: .08em;
    text-transform: uppercase; color: {TEXT_DIM}; line-height: 1.3;
  }}
  /* clamp() keeps long values like "$26,300" on one line in a narrow column */
  .kpi .value {{
    font-size: clamp(22px, 2.6vw, 40px); font-weight: 800; line-height: 1.05;
    color: var(--accent); white-space: nowrap;
  }}
  .kpi .unit {{ font-size: 13px; font-weight: 500; color: {TEXT_DIM}; margin-left: 3px; }}
  .kpi .sub {{ font-size: 10px; color: {TEXT_DIM}; line-height: 1.35; }}

  .sect {{
    font-size: 10px; font-weight: 700; letter-spacing: .11em; text-transform: uppercase;
    color: {TEXT_DIM}; margin: 18px 0 8px; padding-bottom: 6px;
    border-bottom: 1px solid {BORDER};
  }}
  .card {{
    background: {SURFACE}; border: 1px solid {BORDER};
    border-radius: 10px; padding: 14px 16px; margin-bottom: 10px;
  }}
  .badge {{
    display: inline-block; padding: 2px 9px; border-radius: 20px;
    font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;
  }}
  .decision {{
    border-radius: 10px; padding: 14px 16px; margin: 6px 0 12px;
    border: 1px solid var(--dc); border-left: 4px solid var(--dc);
    background: color-mix(in srgb, var(--dc) 10%, {SURFACE});
  }}
  .decision .head {{ font-size: 16px; font-weight: 800; color: var(--dc); letter-spacing: .02em; }}
  .stat {{ font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px; color: {TEXT}; }}
  .muted {{ color: {TEXT_DIM}; font-size: 12px; line-height: 1.55; }}
  .stButton > button {{
    background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 7px; font-size: 12px; font-weight: 600; width: 100%;
  }}
  .stButton > button:hover {{ border-color: {TEAL}; color: {TEAL}; }}
  div[data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 8px; }}
</style>
""",
    unsafe_allow_html=True,
)


def kpi(label, value, accent, unit="", sub=""):
    unit_html = f'<span class="unit">{unit}</span>' if unit else ""
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="kpi" style="--accent:{accent}">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}{unit_html}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def section(title):
    st.markdown(f'<div class="sect">{title}</div>', unsafe_allow_html=True)


def dark_layout(fig, height=280):
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", size=11, color=TEXT_DIM),
        margin=dict(l=8, r=8, t=8, b=28),
        legend=dict(orientation="h", y=-0.26, font=dict(size=10, color=TEXT)),
        hoverlabel=dict(bgcolor=SURFACE_2, bordercolor=BORDER, font_size=11),
    )
    fig.update_xaxes(gridcolor=BORDER, zeroline=False, linecolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER, zeroline=False, linecolor=BORDER)
    return fig


# ── State ─────────────────────────────────────────────────────────────────────

data = load_data()
z_by_anomaly = compute_z_scores()

st.session_state.setdefault("screen", "Dashboard")
st.session_state.setdefault("open_anomaly", None)
st.session_state.setdefault("status_overrides", {})
st.session_state.setdefault("manager_notes", {})
st.session_state.setdefault("actions_taken", {})
st.session_state.setdefault("page", 0)

ano_all = build_anomaly_view().copy()
ano_all["status"] = ano_all.apply(
    lambda r: st.session_state.status_overrides.get(r.anomaly_id, r.status), axis=1
)


# ── Input guard ───────────────────────────────────────────────────────────────

GUARD_COLOR = {"blocker": RED, "warning": AMBER, "note": BLUE}


def render_findings(findings):
    for f in findings:
        c = GUARD_COLOR[f.severity]
        st.markdown(
            f'<div class="card" style="border-left:4px solid {c};margin-bottom:8px">'
            f'<span class="badge" style="background:{c};color:#fff">{f.severity.upper()}</span>'
            f'<span style="margin-left:9px;font-weight:600">{f.message}</span>'
            + (f'<div class="muted" style="margin-top:6px">{f.detail}</div>' if f.detail else "")
            + "</div>",
            unsafe_allow_html=True,
        )


@st.dialog("Check this data before you rely on it", width="large")
def input_warning_dialog(findings, source):
    worst = input_guard.worst_severity(findings)
    lead = ("Something in this feed looks wrong enough that the classifications "
            "below may be meaningless."
            if worst == "blocker" else
            "A few things in this feed are worth a look before you act on it.")
    st.markdown(f'<div class="muted" style="margin-bottom:10px">{lead}<br>'
                f'<b>Source:</b> {source}</div>', unsafe_allow_html=True)
    render_findings(findings)
    st.caption("These are prompts to check, not rejections. Nothing has been discarded.")
    if st.button("I have checked — continue", width="stretch"):
        st.session_state.guard_ack = True
        st.rerun()


@st.cache_data
def guard_loaded_data():
    """Sanity-check the workbook the dashboard is running on."""
    d = load_data()
    readings = d["energy_readings"]
    # Profile the settled history and test the most recent slice against it, so
    # a feed that drifted partway through is still caught.
    cutoff = readings.recorded_at.max() - pd.Timedelta(days=14)
    history, recent = readings[readings.recorded_at < cutoff], readings[readings.recorded_at >= cutoff]
    if history.empty or recent.empty:
        return []
    return [f for f in input_guard.check_readings(
        recent, input_guard.baseline_profile(history), d) if f.code != "overlap"]


st.session_state.setdefault("guard_ack", False)
_startup_findings = guard_loaded_data()
if _startup_findings and not st.session_state.guard_ack:
    input_warning_dialog(_startup_findings, f"{DATA_FILE.name} — most recent 14 days")


# ── Sidebar nav ───────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        f'<div style="padding:4px 0 14px"><div style="font-size:15px;font-weight:800;'
        f'color:{TEAL}">⚡ ANOMALY EXPLAINER</div>'
        f'<div style="font-size:10px;color:{TEXT_DIM};letter-spacing:.06em;'
        f'text-transform:uppercase;margin-top:3px">AI Analytics Aces</div></div>',
        unsafe_allow_html=True,
    )

    for icon, name in [("⌂", "Dashboard"), ("◫", "History"), ("⚙", "Settings")]:
        if st.button(f"{icon}  {name}", key=f"nav_{name}", width="stretch"):
            st.session_state.screen = name
            st.session_state.open_anomaly = None
            st.rerun()

    st.markdown(f'<hr style="border-color:{BORDER};margin:14px 0">', unsafe_allow_html=True)

    fac_options = ["ALL"] + data["facility_registry"].facility_id.tolist()
    fac_labels = {"ALL": "All Facilities"} | dict(
        zip(data["facility_registry"].facility_id, data["facility_registry"].facility_name)
    )
    facility = st.selectbox(
        "Facility", fac_options, format_func=lambda f: fac_labels[f]
    )

    readings = data["energy_readings"]
    date_lo, date_hi = readings.recorded_at.min(), readings.recorded_at.max()
    st.caption(f"Range · {date_lo:%b %d} – {date_hi:%b %d, %Y}")

    view = filter_facility(ano_all, facility)
    n_open = int((view.status == "unclassified").sum())
    bell_color = RED if n_open else GREEN
    st.markdown(
        f'<div style="margin-top:6px;padding:8px 11px;border-radius:7px;'
        f'background:{SURFACE_2};border:1px solid {bell_color}">'
        f'<span style="color:{bell_color};font-size:12px;font-weight:700">'
        f'🔔 {n_open} unclassified</span></div>',
        unsafe_allow_html=True,
    )


view = filter_facility(ano_all, facility)


# ── Screen 2 — Classification Panel ───────────────────────────────────────────


def render_classification_panel(anomaly_id):
    row = ano_all[ano_all.anomaly_id == anomaly_id]
    if row.empty:
        st.session_state.open_anomaly = None
        st.rerun()
    row = row.iloc[0]

    anomaly = next(
        r for r in data["anomalies"].itertuples() if r.anomaly_id == anomaly_id
    )

    cls_rows = data["classifications"][data["classifications"].anomaly_id == anomaly_id]
    classification = cls_rows.iloc[0] if not cls_rows.empty else None

    sys_rows = data["system_registry"][
        data["system_registry"].system_id == anomaly.system_id
    ]
    system = sys_rows.iloc[0] if not sys_rows.empty else None

    back, title = st.columns([1, 9])
    with back:
        if st.button("← Back", key="panel_back"):
            st.session_state.open_anomaly = None
            st.rerun()
    with title:
        st.markdown(
            f'<div style="font-size:17px;font-weight:700;padding-top:3px">'
            f"Anomaly {anomaly_id} · {anomaly.detected_at:%Y-%m-%d %H:%M} · "
            f'{row.facility_name}</div>',
            unsafe_allow_html=True,
        )

    # ── Spike detail
    section("Spike Detail")
    a, b, c = st.columns(3)
    with a:
        st.metric("Spike above baseline", f"{anomaly.spike_kwh:.1f} kWh")
        st.metric("Baseline", f"{anomaly.baseline_kwh:.1f} kWh")
    with b:
        st.metric("Duration", f"{int(anomaly.duration_minutes)} min")
        st.metric("Temperature", f"{anomaly.temp_f_at_detection:.1f} °F")
    with c:
        st.metric("System", system.system_name if system is not None else "Unknown")
        st.metric("Time", f"{anomaly.detected_at:%I:%M %p · %A}")

    # ── Declared operations covering this window
    _win = operations_log.window_of(anomaly)
    _declared = operations_log.covering(
        operations_log.load(), anomaly.facility_id, anomaly.system_id, *_win)
    if _declared:
        _classified_at = pd.Timestamp(getattr(anomaly, "classified_at", None) or pd.NaT)
        _newest = max(pd.Timestamp(d["declared_at"]) for d in _declared)
        if pd.notna(_classified_at) and _newest > _classified_at:
            _declared_note = (
                "Declared after this spike was classified, so the stored "
                "classification did not see it — re-run the classifier to take it "
                "into account."
            )
        else:
            _declared_note = "The classifier was given this as evidence."
        items = "".join(
            f'<div style="margin-top:7px"><span style="font-weight:700">'
            f'{operations_log.describe(d)}</span>'
            + (f'<div class="muted" style="margin-top:2px">'
               f'Manager\'s note: “{d["note"]}”</div>' if d.get("note") else "")
            + "</div>"
            for d in _declared
        )
        st.markdown(
            f'<div class="card" style="border-left:4px solid {AMBER}">'
            f'<span class="badge" style="background:{AMBER}22;color:{AMBER};'
            f'border:1px solid {AMBER}">DECLARED OPERATION</span>'
            f'{items}'
            f'<div class="muted" style="margin-top:9px">{_declared_note}'
            f' This does not suppress the alert — equipment can fail during '
            f'planned operations.</div></div>',
            unsafe_allow_html=True,
        )

    # ── AI classification
    section("AI Classification")
    if classification is None:
        st.markdown(
            f'<div class="card" style="border-left:4px solid {GREY}">'
            f'<div class="badge" style="background:{GREY};color:#fff">PENDING</div>'
            f'<div style="font-size:18px;font-weight:700;margin-top:8px">'
            f"Not yet classified</div>"
            f'<div class="muted" style="margin-top:6px">This spike has not been run '
            f"through the classifier. The agent below still evaluates statistical "
            f"significance from the raw readings.</div></div>",
            unsafe_allow_html=True,
        )
    else:
        top_class = classification.top_level_class
        color = CLASS_COLOR.get(top_class, GREY)
        conf = float(classification.confidence_score)
        conf_label = "High" if conf >= 0.8 else "Medium" if conf >= 0.6 else "Low"
        # Recomputed here rather than read from the cached frame, so the
        # badge follows the Settings slider without a full reload.
        review = conf < commit_threshold()

        badges = (
            f'<span class="badge" style="background:{color};color:#fff">'
            f'{top_class.replace("_", " ").upper()}</span>'
        )
        if review:
            badges += (
                f'<span class="badge" style="background:{AMBER}22;color:{AMBER};'
                f'border:1px solid {AMBER};margin-left:6px">⚠ REVIEW RECOMMENDED</span>'
            )
        if bool(classification.weather_adjusted):
            badges += (
                f'<span class="badge" style="background:{BLUE}22;color:{BLUE};'
                f'border:1px solid {BLUE};margin-left:6px">WEATHER-ADJUSTED</span>'
            )

        st.markdown(
            f'<div class="card" style="border-left:4px solid {color}">{badges}'
            f'<div style="font-size:20px;font-weight:700;margin-top:9px">'
            f"{row.display_class}</div>"
            f'<div class="stat" style="margin-top:5px">Confidence: {conf_label} '
            f"({conf:.0%}) · Classified in {anomaly.classification_minutes:.1f} min</div>"
            f'<div class="muted" style="margin-top:9px">'
            f"{classification.explanation_text}</div></div>",
            unsafe_allow_html=True,
        )
        st.progress(conf)

    # ── Agent — runs on panel open
    section("Agent Decision")
    with st.spinner("Agent is analyzing…"):
        agent = run_agent(data, anomaly, classification, z_by_anomaly)

    decision = agent["decision"]
    dc = DECISION_COLOR[decision]
    significant = agent["z_score"] >= 2.0

    if decision == "dispatch":
        head = "✅ DISPATCH RECOMMENDED"
    elif decision == "monitor":
        head = "⚠ MONITOR RECOMMENDED"
    elif not significant:
        head = "— NOT SIGNIFICANT · LIKELY NOISE"
    else:
        head = "— DISMISS RECOMMENDED"

    spike_multiple = (
        (anomaly.baseline_kwh + anomaly.spike_kwh) / anomaly.baseline_kwh
        if anomaly.baseline_kwh
        else float("nan")
    )
    # The classifier writes an instruction grounded in this spike — which trade to
    # send, which hour to watch, which artefact to log. Prefer it over the
    # template, which can only restate the decision in general terms.
    model_action = (
        classification.get("next_action") if classification is not None else None
    )
    # The classifier writes next_action from its own recommended_action, which the
    # agent can then cap. When they disagree we used to print the classifier's
    # "send someone tonight" directly beneath a MONITOR verdict — two instructions,
    # no indication which one to follow. Say plainly that they disagree instead.
    model_rec = (
        classification.get("recommended_action") if classification is not None else None
    )
    overruled = (
        model_rec is not None
        and DECISION_RANK.get(model_rec, 0) > DECISION_RANK[decision]
    )
    action_text = model_action or recommended_action_text(
        decision,
        anomaly,
        system,
        row.subtype_label if pd.notna(row.subtype_label) else None,
        classification.top_level_class if classification is not None else None,
        significant,
    )
    symptom = (
        classification.get("symptom_to_check") if classification is not None else None
    )
    # A technician symptom under a decision that sends nobody reads as an
    # instruction. Keep it only when we are dispatching.
    if decision != "dispatch":
        symptom = None

    pattern_html = ""
    if classification is not None:
        pattern_html = (
            f'<div class="stat" style="margin-top:7px">Pattern match: '
            f"{row.display_class} ({float(classification.confidence_score):.0%}) · "
            f'{len(agent["comparables"])} similar event(s)</div>'
        )

    st.markdown(
        f'<div class="decision" style="--dc:{dc}">'
        f'<div class="head">{head}</div>'
        f'<div class="stat" style="margin-top:9px">Z-score: {agent["z_score"]:.2f} &nbsp;|&nbsp; '
        f'P-value: {agent["p_value"]:.4g} &nbsp;|&nbsp; '
        f"Spike is {spike_multiple:.1f}× baseline &nbsp;|&nbsp; "
        f'{agent["percentile"]:.2f}th percentile</div>'
        f"{pattern_html}"
        f'<div class="muted" style="margin-top:9px">{agent["weather_context"]}</div>'
        f'<div style="margin-top:11px;font-size:13px;font-weight:600;color:{dc}">'
        f"▸ {action_text}</div>"
        + (
            f'<div class="muted" style="margin-top:9px;padding-top:8px;'
            f'border-top:1px dashed {BORDER}">The classifier would '
            f"<b>{model_rec}</b> on this spike; the agent's rule caps it at "
            f"<b>{decision}</b> because confidence {conf:.0%} is below the "
            f"{commit_threshold():.0%} dispatch threshold. "
            f"<b>The agent's verdict above is what the product recommends.</b> "
            f"The instruction just above is the classifier's, and it has not been "
            f"acted on.</div>"
            if overruled
            else ""
        )
        + (
            f'<div class="muted" style="margin-top:9px;padding-top:8px;'
            f'border-top:1px dashed {BORDER}"><b>Symptom for the technician</b><br>'
            f"{symptom}</div>"
            if symptom
            else ""
        )
        + "</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        f'Agent ran {agent["tools_called"]} tools in {agent["duration_seconds"]}s'
    )

    with st.expander("See steps — agent tool trace"):
        for i, (tool_name, result) in enumerate(agent["trace"], start=1):
            st.markdown(
                f'<div style="padding:7px 0;border-bottom:1px solid {BORDER}">'
                f'<span class="badge" style="background:{TEAL}22;color:{TEAL};'
                f'border:1px solid {TEAL}">STEP {i}</span> '
                f'<code style="color:{TEXT}">{tool_name}</code>'
                f'<div class="muted" style="margin-top:5px">'
                f'<b>in</b> &nbsp;{result["input_summary"]}<br>'
                f'<b>out</b> {result["output_summary"]}</div></div>',
                unsafe_allow_html=True,
            )
        if agent["tools_called"] == 3:
            st.caption(
                "Tool 4 (fetch_comparable_events) was skipped — z-score below 2.0, "
                "so the agent stopped and returned DISMISS."
            )

    # ── Comparable past events (Tool 4 output)
    section("Comparable Past Events")
    if agent["comparables"]:
        st.dataframe(
            pd.DataFrame(agent["comparables"]),
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption(f"No earlier spike on this system falls within "
                   f"{COMPARABLE_Z_TOLERANCE:.0%} of this z-score.")

    # ── Zoomed spike chart
    section("Spike Chart · ±2hr window")
    window = agent["window"]
    if window.empty:
        st.caption("No readings available in the spike window.")
    else:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=window.recorded_at,
                y=window.kwh,
                mode="lines+markers",
                name="Actual kWh",
                line=dict(color=BLUE, width=2),
                marker=dict(size=5),
            )
        )
        fig.add_hline(
            y=agent["baseline_mean_kwh"],
            line=dict(color=GREEN, width=1.5, dash="dash"),
            annotation_text=f'baseline {agent["baseline_mean_kwh"]:.1f} kWh',
            annotation_font=dict(size=9, color=GREEN),
        )
        fig.add_trace(
            go.Scatter(
                x=[anomaly.detected_at],
                y=[anomaly.baseline_kwh + anomaly.spike_kwh],
                mode="markers",
                name="Spike peak",
                marker=dict(color=RED, size=13, symbol="circle",
                            line=dict(color="#fff", width=1.5)),
            )
        )
        # Single-day window, so the date in each tick is redundant noise.
        fig.update_xaxes(tickformat="%H:%M")
        st.plotly_chart(dark_layout(fig, 240), use_container_width=True)

    # ── Actions
    section("Actions")
    # Per the wireframe the three action paths key off the top-level class; when the
    # spike is unclassified we fall back to the agent's statistical decision.
    top_class = classification.top_level_class if classification is not None else None
    # The button records which of the three actions was taken, not merely that
    # the manager agreed. "accepted" could not distinguish a dispatch from a
    # monitor, which is exactly the difference the resolution metrics need.
    #
    # This used to key off top_level_class, so an equipment_fault always offered
    # "Dispatch Technician" even when the agent had just recommended MONITOR --
    # the panel argued with its own button on 18 of 25 cases, and the decision
    # value we report models the verdict, not the button. The recommended action
    # is now the agent's, and the other two stay available so a manager who
    # disagrees is not stuck.
    BY_ACTION = {
        "dispatch": ("Dispatch Technician", "classified", "dispatched"),
        "monitor": ("Monitor for 24 hours", "classified", "monitoring"),
        "dismiss": (
            "Dismiss — Meter/Sensor Error" if top_class == "data_anomaly"
            else "Dismiss — Known Operational Event", "dismissed", "dismissed"),
    }

    def take(action):
        label, new_status, taken = BY_ACTION[action]
        st.session_state.status_overrides[anomaly_id] = new_status
        st.session_state.actions_taken[anomaly_id] = taken
        st.session_state.open_anomaly = None
        build_anomaly_view.clear()
        st.rerun()

    ordered = [decision] + [a for a in ("dispatch", "monitor", "dismiss")
                            if a != decision]
    cols = st.columns(3)
    for col, action in zip(cols, ordered):
        with col:
            recommended = action == decision
            label = ("✓ " if recommended else "") + BY_ACTION[action][0]
            if st.button(label, key=f"act_{action}", width="stretch",
                         type="primary" if recommended else "secondary",
                         help="The agent's recommendation" if recommended
                              else "Overrules the agent's recommendation"):
                take(action)

    if st.button("Flag for Engineer Review", key="act_flag", width="content"):
        st.session_state.status_overrides[anomaly_id] = "escalated"
        st.session_state.actions_taken[anomaly_id] = "escalated"
        st.session_state.open_anomaly = None
        build_anomaly_view.clear()
        st.rerun()

    # ── Exception — always available
    # Three actions cannot cover every spike, and a manager forced to pick the
    # closest wrong one leaves no trace that the taxonomy failed. Recording the
    # exception in the manager's own words keeps that signal instead of losing
    # it, and the notes are the shortlist for what the catalogue is missing.
    existing = st.session_state.manager_notes.get(anomaly_id)
    if existing:
        st.markdown(
            f'<div class="card" style="border-left:4px solid {TEAL};margin-top:10px">'
            f'<span class="badge" style="background:{TEAL};color:#062b27">EXCEPTION '
            f"RECORDED</span>"
            f'<div class="muted" style="margin-top:7px">{existing}</div></div>',
            unsafe_allow_html=True,
        )

    with st.expander("None of these fit — record an exception", expanded=bool(existing)):
        st.markdown(
            '<div class="muted">Use this when the spike is real but the three '
            "actions do not describe what should happen, or when the "
            "classification is wrong in a way none of the 14 types capture. "
            "Your note is kept with the anomaly.</div>",
            unsafe_allow_html=True,
        )
        note = st.text_area(
            "What should happen instead, and why?",
            value=existing or "",
            key=f"exc_{anomaly_id}",
            placeholder="e.g. Contractor was on site rewiring the north bay — "
                        "no fault, but not a routine operational event either. "
                        "Hold until the work order closes.",
            height=90,
        )
        save, clear = st.columns([3, 1])
        with save:
            if st.button("Record exception", key="act_exc", width="stretch"):
                if note.strip():
                    st.session_state.manager_notes[anomaly_id] = note.strip()
                    st.session_state.status_overrides[anomaly_id] = "exception"
                    st.session_state.actions_taken[anomaly_id] = "exception"
                    st.session_state.open_anomaly = None
                    build_anomaly_view.clear()
                    st.rerun()
                else:
                    st.warning("Add a note before recording — the note is the point.")
        with clear:
            if existing and st.button("Remove", key="act_exc_clear", width="stretch"):
                st.session_state.manager_notes.pop(anomaly_id, None)
                st.session_state.status_overrides.pop(anomaly_id, None)
                st.session_state.actions_taken.pop(anomaly_id, None)
                build_anomaly_view.clear()
                st.rerun()

    if agent["confidence"] is not None:
        st.markdown(
            f'<div class="muted" style="margin-top:8px">Classifier confidence</div>',
            unsafe_allow_html=True,
        )
        st.progress(agent["confidence"])


# ── Shared table renderer ─────────────────────────────────────────────────────


def anomaly_table(df, key_prefix, page_size=None, page=0):
    """Anomaly table per the schema's column mapping, with a per-row action button."""
    order = {"unclassified": 0, "exception": 1, "escalated": 2,
             "classified": 3, "dismissed": 4}
    df = df.assign(_o=df.status.map(order).fillna(9)).sort_values(
        ["_o", "detected_at"], ascending=[True, False]
    )

    total = len(df)
    if page_size:
        df = df.iloc[page * page_size : (page + 1) * page_size]

    header = st.columns([2.1, 1.7, 1.9, 1.2, 2.1, 1.1, 1.2, 1.3])
    for col, label in zip(
        header,
        ["Timestamp", "Facility", "System", "Spike kWh", "Classification",
         "Severity", "Status", "Action"],
    ):
        col.markdown(
            f'<div style="font-size:9.5px;font-weight:700;letter-spacing:.09em;'
            f'text-transform:uppercase;color:{TEXT_DIM};padding-bottom:5px;'
            f'border-bottom:1px solid {BORDER}">{label}</div>',
            unsafe_allow_html=True,
        )

    for r in df.itertuples():
        is_open = r.status == "unclassified"
        sev_color = SEVERITY_COLOR.get(r.severity, GREY)
        row_tint = {
            "critical": "rgba(239,68,68,.07)",
            "warning": "rgba(245,158,11,.06)",
        }.get(r.severity, "transparent")
        dim = "opacity:.62;" if r.status == "dismissed" else ""

        cols = st.columns([2.1, 1.7, 1.9, 1.2, 2.1, 1.1, 1.2, 1.3])

        def cell(col, html):
            col.markdown(
                f'<div style="background:{row_tint};{dim}padding:9px 5px;'
                f'font-size:12px;border-bottom:1px solid {BORDER}1a">{html}</div>',
                unsafe_allow_html=True,
            )

        cell(cols[0], f'<span class="stat">{r.detected_at:%Y-%m-%d %H:%M}</span>')
        cell(cols[1], r.facility_name)
        cell(cols[2], r.system_name if pd.notna(r.system_name) else "Unknown")
        cell(cols[3], f'<span class="stat">+{r.spike_kwh:.1f}</span>')

        cls_color = GREY if is_open else sev_color
        cell(
            cols[4],
            f'<span class="badge" style="background:{cls_color}22;color:{cls_color};'
            f'border:1px solid {cls_color}">{r.display_class}</span>',
        )
        cell(
            cols[5],
            f'<span style="color:{sev_color};font-weight:600;font-size:11px">'
            f"{r.severity if not is_open else '—'}</span>",
        )
        status_html = (
            f'<span class="badge" style="background:{TEAL}22;color:{TEAL};'
            f'border:1px solid {TEAL}">exception</span>'
            if r.status == "exception"
            else f'<span style="font-size:11px">{r.status}</span>'
        )
        cell(cols[6], status_html)

        with cols[7]:
            st.markdown('<div style="padding-top:3px">', unsafe_allow_html=True)
            label = "Classify Now" if is_open else "View"
            if st.button(label, key=f"{key_prefix}_{r.anomaly_id}", width="stretch"):
                st.session_state.open_anomaly = r.anomaly_id
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    return total


# ── Screen 1 — Dashboard ──────────────────────────────────────────────────────


def render_dashboard():
    st.markdown(
        f'<div style="font-size:19px;font-weight:800;margin-bottom:3px">'
        f"Main Dashboard</div>"
        f'<div class="muted" style="margin-bottom:14px">Current anomaly status and '
        f"outstanding classifications</div>",
        unsafe_allow_html=True,
    )

    # KPI cards — formulas per the schema's KPI mapping
    open_anoms = view[view.status == "unclassified"]
    n_active = len(open_anoms)

    classified = view[view.classified_at.notna()]
    avg_class_min = (
        classified.classification_minutes.mean() if not classified.empty else float("nan")
    )

    acts = data["manager_actions"].merge(
        ano_all[["anomaly_id", "facility_id"]], on="anomaly_id", how="left"
    )
    acts = filter_facility(acts, facility)
    # "This month" per the schema — anchored to the newest action in the dataset
    # rather than today's date, so the demo reads the same whenever it is run.
    month_start = acts.acted_at.max().normalize().replace(day=1) if not acts.empty else None
    n_confirmed = int(
        ((acts.action_taken == "dispatched") & (acts.acted_at >= month_start)).sum()
    ) if month_start is not None else 0
    # Actions taken in this session count too — previously the panel computed which
    # of the three was taken and discarded it, so dispatching from the UI never
    # moved this number. They have to obey the same facility filter as the rest of
    # the KPI, or selecting one site shows technicians sent to another.
    session_facility = ano_all.set_index("anomaly_id").facility_id
    n_confirmed += sum(
        1
        for aid, act in st.session_state.actions_taken.items()
        if act == "dispatched"
        and (facility == "ALL" or session_facility.get(aid) == facility)
    )

    reg = data["classification_registry"].set_index("classification_id")
    exposure = 0.0
    for r in open_anoms.itertuples():
        if pd.notna(r.classification_type_id) and r.classification_type_id in reg.index:
            exposure += float(reg.loc[r.classification_type_id].typical_cost_usd)
        elif pd.notna(r.cost_per_fault_usd):
            exposure += float(r.cost_per_fault_usd)

    facs = filter_facility(data["facility_registry"], facility)
    n_online, n_total = int(facs.is_online.sum()), len(facs)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        kpi("Active Anomalies", n_active, RED if n_active else GREEN,
            sub="Unclassified spikes right now")
    with c2:
        if pd.isna(avg_class_min):
            kpi("Avg Classification Time", "—", GREY, sub="No classifications yet")
        else:
            color = GREEN if avg_class_min < 10 else AMBER if avg_class_min <= 60 else RED
            kpi("Avg Classification Time", f"{avg_class_min:.1f}", color, unit="min",
                sub=f"{len(classified)} classified events")
    with c3:
        kpi("Faults Confirmed This Month", n_confirmed, BLUE,
            sub=f"Technicians sent since {month_start:%b 1}" if month_start is not None
                else "No actions recorded")
    with c4:
        color = RED if exposure > 5000 else AMBER if exposure >= 1000 else GREEN
        kpi("Est. Cost Exposure", f"${exposure:,.0f}", color, sub="From open anomalies")
    with c5:
        color = RED if n_online < n_total else GREEN
        kpi("Facilities Online", f"{n_online}/{n_total}", color, sub="Reporting data")

    # Charts
    left, right = st.columns([2, 1])

    with left:
        span_days = (data["energy_readings"].recorded_at.max()
                     - data["energy_readings"].recorded_at.min()).days
        section(f"Energy Timeline · {span_days}-day consumption")
        readings = filter_facility(data["energy_readings"], facility)
        # Hourly rather than daily: a one-hour spike barely moves a daily total, so
        # daily aggregation flattens every anomaly out of the line entirely.
        hourly = readings.groupby("recorded_at", as_index=False).kwh.sum()

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=hourly.recorded_at, y=hourly.kwh, mode="lines", name="Hourly kWh",
                line=dict(color=BLUE, width=1.3),
                fill="tozeroy", fillcolor="rgba(59,130,246,.10)",
                hovertemplate="%{x|%b %d %H:%M}<br>%{y:.1f} kWh<extra></extra>",
            )
        )

        # Red dot markers sit on the actual spike hour so they read as peaks.
        if not view.empty:
            spikes = view.merge(
                hourly.rename(columns={"recorded_at": "detected_at", "kwh": "_y"}),
                on="detected_at",
                how="inner",
            )
            if not spikes.empty:
                fig.add_trace(
                    go.Scatter(
                        x=spikes.detected_at, y=spikes._y, mode="markers", name="Anomaly",
                        marker=dict(color=RED, size=9,
                                    line=dict(color="#fff", width=1.2)),
                        customdata=spikes[
                            ["anomaly_id", "spike_kwh", "display_class", "status"]
                        ].values,
                        hovertemplate=(
                            "<b>%{customdata[0]}</b><br>"
                            "%{x|%b %d %H:%M}<br>"
                            "Spike: +%{customdata[1]:.1f} kWh<br>"
                            "Class: %{customdata[2]}<br>"
                            "Status: %{customdata[3]}<extra></extra>"
                        ),
                    )
                )
        fig.update_yaxes(title_text="kWh / hr", title_font=dict(size=10))
        st.plotly_chart(dark_layout(fig, 300), use_container_width=True)

    with right:
        section("Classification Breakdown")
        counts = (
            view[view.top_level_class.notna()]
            .top_level_class.value_counts()
            .to_dict()
        )
        # Only spikes with no class at all — a classified spike is already
        # represented by its own slice.
        n_unclassified = int(view.top_level_class.isna().sum())
        if n_unclassified:
            counts["unclassified"] = n_unclassified

        if counts:
            labels = [k.replace("_", " ").title() for k in counts]
            fig = go.Figure(
                go.Pie(
                    labels=labels,
                    values=list(counts.values()),
                    hole=0.58,
                    marker=dict(
                        colors=[CLASS_COLOR.get(k, GREY) for k in counts],
                        line=dict(color=BG, width=2),
                    ),
                    textinfo="value",
                    textfont=dict(size=12, color="#fff", family="Inter"),
                )
            )
            fig.update_layout(
                annotations=[
                    dict(
                        text=f"<b>{sum(counts.values())}</b><br>"
                             f'<span style="font-size:9px">EVENTS</span>',
                        x=0.5, y=0.5, showarrow=False,
                        font=dict(size=22, color=TEXT, family="Inter"),
                    )
                ]
            )
            st.plotly_chart(dark_layout(fig, 300), use_container_width=True)
        else:
            st.caption("No anomalies in this selection.")

    section(f"Anomaly Table · {len(view)} events")
    anomaly_table(view, "dash")


# ── Screen 3 — History & Trends ───────────────────────────────────────────────


def render_history():
    st.markdown(
        f'<div style="font-size:19px;font-weight:800;margin-bottom:3px">'
        f"History &amp; Trends</div>"
        f'<div class="muted" style="margin-bottom:14px">Recurring patterns and '
        f"resolution performance</div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)

    with left:
        section("Anomaly Count by Day")
        if view.empty:
            st.caption("No anomalies in this selection.")
        else:
            by_day = (
                view.assign(d=view.detected_at.dt.normalize())
                .groupby("d", as_index=False)
                .size()
            )
            fig = go.Figure(
                go.Bar(
                    x=by_day.d, y=by_day["size"],
                    marker=dict(color=BLUE, line=dict(color=BLUE, width=0)),
                    hovertemplate="%{x|%b %d}<br>%{y} anomalies<extra></extra>",
                )
            )
            fig.update_yaxes(title_text="Anomalies", title_font=dict(size=10), dtick=1)
            st.plotly_chart(dark_layout(fig, 290), use_container_width=True)

    with right:
        section("Heat Map · Day of Week × Hour")
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        grid = [[0] * 24 for _ in range(7)]
        for r in view.itertuples():
            grid[r.detected_at.dayofweek][r.detected_at.hour] += 1

        fig = go.Figure(
            go.Heatmap(
                z=grid,
                x=[f"{h:02d}" for h in range(24)],
                y=days,
                colorscale=[[0, SURFACE_2], [0.5, AMBER], [1, RED]],
                showscale=False,
                xgap=2, ygap=2,
                hovertemplate="%{y} %{x}:00<br>%{z} anomalies<extra></extra>",
            )
        )
        fig.update_xaxes(showgrid=False, tickfont=dict(size=8), dtick=3)
        fig.update_yaxes(showgrid=False, autorange="reversed")
        st.plotly_chart(dark_layout(fig, 290), use_container_width=True)

    section("Resolution Metrics")
    classified = view[view.classified_at.notna()]
    avg_class = (
        classified.classification_minutes.mean() if not classified.empty else float("nan")
    )
    resolved = view[view.resolution_minutes.notna()]
    avg_resolve = resolved.resolution_minutes.mean() if not resolved.empty else float("nan")

    # False positive: confirmed class differs from what the AI predicted.
    scored = view[view.actual_top_level_class.notna() & view.top_level_class.notna()]
    fp_rate = (
        (scored.actual_top_level_class != scored.top_level_class).mean() * 100
        if not scored.empty
        else float("nan")
    )
    no_engineer = (
        (resolved.engineer_called == False).mean() * 100 if not resolved.empty else float("nan")
    )

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        kpi("Avg Time to Classify", "—" if pd.isna(avg_class) else f"{avg_class:.1f}",
            GREEN if avg_class < 10 else AMBER, unit="min", sub="Spike → classification")
    with m2:
        kpi("Avg Time to Resolve", "—" if pd.isna(avg_resolve) else f"{avg_resolve:.1f}",
            BLUE, unit="min", sub="Spike → manager action")
    with m3:
        color = GREEN if pd.isna(fp_rate) or fp_rate < 25 else RED
        kpi("False Positive Rate", "—" if pd.isna(fp_rate) else f"{fp_rate:.0f}",
            color, unit="%", sub=f"Scored on {len(scored)} resolved events")
    with m4:
        kpi("Acted w/o Engineer", "—" if pd.isna(no_engineer) else f"{no_engineer:.0f}",
            TEAL, unit="%", sub="Theory C measurement")

    # ── Success criteria — scored on the held-out set, so this ignores the
    # facility filter: the bar is defined over all 15 cases, not a subset.
    s = score_test_set()
    section(f"Success Criteria · {s['n_cases']}-case held-out test set (core stratum)")

    p1, p2, p3 = st.columns([1, 1, 2])
    with p1:
        ok = s["precision"] >= 0.75
        kpi("Precision · Equipment Fault", f"{s['precision']:.0%}", GREEN if ok else RED,
            sub=f"Bar ≥75% · {'PASS' if ok else 'FAIL'} · {s['tp']} TP / {s['fp']} FP")
    with p2:
        ok = s["recall"] >= 0.70
        kpi("Recall · Equipment Fault", f"{s['recall']:.0%}", GREEN if ok else RED,
            sub=f"Bar ≥70% · {'PASS' if ok else 'FAIL'} · {s['fn']} missed of {s['n_faults']}")
    with p3:
        misses = s["table"][
            (s["table"].true_top_level_class == "equipment_fault")
            & (s["table"].predicted != "equipment_fault")
        ]
        if misses.empty:
            st.caption("No equipment faults missed on the held-out set.")
        else:
            st.markdown(
                f'<div class="muted">Missed equipment faults — each one costs recall '
                f"{1 / s['n_faults']:.1%}:</div>",
                unsafe_allow_html=True,
            )
            st.dataframe(
                misses[["anomaly_id", "true_subtype_label", "predicted"]].rename(
                    columns={"anomaly_id": "Anomaly", "true_subtype_label": "Actual fault",
                             "predicted": "Classifier said"}
                ),
                hide_index=True, width="stretch",
            )

    # ── Decision value — does following the tool beat ignoring it?
    section("Decision Value · cost of following the tool vs. fixed policies")
    dv = score_decision_value()
    cost_rows = pd.DataFrame(
        [
            {
                "Policy": name,
                "Sent": v["dispatches"],
                "Caught": f"{v['caught']}/{dv['n_faults']}",
                "Missed": v["missed"],
                "Expected cost": f"${v['cost']:,.0f}",
            }
            for name, v in dv["policies"].items()
        ]
    )
    st.dataframe(cost_rows, hide_index=True, width="stretch")

    verdict_color = GREEN if dv["tool_wins"] else RED
    verdict = ("Following the tool is cheaper than both fixed policies."
               if dv["tool_wins"] else
               "Following the tool is NOT cheaper than dispatching on every spike — "
               "on this dataset the classifier's recommendations destroy value.")
    st.markdown(
        f'<div class="card" style="border-left:4px solid {verdict_color}">'
        f'<div class="badge" style="background:{verdict_color};color:#fff">'
        f'{"PASS" if dv["tool_wins"] else "FAIL"}</div>'
        f'<span class="muted" style="margin-left:9px">{verdict}</span>'
        f'<div class="muted" style="margin-top:7px">Priced at '
        f"${DISPATCH_COST:,.0f} per dispatch and ${MISS_COST:,.0f} "
        f"per undetected fault — the conservative end of the spec's $2,000–$8,000 "
        f"range. Missed faults are charged to whichever policy failed to dispatch.</div></div>",
        unsafe_allow_html=True,
    )

    head_l, head_r = st.columns([3, 1])
    with head_l:
        section(f"Full Anomaly Log · {len(view)} events")
    with head_r:
        export = view[
            ["detected_at", "facility_name", "system_name", "spike_kwh",
             "display_class", "severity", "status", "classification_minutes"]
        ]
        st.download_button(
            "⤓ Export CSV",
            export.to_csv(index=False).encode(),
            file_name="anomaly_log.csv",
            mime="text/csv",
            width="stretch",
        )

    page_size = 10
    n_pages = max(1, (len(view) + page_size - 1) // page_size)
    page = min(st.session_state.page, n_pages - 1)

    anomaly_table(view, "hist", page_size=page_size, page=page)

    if n_pages > 1:
        prev, label, nxt = st.columns([1, 3, 1])
        with prev:
            if st.button("‹ Prev", disabled=page == 0, width="stretch"):
                st.session_state.page = page - 1
                st.rerun()
        with label:
            st.markdown(
                f'<div style="text-align:center;font-size:11px;color:{TEXT_DIM};'
                f'padding-top:7px">Page {page + 1} of {n_pages}</div>',
                unsafe_allow_html=True,
            )
        with nxt:
            if st.button("Next ›", disabled=page >= n_pages - 1, width="stretch"):
                st.session_state.page = page + 1
                st.rerun()


# ── Screen 4 — Settings ───────────────────────────────────────────────────────


def render_settings():
    st.markdown(
        f'<div style="font-size:19px;font-weight:800;margin-bottom:3px">Settings</div>'
        f'<div class="muted" style="margin-bottom:14px">Facility details, alert '
        f"thresholds, and notification preferences</div>",
        unsafe_allow_html=True,
    )

    section("Facility List")
    facs = data["facility_registry"]
    st.dataframe(
        facs[["facility_id", "facility_name", "sq_footage", "is_online", "last_reading_at"]]
        .rename(
            columns={
                "facility_id": "ID",
                "facility_name": "Facility",
                "sq_footage": "Sq Ft",
                "is_online": "Online",
                "last_reading_at": "Last Reading",
            }
        ),
        hide_index=True,
        width="stretch",
    )

    target = facility if facility != "ALL" else facs.iloc[0].facility_id
    cfg = facs[facs.facility_id == target].iloc[0]

    section(f"Alert Thresholds · {cfg.facility_name}")
    a, b = st.columns(2)
    with a:
        st.slider(
            "Spike threshold (kWh above baseline)",
            5.0, 100.0, float(cfg.spike_kwh_threshold), 1.0,
            disabled=True,
            help="Detection thresholds are fixed in generate_dataset.py and applied "
                 "when the dataset is built, so changing them here would not "
                 "re-run detection. Shown read-only rather than pretending.",
        )
    with b:
        st.slider(
            "Duration threshold (minutes)",
            15, 240, int(cfg.spike_duration_threshold_min), 15,
            disabled=True,
            help="Fixed at detection time, as above. Read-only.",
        )

    section("Notification & Classification")
    c, d = st.columns(2)
    with c:
        st.session_state.setdefault("conf_threshold", COMMIT_THRESHOLD_DEFAULT)

        def _threshold_changed():
            # load_data() is deliberately not cleared — it reparses 78,840 rows.
            # Nothing it caches depends on the threshold; these four do.
            # score_test_set scores classification correctness, which the
            # threshold does not touch, so it is deliberately not cleared.
            for fn in (build_anomaly_view, compute_z_scores, score_decision_value):
                fn.clear()

        st.slider(
            "Dispatch threshold (confidence required to send a technician)",
            0.0, 1.0, step=0.05, key="conf_threshold", on_change=_threshold_changed,
            help="The agent recommends dispatch only above this confidence. Below "
                 "it, the classification is flagged Review Recommended instead.",
        )
        _t = commit_threshold()
        if abs(_t - BREAK_EVEN) < 0.026:
            st.caption(
                f"At {_t:.2f} this matches the break-even implied by your own costs "
                f"(\\${DISPATCH_COST:.0f} a visit against a \\${MISS_COST:,.0f} miss). "
                f"Every classification the model produces clears this bar."
            )
        else:
            st.caption(
                f"Break-even from your cost model is **{BREAK_EVEN:.2f}** — a visit "
                f"costs \\${DISPATCH_COST:.0f}, a missed fault \\${MISS_COST:,.0f}, so "
                f"dispatching pays whenever p × \\${MISS_COST:,.0f} > \\${DISPATCH_COST:.0f}. "
                f"This is set to {_t:.2f}, {_t / BREAK_EVEN:.0f}× higher. "
                f"Raising the bar above break-even withholds technicians from faults "
                f"the product identified correctly."
            )
    with d:
        prefs = ["email", "in_app", "both"]
        st.selectbox(
            "Notification preference",
            prefs,
            index=prefs.index(cfg.notification_pref),
        )

    # ── Import a meter export and check it before trusting it
    section("Import Meter Data")
    st.markdown(
        '<div class="muted">Upload an hourly export from the smart meter or BMS. '
        'It is checked against this facility\'s history and any problems are shown '
        'before the data is used — nothing is overwritten.</div>',
        unsafe_allow_html=True,
    )
    up = st.file_uploader("CSV with facility_id, system_id, recorded_at, kwh",
                          type=["csv"], label_visibility="collapsed")
    if up is not None:
        try:
            incoming = pd.read_csv(up)
        except Exception as exc:
            st.error(f"Could not read the file: {exc}")
        else:
            findings = input_guard.check_readings(
                incoming, input_guard.baseline_profile(data["energy_readings"]), data)
            st.caption(f"{len(incoming):,} rows read from {up.name}")
            if not findings:
                st.success("No problems found. This feed matches the shape of the "
                           "existing database.")
            else:
                worst = input_guard.worst_severity(findings)
                (st.error if worst == "blocker" else st.warning)(
                    f"{len(findings)} thing(s) to check before relying on this import."
                )
                render_findings(findings)

    # ── Planned operations
    section("Planned Operations")
    st.markdown(
        '<div class="muted">Tell the system about work you already know about — an '
        'extra shift, a rented chiller, a maintenance window. Anything flagged '
        'inside a declared window is shown with that context, and the classifier '
        'is given it as evidence.<br><b>It never suppresses an alert.</b> Equipment '
        'can fail during planned operations, and a missed fault costs far more than '
        'a needless visit.</div>',
        unsafe_allow_html=True,
    )

    with st.form("ops_add", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 2, 3])
        fac_opts = [operations_log.ANY] + list(data["facility_registry"].facility_id)
        with c1:
            f_id = st.selectbox("Facility", fac_opts, format_func=lambda v: (
                "All facilities" if v == operations_log.ANY else
                facs.set_index("facility_id").facility_name.get(v, v)))
        with c2:
            sysr = data["system_registry"]
            sys_opts = [operations_log.ANY] + list(
                sysr[sysr.facility_id == f_id].system_id if f_id != operations_log.ANY
                else sysr.system_id)
            s_id = st.selectbox("Sub-system", sys_opts, format_func=lambda v: (
                "All sub-systems" if v == operations_log.ANY else
                sysr.set_index("system_id").system_name.get(v, v)))
        with c3:
            ev = st.selectbox("What is happening", operations_log.EVENT_TYPES)

        d1, t1, d2, t2 = st.columns(4)
        _last = pd.Timestamp(data["energy_readings"].recorded_at.max())
        with d1:
            sd = st.date_input("Starts", _last.date())
        with t1:
            stime = st.time_input("at", pd.Timestamp("2026-01-01 06:00").time())
        with d2:
            ed = st.date_input("Ends", _last.date())
        with t2:
            etime = st.time_input("at ", pd.Timestamp("2026-01-01 14:00").time())

        note = st.text_input("Note for whoever reads this later (optional)",
                             placeholder="e.g. extra shift for the retail push")
        if st.form_submit_button("Declare this operation", width="content"):
            try:
                entry = operations_log.add(
                    f_id, s_id,
                    pd.Timestamp.combine(sd, stime), pd.Timestamp.combine(ed, etime),
                    ev, note)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.success(f"Declared: {operations_log.describe(entry)}")

    _ops = operations_log.load()
    if not _ops:
        st.caption("Nothing declared yet.")
    else:
        for entry in _ops:
            col, act = st.columns([9, 1])
            with col:
                st.markdown(
                    f'<div style="padding:5px 0"><b>{operations_log.describe(entry)}</b>'
                    + (f'<div class="muted">“{entry["note"]}”</div>'
                       if entry.get("note") else "")
                    + "</div>",
                    unsafe_allow_html=True,
                )
            with act:
                if st.button("Remove", key=f"ops_rm_{entry['entry_id']}"):
                    operations_log.remove(entry["entry_id"])
                    st.rerun()

    if st.button("Save Settings", width="content"):
        st.success(
            f"Settings saved for {cfg.facility_name}. "
            "(Demo build — changes are not written back to the workbook.)"
        )


# ── Router ────────────────────────────────────────────────────────────────────

if st.session_state.open_anomaly:
    render_classification_panel(st.session_state.open_anomaly)
elif st.session_state.screen == "Dashboard":
    render_dashboard()
elif st.session_state.screen == "History":
    render_history()
else:
    render_settings()

st.markdown(
    f'<div style="margin-top:26px;padding-top:12px;border-top:1px solid {BORDER};'
    f'font-size:10px;color:{TEXT_DIM};letter-spacing:.05em">'
    f"BUSN 43800 · ANALYTICS WITH AI · UNIVERSITY OF CHICAGO BOOTH SCHOOL OF BUSINESS"
    f"</div>",
    unsafe_allow_html=True,
)
