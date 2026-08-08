# Demo recording script — Energy Anomaly Explainer

**Target 2:30.** Three cases in a deliberate order: it works → it saves a needless
trip → it fails. Then the guardrails. Every number below is what the panel actually
shows; anything you must read off the screen is marked `[read]`.

---

## Which cases, and why

| Case | System | On screen | Why it earns its place |
|---|---|---|---|
| **ANO-2000** | Refrigeration Zone A | 122.5 vs 61.1 kWh, **2.01×**, 3 h, 48 °F | The happy path. Big unambiguous spike, correct diagnosis, and a dispatch carrying a symptom a refrigeration tech can act on. |
| **ANO-2012** | Lighting Grid South | 101.4 vs 27.0 kWh, **3.75×**, 1 h | The most alarming number in the deck, and the right answer is *don't send anyone*. Highest confidence in the whole set (0.88). |
| **ANO-2009** | Compressor Bank | 98.0 vs 85.3 kWh, **1.15×**, 8 h | The failure. Called a Compressor Fault at 0.78; it was a Peak Throughput Day. Shows the limit honestly. |

### Do not use ANO-2010

The old script opened on it. Its "spike" is **21.4 kWh against a 38.4 baseline —
0.56×, seventeen kWh *below* normal**. The screen contradicts the word "spike," and
the first question from the room is one you cannot answer cleanly on camera.
ANO-2012 delivers the same beat — a scary number correctly dismissed — with numbers
that support the story.

---

## Before you hit record

- `python3 run_dashboard.py`, then **load the dashboard once** and let it cache.
  First parse of 78,840 rows takes several seconds and you do not want it on tape.
- Build the broken export (one-liner in the README) and leave `sample_bad_export.csv`
  on the desktop.
- Do Not Disturb on. Close Slack, Mail, everything with a badge.
- Browser at 1920×1080, zoom 100%, bookmarks bar hidden.
- Move the mouse slowly and deliberately. Pause ~1 s after each click before you
  speak — it reads as confident, and it gives you clean cut points.
- Record 3 short takes, one per case, rather than one long take. Far easier to redo
  a 40-second segment than a 2:30 run.

---

## 1 · Orientation — 0:15

> **Dashboard screen.**

"This is twelve months of hourly electricity data from three distribution centers —
about seventy-nine thousand readings across nine sub-systems. Every red dot is an
hour our detector flagged as unusual. The question for the operations manager is
always the same one: which of these is worth a technician?"

---

## 2 · It works — ANO-2000 — 0:45

> **Open ANO-2000** (Refrigeration Zone A, FAC-003, Friday 17 April, 04:00).

"Refrigeration Zone A, four in the morning. Draw is a hundred and twenty-two
kilowatt-hours against a baseline of sixty-one — **double**, held for three hours."

"It's forty-eight degrees outside. Nobody's in the building, and the weather can't
explain a cooling system running flat out at four a.m."

> **Expand "See steps."** Scroll the four tools.

"Behind that sit four tools running over the real data — it pulls the window around
the spike, builds a baseline from hours at a *similar temperature*, runs a
significance test `[read the z-score aloud]`, and looks for comparable past events."

> **Point at the classification, then the symptom line.**

"It calls this a compressor fault at seventy-eight percent confidence, and
recommends dispatch. The part I'd point at is the last field — the symptom:
*compressor running continuously without cycling off, high discharge and low suction
pressure, elevated superheat.* That's not a summary for a manager. That's what you
say to the refrigeration tech when you call them."

---

## 3 · It saves the trip — ANO-2012 — 0:35

> **Back, open ANO-2012** (Lighting Grid South, FAC-003, Friday 13 March, 08:00).

"Here's the biggest number in the dataset. Lighting Grid South, a hundred and one
kilowatt-hours against a baseline of twenty-seven — **three and three-quarter times
normal**. If you're the manager, this is the one that scares you."

> **Read the explanation on screen.**

"The system says don't send anyone. The reason is in the hour *before*: it recorded
almost no electricity at all, which is impossible for a lighting circuit that was
on. The missing usage got bundled into the next reading. This is the meter failing
and catching up — not the lights."

"Meter dropout, eighty-eight percent — the highest confidence it gives anything in
our test set. Action: dismiss. That's a three-hundred-dollar technician visit it
just didn't spend."

---

## 4 · It fails — ANO-2009 — 0:30

> **Open ANO-2009** (Compressor Bank, FAC-002, Monday 27 July, 20:00).

"And now one it gets wrong, because you should see this too."

"Compressor Bank, eight in the evening. Ninety-eight kilowatt-hours against
eighty-five — only fifteen percent above baseline, but it holds there for **eight
hours** while the outside air cools off."

"It calls that a compressor fault at seventy-eight percent and sends a technician.
It was a **peak throughput day** — the warehouse was simply busy."

"And this is not a prompt we can fix. Shift schedules aren't an input this product
receives. On kilowatt-hours alone, a busy shift and a stuck compressor look the
same. We say so in the presentation."

---

## 5 · The guardrails — 0:25

> **Settings → Import Meter Data → upload `sample_bad_export.csv`.**

"Two things protect the numbers you just saw. First, every import is checked against
the existing database. This file is in watts instead of kilowatts and carries a
sub-system code that doesn't exist `[read the findings]`. Without that check you get
a perfectly plausible dashboard where every classification behind it is meaningless
— and it shows up in no accuracy metric, because the labels still match."

> **Back to any case → expand "None of these fit."** Type a short reason, record it.

"Second — three actions can't cover everything. When none of them fit, the manager
records an exception in their own words instead of picking the closest wrong one.
Those notes are the best evidence we get about what our fourteen-cause taxonomy is
missing."

---

## Closing line (optional, 0:05)

"That's the product. The next three slides are how we tested it, and what it can't do."

---

## If a number on screen differs from this script

Read what's on the screen, not what's written here. The classifications are
regenerated by `classifier.py`, and confidence can move by ~0.04 between runs —
class, subtype and action have been stable across three runs, but the decimals move.
Re-record the segment rather than talking over a mismatch.
