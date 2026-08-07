# Energy Anomaly Explainer — Data Schema
**Team:** AI Analytics Aces · BUSN 43800  
**Last updated:** August 2026  
*Read alongside: `energy_anomaly_explainer_wireframe.md`*

---

## Overview

Five source tables feed the dashboard. Raw meter readings flow in at the bottom; every KPI card, chart, and table row is a derived computation on top of them. The AI classification layer sits between the raw spike detection and the dashboard outputs.

```
RAW SOURCES                  AI LAYER              DASHBOARD OUTPUTS
─────────────────────────────────────────────────────────────────────
energy_readings              ┌──────────────┐      KPI Cards
facility_registry     ──────▶│  Spike       │      Timeline Chart
system_registry              │  Detector    │      Donut Chart
fault_type_registry          └──────┬───────┘      Anomaly Table
manager_actions                     │              Classification Panel
                                    ▼              History & Trends
                             ┌──────────────┐      Heat Map
                             │  AI          │
                             │  Classifier  │
                             └──────┬───────┘
                                    │
                                    ▼
                             anomalies  (derived)
                             classifications (derived)
                                    │
                                    ▼
                             ┌──────────────────────────────┐
                             │  AGENT ORCHESTRATOR          │
                             │  Tool 1: fetch_readings      │
                             │  Tool 2: compute_baseline    │
                             │  Tool 3: run_significance    │
                             │  Tool 4: fetch_comparables   │
                             └──────┬───────────────────────┘
                                    │
                                    ▼
                             agent_runs  (derived)        Agent Decision Panel
                             agent_tool_calls (derived)   "See steps" trace
```

---

## Table 1 — `energy_readings` (raw input)

The foundational table. One row per meter reading per hour. This is what the user uploads via CSV or pipes in via API. Hourly granularity matches the spec's requirement and the synthetic dataset the team is building.

| Column | Type | Description | Example |
|---|---|---|---|
| `reading_id` | UUID | Unique ID for this reading | `a3f2...` |
| `facility_id` | FK → facility_registry | Which facility | `FAC-003` |
| `system_id` | FK → system_registry | Which sub-system (nullable — not all facilities have sub-metering) | `SYS-012` |
| `recorded_at` | TIMESTAMP | When the reading was taken (top of each hour) | `2026-08-03 14:00:00` |
| `kwh` | FLOAT | Energy consumption in this hour | `47.3` |
| `temp_f` | FLOAT | Outdoor temperature at recorded_at (°F) — from weather API or manual entry | `94.2` |

**Notes:**
- Minimum required: `facility_id`, `recorded_at`, `kwh`
- `system_id` is optional but enables system-level breakdown in the donut chart; facilities with only whole-building meters leave this NULL
- `temp_f` is required for weather-adjusted baseline computation (Theory A test); if unavailable, agent falls back to hour/day-of-week baseline only and flags `weather_adjusted = false`
- Interval is fixed at 60 minutes (hourly) to match the spec's synthetic dataset and real-world smart meter standard

---

## Table 2 — `facility_registry` (reference)

One row per facility. Configured once in Settings (Screen 4).

| Column | Type | Description | Example |
|---|---|---|---|
| `facility_id` | PK | Unique facility identifier | `FAC-003` |
| `facility_name` | VARCHAR | Human-readable name | `"Chicago South DC"` |
| `sq_footage` | INT | Facility size in sq ft | `185000` |
| `is_online` | BOOLEAN | Currently sending data | `true` |
| `last_reading_at` | TIMESTAMP | Most recent reading received | `2026-08-04 06:15:00` |
| `spike_kwh_threshold` | FLOAT | Alert if spike exceeds this (kWh above baseline) | `20.0` |
| `spike_duration_threshold_min` | INT | Alert if spike lasts longer than this | `10` |
| `confidence_threshold` | FLOAT | Min confidence before auto-classifying | `0.75` |
| `notification_pref` | ENUM | `email`, `in_app`, `both` | `both` |

**Feeds into:**
- Header facility selector dropdown
- "Facilities Online" KPI card → `COUNT(*) WHERE is_online = true`
- Alert logic → spike thresholds applied per facility

---

## Table 3 — `system_registry` (reference)

One row per monitored sub-system within a facility. Optional but required for donut chart breakdown.

| Column | Type | Description | Example |
|---|---|---|---|
| `system_id` | PK | Unique system identifier | `SYS-012` |
| `facility_id` | FK → facility_registry | Which facility this belongs to | `FAC-003` |
| `system_name` | VARCHAR | Human-readable label | `"Refrigeration Zone B"` |
| `system_type` | ENUM | `hvac`, `refrigeration`, `lighting`, `other` | `refrigeration` |
| `cost_per_fault_usd` | FLOAT | Estimated cost if this system faults undetected | `8500.00` |

**Feeds into:**
- Donut chart → grouped by `system_type`
- "Est. Cost Exposure" KPI card → uses `cost_per_fault_usd` for open anomalies
- Classification Panel spike detail → `system_name`

---

## Table 4 — `classification_registry` (reference)

Lookup table of all classifications the AI can assign, covering all three required output classes: equipment fault, operational variation, and data anomaly. The `top_level_class` column is the primary output; `subtype_label` provides detail within equipment faults.

| Column | Type | Description | Example |
|---|---|---|---|
| `classification_id` | PK | Unique classification type ID | `CT-007` |
| `top_level_class` | ENUM | `equipment_fault`, `operational_variation`, `data_anomaly` | `equipment_fault` |
| `subtype_label` | VARCHAR | Specific label shown in UI (NULL for operational_variation and data_anomaly subtypes) | `"Compressor Fault"` |
| `system_type` | ENUM | Applicable system (`refrigeration`, `hvac`, `lighting`, `other`, `any`) | `refrigeration` |
| `severity` | ENUM | `critical`, `warning`, `informational` | `critical` |
| `typical_cost_usd` | FLOAT | Historical avg cost if unresolved (0 for operational variation and data anomaly) | `12000.00` |
| `recommended_action` | ENUM | `dispatch`, `monitor`, `dismiss` | `dispatch` |
| `description` | TEXT | Plain-language explanation shown in Classification Panel | `"Rapid rise and sustained plateau suggests compressor start-fail..."` |

**Reference data — all classification types:**

| classification_id | top_level_class | subtype_label | recommended_action |
|---|---|---|---|
| CT-001 | equipment_fault | Compressor Fault | dispatch |
| CT-002 | equipment_fault | Refrigerant Leak | dispatch |
| CT-003 | equipment_fault | HVAC Fan Failure | dispatch |
| CT-004 | equipment_fault | HVAC Filter Blockage | monitor |
| CT-005 | equipment_fault | Lighting Control Fault | monitor |
| CT-006 | equipment_fault | Door Seal Failure | dispatch |
| CT-007 | equipment_fault | Power Surge | monitor |
| CT-008 | operational_variation | Peak Throughput Day | dismiss |
| CT-009 | operational_variation | Unscheduled Overtime Shift | dismiss |
| CT-010 | operational_variation | Weather-Driven HVAC Surge | dismiss |
| CT-011 | operational_variation | Temporary Equipment Rental | dismiss |
| CT-012 | data_anomaly | Meter Dropout | dismiss |
| CT-013 | data_anomaly | Sensor Noise Spike | dismiss |
| CT-014 | data_anomaly | Communication Error | dismiss |

**Feeds into:**
- Classification Panel → `subtype_label` or `top_level_class`, `description`, `severity`, action button label (via `recommended_action`)
- Anomaly table → `Classification` column, row color (via `severity`)
- Donut chart → grouped by `top_level_class`
- "Est. Cost Exposure" KPI card → `typical_cost_usd` × count of open equipment_fault anomalies only
- Precision/recall measurement → `top_level_class = 'equipment_fault'` is the target class

---

## Table 5 — `anomalies` (derived — spike detector output)

One row per detected spike event. Generated automatically when a reading exceeds the facility's thresholds.

| Column | Type | Description | Example |
|---|---|---|---|
| `anomaly_id` | PK | Unique anomaly ID | `ANO-1042` |
| `facility_id` | FK → facility_registry | Which facility | `FAC-003` |
| `system_id` | FK → system_registry | Which system (nullable) | `SYS-012` |
| `detected_at` | TIMESTAMP | When spike was first detected | `2026-08-03 14:22:00` |
| `spike_kwh` | FLOAT | kWh above baseline at peak | `47.3` |
| `duration_minutes` | INT | How long spike lasted | `38` |
| `baseline_kwh` | FLOAT | Expected consumption at this time | `21.1` |
| `status` | ENUM | `unclassified`, `classified`, `dismissed`, `escalated` | `unclassified` |
| `classified_at` | TIMESTAMP | When AI classification completed (nullable) | `2026-08-03 14:26:00` |
| `classification_minutes` | FLOAT | `classified_at - detected_at` in minutes (nullable) | `4.0` |
| `temp_f_at_detection` | FLOAT | Outdoor temperature when spike was detected (from energy_readings) | `94.2` |

**How baseline is computed:**
> Rolling 4-week median of `kwh` at the same facility, system, day-of-week, hour, and temperature band (±5°F of current `temp_f`). If fewer than 5 historical readings exist in the temperature band, falls back to hour/day-of-week only. Anything exceeding `baseline_kwh + spike_kwh_threshold` for longer than `spike_duration_threshold_min` creates a new anomaly row. The `temp_f` at detection time is stored alongside `baseline_kwh` so the agent can explain the weather context in its classification.

**Feeds into:**
- "Active Anomalies" KPI → `COUNT(*) WHERE status = 'unclassified'`
- "Avg Classification Time" KPI → `AVG(classification_minutes) WHERE classified_at IS NOT NULL`
- Timeline chart → each anomaly is a red dot at `detected_at`
- Anomaly table → one row per anomaly
- Heat map → `detected_at` hour and day of week
- Weekly bar chart → `COUNT(*) GROUP BY week(detected_at)`

---

## Table 6 — `classifications` (derived — AI classifier output)

One row per AI classification attempt. Linked to an anomaly. Created when "Classify Now" is triggered or when an anomaly is auto-classified.

| Column | Type | Description | Example |
|---|---|---|---|
| `classification_id` | PK | Unique classification ID | `CLS-0891` |
| `anomaly_id` | FK → anomalies | Which anomaly this classifies | `ANO-1042` |
| `fault_type_id` | FK → fault_type_registry | What the AI thinks it is | `FT-007` |
| `confidence_score` | FLOAT | AI confidence 0.0–1.0 | `0.82` |
| `explanation_text` | TEXT | Plain-language rationale (AI-generated) | `"Spike profile matches compressor start-fail pattern..."` |
| `comparable_anomaly_ids` | ARRAY[UUID] | Up to 3 past anomalies used as reference | `[ANO-0881, ANO-0734]` |
| `created_at` | TIMESTAMP | When classification was generated | `2026-08-03 14:26:00` |
| `review_recommended` | BOOLEAN | True if `confidence_score < facility confidence_threshold` | `false` |

**Feeds into:**
- Classification Panel → all fields
- "Faults Confirmed This Month" KPI → joined with `manager_actions` below
- "Avg Classification Time" KPI → `classifications.created_at - anomalies.detected_at`

---

## Table 7 — `manager_actions` (derived — user actions)

One row per manager decision on a classification. Created when the manager clicks Accept, Dismiss, or Escalate.

| Column | Type | Description | Example |
|---|---|---|---|
| `action_id` | PK | Unique action ID | `ACT-0441` |
| `classification_id` | FK → classifications | Which classification was acted on | `CLS-0891` |
| `anomaly_id` | FK → anomalies | Which anomaly (denormalized for speed) | `ANO-1042` |
| `action_taken` | ENUM | `dispatched`, `monitoring`, `dismissed`, `escalated` — one verb per outcome, matching the agent's own vocabulary | `dispatched` |
| `acted_at` | TIMESTAMP | When the manager clicked | `2026-08-03 14:31:00` |
| `resolution_minutes` | FLOAT | `acted_at - anomaly.detected_at` in minutes | `9.0` |
| `engineer_called` | BOOLEAN | Did the manager call an engineer anyway? (self-reported) | `false` |
| `actual_top_level_class` | ENUM | Post-resolution confirmed top-level class: `equipment_fault`, `operational_variation`, `data_anomaly` (nullable, filled in after resolution) | `equipment_fault` |
| `actual_classification_id` | FK → classification_registry | Post-resolution confirmed subtype (nullable) | `CT-001` |

**Feeds into:**
- "Faults Confirmed This Month" KPI → `COUNT(*) WHERE action_taken = 'dispatched'`
- "Avg Classification Time" KPI → also uses `resolution_minutes` for end-to-end view
- History screen resolution metrics → `AVG(resolution_minutes)`, false positive % (where `actual_fault_type_id ≠ classifications.fault_type_id`)
- Success criteria tracking → `engineer_called = false` rate measures Theory C

---

## Table 8 — `agent_runs` (derived — agent orchestrator output)

One row per agent analysis of an anomaly. Created automatically when the Classification Panel opens. Stores the final structured decision and statistical outputs.

| Column | Type | Description | Example |
|---|---|---|---|
| `run_id` | PK | Unique agent run ID | `RUN-0041` |
| `anomaly_id` | FK → anomalies | Which anomaly was analyzed | `ANO-1042` |
| `classification_id` | FK → classifications | The AI classification this run accompanies (nullable if unclassified) | `CLS-0891` |
| `started_at` | TIMESTAMP | When the agent began | `2026-08-03 14:26:01` |
| `completed_at` | TIMESTAMP | When the agent returned its decision | `2026-08-03 14:26:04` |
| `duration_seconds` | FLOAT | `completed_at - started_at` | `3.2` |
| `z_score` | FLOAT | Statistical z-score of the spike vs. baseline | `3.4` |
| `p_value` | FLOAT | Two-tailed p-value | `0.0003` |
| `baseline_mean_kwh` | FLOAT | Baseline mean at this interval | `21.1` |
| `baseline_std_kwh` | FLOAT | Baseline standard deviation at this interval | `7.7` |
| `percentile` | FLOAT | Where the spike sits in historical distribution | `99.97` |
| `decision` | ENUM | `dispatch`, `monitor`, `dismiss` | `dispatch` |
| `recommended_action` | TEXT | Plain-language action recommendation | `"Dispatch refrigeration tech to Zone A. Check compressor start capacitor first."` |
| `comparable_anomaly_ids` | ARRAY[UUID] | Past anomalies used as evidence by Tool 4 | `[ANO-0881, ANO-0734]` |
| `tools_called` | INT | How many tools the agent invoked (1–4) | `4` |

**Notes:**
- `tools_called` will be fewer than 4 if z-score < 2.0 — the agent stops after Tool 3 and returns `dismiss` without running Tool 4
- `decision = 'dismiss'` when z < 2.0 regardless of the AI classifier's output — the statistical test overrides the pattern match for noise spikes

**Feeds into:**
- Agent Decision panel in Classification Panel (Screen 2) → all fields
- `decision` drives the panel header color (green / amber / grey)
- History screen — can be aggregated to show false positive rate of agent vs. actual outcomes

---

## Table 9 — `agent_tool_calls` (derived — agent step trace)

One row per tool call within an agent run. Powers the "See steps" expandable trace in the Classification Panel.

| Column | Type | Description | Example |
|---|---|---|---|
| `call_id` | PK | Unique tool call ID | `CALL-0201` |
| `run_id` | FK → agent_runs | Which agent run this belongs to | `RUN-0041` |
| `tool_name` | ENUM | `fetch_readings`, `compute_baseline`, `run_significance_test`, `fetch_comparable_events` | `run_significance_test` |
| `step_number` | INT | Order within the run (1–4) | `3` |
| `called_at` | TIMESTAMP | When this tool was invoked | `2026-08-03 14:26:02` |
| `duration_ms` | INT | How long the tool took in milliseconds | `340` |
| `input_summary` | TEXT | Brief description of what was passed in | `"spike_kwh=47.3, baseline_mean=21.1, baseline_std=7.7"` |
| `output_summary` | TEXT | Brief description of what came back | `"z_score=3.4, p_value=0.0003, verdict=significant"` |

**Feeds into:**
- "See steps" expandable trace in Classification Panel — one row per tool call, in order
- Gives the manager full transparency into how the agent reached its decision

---

## KPI Card → Source Mapping

| KPI Card | Formula | Source tables |
|---|---|---|
| **Active Anomalies** | `COUNT(*) WHERE anomalies.status = 'unclassified'` | `anomalies` |
| **Avg Classification Time** | `AVG(classification_minutes) WHERE classified_at IS NOT NULL`, rolling 30 days | `anomalies` |
| **Faults Confirmed This Month** | `COUNT(*) WHERE action_taken = 'dispatched' AND acted_at >= start_of_month` | `manager_actions` |
| **Est. Cost Exposure** | `SUM(fault_type_registry.typical_cost_usd)` for all open `unclassified` anomalies, joined via most likely system type | `anomalies` + `system_registry` + `fault_type_registry` |
| **Facilities Online** | `COUNT(*) WHERE facility_registry.is_online = true` | `facility_registry` |

---

## Chart → Source Mapping

| Chart | What it queries | Key columns |
|---|---|---|
| **Timeline (line)** | `energy_readings` averaged to hourly, 30-day window | `recorded_at`, `kwh` |
| **Timeline (red dots)** | `anomalies` in same window | `detected_at`, `spike_kwh` |
| **Donut (fault types)** | `classifications` joined to `fault_type_registry`, grouped by `system_type` | `system_type`, count |
| **Weekly bar chart** | `anomalies` grouped by `DATE_TRUNC('week', detected_at)` | `detected_at`, count |
| **Heat map** | `anomalies` grouped by `EXTRACT(dow)` and `EXTRACT(hour)` | `detected_at`, count |
| **Zoomed spike chart** | `energy_readings` ±2hr window around `anomaly.detected_at` | `recorded_at`, `kwh`, `baseline_kwh` |

---

## Agent Decision Panel → Source Mapping

| Panel element | Source | Notes |
|---|---|---|
| Decision header (DISPATCH / MONITOR / DISMISS) | `agent_runs.decision` | Color: green / amber / grey |
| Z-score | `agent_runs.z_score` | |
| P-value | `agent_runs.p_value` | |
| Percentile | `agent_runs.percentile` | |
| Spike multiple (e.g. "2.8x baseline") | `anomalies.spike_kwh / agent_runs.baseline_mean_kwh` | Computed on the fly |
| Pattern match fault + confidence | `classifications.fault_type_id` + `classifications.confidence_score` | |
| Comparable past events | `agent_runs.comparable_anomaly_ids` → join `anomalies` + `manager_actions` | |
| Recommended action text | `agent_runs.recommended_action` | |
| "See steps" trace | `agent_tool_calls` WHERE `run_id = current run`, ordered by `step_number` | |
| Agent runtime | `agent_runs.duration_seconds` | Shown as "Agent ran 4 tools in 3.2s" |

---

## Anomaly Table → Column Mapping

| Table column | Source | Notes |
|---|---|---|
| Timestamp | `anomalies.detected_at` | Formatted as local time |
| Facility | `facility_registry.facility_name` | Via `anomalies.facility_id` |
| System | `system_registry.system_name` | Nullable — shows "Unknown" if no system_id |
| Spike (kWh) | `anomalies.spike_kwh` | Shown as delta above baseline |
| Classification | `fault_type_registry.fault_label` | Via `classifications.fault_type_id`; "Unclassified" if no classification yet |
| Severity | `fault_type_registry.severity` | Drives row color: critical=red, warning=amber, informational=grey |
| Status | `anomalies.status` | `unclassified` / `classified` / `dismissed` / `escalated` |
| Action | UI button | "Classify Now" if unclassified; "View" if classified |

---

## Success Criteria → Measurement Mapping

These are the four success criteria from the wireframe, with the exact query that measures each:

| Success criterion | How to measure | Source |
|---|---|---|
| Classification in <5 min | `AVG(classification_minutes) < 5` over test set | `anomalies.classification_minutes` |
| Precision ≥75% on equipment fault class | Compare `classifications.top_level_class = 'equipment_fault'` vs `manager_actions.actual_top_level_class` on 15-case test set | `classifications` + `manager_actions` |
| Recall ≥70% on equipment fault class | True positives / (true positives + false negatives) on equipment fault class | `classifications` + `manager_actions` |
| Dispatch decision time drops vs. 1–3 day baseline | `AVG(resolution_minutes)` vs. historical baseline (pre-tool) | `manager_actions.resolution_minutes` |
| Manager acts without calling engineer | `COUNT(*) WHERE engineer_called = false / total accepted` | `manager_actions.engineer_called` |

---

## Data Flow Diagram (end to end)

```
Utility meter / CSV upload
         │
         ▼
  energy_readings
  (raw kWh per interval)
         │
         ├──────────────────────────────────────┐
         │                                      │
         ▼                                      ▼
  Baseline computation               Timeline chart
  (rolling 4-week median)            (line chart, Screen 1)
         │
         ▼
  Spike detection
  (reading > baseline + threshold
   for > duration threshold)
         │
         ▼
   anomalies table ──────────────────▶ Anomaly table (Screen 1)
         │                            Active Anomalies KPI
         │                            Red dots on timeline
         │                            Heat map (Screen 3)
         │
         ▼
  AI Classifier
  (fault_type, confidence,
   explanation, comparables)
         │
         ▼
  classifications table ────────────▶ Classification Panel (Screen 2)
         │                            Avg Classification Time KPI
         │                            Donut chart
         │
         ▼
  Agent Orchestrator
  (triggered when panel opens)
  │
  ├─ Tool 1: fetch_readings ──────▶ energy_readings (28-day window)
  ├─ Tool 2: compute_baseline ───▶ baseline_mean, baseline_std
  ├─ Tool 3: run_significance ───▶ z_score, p_value, percentile, verdict
  └─ Tool 4: fetch_comparables ──▶ anomalies + classifications + manager_actions
         │
         ▼
  agent_runs table ─────────────────▶ Agent Decision panel (Screen 2)
  agent_tool_calls table ───────────▶ "See steps" trace (Screen 2)
         │
         ▼
  Manager action
  (accept / dismiss / escalate)
         │
         ▼
  manager_actions table ────────────▶ Faults Confirmed KPI
                                      Est. Cost Exposure KPI
                                      History & Trends (Screen 3)
                                      Success criteria tracking
                                      Theory C measurement (engineer_called)
```

---

*Built for BUSN 43800 · Analytics with AI · University of Chicago Booth School of Business*
