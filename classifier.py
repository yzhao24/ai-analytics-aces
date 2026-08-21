"""
AI classification layer — the Day 3 deliverable from the team specification.

Sends each detected spike to Claude with the spike's shape, weather context, and
timing, plus the full classification registry as the candidate list, and gets
back a structured classification with a confidence score and a plain-language
explanation.

Output is written to `classifications_llm.json`, which the dashboard picks up
automatically. Nothing is written back into the workbook — that file is binary
and git cannot merge it, so a single owner keeps it.

Credentials are read from the environment by the SDK. Either run
`ant auth login` once (stores an OAuth profile under ~/.config/anthropic/, no
static key on disk) or export ANTHROPIC_API_KEY. No key is stored in this repo.

Usage:
    python classifier.py                # classify all 15 spikes
    python classifier.py --only-missing # only spikes with no existing label
    python classifier.py --score        # classify, then score against ground truth
"""

import argparse
import json
import time
import sys
from pathlib import Path

import pandas as pd

import operations_log

DATA_FILE = Path(__file__).parent / "dummy_data_set2.xlsx"
OUT_FILE = Path(__file__).parent / "classifications_llm.json"

MODEL = "claude-opus-5"

# The classifier sees the spike and the candidate taxonomy — never the answer.
# `test_set_15_cases` holds the ground truth and is deliberately not loaded here;
# scoring reads it separately, after every prediction is already committed.
FORBIDDEN_SHEET = "test_set_15_cases"

SYSTEM_PROMPT = """You are a diagnostic layer for an energy operations dashboard \
at a US distribution centre. An hourly electricity spike has been detected on one \
metered sub-system. Classify its most likely cause.

You will be given the spike's magnitude relative to its own baseline, how long it \
lasted, the outdoor temperature at detection, the time of day and day of week, and \
the sub-system it occurred on. You will also be given the complete list of \
classifications you may choose from. Choose exactly one.

How to weigh the evidence:
- Equipment faults tend to show a rapid rise and a sustained plateau with no \
return to baseline, or a gradual climb over several hours. They are largely \
independent of shift boundaries.
- Operational variation tracks the business: peak throughput during day shift, \
extended hours past a shift boundary, or load that scales with outdoor \
temperature on a hot day. Weather-driven HVAC load at high temperatures is \
expected behaviour, not a fault.
- Data anomalies are physically implausible: readings many times the historical \
maximum, or a near-zero reading followed by a compensating spike. Magnitude alone \
is the tell — a spike far larger than the plant can physically draw is a metering \
artefact, not a bigger fault.

Telling a one-hour equipment fault from a one-hour metering artefact is the \
hardest call here, and shape alone will not do it. Ask whether the plant could \
physically draw that much. A lighting circuit or a surge pulling two or three \
times its normal load is electrically possible and is a fault. A meter reporting \
five or ten times what the sub-system could ever draw, or dropping to near zero \
and then repaying it in the next hour, is the instrument failing, not the plant. \
Sustained draw across several hours is almost never a metering artefact.

Set confidence_score to your genuine posterior, not a default. The cost of \
missing a real equipment fault is far higher than the cost of an unnecessary \
technician visit, so do not label something operational variation merely because \
it is plausible — reserve that for cases where the operational explanation is \
clearly better supported.

Then say what to do about it. recommended_action must match the typical action \
shown for the classification you picked, so the manager is never told to dispatch \
on something the catalogue treats as routine.

next_action is the instruction the manager acts on, and it must be specific to \
this spike rather than generic advice. Follow the shape of the decision:
- dispatch: name the trade to send and the first thing to look at.
- monitor: name what would confirm the fault if it recurs — which hour, which \
system, what magnitude — over the next 24 hours.
- dismiss: name the known event or artefact this is, and say what if anything to \
log so the same spike is not re-investigated next month.

symptom_to_check is what the technician is told they are looking for, in the \
words a refrigeration or HVAC engineer would use. Fill it only when dispatching; \
leave it empty otherwise.

explanation_text is read by a non-technical operations manager who must decide \
whether to dispatch. State what the pattern shows and what it implies, in two or \
three sentences. No jargon, no hedging, no restating the input numbers back."""

SCHEMA = {
    "type": "object",
    "properties": {
        "top_level_class": {
            "type": "string",
            "enum": ["equipment_fault", "operational_variation", "data_anomaly"],
        },
        "classification_type_id": {
            "type": "string",
            "description": "One classification_id from the candidate list, e.g. CT-001",
        },
        "confidence_score": {
            "type": "number",
            "description": "Posterior probability that this classification is correct, 0.0-1.0",
        },
        "explanation_text": {"type": "string"},
        "recommended_action": {
            "type": "string",
            "enum": ["dispatch", "monitor", "dismiss"],
            "description": "Must match the typical action for the chosen classification",
        },
        "next_action": {
            "type": "string",
            "description": "The specific instruction for the manager, one or two sentences",
        },
        "symptom_to_check": {
            "type": "string",
            "description": "For dispatch, the symptom to hand the technician. Empty otherwise.",
        },
    },
    "required": [
        "top_level_class",
        "classification_type_id",
        "confidence_score",
        "explanation_text",
        "recommended_action",
        "next_action",
        "symptom_to_check",
    ],
    "additionalProperties": False,
}


def org_hint():
    """Which account the SDK resolved, for error messages. Never prints a secret."""
    import subprocess

    try:
        out = subprocess.run(["ant", "auth", "status"], capture_output=True,
                             text=True, timeout=10).stdout
        for line in out.splitlines():
            if "Logged in to" in line:
                return line.strip()
    except Exception:
        pass
    return "unknown (ANTHROPIC_API_KEY, or `ant auth status` for details)"


def load_inputs():
    xl = pd.ExcelFile(DATA_FILE)
    sheets = {n: xl.parse(n) for n in xl.sheet_names if n != FORBIDDEN_SHEET}
    sheets["anomalies"]["detected_at"] = pd.to_datetime(sheets["anomalies"].detected_at)
    sheets["energy_readings"]["recorded_at"] = pd.to_datetime(
        sheets["energy_readings"].recorded_at
    )
    return sheets


def candidate_table(registry):
    """The taxonomy the model must choose from, as a compact markdown table."""
    lines = ["| id | top_level_class | label | applies to | typical action |",
             "|---|---|---|---|---|"]
    for r in registry.itertuples():
        label = r.subtype_label if pd.notna(r.subtype_label) else "—"
        lines.append(
            f"| {r.classification_id} | {r.top_level_class} | {label} "
            f"| {r.system_type} | {r.recommended_action} |"
        )
    return "\n".join(lines)


def spike_profile(readings, anomaly):
    """The ±3h shape around the spike — the model needs the curve, not just the peak."""
    meter = readings[
        (readings.facility_id == anomaly.facility_id)
        & (readings.system_id == anomaly.system_id)
    ]
    window = meter[
        meter.recorded_at.between(
            anomaly.detected_at - pd.Timedelta(hours=3),
            anomaly.detected_at + pd.Timedelta(hours=3),
        )
    ].sort_values("recorded_at")
    return "\n".join(
        f"  {r.recorded_at:%H:%M}  {r.kwh:7.1f} kWh  {r.temp_f:5.1f}F"
        + ("   <-- spike detected here" if r.recorded_at == anomaly.detected_at else "")
        for r in window.itertuples()
    )


def build_prompt(data, anomaly, system, declared=None):
    sys_name = system.system_name if system is not None else "unknown sub-system"
    sys_type = system.system_type if system is not None else "unknown"
    peak = anomaly.baseline_kwh + anomaly.spike_kwh
    multiple = peak / anomaly.baseline_kwh if anomaly.baseline_kwh else float("nan")

    return f"""SPIKE
  Sub-system      : {sys_name} ({sys_type})
  Detected        : {anomaly.detected_at:%A %Y-%m-%d %H:%M}
  Baseline        : {anomaly.baseline_kwh:.1f} kWh/hr for this hour and temperature
  Peak            : {peak:.1f} kWh/hr  ({multiple:.1f}x baseline, +{anomaly.spike_kwh:.1f} above)
  Duration        : {int(anomaly.duration_minutes)} minutes
  Outdoor temp    : {anomaly.temp_f_at_detection:.1f}F

CONSUMPTION, 3 HOURS EITHER SIDE
{spike_profile(data['energy_readings'], anomaly)}

{operations_log.as_prompt_evidence(declared or [])}

CANDIDATE CLASSIFICATIONS — choose exactly one classification_type_id
{candidate_table(data['classification_registry'])}"""


def classify_all(only_missing=False):
    try:
        import anthropic
    except ModuleNotFoundError:
        sys.exit("anthropic SDK not installed — run: pip install anthropic")

    NO_CREDS = (
        "\nNo usable credentials found.\n"
        "  Run once:  ant auth login       (stores an OAuth profile, no key on disk)\n"
        "  Or:        export ANTHROPIC_API_KEY=...\n"
        "Then re-run this script."
    )

    data = load_inputs()
    ops_log = operations_log.load()
    if ops_log:
        print(f"  {len(ops_log)} declared operation(s) will be offered as evidence")
    try:
        # Resolves, in order: ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, then the
        # active `ant auth login` profile. Nothing is read from this repo.
        client = anthropic.Anthropic()
        client.models.retrieve(MODEL)
    except (anthropic.AuthenticationError, TypeError):
        sys.exit(NO_CREDS)
    except anthropic.NotFoundError:
        sys.exit(f"\nModel {MODEL} not available on this account.")

    already = set(data["classifications"].anomaly_id)

    results = {}
    for anomaly in data["anomalies"].itertuples():
        if only_missing and anomaly.anomaly_id in already:
            continue

        sys_rows = data["system_registry"][
            data["system_registry"].system_id == anomaly.system_id
        ]
        system = sys_rows.iloc[0] if not sys_rows.empty else None

        declared = operations_log.covering(
            ops_log, anomaly.facility_id, anomaly.system_id,
            *operations_log.window_of(anomaly))

        print(f"  {anomaly.anomaly_id} …", end="", flush=True)
        t0 = time.monotonic()
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=8000,  # covers thinking + output; Opus 5 thinks by default
                system=SYSTEM_PROMPT,
                output_config={
                    "effort": "medium",
                    "format": {"type": "json_schema", "schema": SCHEMA},
                },
                messages=[
                    {"role": "user",
                     "content": build_prompt(data, anomaly, system, declared)}
                ],
            )
        except anthropic.AuthenticationError:
            sys.exit(NO_CREDS)
        except anthropic.BadRequestError as e:
            # Credentials can be perfectly valid on an org with no credits, and
            # the models endpoint answers fine, so this only surfaces here.
            if "credit balance" in str(e).lower():
                sys.exit(
                    "\nThe account is authenticated but has no API credits.\n"
                    "  Add credits at https://console.anthropic.com -> Plans & Billing,\n"
                    "  or re-run `ant auth login` and pick an organisation that has them.\n"
                    f"  Currently signed in to: {org_hint()}"
                )
            raise

        if resp.stop_reason == "refusal":
            print(" refused, skipped")
            continue

        text = next(b.text for b in resp.content if b.type == "text")
        out = json.loads(text)
        # Wall-clock per spike is the spec's "classification within 5 minutes"
        # criterion. It was unmeasurable while the labels were pre-written.
        out["latency_seconds"] = round(time.monotonic() - t0, 2)
        results[anomaly.anomaly_id] = out
        print(f" {out['classification_type_id']} {out['recommended_action'].upper():8} "
              f"({out['confidence_score']:.0%})  {out['latency_seconds']:.1f}s")

    OUT_FILE.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {len(results)} classifications -> {OUT_FILE.name}")
    return results


def score():
    """Precision/recall on the equipment-fault class, ground truth loaded only now."""
    if not OUT_FILE.exists():
        sys.exit(f"{OUT_FILE.name} not found — run the classifier first.")
    preds = json.loads(OUT_FILE.read_text())
    truth = pd.ExcelFile(DATA_FILE).parse(FORBIDDEN_SHEET)

    truth["pred"] = truth.anomaly_id.map(
        lambda a: preds.get(a, {}).get("top_level_class", "(abstained)")
    )
    is_fault = truth.true_top_level_class == "equipment_fault"
    said = truth.pred == "equipment_fault"
    tp, fp, fn = int((said & is_fault).sum()), int((said & ~is_fault).sum()), int((~said & is_fault).sum())
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")

    print(f"\n{'=' * 62}\nPRIMARY SUCCESS BAR — equipment_fault\n{'=' * 62}")
    print(f"  TP={tp}  FP={fp}  FN={fn}")
    print(f"  Precision = {precision:.1%}  (bar >=75%)  "
          f"{'PASS' if precision >= .75 else 'FAIL'}")
    print(f"  Recall    = {recall:.1%}  (bar >=70%)  "
          f"{'PASS' if recall >= .70 else 'FAIL'}")
    wrong = truth[truth.pred != truth.true_top_level_class]
    if not wrong.empty:
        print("\nDisagreements with ground truth:")
        print(wrong[["anomaly_id", "true_subtype_label", "true_top_level_class", "pred"]]
              .to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-missing", action="store_true",
                    help="skip spikes that already carry a label in the workbook")
    ap.add_argument("--score", action="store_true",
                    help="score against test_set_15_cases after classifying")
    args = ap.parse_args()

    classify_all(only_missing=args.only_missing)
    if args.score:
        score()
