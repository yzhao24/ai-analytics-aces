"""
Group Assignment 2 — Evaluation & Measurement, as a Word document.

    python3 build_assignment2_docx.py

Keeps the team's numbered specification structure for Part A and adds Parts
B-D. Every figure comes from score_rubric.py, stability_test.py and
usability_test.py -- re-run those first if the classifier or dataset changed.

Hard constraint: 5 pages including appendices. Check with pagecount.py after
any edit; the layout is already tight, so new prose has to displace old.
"""

import json
from pathlib import Path

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

HERE = Path(__file__).parent
OUT = HERE.parent / "Group_Assignment_2.docx"

GREEN = RGBColor(0x1A, 0x7F, 0x37)
RED = RGBColor(0xB3, 0x26, 0x1E)
AMBER = RGBColor(0x8A, 0x6D, 0x00)
GREY = RGBColor(0x55, 0x55, 0x55)
BLACK = RGBColor(0x1A, 0x1A, 0x1A)

BODY = 9.0
TBL = 7.5
B = {"b": True}
I = {"i": True}
G = {"c": GREY, "size": 8.0}
GB = {"c": GREY, "size": 8.0, "b": True}
GI = {"c": GREY, "size": 8.0, "i": True}


# ── helpers ──────────────────────────────────────────────────────────────────
def shade(cell, hexfill):
    cell._tc.get_or_add_tcPr().append(docx.oxml.parse_xml(
        r'<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/'
        r'2006/main" w:val="clear" w:color="auto" w:fill="{}"/>'.format(hexfill)))


def runs(p, parts, size):
    if isinstance(parts, str):
        parts = [(parts, {})]
    for text, opt in parts:
        r = p.add_run(text)
        r.font.size = Pt(opt.get("size", size))
        r.bold = opt.get("b", False)
        r.italic = opt.get("i", False)
        if opt.get("c"):
            r.font.color.rgb = opt["c"]
        if opt.get("mono"):
            r.font.name = "Consolas"
    return p


def para(doc, parts, size=BODY, after=3.5, before=0):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.line_spacing = 1.0
    return runs(p, parts, size)


def head(doc, text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(7 if level == 1 else 5)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(11 if level == 1 else 9.5)
    r.font.color.rgb = BLACK


def bullet(doc, parts, size=BODY):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.left_indent = Inches(0.2)
    p.paragraph_format.line_spacing = 1.0
    return runs(p, parts, size)


def table(doc, headers, rows, widths, center_from=99, highlight=(), size=TBL):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    t.autofit = False

    def fill(cell, content, w, bold=False, align=None, fillc=None):
        cell.width = Inches(w)
        if fillc:
            shade(cell, fillc)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        if align:
            p.alignment = align
        for text, opt in ([(content, {})] if isinstance(content, str) else content):
            r = p.add_run(text)
            r.font.size = Pt(opt.get("size", size))
            r.bold = opt.get("b", bold)
            r.italic = opt.get("i", False)
            if opt.get("c"):
                r.font.color.rgb = opt["c"]

    for i, h in enumerate(headers):
        fill(t.rows[0].cells[i], h, widths[i], True, WD_ALIGN_PARAGRAPH.CENTER, "E8E8E8")
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, c in enumerate(row):
            fill(cells[i], c, widths[i],
                 align=WD_ALIGN_PARAGRAPH.CENTER if i >= center_from else None,
                 fillc="FBEAEA" if ri in highlight else None)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)


# ═════════════════════════════════════════════════════════════════════════════
doc = docx.Document()
s = doc.sections[0]
s.page_width, s.page_height = Inches(8.5), Inches(11)
s.top_margin = s.bottom_margin = Inches(0.55)
s.left_margin = s.right_margin = Inches(0.6)
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(BODY)
normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")

para(doc, [("Group Assignment 2 — Evaluation & Measurement", {"b": True, "size": 13}),
           ("     Energy Anomaly Explainer · AI Analytics Aces · BUSN 43800", G)], after=5)

# ───────────────────────────── PART A ────────────────────────────────────────
head(doc, "5.1  Part A — The core task specification")
para(doc, [("The task. ", B),
           ("Given one spike the detector has already flagged, name its most likely cause and "
            "tell the operations manager what to do about it. One spike in, one record out. "
            "Detection, the significance test and the dispatch gate are separate components.", {})])

para(doc, [("2.1  Input. ", B),
           ("Hourly kWh consumption (smart meter or BMS export), via CSV upload in Settings. "
            "Outdoor temperature from a public weather API (Open-Meteo), fetched automatically — "
            "no sensor required. No sub-metering or new infrastructure. Every import is checked "
            "against the existing database before use — unit scale, negatives, runs of zeros, "
            "coverage gaps, unregistered sub-systems, and temperatures that read as Celsius in a "
            "Fahrenheit column. Findings are prompts to check, never rejections.", {})])

para(doc, [("2.2  Classification engine. ", B),
           ("Three top-level categories and 14 subtypes: ", {}),
           ("equipment fault", I),
           (" (7 — compressor fault, refrigerant leak, HVAC fan failure, filter blockage, "
            "lighting control fault, door seal failure, power surge), ", {}),
           ("operational variation", I),
           (" (4 — peak throughput, unscheduled overtime, weather-driven HVAC surge, temporary "
            "equipment rental), ", {}),
           ("data anomaly", I),
           (" (3 — meter dropout, sensor noise spike, communication error). Evidence given: the "
            "spike's peak, its baseline for that hour and temperature, the excess in kWh and as a "
            "multiple, duration, outdoor temperature, timestamp with weekday, the sub-system's "
            "name and type, the consumption curve ±3 hours, and the full catalogue.", {})])
para(doc, [("Deliberately withheld: ", B),
           ("the ground-truth label, every other anomaly, any previous classification, and the "
            "outcome of the significance test. Labels are opened only by the scoring script, "
            "after every prediction is written to disk — which is why the measured precision is "
            "not circular.", {})])

para(doc, [("2.3  Output. ", B),
           ("Seven fields, enforced by the API so a malformed record cannot be returned: "
            "top-level class; subtype; confidence as a genuine posterior rather than a default; "
            "a plain-English explanation for a non-technical reader; a recommended action "
            "(dispatch / monitor / dismiss); the manager's next step, grounded in this spike; and "
            "the symptom for the technician in an engineer's words, required when dispatching.",
            {})])
para(doc, [("When none of the three actions fit. ", B),
           ("A manager forced to pick the closest wrong one leaves no trace that the taxonomy "
            "failed, so every anomaly carries a fifth path: record an ", {}),
           ("exception", I),
           (" with a free-text reason. Those notes are the shortlist for what the catalogue is "
            "missing — both misclassifications in Part C would have surfaced there long before "
            "anyone scored a rubric.", {})])

para(doc, [("2.4  Response time. ", B),
           ("Bar: within 5 minutes of upload or query. ", {}),
           ("Measured: 10.0 s average, 17.8 s worst case.", B)])

head(doc, "3.  Performance specifications")
para(doc, [("3.1  Primary bar. ", B),
           ("Precision on the equipment fault class ≥ 75% — ", {}),
           ("measured 82%", {"b": True, "c": GREEN}),
           (" (9 TP, 2 FP). Recall ≥ 70% — ", {}),
           ("measured 100%", {"b": True, "c": GREEN}),
           (" (0 FN). Validated on a 14-case held-out synthetic test set. We planned 15 and "
            "report 14: one injected fault was never detected, and a case the detector does not "
            "surface cannot be classified.", {})])
para(doc, [("3.2  Secondary bar. ", B),
           ("Explanation quality, four yes/no points per output — names a cause, states the "
            "evidence, gives a specific next step, avoids jargon; all four required to pass. Two "
            "human raters score independently, blind to the label and to each other; splits go to "
            "a third reader. ", {}),
           ("An LLM pre-rating scores 13/14; human scoring is outstanding", B),
           (", and the judge is not authoritative until shown to agree with the readers it "
            "replaces.", {})])
para(doc, [("3.3  Failure condition. ", B),
           ("If precision on the equipment fault class falls below 60%, the product must be "
            "redesigned to require shift schedule data as a mandatory input. If fault vs. "
            "operational variation confusion persists while precision remains above 60%, the "
            "redesign is structural rather than input-side: detection and classification move "
            "from the sub-system to the facility, with the sub-system carried as an attribute, "
            "and the alert threshold is restated relative to each meter's own variability rather "
            "than in absolute kWh. Adding inputs is not a remedy for a confusion produced by the "
            "unit of analysis.", {})])
para(doc, [("Amended after testing. ", GB),
           ("The original prescribed shift schedule ", G), ("or", GI),
           (" outdoor temperature. Temperature was already mandatory before the trigger fired, "
            "and shift schedule was implemented and measured as blocked (Part C). The second limb "
            "has been triggered; this states what the remedy should be.", G)])

head(doc, "4.  User & deployment specifications")
para(doc, [("4.1  Target user. ", B),
           ("Operations managers at U.S. distribution centers ≥100,000 sq ft, assumed to lack the "
            "statistical background to interpret raw time-series data.", {})])
para(doc, [("4.2  Deployment context. ", B),
           ("Facilities need hourly smart meter or BMS data and at least 2 unexplained spikes a "
            "month in the historical record.", {})])
para(doc, [("4.3  Constraints. ", B),
           ("Must operate on hourly kWh readings already available to the manager, plus outdoor "
            "temperature from a public weather API. No new sensors, sub-metering, or "
            "infrastructure spend — any further input must be obtainable without installation or "
            "procurement. Must not require engineering consultation for the initial triage.", {})])
para(doc, [("Amended. ", GB),
           ("The original read “solely on hourly kWh readings”, which was never true of the "
            "build: temperature is carried on every reading, drives the agent's baseline, and "
            "appears in every prompt. Removing it disables the weather-adjusted baseline and the "
            "entire not-significant path. What actually binds is no capital expenditure and "
            "nothing to install.", G)])

head(doc, "5.  Data specifications")
para(doc, [("5.1  Dataset (synthetic). ", B),
           ("12 months hourly — 78,840 readings, 3 facilities, 9 sub-systems. ", {}),
           ("Outdoor temperature is real", B),
           (" (Open-Meteo ERA5 hourly observations for Chicago, Milwaukee, Indianapolis) and "
            "consumption is computed from it, so weather adjustment is tested rather than "
            "assumed. Two shifts, mixed dry and refrigerated storage, 40–60 kW base load, "
            "forklift charging bursts, 4-hour compressor cycles, stochastic variation. "
            "Reproducible from generate_dataset.py — the original workbook shipped without the "
            "script that made it.", {})])
para(doc, [("5.2  Injected anomaly classes. ", B),
           ("Anomalies are injected, then found by a real detector, so detected_at, spike_kwh and "
            "baseline_kwh are measured off the series rather than asserted; an injection the "
            "detector misses is reported as a detection miss instead of silently becoming a test "
            "case. Three strata: core (14 single-cause cases, the success bar), co-occurring, "
            "sub-threshold. One ground-truth source — the previous workbook carried two that "
            "disagreed, and its own documentation prescribed the one covering 4 of 15 cases.",
            {})])

head(doc, "6.  Integration specifications")
para(doc, [("AI explanation layer powered by ", {}),
           ("Claude Opus 5 (claude-opus-5)", B),
           (" via the Anthropic Messages API, output constrained by a JSON schema so a malformed "
            "record cannot be returned. Streamlit web application, four screens. A four-tool "
            "agent orchestrator runs when the Classification Panel opens: fetch readings, compute "
            "baseline, run significance test, fetch comparable events.", {})])

head(doc, "7.  Scope limitations")
para(doc, [("Validated at the classification level on synthetic data only; real-world validation "
            "needs field deployment with maintenance log access. ", {}),
           ("The detector raises 562 alarms across the year and only the 25 matching an injected "
            "anomaly reach the test set", {"c": RED}),
           (", so every case scored is a genuine planted event — precision measures label "
            "accuracy, never the harder question of telling a real event from a false alarm.",
            {})])

head(doc, "A good output and a bad one", 2)
table(doc, ["", "Good — ANO-2010", "Bad — ANO-2009"], [
    ["Did",
     "Midnight HVAC spike → Weather-Driven HVAC Surge, 0.72, dismiss. Correct.",
     "Eight-hour refrigeration spike → Compressor Fault, 0.78, dispatch. It was a Peak "
     "Throughput Day."],
    ["Why",
     "Reasoned from shape — the flagged hour sits below the hours before it, and the evening "
     "tails off as the air cools — and named the mechanism, not the magnitude.",
     "The reasoning is sound and the evidence is absent. A sustained overnight load that does not "
     "ease as it cools does look like a compressor fault when shift schedules are not an input."],
    ["Effect",
     "“Log this as expected warm-night cooling load on HVAC Unit 1… so the same midnight hour is "
     "not re-flagged.” Specific, and closes the loop.",
     "Sends a technician overnight to a healthy compressor bank. Confidently wrong is worse than "
     "uncertain: at 0.78 it clears the commit gate."],
], [0.45, 3.4, 3.35])

# ───────────────────────────── PART B ────────────────────────────────────────
head(doc, "5.2  Part B — The evaluation rubric")
para(doc, [("One output = one classified spike. ", B),
           ("Each criterion is scored on every case; a record passes only if it passes all five. "
            "Aggregates are rolled up from those per-case scores, never measured directly. Scored "
            "on the 14-case core stratum (9 equipment faults), classified by claude-opus-5.", {})])
table(doc, ["Criterion", "How it is judged", "Acceptable at", "Result"], [
    ["Correctness", "Right cause? Class and subtype each compared to the held-out label by exact "
     "match.", "Both exact",
     [("86% class", {"b": True, "c": RED}), ("  ", {}), ("50% subtype", {"b": True, "c": RED})]],
    ["Completeness", "All seven fields present and non-empty, with a symptom whenever the action "
     "is dispatch.", "All fields", [("14/14", {"b": True, "c": GREEN})]],
    ["Calibration", "Does confidence agree with correctness — commit (≥0.75) when right, hedge "
     "when wrong? A wrong label at ≥0.75 is an overclaim and fails the case outright.",
     "No overclaims; ≥80% agree",
     [("43%", {"b": True, "c": RED}), ("  ", {}), ("1 overclaim", {"b": True, "c": RED})]],
    ["Usability", "Could the manager act unaided? Four yes/no points (cause, evidence, specific "
     "next step, no jargon). Two human raters, blind.", "≥80% of cases",
     [("13/14 judge", {"b": True, "c": AMBER}), ("  ", {}),
      ("humans pending", {"b": True, "c": AMBER})]],
    ["Timeliness", "Wall clock from request to returned record, timed in the classifier.",
     "< 5 min", [("10.0 s avg", {"b": True, "c": GREEN}), ("  ", {}),
                 ("17.8 s max", {"b": True, "c": GREEN})]],
    [[("Precision", B)], "Share of predicted faults that are faults — rolled up from Correctness. "
     "9 TP, 2 FP.", "≥ 75%", [("82%", {"b": True, "c": GREEN})]],
    [[("Recall", B)], "Share of true faults caught; an abstention counts as a miss. 0 FN.",
     "≥ 70%", [("100%", {"b": True, "c": GREEN})]],
    [[("Decision value", B)], "Cost of following the tool vs. two fixed policies, at $300 a "
     "dispatch and $2,000 a missed fault, over all 25 anomalies.", "beat $7,500",
     [("$35,200", {"b": True, "c": RED})]],
], [0.85, 3.65, 1.15, 1.55], center_from=2, highlight=(0, 2, 3, 7))

head(doc, "Do we use a model to judge outputs?", 2)
para(doc, [("Four of the five criteria use no judge at all. ", B),
           ("Correctness is an exact string match against held-out labels; Completeness and "
            "Calibration are field and threshold checks; Timeliness reads a timer. Nothing there "
            "can drift, and the model is never both author and marker. ", {}),
           ("Usability is the exception, and we checked the judge rather than trusting it. ", B),
           ("The rating pack carries only the explanation, the action and the symptom — no class, "
            "no confidence, no ground truth — so a rater cannot be swayed by knowing which cases "
            "were right, and the instructions say they are scoring how it reads, not whether it "
            "is correct. An LLM judge scored 13/14, failing ANO-2008 on ", {}),
           ("names a cause", I),
           (" (“a mechanical problem in the air-handling side” is a category, not a mechanism). "
            "We do not quote that as the result: the script prints it as not authoritative and "
            "refuses to stand on it until human scores exist.", {})])

# ───────────────────────────── PART C ────────────────────────────────────────
head(doc, "5.3  Part C — The test set")
para(doc, [("14 cases. ", B),
           ("The core stratum of a 12-month generated dataset: 9 equipment faults, 3 operational "
            "variations, 2 data anomalies, across three facilities and all nine sub-systems. Two "
            "further strata — 5 co-occurring causes and 6 deliberately marginal spikes — are held "
            "out of the headline number. Results are the Result column above: Completeness, "
            "Timeliness, Precision and Recall pass; Correctness, Calibration and Decision value "
            "fail.", {})])

head(doc, "Every failure, and what it was", 2)
table(doc, ["Failure", "What went wrong", "Diagnosis"], [
    ["ANO-2009, ANO-2011",
     "Peak Throughput Day and Temporary Equipment Rental both read as equipment faults, at 0.78 "
     "and 0.72. Neither shift schedules nor rental logs are inputs the product receives, so no "
     "prompt can separate a busy shift from a stuck compressor on kWh alone.",
     [("Specification", B)]],
    ["5 of 14 cases",
     "Right top-level class, wrong subtype — e.g. Door Seal Failure read as Refrigerant Leak. "
     "Hourly kWh underdetermines which fault; two mechanisms with the same load signature are "
     "indistinguishable at this sampling rate.", [("Evidence", B)]],
    ["1 overclaim, 7 hedges",
     "Confidence averages 0.70 when right and 0.75 when wrong — miscalibrated, and inverted "
     "rather than merely noisy. A property of the model, not of our inputs.", [("Model", B)]],
    ["Decision value",
     "82% precision, 100% recall, and following the tool still costs 4.7× dispatching on "
     "everything. We asked “what is this spike?” when the decision needs “should I dispatch?”. A "
     "correct label at 0.72 still produces no dispatch.", [("Question", B)]],
], [0.95, 5.3, 0.95], center_from=2)

head(doc, "Are the specification failures reducible? We tested it", 2)
para(doc, [("Our failure condition names this confusion as the trigger to require shift schedule "
            "data. We implemented that remedy and a second one, and measured both. ", {}),
           ("Shift schedule — blocked, precision 82% → 64%.", {"b": True, "c": RED}),
           (" A day planned at 130% of normal adds 7–10 kWh to a sub-system; the alarm fires at "
            "20. A realistic busy day never reaches the detector, so any operational event large "
            "enough to alarm is larger than its own explanation — at which point “fault” is the "
            "correct read. ", {}),
           ("Sibling co-movement — net negative, recall 100% → 78%.", {"b": True, "c": AMBER}),
           (" A fault lifts one meter and site activity lifts every meter, so this fixed the Peak "
            "Throughput case and un-inverted calibration, but it cannot tell one shared cause "
            "from two simultaneous single-asset events, and a real refrigerant leak was read as "
            "operational.", {})])
para(doc, [("Neither dead end is about which variables the model receives. Both are about the "
            "unit of analysis — nine meters treated as nine independent problems, when "
            "operational variation is a facility-level phenomenon — and the alert threshold, set "
            "per sub-system in absolute kWh. Under the specification's own 167:1 "
            "miss-to-false-alarm ratio, trading recall for precision is the wrong direction, so "
            "neither was merged; both are preserved on branches with their measurements.", {})])

head(doc, "Where the $35,200 comes from", 2)
table(doc, ["Policy", "Sent", "Caught", "Dispatch spend", "Missed-fault exposure", "Total"], [
    ["Follow the tool", "4", "3 / 20", "$1,200", "17 × $2,000 = $34,000",
     [("$35,200", {"b": True, "c": RED})]],
    ["Dispatch on every spike", "25", "20 / 20", "$7,500", "none",
     [("$7,500", {"b": True, "c": GREEN})]],
    ["Dispatch on none", "0", "0 / 20", "$0", "20 × $2,000 = $40,000",
     [("$40,000", {"b": True, "c": RED})]],
], [1.3, 0.45, 0.65, 0.95, 1.5, 0.85], center_from=1, highlight=(0,))
para(doc, [("97% of the tool's cost is exposure, not spend. ", B),
           ("It disburses $1,200 and leaves $34,000 of faults uninvestigated. Two multipliers "
            "drive it: a miss costs 6.7× a dispatch, and 20 of these 25 anomalies are genuine "
            "faults. At an 80% base rate you would need near-certainty before ", {}),
           ("not", I),
           (" sending someone, and a 0.75 gate is nowhere near that. One modelling choice to "
            "state plainly: a ", {}),
           ("monitor", I),
           (" counts as a miss because nobody is dispatched — if monitoring reliably catches the "
            "fault later at reduced cost, the figure falls; we have no evidence either way, so we "
            "scored the conservative reading.", {})])
para(doc, [("The calibration failure is the one we did not anticipate, and it matters most. ", B),
           ("The 0.75 commit gate selects for errors: it admits the single overclaim while "
            "hedging seven correct calls. Only 4 of 25 spikes clear it, so 17 of 20 real faults "
            "are told to “monitor” and nobody is dispatched. A rubric that stopped at precision "
            "and recall would have reported success.", {})])

# ───────────────────────────── PART D ────────────────────────────────────────
head(doc, "5.4  Part D — The measurement layer")
para(doc, [("The construct. ", B),
           ("The cause of a flagged spike — a latent categorical variable taking one of 14 values "
            "in three families — together with ", {}),
           ("confidence", B),
           (", a claimed posterior that the assigned cause is correct. The conversion is from a "
            "7-hour window of hourly kWh plus temperature and timing into that pair. Confidence "
            "is the more demanding claim: a category can be checked against a label, whereas a "
            "probability is only meaningful if calibrated — which is why Calibration is scored "
            "separately rather than folded into Correctness.", {})])
table(doc, ["Input signal", "→ Construct", "Correct?"], [
    ["HVAC Unit 1, midnight, 21.4 kWh above a 38.4 baseline, 76°F, one hour; the flagged hour "
     "sits below the three before it and the evening tails off.",
     "operational_variation / Weather-Driven HVAC Surge, 0.72, dismiss",
     [("Yes", {"b": True, "c": GREEN})]],
    ["Compressor Bank, 20:00, roughly double normal draw held for eight hours without settling, "
     "outside air cooling.", "equipment_fault / Compressor Fault, 0.78, dispatch",
     [("No — was Peak Throughput", {"b": True, "c": RED})]],
    ["HVAC Unit 2, 14:00, 116.8 kWh above baseline for one hour, ~6× normal draw, neighbours "
     "unremarkable.", "data_anomaly / Sensor Noise Spike, 0.78, dismiss",
     [("Yes", {"b": True, "c": GREEN})]],
], [3.3, 2.3, 1.6], center_from=2)

para(doc, [("Error. ", B),
           ("Against held-out labels the top-level class is right on 12 of 14 and the subtype on "
            "7 of 14 — the family of cause is measured reasonably well, the specific mechanism is "
            "close to a coin flip. Confidence is worse than uninformative: 0.70 when right, 0.75 "
            "when wrong, so it runs against correctness. We know this because the labels came "
            "from a documented injection process and were opened only after every prediction was "
            "written.", {})])
para(doc, [("Stability. ", B),
           ("Across three runs on the same inputs, the class, subtype and recommended action were "
            "identical on all 14 cases; only confidence moved, by 0.041 on average and 0.10 at "
            "worst. The measure is reproducible — its errors are systematic rather than random, "
            "so they will not average out over more cases and cannot be fixed by sampling more.",
            {})])
para(doc, [("Bias. ", B),
           ("Facility (75–80%), system type (75–83%) and season (75–83% ) are flat within the "
            "noise of a 14-case set. ", {}),
           ("The bias is in the true class:", B),
           (" equipment faults 8/9 (89%), data anomalies 2/2 (100%), operational variation ", {}),
           ("1/3 (33%)", B),
           (". The measure resolves ambiguity toward “fault”. Given a miss costs far more than a "
            "needless visit that is the safer direction to err, but it is not free — it is the "
            "same asymmetry that produces the two specification failures above, and it means any "
            "deployment will over-report faults during peak season.", {})])
para(doc, [("Where the inputs come from. ", B),
           ("Consumption is generated by a documented model (base load, shift ramps, compressor "
            "cycles, forklift charging, weather response, noise); temperature is real hourly "
            "Open-Meteo data, and consumption is computed from it. Anomalies are injected and "
            "then found by a detector, so spike magnitude and baseline are measured from the "
            "series rather than asserted.", {})])
para(doc, [("Protecting the measure from a bad feed. ", B),
           ("Every figure above assumes the inputs are what they claim to be. A file in watts "
            "rather than kilowatts, a meter that stopped reporting, or a sub-system code that "
            "does not exist all render a plausible dashboard while every classification behind it "
            "is meaningless — and none of it shows up in precision or recall, because the labels "
            "still match. Each import is profiled against the settled history and checked for "
            "unit scale, negatives, runs of zeros, out-of-range values, duplicate timestamps, "
            "coverage gaps, unregistered sub-systems, unreadable or future timestamps, and "
            "Celsius in a Fahrenheit column — that last needs a comparison against the range the "
            "database has actually seen, since 70°F becomes 21°C, which passes any "
            "plausible-range check.", {})])
para(doc, [("Why this does not fully identify what we need. ", B),
           ("Cause is only recoverable from consumption when the operational context that would "
            "explain it is absent. It is not: shift schedules, throughput and equipment rentals "
            "all move load, and none is an input. The two specification failures in Part C are "
            "that gap, measured.", {})])

# ───────────────────────────── APPENDICES ────────────────────────────────────
head(doc, "Appendix 1 — The prompt")
para(doc, [("System prompt, verbatim, sent unchanged on every case.", G)], after=2)
prompt = (HERE / "appendix_prompt.txt").read_text()
for block in prompt.split("\n\n"):
    if block.strip():
        para(doc, [(" ".join(block.split()), {"size": 6.5, "mono": True})], after=2.5)
para(doc, [("Schema (all required, no additional properties): top_level_class (enum: "
            "equipment_fault | operational_variation | data_anomaly) · classification_type_id · "
            "confidence_score (0–1) · explanation_text · recommended_action (enum: dispatch | "
            "monitor | dismiss) · next_action · symptom_to_check.",
            {"size": 6.5, "mono": True})])

head(doc, "Appendix 2 — Per-case scores, core stratum")
cases = json.loads((HERE / "appendix_cases.json").read_text())
table(doc, ["Case", "True", "Predicted", "Class", "Subtype", "Conf.", "Action", "Sec"],
      [[c if i < 3 else [(c, B)] for i, c in enumerate(row)] for row in cases],
      [0.5, 0.75, 0.85, 0.5, 0.6, 0.5, 0.75, 0.45], center_from=3, size=7,
      highlight=tuple(i for i, r in enumerate(cases) if r[3] == "N"))
para(doc, [("Reproduce every figure with python3 score_rubric.py, python3 stability_test.py "
            "--report-only, python3 usability_test.py --score.", G)], after=2)
para(doc, [("Honor Code. ", GB),
           ("We pledge our honor that we have not violated the Honor Code in preparation of this "
            "case assignment / group Project. ", G),
           ("AI-use disclosure. ", GB),
           ("Claude (Anthropic) is the classifier under evaluation and was also used to implement "
            "the remedies tested in Part C, to compute the measurements, and to draft this "
            "document. All criteria, thresholds, diagnoses and interpretations are the team's "
            "own; every figure is reproducible from the repository.", G)])

doc.save(OUT)
print("wrote", OUT)
