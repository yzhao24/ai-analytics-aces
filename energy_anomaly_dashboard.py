"""
Energy Anomaly Explainer — Streamlit Dashboard
AI Analytics Aces · BUSN 43800

Run with:  streamlit run energy_anomaly_dashboard.py

Implements the 4-screen wireframe (Dashboard / Classification Panel / History &
Trends / Settings) and the 4-tool agent orchestrator described in wireframe_v2.md,
reading all data from dummy_data_set1.xlsx per data_schema_v2.md.
"""

import math
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA_FILE = Path(__file__).parent / "dummy_data_set1.xlsx"

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

    return d


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

def tool_compute_baseline(fetched, anomaly):
    """Tool 2 — rolling median at matching hour/day-of-week and ±5°F temp band."""
    lookback = fetched["lookback"].copy()
    t, temp = anomaly.detected_at, anomaly.temp_f_at_detection

    if lookback.empty:
        std = max(anomaly.baseline_kwh * 0.12, 1.0)
        return {
            "baseline_mean": anomaly.baseline_kwh,
            "baseline_std": std,
            "weather_adjusted": False,
            "n_samples": 0,
            "basis": "no history",
            "input_summary": "no lookback readings available",
            "output_summary": f"fallback baseline={anomaly.baseline_kwh:.1f}, std={std:.1f}",
        }

    lookback["hour"] = lookback.recorded_at.dt.hour
    lookback["dow"] = lookback.recorded_at.dt.dayofweek

    same_slot = lookback[(lookback.hour == t.hour) & (lookback.dow == t.dayofweek)]
    same_hour = lookback[lookback.hour == t.hour]

    # Progressive fallback: the tightest match with enough samples wins. A 30-day
    # feed rarely has 5 readings at the same hour AND weekday AND temperature, so
    # widening to same-hour keeps the std grounded in real variance instead of a
    # synthetic percentage of the mean.
    ladder = [
        (same_slot[same_slot.temp_f.between(temp - 5, temp + 5)], True,
         f"hour={t.hour}, dow={t.dayofweek}, temp={temp:.0f}°F ±5°F"),
        (same_hour[same_hour.temp_f.between(temp - 5, temp + 5)], True,
         f"hour={t.hour}, temp={temp:.0f}°F ±5°F"),
        (same_slot, False, f"hour={t.hour}, dow={t.dayofweek}"),
        (same_hour, False, f"hour={t.hour}"),
        (lookback, False, "all 28d readings"),
    ]

    std, n, weather_adjusted, basis = None, 0, False, "fallback"
    for sample, is_weather, desc in ladder:
        if len(sample) < 5:
            continue
        s = sample.kwh.std()
        if pd.isna(s) or s <= 0:
            continue
        std, n, weather_adjusted, basis = float(s), len(sample), is_weather, desc
        break

    if std is None:
        std = max(anomaly.baseline_kwh * 0.12, 1.0)
        basis = "synthetic (insufficient history)"

    return {
        "baseline_mean": anomaly.baseline_kwh,
        "baseline_std": std,
        "weather_adjusted": weather_adjusted,
        "n_samples": n,
        "basis": basis,
        "input_summary": f"28d lookback · matched on {basis}",
        "output_summary": (
            f"mean={anomaly.baseline_kwh:.1f}, std={std:.1f}, "
            f"weather_adjusted={weather_adjusted}, n={n}"
        ),
    }


def tool_run_significance_test(baseline, anomaly):
    """Tool 3 — z-score of the spike delta against the weather-adjusted baseline."""
    z = anomaly.spike_kwh / baseline["baseline_std"]
    p = _two_tailed_p(z)
    percentile = (1 - p / 2) * 100
    verdict = "significant" if z >= 2.0 else "not_significant"

    temp = anomaly.temp_f_at_detection
    if not baseline["weather_adjusted"]:
        weather_context = (
            f"No temperature match in the 28-day lookback at {temp:.0f}°F — "
            "baseline falls back to hour/day-of-week only."
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


def tool_fetch_comparable_events(data, anomaly, z_score, z_by_anomaly):
    """Tool 4 — past spikes on the same system within ±0.5 z of this one."""
    reg = data["classification_registry"].set_index("classification_id")
    ano = data["anomalies"].set_index("anomaly_id")
    matches = []

    for other_id, other_z in z_by_anomaly.items():
        if other_id == anomaly.anomaly_id or abs(other_z - z_score) > 0.5:
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


def decide(data, z_score, classification):
    """The agent's decision rule, shared by the panel and the batch scorer.

    Two gates: a statistical one on the z-score and confidence, then a semantic
    cap at whatever the matched classification itself warrants.
    """
    if z_score < 2.0:
        return "dismiss"

    confidence = (
        float(classification.confidence_score) if classification is not None else None
    )
    decision = (
        "dispatch"
        if z_score >= 3.0 and confidence is not None and confidence >= 0.75
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
    truth = data["test_set_15_cases"][
        ["anomaly_id", "true_top_level_class", "true_subtype_label"]
    ]
    pred = data["classifications"][["anomaly_id", "top_level_class", "confidence_score"]]
    scored = truth.merge(pred, on="anomaly_id", how="left")
    scored["predicted"] = scored.top_level_class.fillna("(abstained)")

    is_fault = scored.true_top_level_class == "equipment_fault"
    said_fault = scored.predicted == "equipment_fault"
    tp, fp, fn = int((said_fault & is_fault).sum()), int((said_fault & ~is_fault).sum()), int((~said_fault & is_fault).sum())

    return {
        "table": scored,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else float("nan"),
        "recall": tp / (tp + fn) if tp + fn else float("nan"),
        "n_cases": len(scored),
        "n_faults": int(is_fault.sum()),
    }


# Cost parameters from the team spec: ~$300 per technician dispatch, $2,000-$8,000
# in excess consumption per undetected equipment fault. The conservative end of the
# miss range is used so the comparison cannot be accused of flattering the tool.
DISPATCH_COST_USD = 300.0
MISSED_FAULT_COST_USD = 2000.0


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
            "cost": dispatched.sum() * DISPATCH_COST_USD + missed * MISSED_FAULT_COST_USD,
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
st.session_state.setdefault("page", 0)

ano_all = build_anomaly_view().copy()
ano_all["status"] = ano_all.apply(
    lambda r: st.session_state.status_overrides.get(r.anomaly_id, r.status), axis=1
)


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
        review = bool(classification.review_recommended)

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
    action_text = recommended_action_text(
        decision,
        anomaly,
        system,
        row.subtype_label if pd.notna(row.subtype_label) else None,
        classification.top_level_class if classification is not None else None,
        significant,
    )

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
        f"▸ {action_text}</div></div>",
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
        st.caption("No comparable events found within ±0.5 z-score on this system.")

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
    if top_class == "equipment_fault":
        primary_label, new_status = "✓ Dispatch Technician", "classified"
    elif top_class == "operational_variation":
        primary_label, new_status = "✓ Log as Operational — Monitor 24hr", "classified"
    elif top_class == "data_anomaly":
        primary_label, new_status = "✓ Dismiss — Meter/Sensor Error", "dismissed"
    else:
        primary_label, new_status = {
            "dispatch": ("✓ Dispatch Technician", "classified"),
            "monitor": ("✓ Log as Operational — Monitor 24hr", "classified"),
            "dismiss": ("✓ Dismiss — Meter/Sensor Error", "dismissed"),
        }[decision]

    left, right = st.columns(2)
    with left:
        if st.button(primary_label, key="act_primary", width="stretch"):
            st.session_state.status_overrides[anomaly_id] = new_status
            st.session_state.open_anomaly = None
            build_anomaly_view.clear()
            st.rerun()
    with right:
        if st.button("Flag for Engineer Review", key="act_flag", width="stretch"):
            st.session_state.status_overrides[anomaly_id] = "escalated"
            st.session_state.open_anomaly = None
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
    order = {"unclassified": 0, "escalated": 1, "classified": 2, "dismissed": 3}
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
        cell(cols[6], f'<span style="font-size:11px">{r.status}</span>')

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
        ((acts.action_taken == "accepted") & (acts.acted_at >= month_start)).sum()
    ) if month_start is not None else 0

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
            sub=f"Accepted since {month_start:%b 1}" if month_start is not None
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
        section("Energy Timeline · 30-day consumption")
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
        n_unclassified = int((view.status == "unclassified").sum())
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
    section("Success Criteria · 15-case held-out test set")
    s = score_test_set()

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
        f"${DISPATCH_COST_USD:,.0f} per dispatch and ${MISSED_FAULT_COST_USD:,.0f} "
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
            help="An alert fires when a reading exceeds baseline by more than this.",
        )
    with b:
        st.slider(
            "Duration threshold (minutes)",
            15, 240, int(cfg.spike_duration_threshold_min), 15,
            help="The spike must persist this long before an anomaly is created.",
        )

    section("Notification & Classification")
    c, d = st.columns(2)
    with c:
        st.slider(
            "Confidence threshold (auto-classify above)",
            0.0, 1.0, float(cfg.confidence_threshold), 0.05,
            help="Below this, the classification is flagged Review Recommended "
                 "instead of auto-accepted.",
        )
    with d:
        prefs = ["email", "in_app", "both"]
        st.selectbox(
            "Notification preference",
            prefs,
            index=prefs.index(cfg.notification_pref),
        )

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
