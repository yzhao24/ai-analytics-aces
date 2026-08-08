# Demo recording script — Energy Anomaly Explainer

**Target 2:35.** Three cases in a deliberate order: it works → the agent overturns
the alarm → it fails. Then the guardrails.

**Every number below was read off the live panel on 8 Aug 2026.** Where the script
quotes a figure, that figure is on screen. Re-verify if you re-run `classifier.py`.

---

## Which cases, and why

| Case | System | z-score | Why it earns its place |
|---|---|---|---|
| **ANO-2000** | Refrigeration Zone A, Milwaukee Central | **29.50** | The happy path. Big unambiguous spike, correct fault, dispatch with a symptom a refrigeration tech can act on. |
| **ANO-2010** | HVAC Unit 1, Chicago South DC | **−0.04** | **The one that proves the agent is doing work.** The only case where the weather-matched baseline overturns the detector. Everything else scores z ≥ 20. |
| **ANO-2009** | Compressor Bank, Indianapolis East | **20.82** | The failure. Compressor Fault at 0.78; it was a Peak Throughput Day. |

**Reading the panel correctly.** "Spike above baseline: 122.5 kWh" is the *excess*,
not the total. Baseline 61.1 + excess 122.5 = a 183.6 kWh peak, which is why the
agent line reads **3.0× baseline**. Quote the two numbers and the multiple exactly as
the panel gives them and you cannot go wrong.

*Optional fourth if you want a "saves the trip" beat:* **ANO-2012** — Lighting Grid
South, 101.4 above a 27.0 baseline, **4.8× baseline, z = 43.35**, correctly dismissed
as Meter Dropout at 88%. Highest confidence in the whole set.

---

## Before you hit record

- The dashboard is already running on **http://localhost:8520** and the data is
  cached. **Do not restart it** — first load costs ~35 s while it parses 78,840 rows.
- Build the broken export and leave it on the desktop:
  ```bash
  cd /Users/yunzhao/Downloads/AI/energy-anomaly-explainer && python3 -c "
  import pandas as pd
  r = pd.ExcelFile('dummy_data_set2.xlsx').parse('energy_readings').tail(300).copy()
  r['kwh'] *= 1000
  r.loc[r.index[:6], 'system_id'] = 'SYS-999'
  r.to_csv('sample_bad_export.csv', index=False)"
  ```
- Do Not Disturb on. Close anything with a badge.
- Browser at 1920×1080, zoom 100%, bookmarks bar hidden.
- **Record four short takes**, one per section. Redoing 40 seconds beats redoing 2:35.
- Pause ~1 s after each click before speaking. It reads as confident and gives you
  clean cut points.

---

## 1 · Orientation — 0:15

> **Dashboard screen.**

"Twelve months of hourly electricity data from three distribution centers — about
seventy-nine thousand readings across nine sub-systems. Every red dot is an hour our
detector flagged. Twenty-five of them. The manager's question is always the same:
which of these is worth a technician?"

---

## 2 · It works — ANO-2000 — 0:40

> **Anomaly table → row dated 2026-04-17 04:00, Milwaukee Central → View.**

"Refrigeration Zone A, four in the morning. A hundred and twenty-two kilowatt-hours
**above** a baseline of sixty-one — three times normal, held for three hours."

"It's forty-eight degrees outside. Nobody's in the building, and the weather cannot
explain a cooling system running flat out at four a.m. — the panel says exactly that."

> **Point at the agent line.**

"The agent scores it z equals twenty-nine point five. That is not a marginal call."

> **Scroll to the symptom.**

"Compressor fault, seventy-eight percent, dispatch. And the field I'd point at is the
last one — the symptom: *running continuously without cycling off, high discharge and
low suction pressure, elevated superheat.* That isn't a summary for a manager. That's
what you say to the refrigeration tech when you call them."

---

## 3 · The agent earns its keep — ANO-2010 — 0:45

> **Back → row dated 2026-07-17 00:00, Chicago South DC → View.**

"Now the case that shows why there's an agent here at all."

"Midnight, HVAC Unit 1. Twenty-one kilowatt-hours above baseline — one-point-six times
normal. Your building management system flagged this, and it would tell you to look
into it."

> **Point at the agent decision block.**

"The agent disagrees. **Z-score minus zero point zero four.** Fifty-first percentile.
Not significant."

> **Read the line on screen.**

"And here's why: *at seventy-six degrees this sits within normal consumption for
comparable hours — the alert came from a baseline that does not account for
temperature.* It was a warm night in July. The detector didn't know that. The agent
built its comparison from other hours at the same temperature, and the spike
disappeared."

> **Point at the tool count.**

"Note it ran three tools, not four — once the spike isn't significant it stops looking
for comparable events. And the recommendation is log it and monitor, not dispatch."

"**The alarm was real. The fault was not. That gap is the whole product.**"

---

## 4 · It fails — ANO-2009 — 0:30

> **Back → top row, 2026-07-27 20:00, Indianapolis East → View.**

"And one it gets wrong, because you should see this too."

"Compressor Bank, eight in the evening. Ninety-eight above a baseline of eighty-five —
two-point-one times normal, but held for **eight hours** while the outside air cooled."

"Compressor fault, seventy-eight percent, dispatch a technician. It was a **peak
throughput day**. The warehouse was busy."

"This is not a prompt we can fix. Shift schedules aren't an input this product
receives, so on kilowatt-hours alone a busy shift and a stuck compressor look the
same. We say so in the presentation."

---

## 5 · The guardrails — 0:25

> **Settings → Import Meter Data → upload `sample_bad_export.csv`.**

"Two things protect the numbers you just saw. Every import is checked against the
existing database — this file is in watts instead of kilowatts and carries a
sub-system code that doesn't exist. Without that check you get a perfectly plausible
dashboard where every classification behind it is meaningless, and it shows up in no
accuracy metric, because the labels still match."

> **Back to any case → expand "None of these fit — record an exception."** Type a
> short reason and record it.

"And three actions can't cover everything. When none fit, the manager writes down what
should happen instead. Those notes are the best evidence we get about what our
fourteen-cause taxonomy is missing."

---

## Closing line (optional, 0:05)

"That's the product. The next slides are how we tested it, and what it can't do."

---

## Two things to expect on camera

**ANO-2010 carries a ⚠ REVIEW RECOMMENDED badge.** That is not an error — it appears
because confidence is 0.72, below the 0.75 gate. If anyone asks, it is the exact
mechanism Nathanael describes on slide 8: the gate is set five times higher than
break-even, so it flags correct answers for review.

**If a number differs from this script, read the screen, not the page.** Class,
subtype and action have been stable across three runs; confidence moves by about 0.04.
Re-record the segment rather than talking over a mismatch.

---

## Reference — exactly what each panel showed (read 8 Aug 2026)

Check the screen against this while recording. If a line differs, the classifier has
been re-run; re-verify before you narrate it.

| | **ANO-2000** | **ANO-2010** | **ANO-2009** |
|---|---|---|---|
| Timestamp | 2026-04-17 04:00 | 2026-07-17 00:00 | 2026-07-27 20:00 |
| Facility | Milwaukee Central | Chicago South DC | Indianapolis East |
| System | Refrigeration Zone A | HVAC Unit 1 | Compressor Bank |
| Spike above baseline | 122.5 kWh | 21.4 kWh | 98.0 kWh |
| Baseline | 61.1 kWh | 38.4 kWh | 85.3 kWh |
| Duration | 180 min | 60 min | 480 min |
| Temperature | 48.0 °F | 76.4 °F | 74.1 °F |
| Class | Equipment Fault | Operational Variation | Equipment Fault |
| Subtype | Compressor Fault | Weather-Driven HVAC Surge | Compressor Fault |
| Confidence | Medium (78%) | Medium (72%) | Medium (78%) |
| **z-score** | **29.50** | **−0.04** | **20.82** |
| p-value | 3.706e-191 | 0.9677 | 3.369e-96 |
| Multiple | 3.0× baseline | 1.6× baseline | 2.1× baseline |
| Percentile | 100.00th | 51.61th | 100.00th |
| Agent decision | DISPATCH RECOMMENDED | NOT SIGNIFICANT · LIKELY NOISE | DISPATCH RECOMMENDED |
| Tools run | 4 in 3.2 s | **3 in 2.4 s** | 4 in 3.2 s |
| Button | Dispatch Technician | Log as Operational — Monitor 24hr | Dispatch Technician |
| Badge | — | ⚠ REVIEW RECOMMENDED | — |
| Ground truth | Compressor Fault ✓ | Weather-Driven HVAC Surge ✓ | **Peak Throughput Day ✗** |

Optional fourth — **ANO-2012**, 2026-03-13 08:00, Milwaukee Central, Lighting Grid
South: 101.4 above a 27.0 baseline, 37.7 °F, Meter Dropout, High (88%), **z = 43.35**,
4.8× baseline, DISMISS RECOMMENDED, button "Dismiss — Meter/Sensor Error".
