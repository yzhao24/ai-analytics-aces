# Energy Anomaly Explainer — Dashboard

**Team:** AI Analytics Aces · BUSN 43800 · University of Chicago Booth School of Business

A Streamlit dashboard that classifies energy consumption spikes at distribution
facilities and tells an operations manager whether to dispatch, monitor, or dismiss —
with the statistical evidence behind the call.

---

## What's in this folder

| File | What it is |
|---|---|
| **The product** | |
| `energy_anomaly_dashboard.py` | The whole dashboard — all four screens and the agent |
| `run_dashboard.py` | Launcher that works from any working directory |
| `classifier.py` | The AI classification layer. Calls Claude, writes `classifications_llm.json` |
| `input_guard.py` | Checks incoming meter data against the settled history |
| **The data** | |
| `generate_dataset.py` | Builds the dataset from scratch. Edit this when the data needs to change |
| `fetch_weather.py` | Real hourly temperatures from Open-Meteo. Also imported by the generator |
| `dummy_data_set2.xlsx` | The dataset the dashboard reads (9 sheets, 12 months) |
| `registries.xlsx` | Facilities, sub-systems, and the 14 classification types |
| `classifications_llm.json` | Classifier output. Overlaid on the workbook at load time |
| **Evaluation** | |
| `score_rubric.py` | Scores the Assignment 2 rubric and the decision value |
| `stability_test.py` | Repeat runs and bias breakdown → `stability_runs.json` |
| `usability_test.py` | Rater sheets, scoring, and the optional LLM judge → `usability_judge.json` |
| `usability_cases.md` | The blind rating pack handed to two human raters |
| `verify_review_numbers.py` | Reproduces the figures cited in the adversarial reviews |
| **Deliverables** | |
| `build_assignment2_docx.py` | Group Assignment 2 as a 5-page Word document |
| `build_final_deck.py` | The final presentation, on the Booth master |
| `build_speech_doc.py` | The speaking script as cue cards, one page per speaker |
| `speaker_notes.py` | The spoken script and its timing — the source both of the above read |
| `DEMO_SCRIPT.md` | Demo recording script, with every figure verified against the live panel |
| `appendix_prompt.txt` · `appendix_cases.json` | Generated appendix inputs — do not hand-edit |
| **Specs** | |
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

**Settings** — facility list, threshold and confidence sliders, and **Import Meter Data**:
upload an hourly CSV export and it is checked against the existing database before you
rely on it. See below.

## Checking incoming data

The product used to tell you when one *reading* was implausible and say nothing when an
entire *feed* was wrong. A file in watts instead of kilowatts, a meter that stopped
reporting, a sub-system code that does not exist — each renders a perfectly plausible
dashboard while every classification behind it is meaningless.

`input_guard.py` profiles the settled history and tests new data against it: unit scale,
negative and non-numeric values, runs of zeros, readings far beyond anything recorded,
duplicate timestamps, gaps in hourly coverage, unregistered sub-systems, unreadable or
future timestamps, overlap with data already held, and temperatures that read as Celsius
in a Fahrenheit column.

Two entry points. On load the dashboard checks its own most recent 14 days against the
preceding history and raises a modal if anything looks off. Settings takes a CSV and
checks it the same way. **Findings are prompts to check, never rejections** — nothing is
discarded and nothing is overwritten.

To try it, build a broken export and upload it in Settings:

```bash
python3 -c "
import pandas as pd
r = pd.ExcelFile('dummy_data_set2.xlsx').parse('energy_readings').tail(300).copy()
r['kwh'] *= 1000                      # watts, not kilowatts
r.loc[r.index[:6], 'system_id'] = 'SYS-999'
r.to_csv('sample_bad_export.csv', index=False)"
```

## The three actions

Every recommendation is one of **dispatch**, **monitor**, or **dismiss**, and the same
three verbs run through the whole system — the classifier's output schema, the standing
action attached to each of the 14 classification types, the button in the Classification
Panel, and what gets written to `manager_actions`. A fourth path, **Flag for Engineer
Review**, is always available and records as `escalated`.

Only 4 of the 14 types call for a technician, so "equipment fault" and "send someone" are
not the same thing.

**A fifth path, exception, is always available.** Three actions cannot cover every spike,
and a manager forced to pick the closest wrong one leaves no trace that the taxonomy
failed. The Classification Panel takes a free-text note — what should happen instead and
why — records the anomaly as `exception`, and shows it in the log with a teal badge.

Those notes are the most useful data the product collects about its own limits. A reason
that keeps recurring is a candidate for a fifteenth classification type. Both operational
misclassifications in the current test set would have been caught this way, months before
anyone scored a rubric.

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
| Avg time to classify | **10.0 s** (17.8 s max) | <5 min ✅ |

Reproduce with `python3 score_rubric.py`.

**Decision value fails, and that matters more than the two passes above.** Following
the tool costs $35,200 against $7,500 for dispatching a technician to every spike.
Only 4 of 25 spikes clear the 0.75 confidence gate, so 17 of 20 real faults get
"monitor" and nobody is sent. The classifier is accurate and the product still loses
money. The History screen shows the full comparison.

Two things drive it, and neither is the classifier. The gate is set by convention:
a dispatch costs $300 against a $2,000 miss, so break-even is `p > 0.15` and we
gated at 0.75 — five times too high. Removing the gate entirely drops the cost to
$15,100, which is still worse than blanket dispatch, because with 20 faults among
25 anomalies a perfect classifier saves only $1,500 while one missed fault costs
$2,000. The base rate caps the prize below the price of a single mistake, and that
base rate comes from discarding the detector's false alarms — see below.

---

## Known limitations

**Detector false alarms are discarded.** The detector raises 562 alarms across the
year; only the 25 that match an injected anomaly reach the workbook. Every case the
classifier is scored on is therefore a genuine planted event, so precision measures
label accuracy and never the harder question of telling a real event from a false
alarm. It also leaves the test set with an 80% fault base rate, which is why no
dispatch policy can beat dispatching on everything.

**Operational variation is still confused with equipment fault.** The remaining core
errors are Peak Throughput Day and Temporary Equipment Rental read as faults.

We tried the obvious fix and it did not work. The reasoning was sound: an hourly meter
measures one number, and a busy shift and a stuck compressor both produce "more kWh for
several hours", so no function of kWh alone can separate them. Temperature already
supplies a second signal, which is why the weather-driven case is classified correctly
and dismissed at z = −0.04. Planned throughput should do the same for operational
variation.

It runs into a threshold conflict. A day planned at 130% of normal adds 7–10 kWh to a
sub-system; the alarm fires at 20. So a realistic busy day never reaches the detector,
and any operational event large enough to alarm is by construction larger than its own
explanation — at which point calling it a fault is correct, not a mistake. Sizing the
events down to what the plan predicts made them undetectable and collapsed the test set.

Either the alert threshold drops far enough to surface ordinary operational variation,
which floods the queue, or the three-class scheme collapses toward two above the alarm
line. That is a specification decision, not a prompt or feature-engineering one. The
full experiment, with measurements at each step, is on the `experiment/shift-schedule`
branch.

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
