"""Render Group Assignment 2 — Evaluation & Measurement, all four parts.

    python build_assignment2.py

Every figure in the document comes from score_rubric.py, stability_test.py and
usability_test.py. Re-run those first if the classifier or the dataset has
changed, then re-quote whatever moved.
"""

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (HRFlowable, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

REPO = Path(__file__).parent
OUT = str(REPO.parent / "Group_Assignment_2_Evaluation_Measurement.pdf")
GREEN, RED, AMBER = "#1a7f37", "#b3261e", "#8a6d00"

b = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=b["Normal"], fontName="Times-Bold", fontSize=13.5, leading=15.5, spaceAfter=2)
SUB = ParagraphStyle("SUB", parent=b["Normal"], fontName="Times-Roman", fontSize=8.6, leading=10.5, textColor="#444444", spaceAfter=7)
H2 = ParagraphStyle("H2", parent=b["Normal"], fontName="Times-Bold", fontSize=11, leading=13, spaceBefore=11, spaceAfter=3)
H3 = ParagraphStyle("H3", parent=b["Normal"], fontName="Times-Bold", fontSize=9.4, leading=11.5, spaceBefore=7, spaceAfter=2)
BODY = ParagraphStyle("BODY", parent=b["Normal"], fontName="Times-Roman", fontSize=9.1, leading=11.4, alignment=TA_JUSTIFY, spaceAfter=4.5)
CELL = ParagraphStyle("CELL", parent=b["Normal"], fontName="Times-Roman", fontSize=8.0, leading=9.6)
CTR = ParagraphStyle("CTR", parent=CELL, fontName="Times-Bold", alignment=1)
HEAD = ParagraphStyle("HEAD", parent=CELL, fontName="Times-Bold", alignment=1)
MONO = ParagraphStyle("MONO", parent=b["Normal"], fontName="Courier", fontSize=6.9, leading=8.4, spaceAfter=3)
NOTE = ParagraphStyle("NOTE", parent=BODY, fontSize=7.9, leading=9.6, textColor="#444444")

doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=0.7*inch, rightMargin=0.7*inch,
                        topMargin=0.58*inch, bottomMargin=0.5*inch,
                        title="Group Assignment 2 — Evaluation & Measurement",
                        author="AI Analytics Aces")
S = []
P = lambda t, s=BODY: S.append(Paragraph(t, s))


def table(data, widths, highlight=(), size=8.0):
    t = Table(data, colWidths=widths, repeatRows=1)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
          ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
          ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    for r in highlight:
        st.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#fbeaea")))
    t.setStyle(TableStyle(st))
    return t


def hdr(cols):
    return [Paragraph(c, HEAD) for c in cols]


P("Group Assignment 2 — Evaluation &amp; Measurement", H1)
P("Energy Anomaly Explainer · AI Analytics Aces · BUSN 43800 · University of Chicago Booth", SUB)

# ───────────────────────────── PART A ─────────────────────────────
P("Part A — The core task specification", H2)

P("<b>The task.</b> Given one spike the detector has already flagged, name its most likely cause "
  "and tell the operations manager what to do about it. One spike in, one record out. Detection, "
  "the statistical significance test, and the dispatch gate are separate components and are not "
  "part of this task.")

P("<b>What the model is given.</b> The spike's peak and its baseline for that hour and "
  "temperature, the excess in kWh and as a multiple, duration, outdoor temperature at detection, "
  "the timestamp with weekday, the sub-system's name and type, the consumption curve for three "
  "hours either side of the spike, and the complete 14-item classification catalogue with each "
  "entry's applicable system type and standing action.")

P("<b>What it is deliberately not given.</b> The ground-truth label, any other anomaly, any "
  "previous classification, and the outcome of the statistical test. The candidate catalogue is "
  "identical on every case, so no case carries a hint about its own answer. This is why the "
  "measured precision is not circular: the held-out labels are opened only by the scoring "
  "script, after every prediction is written to disk.")

P("<b>Constraints.</b> Exactly one of the 14 subtypes. The recommended action must match the "
  "standing action the catalogue gives that subtype, so the manager is never told to dispatch on "
  "something the catalogue treats as routine. Confidence must be a genuine posterior rather than "
  "a default. A technician symptom is required when dispatching and must be empty otherwise. The "
  "explanation is written for a non-technical reader and may not restate the input numbers.")

P("<b>The output is seven fields</b>, enforced by the API so a malformed record cannot be "
  "returned: top-level class, subtype, confidence, explanation, recommended action, the manager's "
  "next step, and the technician symptom. Three of these — action, next step and symptom — were "
  "added after the first build, when the recommendation was still a string template in the "
  "dashboard that could not reference the spike it described.")

P("<b>What the product does when the task fails.</b> Three actions cannot cover every spike, and "
  "a manager forced to pick the closest wrong one leaves no trace that the taxonomy failed. Every "
  "anomaly therefore carries a fifth path: record an <i>exception</i> with a free-text reason. "
  "Those notes are the shortlist for what the catalogue is missing, and both misclassifications "
  "in Part C would have surfaced through it long before anyone scored a rubric.")

P("A good output and a bad one", H3)
rows = [hdr(["", "Good — ANO-2010", "Bad — ANO-2009"])]
rows.append([
    Paragraph("<b>What it did</b>", CELL),
    Paragraph("Called a midnight HVAC spike <i>Weather-Driven HVAC Surge</i> at 0.72, "
              "action <b>dismiss</b>. Correct.", CELL),
    Paragraph("Called an eight-hour refrigeration spike <i>Compressor Fault</i> at 0.78, "
              "action <b>dispatch</b>. It was a Peak Throughput Day.", CELL)])
rows.append([
    Paragraph("<b>Why</b>", CELL),
    Paragraph("Reasoned from the shape — the flagged hour sits <i>below</i> the hours before it "
              "and the evening tails off as the air cools — and named the mechanism rather than "
              "the magnitude.", CELL),
    Paragraph("The reasoning is sound and the evidence is absent. A sustained overnight load that "
              "does not ease as it cools really does look like a compressor fault when shift "
              "schedules are not an input.", CELL)])
rows.append([
    Paragraph("<b>Next step</b>", CELL),
    Paragraph("“Log this as expected warm-night cooling load on HVAC Unit 1… so the same midnight "
              "hour is not re-flagged next month.” Specific, and closes the loop.", CELL),
    Paragraph("Sends a technician overnight to a healthy compressor bank. Confidently wrong is "
              "worse than uncertain: at 0.78 it clears the commit gate.", CELL)])
S.append(table(rows, [0.68*inch, 3.16*inch, 3.16*inch], highlight=()))
P("Full prompt text in Appendix 1. The renderer is <font face='Courier'>build_prompt()</font> in "
  "<font face='Courier'>classifier.py</font>.", NOTE)

# ───────────────────────────── PART B ─────────────────────────────
P("Part B — The evaluation rubric", H2)
P("<b>One output = one classified spike.</b> Each of the five criteria is scored on every case; "
  "a record passes only if it passes all five. Aggregates are rolled up from those per-case "
  "scores, never measured directly.")

rows = [hdr(["Criterion", "How it is judged", "Acceptable at", "Result"])]
for c, how, ok, res, col in [
    ("Correctness", "Right cause? Top-level class and subtype each compared to the held-out "
     "label by exact match.", "Both exact", "86% class<br/>50% subtype", RED),
    ("Completeness", "All seven fields present and non-empty, with a symptom whenever the action "
     "is dispatch.", "All fields", "14/14", GREEN),
    ("Calibration", "Commit (≥0.75) when right, hedge (&lt;0.75) when wrong. A wrong label at "
     "≥0.75 is an overclaim and fails the case outright.", "No overclaims;<br/>≥80% agree",
     "43%<br/>1 overclaim", RED),
    ("Usability", "Could the manager act unaided? Four yes/no points — names a cause, states the "
     "evidence, gives a specific next step, avoids jargon. Two human raters, blind.",
     "≥80% of cases", "13/14 judge<br/>humans pending", AMBER),
    ("Timeliness", "Wall clock from request to returned record, timed in the classifier.",
     "&lt; 5 min", "10.0 s avg<br/>17.8 s max", GREEN),
]:
    rows.append([Paragraph(f"<b>{c}</b>", CELL), Paragraph(how, CELL), Paragraph(ok, CELL),
                 Paragraph(f'<font color="{col}"><b>{res}</b></font>', CTR)])
S.append(table(rows, [0.8*inch, 3.3*inch, 1.05*inch, 0.95*inch], highlight=(1, 3, 4)))

rows = [hdr(["Aggregate", "How it is derived", "Acceptable at", "Result"])]
for a, how, ok, res, col in [
    ("Precision, equipment fault", "Share of predicted faults that are faults. 9 TP, 2 FP.",
     "≥ 75%", "82%", GREEN),
    ("Recall, equipment fault", "Share of true faults caught; abstention counts as a miss. 0 FN.",
     "≥ 70%", "100%", GREEN),
    ("Decision value", "Cost of following the tool vs. two fixed policies at $300 a dispatch and "
     "$2,000 a missed fault, over all 25 anomalies.", "beat $7,500", "$35,200", RED),
]:
    rows.append([Paragraph(a, CELL), Paragraph(how, CELL), Paragraph(ok, CELL),
                 Paragraph(f'<font color="{col}"><b>{res}</b></font>', CTR)])
S.append(table(rows, [1.3*inch, 2.8*inch, 1.05*inch, 0.95*inch], highlight=(3,)))

P("<b>Do we use a model to judge?</b> Four of the five criteria use no judge at all — Correctness "
  "is an exact string match against held-out labels, Completeness and Calibration are field and "
  "threshold checks, Timeliness reads a timer. Nothing in that path can drift and the model is "
  "never both author and marker.")

P("<b>Usability is the exception, and we have checked the judge rather than trusted it.</b> Two "
  "human raters score it independently, blind to the label and to each other; "
  "<font face='Courier'>usability_cases.md</font> carries only the explanation, the action and the "
  "symptom, so a rater cannot be swayed by knowing which cases were right, and the instructions "
  "say plainly that they are scoring how it reads and not whether it is correct. Raw agreement is "
  "reported per point and splits go to a third reader.")

P("An LLM judge scored the same 14 cases at <b>13/14</b>, failing ANO-2008 on <i>names a cause</i> "
  "— “a mechanical problem in the air-handling side” is a category, not a mechanism. We are not "
  "quoting that as the result. The scoring script prints it as not authoritative and refuses to "
  "stand on it until human scores exist, because a judge is usable only once it has been shown to "
  "agree with the readers it replaces. The human pass is the number that counts and it is still "
  "outstanding.")

# ───────────────────────────── PART C ─────────────────────────────
P("Part C — The test set", H2)
P("<b>14 cases.</b> The core stratum of a 12-month generated dataset: 9 equipment faults, 3 "
  "operational variations, 2 data anomalies, spanning three facilities and all nine sub-systems. "
  "We planned 15 and report 14 — one injected fault was never detected, and a case the detector "
  "does not surface cannot be classified. Counting it would flatter the classifier by hiding a "
  "detection failure inside a classification score. Two further strata (5 co-occurring causes, 6 "
  "deliberately marginal spikes) are held out of the headline number and reported separately.")

P("Results", H3)
rows = [hdr(["Criterion", "Result", "Verdict"])]
for c, r, v, col in [("Correctness — class", "12 / 14 (86%)", "FAIL", RED),
                     ("Correctness — subtype", "7 / 14 (50%)", "FAIL", RED),
                     ("Completeness", "14 / 14", "PASS", GREEN),
                     ("Calibration", "43%, 1 overclaim", "FAIL", RED),
                     ("Timeliness", "10.0 s avg", "PASS", GREEN),
                     ("Precision / Recall", "82% / 100%", "PASS", GREEN),
                     ("Decision value", "$35,200 vs $7,500", "FAIL", RED)]:
    rows.append([Paragraph(c, CELL), Paragraph(r, CTR),
                 Paragraph(f'<font color="{col}"><b>{v}</b></font>', CTR)])
S.append(table(rows, [2.0*inch, 1.4*inch, 0.8*inch], highlight=(1, 2, 4, 7)))

P("Every failure, and what it was", H3)
rows = [hdr(["Failure", "What went wrong", "Diagnosis"])]
for f, w, dg, why in [
    ("ANO-2009, ANO-2011", "Peak Throughput Day and Temporary Equipment Rental both read as "
     "equipment faults, at 0.78 and 0.72.", "Specification",
     "Neither shift schedules nor rental logs are inputs the product receives. No prompt can "
     "separate a busy shift from a stuck compressor on kWh alone."),
    ("5 of 14 cases", "Right top-level class, wrong subtype — e.g. Door Seal Failure read as "
     "Refrigerant Leak.", "Evidence",
     "Hourly kWh underdetermines which fault. Two mechanisms with the same load signature are "
     "indistinguishable at this sampling rate."),
    ("1 overclaim, 7 hedges", "Confidence averages 0.70 when right and 0.75 when wrong.", "Model",
     "The model's confidence is miscalibrated, and inverted rather than merely noisy. This is a "
     "property of the model, not of our inputs."),
    ("Decision value", "82% precision and 100% recall, and following the tool still costs 4.7× "
     "dispatching on everything.", "Question",
     "We asked “what is this spike?” when the decision needs “should I dispatch?”. A correct "
     "label at 0.72 still produces no dispatch."),
]:
    rows.append([Paragraph(f"<b>{f}</b>", CELL), Paragraph(w, CELL),
                 Paragraph(f'<b>{dg}</b>', CTR)])
    rows.append([Paragraph("", CELL), Paragraph(f"<i>{why}</i>", CELL), Paragraph("", CELL)])
S.append(table(rows, [1.15*inch, 4.15*inch, 0.9*inch]))

P("<b>The specification failures are the ones our own Assignment 1 anticipated</b>, and we have "
  "now tested whether they are reducible. Our failure condition names confusion between fault and "
  "operational variation as the trigger to require shift schedule data. We implemented that "
  "remedy and a second one, and measured both.")

rows = [hdr(["Remedy", "Result", "Why"])]
rows.append([Paragraph("<b>Shift schedule</b><br/><i>the prescribed remedy</i>", CELL),
             Paragraph(f'<font color="{RED}"><b>Blocked</b></font><br/>precision 82% → 64%', CTR),
             Paragraph("A day planned at 130% of normal adds 7–10 kWh to a sub-system; the alarm "
                       "fires at 20. A realistic busy day never reaches the detector, so any "
                       "operational event large enough to alarm is larger than its own "
                       "explanation — at which point “fault” is the correct read.", CELL)])
rows.append([Paragraph("<b>Sibling co-movement</b><br/><i>needs no new input</i>", CELL),
             Paragraph(f'<font color="{AMBER}"><b>Net negative</b></font><br/>recall 100% → 78%', CTR),
             Paragraph("A fault lifts one meter and site activity lifts every meter, so this "
                       "fixed the Peak Throughput case and un-inverted calibration. But it cannot "
                       "tell one shared cause from two simultaneous single-asset events, and a "
                       "real refrigerant leak was read as operational.", CELL)])
S.append(table(rows, [1.3*inch, 1.35*inch, 4.35*inch]))

P("Neither dead end is about which variables the model receives. Both are about the <b>unit of "
  "analysis</b> — nine meters treated as nine independent problems, when operational variation is "
  "a facility-level phenomenon — and the <b>alert threshold</b>, set per sub-system in absolute "
  "kWh. Under the specification's own 167:1 miss-to-false-alarm ratio, trading recall for "
  "precision is the wrong direction, so neither was merged. Both are preserved on branches with "
  "their measurements.")

P("<b>The calibration failure is the one we did not anticipate, and it matters most.</b> The 0.75 "
  "commit gate selects for errors: it admits the single overclaim while hedging seven correct "
  "calls. Only 4 of 25 spikes clear it, so 17 of 20 real faults are told to “monitor” and nobody "
  "is dispatched. A rubric that stopped at precision and recall would have reported success.")

P("Where the $35,200 comes from", H3)
rows = [hdr(["Policy", "Dispatched", "Faults caught", "Dispatch spend", "Missed-fault exposure", "Total"])]
for pol, sent, caught, spend, exposure, tot, col in [
    ("Follow the tool", "4", "3 / 20", "$1,200", "17 × $2,000 = $34,000", "$35,200", RED),
    ("Dispatch on every spike", "25", "20 / 20", "$7,500", "none", "$7,500", GREEN),
    ("Dispatch on none", "0", "0 / 20", "$0", "20 × $2,000 = $40,000", "$40,000", RED),
]:
    rows.append([Paragraph(pol, CELL), Paragraph(sent, CTR), Paragraph(caught, CTR),
                 Paragraph(spend, CTR), Paragraph(exposure, CTR),
                 Paragraph(f'<font color="{col}"><b>{tot}</b></font>', CTR)])
S.append(table(rows, [1.5*inch, 0.75*inch, 0.9*inch, 1.0*inch, 1.55*inch, 0.8*inch], highlight=(1,)))

P("<b>97% of the tool's cost is exposure, not spend.</b> It disburses $1,200 and leaves $34,000 "
  "of faults uninvestigated. Two multipliers drive it: a miss costs 6.7× a dispatch, and 20 of "
  "these 25 anomalies are genuine faults. At an 80% base rate you would need to be almost certain "
  "before <i>not</i> sending someone, and a gate set at 0.75 confidence is nowhere near that.")

P("One modelling choice to state plainly: a <i>monitor</i> counts as a miss, because nobody is "
  "dispatched. If monitoring reliably catches the fault later at reduced cost, the figure falls. "
  "We have no evidence either way, so we scored the conservative reading.")

# ───────────────────────────── PART D ─────────────────────────────
P("Part D — The measurement layer", H2)
P("Our inputs are numeric, not unstructured text, so this part covers both what the assignment "
  "asks of a measurement layer and where our inputs come from.")

P("The construct", H3)
P("<b>The cause of a flagged spike</b> — a latent categorical variable taking one of 14 values in "
  "three families, together with <b>confidence</b>, a claimed posterior probability that the "
  "assigned cause is correct. The conversion is from a 7-hour window of hourly kWh plus "
  "temperature and timing into that pair. Confidence is the more demanding claim: a category can "
  "be checked against a label, whereas a probability claim is only meaningful if it is calibrated, "
  "which is why Calibration is scored as its own criterion rather than folded into Correctness.")

P("Worked examples", H3)
rows = [hdr(["Input signal", "→ Construct", "Correct?"])]
for sig, con, ok, col in [
    ("HVAC Unit 1, midnight, 21.4 kWh above a 38.4 baseline, 76°F, one hour; the flagged hour sits "
     "below the three hours before it and the evening tails off.",
     "operational_variation / Weather-Driven HVAC Surge, 0.72, dismiss", "Yes", GREEN),
    ("Compressor Bank, 20:00, roughly double normal draw held for eight hours without settling, "
     "outside air cooling.",
     "equipment_fault / Compressor Fault, 0.78, dispatch", "No — was a<br/>Peak Throughput Day", RED),
    ("HVAC Unit 2, 14:00, 116.8 kWh above baseline for a single hour, ~6× the unit's normal draw, "
     "neighbours unremarkable.",
     "data_anomaly / Sensor Noise Spike, 0.78, dismiss", "Yes", GREEN),
]:
    rows.append([Paragraph(sig, CELL), Paragraph(con, CELL),
                 Paragraph(f'<font color="{col}"><b>{ok}</b></font>', CTR)])
S.append(table(rows, [3.1*inch, 2.05*inch, 1.05*inch]))

P("Error — where the measure is wrong, and how we know", H3)
P("Against held-out labels the top-level class is right on 12 of 14 and the subtype on 7 of 14. "
  "So the family of cause is measured reasonably well and the specific mechanism is close to a "
  "coin flip. Confidence is worse than uninformative: it averages 0.70 when the label is right "
  "and 0.75 when it is wrong, so it runs against correctness. We know this because the labels were "
  "generated by a documented injection process and opened only after every prediction was written.")

P("Stability — same input, three runs", H3)
P("The top-level class, the subtype and the recommended action were <b>identical on all 14 cases "
  "across all three runs</b>. Only confidence moved, by 0.041 on average and 0.10 at worst. The "
  "measure is reproducible; its errors are systematic rather than random, which means they will "
  "not average out over more cases and cannot be fixed by sampling more.")

P("Bias", H3)
rows = [hdr(["Group", "Accuracy", "Group", "Accuracy"])]
for a, b_, c, d_ in [("Chicago South DC", "4/5 = 80%", "HVAC", "5/6 = 83%"),
                     ("Indianapolis East", "3/4 = 75%", "Lighting", "3/4 = 75%"),
                     ("Milwaukee Central", "4/5 = 80%", "Refrigeration", "3/4 = 75%"),
                     ("Warm months", "6/8 = 75%", "Cold months", "5/6 = 83%")]:
    rows.append([Paragraph(a, CELL), Paragraph(b_, CTR), Paragraph(c, CELL), Paragraph(d_, CTR)])
S.append(table(rows, [1.55*inch, 1.05*inch, 1.55*inch, 1.05*inch]))
P("Facility, system type and season are flat within the noise of a 14-case set. <b>The bias is in "
  "the true class:</b> equipment faults 8/9 (89%), data anomalies 2/2 (100%), operational "
  "variation <b>1/3 (33%)</b>. The measure resolves ambiguity toward “fault”. Given a miss costs "
  "far more than a needless visit that is the safer direction to err, but it is not free — it is "
  "the same asymmetry that produces the two specification failures in Part C, and it means any "
  "deployment will over-report faults during peak season.")

P("Where the inputs come from", H3)
P("Hourly consumption is generated by a documented model (base load, shift ramps, four-hour "
  "compressor cycles, forklift charging, weather response, stochastic noise) in "
  "<font face='Courier'>generate_dataset.py</font>. <b>Outdoor temperature is real</b> — hourly "
  "observations for Chicago, Milwaukee and Indianapolis from the Open-Meteo archive — and "
  "consumption is computed from it, so weather adjustment is tested rather than assumed. "
  "Anomalies are injected and then found by a detector, so the recorded spike magnitude and "
  "baseline are measured from the series rather than asserted.")
P("Protecting the measure from a bad feed", H3)
P("Every figure above assumes the inputs are what they claim to be. A file in watts rather than "
  "kilowatts, a meter that stopped reporting, or a sub-system code that does not exist all render "
  "a perfectly plausible dashboard while every classification behind it is meaningless — and none "
  "of it shows up in precision or recall, because the labels still match. "
  "<font face='Courier'>input_guard.py</font> profiles the settled history and tests new data "
  "against it: unit scale, negatives, runs of zeros, values beyond anything recorded, duplicate "
  "timestamps, coverage gaps, unregistered sub-systems, unreadable or future timestamps, and "
  "temperatures that read as Celsius in a Fahrenheit column. That last one needs a comparison "
  "against the range the database has actually seen — 70°F becomes 21°C, which passes any "
  "plausible-range check. Findings are prompts to check, never rejections.")

P("<b>Why this does not fully identify what we need.</b> The construct is the cause of a spike, "
  "and cause is only recoverable from consumption when the operational context that would explain "
  "it is absent. It is not: shift schedules, throughput and equipment rentals all move load and "
  "none is an input. The two Part C specification failures are that gap, measured.")

# ───────────────────────────── APPENDICES ─────────────────────────────
S.append(PageBreak())
P("Appendix 1 — The prompt", H2)
P("System prompt, verbatim (3,242 characters). Sent unchanged on every case.", NOTE)
sysp = __import__("sys"); sysp.path.insert(0, str(REPO))
import classifier as C
for para in C.SYSTEM_PROMPT.split("\n\n"):
    P(para.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", " "), MONO)

P("User prompt — the rendered case for ANO-2010", H3)
P("Truncated to the first rows of the consumption window and the first rows of the catalogue; "
  "the real prompt carries all seven hours and all 14 entries.", NOTE)
sample = """SPIKE
  Sub-system      : HVAC Unit 1 (hvac)
  Detected        : Friday 2026-07-17 00:00
  Baseline        : 38.4 kWh/hr for this hour and temperature
  Peak            : 59.8 kWh/hr  (1.6x baseline, +21.4 above)
  Duration        : 60 minutes
  Outdoor temp    : 76.4F

CONSUMPTION, 3 HOURS EITHER SIDE
  21:00     71.2 kWh   79.3F
  22:00     57.2 kWh   78.1F
  23:00     59.8 kWh   77.0F   <-- spike detected here
  00:00     55.7 kWh   76.4F
  ...

CANDIDATE CLASSIFICATIONS - choose exactly one classification_type_id
| id | top_level_class | label | applies to | typical action |
|---|---|---|---|---|
| CT-001 | equipment_fault | Compressor Fault | refrigeration | dispatch |
| CT-002 | equipment_fault | Refrigerant Leak | refrigeration | dispatch |
| ... 12 more rows ..."""
for line in sample.split("\n"):
    P(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(" ", "&nbsp;") or "&nbsp;", MONO)

P("Output schema — enforced by the API, so a malformed record cannot be returned", H3)
P("top_level_class (enum: equipment_fault | operational_variation | data_anomaly) · "
  "classification_type_id · confidence_score (0-1) · explanation_text · "
  "recommended_action (enum: dispatch | monitor | dismiss) · next_action · symptom_to_check. "
  "All seven required; no additional properties permitted.", MONO)

P("Appendix 2 — Per-case scores, core stratum", H2)
data = [["ANO-2000","CT-001","CT-001","Y","Y","0.78","dispatch","8.0"],
        ["ANO-2001","CT-002","CT-002","Y","Y","0.72","dispatch","7.8"],
        ["ANO-2002","CT-003","CT-003","Y","Y","0.55","dispatch","17.8"],
        ["ANO-2003","CT-004","CT-003","Y","N","0.82","dispatch","7.2"],
        ["ANO-2004","CT-005","CT-005","Y","Y","0.60","monitor","11.4"],
        ["ANO-2005","CT-006","CT-002","Y","N","0.58","dispatch","14.3"],
        ["ANO-2006","CT-007","CT-005","Y","N","0.52","monitor","14.5"],
        ["ANO-2007","CT-007","CT-005","Y","N","0.66","monitor","8.6"],
        ["ANO-2008","CT-004","CT-003","Y","N","0.79","dispatch","9.3"],
        ["ANO-2009","CT-008","CT-001","N","N","0.78","dispatch","9.1"],
        ["ANO-2010","CT-010","CT-010","Y","Y","0.72","dismiss","7.5"],
        ["ANO-2011","CT-011","CT-003","N","N","0.72","dispatch","9.0"],
        ["ANO-2012","CT-012","CT-012","Y","Y","0.88","dismiss","7.7"],
        ["ANO-2013","CT-013","CT-013","Y","Y","0.82","dismiss","8.1"]]
rows = [hdr(["Case", "True", "Predicted", "Class", "Subtype", "Conf.", "Action", "Sec"])]
bad = []
for i, r in enumerate(data, start=1):
    rows.append([Paragraph(v, CTR if j >= 3 else CELL) for j, v in enumerate(r)])
    if r[3] == "N":
        bad.append(i)
S.append(table(rows, [0.72*inch, 0.6*inch, 0.75*inch, 0.5*inch, 0.62*inch, 0.5*inch, 0.72*inch, 0.45*inch],
               highlight=tuple(bad)))
P("Reproduce every figure in this document with <font face='Courier'>python3 score_rubric.py</font> "
  "and <font face='Courier'>python3 stability_test.py --report-only</font>.", NOTE)

S.append(Spacer(1, 5))
S.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#999999"), spaceAfter=4))
P("<b>Honor Code.</b> We pledge our honor that we have not violated the Honor Code in preparation "
  "of this case assignment / group Project.", NOTE)
P("<b>AI-use disclosure.</b> Claude (Anthropic) is the classifier under evaluation, and was also "
  "used to draft this document and to compute the scores from our own code and data. All criteria, "
  "thresholds, diagnoses and interpretations are the team's own. Every figure is reproducible from "
  "the repository.", NOTE)

doc.build(S)
print("wrote", OUT)
