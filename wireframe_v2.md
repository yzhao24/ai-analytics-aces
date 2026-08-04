# Energy Anomaly Explainer — App Wireframe Spec
**Team:** AI Analytics Aces · BUSN 43800  
**Last updated:** August 2026

---

## 1. What is this app?

A lightweight web dashboard that classifies energy consumption spikes at distribution facilities in minutes rather than days — giving operations managers at U.S. distribution centers ≥100,000 sq ft an AI-generated classification of the most likely cause (equipment fault, operational variation, or data anomaly) together with a confidence level and a specific recommended next action, fast enough to act within the same operational shift.

---

## 2. The main screens / views

### Screen 1 — Main Dashboard (landing screen)

**Purpose:** Give the operations manager an immediate read on the facility's current anomaly status and outstanding classifications. This is the screen they open first thing in the morning and after every shift handoff.

**Layout:**
```
┌────────────────────────────────────────────────────────────────┐
│  HEADER: [Facility selector ▼]   [Date range ▼]   [🔔 3 alerts]│
├────────────────────────────────────────────────────────────────┤
│  KPI CARDS (5 tiles, full width)                               │
│  [ Active Anomalies ] [ Avg Classification Time ] [ Faults     │
│    Confirmed ]  [ Est. Cost Exposure ]  [ Facilities Online ]  │
├───────────────────────────────┬────────────────────────────────┤
│  ENERGY TIMELINE (line chart) │  CLASSIFICATION BREAKDOWN      │
│  — 30-day consumption         │  (donut) by top-level class:   │
│  — red dot markers on spikes  │  Equipment Fault /             │
│  — hover shows spike detail   │  Operational Variation /       │
│                               │  Data Anomaly / Unclassified   │
├───────────────────────────────┴────────────────────────────────┤
│  ANOMALY TABLE (full width)                                    │
│  Timestamp | Facility | System | Spike (kWh) | Classification  │
│  | Severity | Status | Action                                  │
│  — rows color-coded by severity (red/amber/green)              │
│  — "Classify Now" button on unclassified rows                  │
└────────────────────────────────────────────────────────────────┘
```

**Key elements:**
- 5 KPI stat cards across the top (see Section 5 for definitions)
- Primary line chart: 30-day energy consumption with spike events marked as red dots
- Secondary donut chart: breakdown of confirmed faults by system type
- Anomaly table: all open and recently resolved anomalies, sortable and filterable
- Facility selector dropdown (for multi-facility operators, up to 10 sites)

**Primary action:** Click "Classify Now" on an unclassified anomaly row → opens Classification Panel (Screen 2)

---

### Screen 2 — Classification Panel (slide-in panel, not a new page)

**Purpose:** Show the AI-generated classification for a single spike event with enough context for the manager to decide whether to act without calling an engineer.

**Layout:**
```
┌─────────────────────────────────────────────────┐
│  [← Back]   Anomaly: 2026-08-03 14:22  Fac. 3  │
├─────────────────────────────────────────────────┤
│  SPIKE DETAIL                                   │
│  Size: 47 kWh above baseline                    │
│  Duration: 38 minutes    Temp: 94°F (heat wave) │
│  System: Refrigeration Zone B                   │
│  Time: Mid-shift (2:22 pm) · Tuesday            │
├─────────────────────────────────────────────────┤
│  AI CLASSIFICATION                              │
│  ┌─────────────────────────────────────────┐   │
│  │  CLASS: 🔴 EQUIPMENT FAULT             │   │
│  │  TYPE:  Compressor Fault               │   │
│  │  CONFIDENCE: High (87%)                │   │
│  │  Classified in 4 minutes               │   │
│  └─────────────────────────────────────────┘   │
│  Explanation: Spike profile matches compressor  │
│  start-fail pattern (rapid rise, sustained      │
│  plateau, no return to baseline). At 94°F,      │
│  baseline refrigeration load is ~28 kWh/hr;     │
│  this reading of 47 kWh is anomalous even       │
│  accounting for weather. Similar events at      │
│  this facility: 2 in past 90 days.              │
├─────────────────────────────────────────────────┤
│  COMPARABLE PAST EVENTS (mini table, 3 rows)    │
│  Date | Classification | Resolution | Cost      │
├─────────────────────────────────────────────────┤
│  SPIKE CHART (zoomed, this event only)          │
│  — shows ±2hr window around spike               │
│  — baseline shown as dashed line                │
├─────────────────────────────────────────────────┤
│  AGENT DECISION                                 │
│  ┌─────────────────────────────────────────┐   │
│  │  ✅ DISPATCH RECOMMENDED                │   │
│  │                                         │   │
│  │  Statistical evidence:                  │   │
│  │  Z-score: 3.4  |  P-value: 0.0003      │   │
│  │  Spike is 2.8x baseline                │   │
│  │  (99.97th percentile)                  │   │
│  │                                         │   │
│  │  Pattern match: Compressor Fault (87%) │   │
│  │  2 similar events · both resolved by   │   │
│  │  refrigeration technician              │   │
│  │                                         │   │
│  │  Recommended action:                   │   │
│  │  Dispatch refrigeration tech to Zone A │   │
│  │  Check compressor start capacitor first│   │
│  └─────────────────────────────────────────┘   │
│  Agent ran 4 tools in 3.2 seconds  [See steps] │
├─────────────────────────────────────────────────┤
│  ACTIONS                                        │
│  If Equipment Fault:                            │
│    [ ✓ Dispatch Technician ]                    │
│    — logs classification, attaches AI summary   │
│  If Operational Variation:                      │
│    [ ✓ Log as Operational — Monitor 24hr ]      │
│    — sets recurrence threshold, no dispatch     │
│  If Data Anomaly:                               │
│    [ ✓ Dismiss — Meter/Sensor Error ]           │
│    — flags reading for data quality review      │
│  Always available:                              │
│    [ Flag for Engineer Review ]                 │
│  Confidence: ██████████░░  87%                  │
└─────────────────────────────────────────────────┘
```

**Key elements:**
- Spike detail summary (size, duration, system, current temperature, time-of-day/day-of-week)
- AI classification result showing top-level class (Equipment Fault / Operational Variation / Data Anomaly) plus subtype where applicable, confidence score, and weather-aware plain-language explanation
- 3 comparable past events for context
- Zoomed spike chart with baseline overlay and weather-adjusted baseline shown as dashed line
- **Agent Decision panel** (see Section 10) — statistical significance test + structured DISPATCH / MONITOR / DISMISS recommendation with plain-language reasoning
- "See steps" expandable trace showing which tools the agent called and in what order
- Action buttons adapt to the classification: three distinct paths matching the spec's three required outputs

**Primary action:** Button label and downstream action depend on the top-level class — Dispatch, Monitor, or Dismiss

---

### Screen 3 — Anomaly History & Trends

**Purpose:** Let the manager review past anomalies over time, spot recurring patterns, and produce a monthly report.

**Layout:**
```
┌────────────────────────────────────────────────────────────────┐
│  HEADER: History & Trends  [Date range ▼]  [Facility ▼]       │
├─────────────────────────┬──────────────────────────────────────┤
│  TREND CHART            │  HEAT MAP                           │
│  — anomaly count        │  — frequency by day of week / hour  │
│    by week (bar chart)  │  — identifies recurring spike times  │
├─────────────────────────┴──────────────────────────────────────┤
│  RESOLUTION METRICS                                            │
│  Avg time to classify | Avg time to resolve | False positive % │
├────────────────────────────────────────────────────────────────┤
│  FULL ANOMALY LOG (paginated table, all historical events)     │
│  — same columns as dashboard table                             │
│  — exportable to CSV                                           │
└────────────────────────────────────────────────────────────────┘
```

**Key elements:**
- Weekly bar chart of anomaly frequency
- Heat map showing which hours/days spikes cluster (helps managers adjust schedules)
- Resolution metrics summary row
- Full paginated log with CSV export

**Primary action:** Export report

---

### Screen 4 — Settings (minimal)

**Purpose:** Configure facility details, alert thresholds, and notification preferences.

**Key elements:**
- Facility list (add/remove sites, name them)
- Alert threshold sliders: spike size (kWh) and duration (minutes) above which an alert fires
- Notification preferences: email, in-app, or both
- Confidence threshold: minimum AI confidence score before auto-classifying vs. flagging for review

**Primary action:** Save settings

---

## 3. Navigation

- **Left sidebar** (fixed, narrow): icons + labels for Dashboard, History, Settings
- **Landing screen:** Dashboard (Screen 1)
- **Classification Panel** (Screen 2) slides in from the right over Screen 1 — does not navigate away
- **Top header** persists across all screens: facility selector, date range, alert bell

---

## 4. Data / inputs

**What the user provides:**
- Energy consumption data (CSV upload or API connection to facility meter)
- Facility name and system labels (e.g., "Refrigeration Zone B", "HVAC Unit 3")
- Alert thresholds (customizable per facility)

**What the app shows back:**
- AI-generated fault classification with plain-language explanation
- Confidence score (0–100%)
- Comparable past events from the same facility
- Resolution time tracking (how long from spike to dispatch decision)
- Estimated cost exposure from open unclassified anomalies

---

## 5. KPI Card Definitions

| Card | Metric | Color logic |
|---|---|---|
| Active Anomalies | Count of unclassified spikes right now | Red if >0, green if 0 |
| Avg Classification Time | Mean minutes from spike detection to classification | Green <10 min, amber 10–60, red >60 |
| Faults Confirmed This Month | Count of accepted AI classifications | Neutral (informational) |
| Est. Cost Exposure | $ at risk from open anomalies (based on historical resolution cost per fault type) | Red if >$5k, amber $1–5k, green <$1k |
| Facilities Online | Count of connected facilities reporting data | Red if any offline |

---

## 6. Key interactions

- Clicking a red dot on the timeline opens the Classification Panel for that spike
- Clicking any row in the anomaly table opens the Classification Panel
- "Classify Now" button on unclassified rows triggers immediate AI classification
- Facility selector in header filters all charts and tables to that site
- Date range picker updates the timeline and history views
- Rows in the anomaly table are color-coded: red = critical fault, amber = warning, grey = resolved
- Confidence score below the set threshold shows a "Review Recommended" badge instead of auto-classifying
- Agent Decision panel auto-runs when Classification Panel opens; shows a loading state ("Agent is analyzing…") while the 4 tools execute (~3–5 seconds)
- "See steps" link in Agent Decision panel expands a trace showing each tool call, its input, and its output — gives the manager transparency into how the decision was reached
- If the agent z-score is below 2.0, the Agent Decision panel shows "NOT SIGNIFICANT — likely noise" in grey, overriding any amber/red classification severity

---

## 7. Tone / style

- **Background:** Dark navy (`#0F1B2D`) with slightly lighter card surfaces (`#1A2B3C`) — industrial monitoring aesthetic, similar to Grafana or Schneider EcoStruxure
- **Semantic color system (fixed — never used decoratively):**
  - 🟢 Green `#22C55E` — normal / resolved / within threshold
  - 🟡 Amber `#F59E0B` — warning / approaching threshold
  - 🔴 Red `#EF4444` — fault / critical / action required
  - 🔵 Blue `#3B82F6` — historical / baseline / informational
  - ⬜ Grey `#6B7280` — inactive / offline / no data
- **Accent:** Teal `#00C9B1` for primary action buttons and active states
- **Typography:** Inter (body and UI); large bold numbers for KPI cards (48px+); all-caps tight-tracked labels (10–11px) for section headers — industrial data-readout feel
- **Max 5–7 metrics visible on the main screen** — anything deeper lives in the Classification Panel or History screen
- **Anomaly table rows color-coded by severity**, not just sorted by date

---

## 8. What this app does NOT do

- Does not connect to or replace an enterprise BMS (Siemens, Honeywell, Johnson Controls) — it adds a classification and explanation layer on top of whatever consumption data the manager already receives, whether from a BMS, smart meter, or utility portal
- Does not automatically dispatch work orders without a manager action (manager must click "Accept & Dispatch")
- Does not predict future faults — it classifies spikes that have already occurred
- Does not handle non-energy facility data (temperature sensors, access logs, etc.)
- Does not support facilities larger than ~300,000 sq ft or those already running automated fault detection

---

## 9. Success criteria (from team spec)

**Primary bar:** on a 15-case held-out test set drawn from the synthetic warehouse dataset, the classifier achieves precision ≥75% and recall ≥70% on the equipment fault class specifically. The three output classes are equipment fault, operational variation, and data anomaly — all three must appear in the test set.

**Secondary bar:** the plain-English explanation generated for each classified spike is rated actionable by a non-technical evaluator in ≥80% of test cases, scored against a structured rubric. "Actionable" means the manager knows specifically what to do next and why.

**Failure condition:** if precision on the equipment fault class falls below 60%, or if confusion between fault and operational variation is not reducible through additional feature engineering, the product must be redesigned to require shift schedule or temperature data as mandatory inputs.

**Horizon:** classification and recommended action delivered within 5 minutes of the manager uploading or querying the consumption data.

---

## 10. Agent Layer

The agent answers the question: *"Is this anomaly statistically significant, and should I dispatch?"* It runs automatically when the Classification Panel opens and operates as an orchestrator calling four tools in sequence.

### Decision outputs

| Decision | Condition | Display color |
|---|---|---|
| `DISPATCH` | z-score ≥ 3.0 AND pattern match confidence ≥ 75% | 🟢 Green |
| `MONITOR` | z-score 2.0–2.9 OR confidence 50–74% | 🟡 Amber |
| `DISMISS` | z-score < 2.0 (spike not statistically significant) | ⬜ Grey |

### The four tools

**Tool 1 — `fetch_readings`**
Pulls `energy_readings` for the anomaly's facility, system, and a ±2hr window around `detected_at`. Also pulls the prior 28 days of readings at the same interval for baseline construction.

**Tool 2 — `compute_baseline`**
Takes the 28-day lookback from Tool 1 and returns, for each hourly interval slot:
- `baseline_mean` — rolling median kWh at similar temperature (±5°F band) AND same hour/day-of-week
- `baseline_std` — standard deviation within that temperature band
- `weather_adjusted` — boolean flag indicating whether a temperature match was found; if false, falls back to hour/day-of-week baseline only

Weather adjustment is the direct test of Theory A vs. Theory B from the spec: if weather-adjusted precision improves by >10 percentage points over consumption-only baseline, Theory A holds.

**Tool 3 — `run_significance_test`**
Takes the spike reading, weather-adjusted baseline, and current temperature and computes:
- `z_score = (spike_kwh - baseline_mean) / baseline_std` (using weather-adjusted baseline)
- `p_value` — two-tailed probability this is noise
- `percentile` — where this reading sits in the historical distribution at similar temperatures
- `verdict` — `significant` if z ≥ 2.0, `not_significant` if z < 2.0
- `weather_context` — plain-language note on whether temperature explains part of the spike

This is the direct answer to Theory B: if z < 2.0 even after weather adjustment, the agent stops and returns DISMISS without calling Tool 4.

**Tool 4 — `fetch_comparable_events`**
Queries `anomalies` + `classifications` + `manager_actions` for past spikes on the same system with a z-score within ±0.5 of the current spike. Returns up to 3 matches with their confirmed fault type, resolution action, and cost.

### Agent → UI mapping

| Agent output field | Where it appears in Classification Panel |
|---|---|
| `decision` | Header of Agent Decision panel (DISPATCH / MONITOR / DISMISS) |
| `z_score`, `p_value`, `percentile` | Statistical evidence row |
| `fault_type` + `confidence` | Pattern match row |
| `comparable_events` | Populates the Comparable Past Events mini-table |
| `recommended_action` | Plain-language recommendation text |
| Tool call trace | "See steps" expandable section |

### What this settles from the adversarial review

- **Theory B** (spikes are noise): the z-score test produces a `not_significant` verdict for any spike below 2 standard deviations — the agent explicitly tells the manager not to dispatch rather than classifying noise as a fault.
- **Theory C** (managers call engineer anyway): the agent provides explicit statistical evidence (z-score, p-value, percentile) alongside the classification, giving the manager a defensible basis to act without calling an engineer. The `engineer_called` field in `manager_actions` tracks whether this works in practice.

---

*Built for BUSN 43800 · Analytics with AI · University of Chicago Booth School of Business*
