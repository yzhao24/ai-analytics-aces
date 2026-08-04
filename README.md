# Energy Anomaly Explainer — Dashboard

**Team:** AI Analytics Aces · BUSN 43800 · University of Chicago Booth School of Business

A Streamlit dashboard that classifies energy consumption spikes at distribution
facilities and tells an operations manager whether to dispatch, monitor, or dismiss —
with the statistical evidence behind the call.

---

## What's in this folder

| File | What it is |
|---|---|
| `energy_anomaly_dashboard.py` | The whole dashboard — all four screens and the agent |
| `run_dashboard.py` | Launcher that works from any working directory |
| `dummy_data_set1.xlsx` | The dataset the dashboard reads (7 sheets) |
| `requirements.txt` | Pinned dependency list |
| `wireframe_v2.md` | Screen and agent spec this was built against |
| `data_schema_v2.md` | Table definitions and the KPI/chart source mappings |
| `README.md` | This file |

---

## Quick start

You need **Python 3.9 or newer**. Check with `python3 --version`.

**1 — Clone the repo**

```bash
git clone https://github.com/yzhao24/ai-analytics-aces.git && cd ai-analytics-aces
```

**2 — Create a virtual environment and install the dependencies**

A virtual environment keeps these packages out of your system Python, so
everyone on the team gets the same versions.

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate` instead.

**3 — Start the dashboard**

```bash
python3 run_dashboard.py
```

It opens at **http://localhost:8520**. Press `Ctrl+C` in the terminal to stop it.

If port 8520 is busy, pick another:

```bash
python3 run_dashboard.py --server.port=8600
```

> **Why `run_dashboard.py` instead of `streamlit run`?** Streamlit reads the current
> working directory at startup, which fails on macOS when the app lives under
> `~/Documents` and is launched by another program. The launcher sets the directory
> first. Running `streamlit run energy_anomaly_dashboard.py` directly works fine too,
> as long as you `cd` into this folder first.

---

## Running it with Claude Code

If you have [Claude Code](https://claude.com/claude-code) installed:

**1 — Open this folder**

```bash
cd path/to/Energy_Anomaly_V2 && claude
```

**2 — Ask Claude to run it**

Type this at the prompt:

```
Install the dependencies and start the dashboard, then tell me the URL.
```

Claude will install `streamlit`, `plotly`, `openpyxl`, and `pandas`, launch the app,
and hand you the link.

**Other things you can ask it to do**

```
Add a fourth KPI card showing average spike size in kWh.
```
```
The heat map should use hours 6am–10pm only. Make that change.
```
```
Explain how the z-score is calculated and which anomalies would be
dismissed if the threshold moved from 2.0 to 3.0.
```
```
Load dummy_data_set2.xlsx instead and tell me what changed.
```

Claude can read `wireframe_v2.md` and `data_schema_v2.md` in this folder, so it
already has the spec when you ask for changes.

---

## The four screens

**Dashboard** — five KPI cards, a 30-day hourly consumption line with red dots on
spike hours, a classification donut, and the anomaly table. The facility selector in
the sidebar filters everything.

**Classification Panel** — opens from **Classify Now** or **View** on any table row.
Shows spike detail, the AI classification with its confidence, comparable past
events, a zoomed ±2hr chart with the baseline overlaid, and the Agent Decision box.

**History & Trends** — anomaly counts by day, a day-of-week × hour heat map, four
resolution metrics, and the full log with CSV export.

**Settings** — facility list plus threshold and confidence sliders.

---

## How the agent works

When the Classification Panel opens, an orchestrator runs four tools in order. These
are real functions over the spreadsheet data, not canned responses.

| Tool | What it does |
|---|---|
| `fetch_readings` | Pulls the ±2hr window around the spike plus 28 days of history |
| `compute_baseline` | Finds the expected kWh and its standard deviation for this hour and temperature |
| `run_significance_test` | Computes the z-score, p-value, and percentile |
| `fetch_comparable_events` | Finds up to 3 past spikes with a similar z-score |

The decision comes from two gates:

1. **Statistical** — `z ≥ 3.0` with confidence `≥ 75%` suggests DISPATCH; `z` between
   2.0 and 2.9 suggests MONITOR; `z < 2.0` is DISMISS and Tool 4 is skipped entirely.
2. **Semantic** — the decision is then capped by what the classification itself
   warrants. A statistically significant *operational variation* is still not a
   dispatch, so it settles at DISMISS rather than sending out a technician.

Expand **See steps** in the panel to see each tool's actual inputs and outputs.

On `dummy_data_set1.xlsx` this yields **2 dispatch · 8 monitor · 5 dismiss**.

---

## Two things worth knowing about the data

**Baselines widen their match when history is thin.** The schema asks for a baseline
matched on the same hour, same day-of-week, *and* temperature within ±5°F. A 30-day
feed almost never has five such readings, so the app falls back step by step — same
hour and temperature, then same hour and weekday, then same hour, then all 28 days —
and reports which basis it used in the tool trace. Twelve of the fifteen anomalies get
a genuine weather-adjusted baseline this way.

**No spike in set 1 falls below z = 2.0.** The "NOT SIGNIFICANT — likely noise" path
is implemented and will render, but nothing in this dataset triggers it. Every DISMISS
here comes from the semantic cap instead. Demonstrating the noise path needs a dataset
with a sub-threshold spike.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'streamlit'`**
The install step didn't land in the Python you're running. Try:
```bash
python3 -m pip install --user streamlit plotly openpyxl pandas
```

**`Port 8520 is already in use`**
Either something else is on it or a previous run is still going:
```bash
python3 run_dashboard.py --server.port=8600
```

**`FileNotFoundError: dummy_data_set1.xlsx`**
The spreadsheet must sit in the same folder as `energy_anomaly_dashboard.py`. Keep the
folder contents together.

**The browser shows a blank page**
Give it a few seconds on first load — it parses 6,480 rows and caches them. If it
stays blank, check the terminal for a traceback.

---

## Using your own data

Replace `dummy_data_set1.xlsx` with a workbook using the same seven sheet names and
columns, documented in `data_schema_v2.md`:

`facility_registry` · `system_registry` · `classification_registry` ·
`energy_readings` · `anomalies` · `classifications` · `manager_actions`

The dashboard caches on load, so restart it after swapping the file.

---

*Built for BUSN 43800 · Analytics with AI · University of Chicago Booth School of Business*
