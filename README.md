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
| `classifier.py` | The AI classification layer. Calls Claude, writes `classifications_llm.json` |
| `generate_dataset.py` | Builds the dataset from scratch. Edit this when the data needs to change |
| `fetch_weather.py` | Pulls real hourly temperatures from Open-Meteo |
| `verify_review_numbers.py` | Reproduces the figures cited in the adversarial reviews |
| `dummy_data_set2.xlsx` | The dataset the dashboard reads (9 sheets, 12 months) |
| `registries.xlsx` | Facilities, sub-systems, and the 14 classification types |
| `classifications_llm.json` | Classifier output. Overlaid on the workbook at load time |
| `dummy_data_set1.xlsx` | The original 30-day dataset. Kept for reference, no longer read |
| `wireframe_v2.md` · `data_schema_v2.md` | The specs this was built against |

---

## Quick start

You need **Python 3.9 or newer**. Check with `python3 --version`.

**1 — Clone the repo**

```bash
git clone https://github.com/yzhao24/ai-analytics-aces.git && cd ai-analytics-aces
```

**2 — Create a virtual environment and install the dependencies**

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate` instead.

**3 — Start the dashboard**

```bash
python3 run_dashboard.py
```

It opens at **http://localhost:8520**. Press `Ctrl+C` to stop it. First load takes
several seconds — it parses 78,840 rows and caches them.

If port 8520 is busy, pick another: `python3 run_dashboard.py --server.port=8600`

That is all you need to view the dashboard. The classifier and the generator below
are only needed if you want to re-run the AI or rebuild the data.

---

## Running the classifier

The dashboard ships with `classifications_llm.json` already populated, so it works
out of the box. Re-run the classifier when you change the prompt, the dataset, or
want to reproduce the numbers yourself.

**Authenticate once.** No key is stored in this repo, and none should be added.

```bash
brew install anthropics/tap/ant && ant auth login
```

That stores an OAuth profile under `~/.config/anthropic/` — nothing in a file here
and nothing in your shell history. `export ANTHROPIC_API_KEY=...` works too.

**Then run it:**

```bash
python3 classifier.py --score     # classify all spikes, then score against ground truth
python3 classifier.py --only-missing   # only spikes that have no label yet
```

Roughly **$0.60** per full run and about two minutes. The account needs credits;
authentication alone is not enough.

The classifier never sees `test_set_15_cases`. Ground truth is loaded only by
`--score`, after every prediction is written, so the measured precision and recall
are not contaminated.

---

## Rebuilding the dataset

```bash
python3 generate_dataset.py --months 12 --co-occurring 8 --sub-threshold 6
```

Takes about 15 seconds. Weather is cached after the first fetch, so reruns are
offline. `--months 3` produces a smaller file that loads faster while iterating.

The generator is the file to edit when the data needs to change — the load model,
the anomaly catalogue, and the injection strata are all near the top.

---

## The four screens

**Dashboard** — five KPI cards, a 12-month hourly consumption line with red dots on
spike hours, a classification donut, and the anomaly table. The facility selector in
the sidebar filters everything.

**Classification Panel** — opens from **View** or **Classify Now** on any table row.
Spike detail, the AI classification with its confidence and plain-language
explanation, the agent's decision with the statistics behind it, comparable past
events, and a zoomed ±2hr chart with the baseline overlaid. Dispatch recommendations
carry a symptom written for the technician.

**History & Trends** — anomaly counts by day, a day-of-week × hour heat map,
resolution metrics, **Success Criteria** (precision and recall against ground truth),
**Decision Value** (the tool priced against two fixed policies), and the full log with
CSV export.

**Settings** — facility list plus threshold and confidence sliders.

---

## How the agent works

When the Classification Panel opens, an orchestrator runs four tools in order. These
are real functions over the data, not canned responses.

| Tool | What it does |
|---|---|
| `fetch_readings` | Pulls the ±2hr window around the spike plus 28 days of history |
| `compute_baseline` | Expected consumption and its spread, from one comparison set |
| `run_significance_test` | z-score, p-value, percentile |
| `fetch_comparable_events` | Past spikes on the same system with a similar z-score |

The decision comes from two gates. **Statistical** — `z ≥ 3.0` with confidence
`≥ 75%` suggests DISPATCH, `z` between 2.0 and 2.9 suggests MONITOR, and `z < 2.0`
is DISMISS with Tool 4 skipped. **Semantic** — the decision is then capped by what
the classification itself warrants, so a statistically significant operational
variation is not a dispatch.

Expand **See steps** in the panel to see each tool's actual inputs and outputs.

### Why detection and Tool 2 use different baselines

The detector deliberately ignores temperature. It stands in for the threshold alarm
a manager already receives from a BMS or utility portal, which has no idea what the
weather is doing. Tool 2 then conditions on temperature.

That gap is what the agent is for. A hot afternoon trips the naive threshold and is
cleared once the comparison is drawn from hours at a similar temperature — which is
the Theory A versus Theory B test, running inside the product rather than in a side
analysis. `ANO-2010` is the worked example: flagged at +21.4 kWh, then dismissed at
z = −0.04.

---

## Current results

On the core stratum of `dummy_data_set2.xlsx`, classified by `claude-opus-5`:

| Metric | Result | Bar |
|---|---|---|
| Precision, equipment fault | **82%** | ≥75% ✅ |
| Recall, equipment fault | **100%** | ≥70% ✅ |
| Avg time to classify | **0.2 min** | <5 min ✅ |

Reproduce with `python3 classifier.py --score`.

**Decision value fails, and that matters more than the two passes above.** Following
the tool costs $35,200 against $7,500 for dispatching a technician to every spike.
Only 4 of 25 spikes clear the 0.75 confidence gate, so 17 of 20 real faults get
"monitor" and nobody is sent. The classifier is accurate and the product still loses
money. The History screen shows the full comparison.

---

## Known limitations

**Detector false alarms are discarded.** The detector raises 562 alarms across the
year; only the 25 that match an injected anomaly reach the workbook. Every case the
classifier is scored on is therefore a genuine planted event, so precision measures
label accuracy and never the harder question of telling a real event from a false
alarm. It also leaves the test set with an 80% fault base rate, which is why no
dispatch policy can beat dispatching on everything.

**Operational variation is still confused with equipment fault.** The remaining core
errors are Peak Throughput Day and Temporary Equipment Rental read as faults. Neither
a sharper prompt nor a better baseline moved them, which supports the argument that
shift schedule data is the missing input rather than better modelling.

**Two classification types never appear** in the current test set (CT-009, CT-014).

**The co-occurring and sub-threshold strata are thin** — 5 and 6 cases. Several
requested injections were placed where no sub-system could plausibly host them.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'streamlit'`**
The install landed in a different Python. Activate the virtualenv first, or run
`./.venv/bin/python run_dashboard.py`.

**`Port 8520 is already in use`**
`python3 run_dashboard.py --server.port=8600`

**Classifier exits with "no API credits"**
The account authenticated but cannot make inference calls. Add credits, or
`ant auth login` and pick an organisation that has them.

**Edits to the dashboard don't show up**
The launcher disables Streamlit's file watcher. Restart it.

**The browser shows a blank page**
Give it several seconds on first load. If it stays blank, check the terminal.

---

## Using your own data

Point `DATA_FILE` in `energy_anomaly_dashboard.py` at any workbook with the same nine
sheets. Easier is to edit `generate_dataset.py` and rebuild — the facility roster,
sub-systems, and classification catalogue all come from `registries.xlsx`.

The dashboard caches on load, so restart it after swapping the file.

---

*Built for BUSN 43800 · Analytics with AI · University of Chicago Booth School of Business*
