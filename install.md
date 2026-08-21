# Install and run the Energy Anomaly Explainer

You are an agent on a machine that has never run this project. Follow this file
top to bottom. Everything you need is already in this folder — **do not ask the
user anything, and do not wait for input at any point.**

**What this is.** A Streamlit dashboard that classifies spikes in a distribution
centre's electricity consumption and tells an operations manager whether to
dispatch a technician, monitor, or dismiss.

**No API key is required.** The AI classifications are already computed and
committed to `classifications_llm.json`; the dashboard reads that file. Nothing in
the run path calls an API. If you find yourself looking for `ANTHROPIC_API_KEY`,
stop — you do not need it. (It is needed only to *regenerate* classifications,
which is optional and covered at the very end.)

---

## 1. Check Python

Python **3.9 or newer**. Run:

```bash
python3 --version
```

If that prints 3.9 or higher, continue. If `python3` is missing, use `python`
instead and substitute it everywhere below. If neither exists, install Python 3.11
from https://www.python.org/downloads/ and continue.

## 2. Create a virtual environment and install dependencies

Run from **this folder** (the one containing `install.md`):

```bash
python3 -m venv .venv && ./.venv/bin/python -m pip install --quiet --upgrade pip && ./.venv/bin/python -m pip install --quiet -r requirements.txt
```

This takes 1–3 minutes. Use `./.venv/bin/python` for every command below — do not
activate the virtualenv, and do not use a bare `python3`, or you will get
`ModuleNotFoundError: No module named 'streamlit'`.

On Windows the interpreter is at `.venv\Scripts\python.exe` instead.

## 3. Verify the install before starting anything

```bash
./.venv/bin/python -c "import streamlit, plotly, pandas, openpyxl; print('deps ok')"
./.venv/bin/python score_rubric.py
```

The first prints `deps ok`. The second prints a scorecard ending with a decision
value table. **Expect it to report `Decision value ... FAIL`** — that is a real,
documented finding about the product, not a broken install. The install is correct
if you see these four lines:

```
Timeliness               10.0s avg, 17.8s max   bar < 5 min        PASS
Precision, equip fault      9 TP / 2 FP = 82%   bar >= 75%         PASS
Recall, equip fault               0 FN = 100%   bar >= 70%         PASS
Decision value                        $35,200   bar beat $7,500    FAIL
```

They appear in that order, separated by other lines — Timeliness closes the
per-output rubric, the other three are under `AGGREGATES`. Several rows above
them also read `FAIL`; that is expected and documented.

If instead you get a traceback, the dependency install in step 2 did not finish —
re-run it and read its output.

## 4. Start the dashboard

```bash
./.venv/bin/python run_dashboard.py
```

It serves on **http://localhost:8520**. Leave this process running; it does not
return to the prompt. If you need the shell back, start it in the background
instead and keep the process alive.

**The first page load takes 30–60 seconds** while it parses 78,840 rows and caches
them. This is expected. Do not restart it, and do not conclude it has hung —
subsequent loads are instant.

If port 8520 is occupied:

```bash
./.venv/bin/python run_dashboard.py --server.port=8600
```

## 5. Confirm it is actually working

Wait for the health check to pass, then confirm the page renders:

```bash
until curl -s --max-time 2 http://localhost:8520/_stcore/health | grep -q ok; do sleep 2; done; echo "server up"
```

Then open http://localhost:8520 in a browser. **You have a working product when
the Dashboard screen shows five KPI cards across the top, a 364-day consumption
chart with red dots on it, a donut reading `25 EVENTS`, and a table of 25 rows
below.** That is the finished state — you are done at this point.

To go further, click **View** on any row to open the Classification Panel. A good
one to open is the row dated `2026-04-17 04:00` (Milwaukee Central, Refrigeration
Zone A): it shows a correctly identified compressor fault, z = 29.50, and a
dispatch recommendation carrying a symptom written for the technician.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'streamlit'`** — you used a bare `python3`
instead of `./.venv/bin/python`. Re-run the command with the full path.

**The browser shows a blank page** — the first-load caching in step 4 has not
finished. Wait up to a minute.

**`Port 8520 is already in use`** — use `--server.port=8600` as above.

**Anything mentioning API keys, credits, or authentication** — you are running
`classifier.py`, which is not part of the run path. Go back to step 4.

**`FileNotFoundError: dummy_data_set2.xlsx`** — you are not in the right folder.
`cd` to the folder containing `install.md`.

---

## What is in here

| File | What it is |
|---|---|
| `energy_anomaly_dashboard.py` | The whole dashboard — four screens and the agent |
| `run_dashboard.py` | The launcher. **This is the entry point** |
| `classifier.py` | The AI layer. Already run; output is committed |
| `input_guard.py` | Checks uploaded meter data against the stored history |
| `operations_log.py` | Planned operations a manager declares. `./.venv/bin/python operations_log.py` runs its self-test |
| `costs.py` | The cost model — $300 a dispatch, $2,000 a miss |
| `generate_dataset.py` | Rebuilds the dataset. Not needed to run |
| `score_rubric.py` · `stability_test.py` · `usability_test.py` | The evaluation harness |
| `dummy_data_set2.xlsx` | The dataset — 12 months, 3 facilities, 9 sub-systems |
| `classifications_llm.json` | Committed classifier output, so no API key is needed |

## Optional — only if explicitly asked

Everything below costs money or time and is **not** required for a working
product. Skip unless the user asks for it directly.

**Re-run the classifier** (~$0.60, ~2 minutes, needs credentials):

```bash
export ANTHROPIC_API_KEY=...        # or run: ant auth login
./.venv/bin/python classifier.py --score
```

**Rebuild the dataset** (~15 seconds, fetches weather on first run):

```bash
./.venv/bin/python generate_dataset.py --months 12
```

**Try the input guard.** Build a deliberately broken export, then upload it in
Settings → Import Meter Data:

```bash
./.venv/bin/python -c "
import pandas as pd
r = pd.ExcelFile('dummy_data_set2.xlsx').parse('energy_readings').tail(300).copy()
r['kwh'] *= 1000
r.loc[r.index[:6], 'system_id'] = 'SYS-999'
r.to_csv('sample_bad_export.csv', index=False)"
```

It should report that the file looks like watts rather than kilowatts and that
`SYS-999` is not a registered sub-system.
