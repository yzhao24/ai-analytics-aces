"""
Usability scoring for the Part B rubric.

"Could the manager act unaided?" is a claim about a reader, so the model cannot
be both author and marker. Two people score it independently, blind to the
ground-truth label and to each other, and we report raw agreement. This script
prepares their sheets and scores them back.

    python usability_test.py --sheets          # write two blank rating sheets
    python usability_test.py --score           # score whatever has been filled in
    python usability_test.py --judge           # optional LLM pre-rating, ~$0.30

The four points, all required for a case to pass:

  1. names a cause      — a specific mechanism, not "an anomaly was detected"
  2. states the evidence — what in the data supports it
  3. specific next step  — who does what, or what to watch for and when
  4. avoids jargon       — a non-technical manager can read it unaided

The LLM judge exists only to scale this later. A judge is usable only once it has
been shown to agree with the readers it replaces, so --score reports both and
their agreement whenever human sheets exist.
"""

import argparse
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
DATA_FILE = HERE / "dummy_data_set2.xlsx"
LLM_FILE = HERE / "classifications_llm.json"
JUDGE_FILE = HERE / "usability_judge.json"
RATERS = ["A", "B"]
POINTS = ["names_cause", "states_evidence", "specific_next_step", "avoids_jargon"]

RUBRIC = """Score each output on four yes/no points. Write 1 for yes, 0 for no.
A case passes only if all four are 1.

  names_cause         Does it name a specific mechanism (e.g. "compressor
                      short-cycling"), not just "an anomaly" or "high usage"?
  states_evidence     Does it say what in the data supports that — the shape,
                      the timing, the temperature, the magnitude?
  specific_next_step  Could you act on it without asking anyone? Names a trade,
                      a component, an hour to watch, or a thing to log.
  avoids_jargon       Could a non-technical operations manager read it unaided?
                      Undefined engineering terms in the manager-facing text
                      count as a failure; the technician symptom line is exempt.

You are scoring how it READS, not whether it is CORRECT. A confidently wrong
explanation that names a cause, cites evidence and gives a clear next step
scores 4. Do not look up the answer, and do not confer with the other rater."""


def load_cases():
    xl = pd.ExcelFile(DATA_FILE)
    truth = xl.parse("test_set_15_cases")
    core = truth[truth.stratum == "core"] if "stratum" in truth else truth
    preds = json.loads(LLM_FILE.read_text())
    return [(a, preds[a]) for a in core.anomaly_id if a in preds]


def write_sheets():
    cases = load_cases()
    for r in RATERS:
        path = HERE / f"usability_rater_{r}.csv"
        if path.exists():
            print(f"  {path.name} already exists — left alone")
            continue
        pd.DataFrame([{"case": a, **{p: "" for p in POINTS}, "comment": ""}
                      for a, _ in cases]).to_csv(path, index=False)
        print(f"  wrote {path.name} ({len(cases)} rows)")

    md = [f"# Usability rating — {len(cases)} cases\n", RUBRIC, "\n---\n"]
    for a, v in cases:
        md += [f"\n## {a}\n",
               f"**Explanation.** {v['explanation_text']}\n",
               f"**Recommended action.** {v['recommended_action']} — {v['next_action']}\n"]
        if v.get("symptom_to_check"):
            md.append(f"**Symptom for the technician.** {v['symptom_to_check']}\n")
    (HERE / "usability_cases.md").write_text("\n".join(md))
    print(f"  wrote usability_cases.md — give this to both raters")
    print("\n  Neither the class, the confidence, nor the correct answer appears in "
          "that file,\n  so raters cannot be swayed by knowing which cases the "
          "classifier got right.")


def read_sheet(path):
    if not path.exists():
        return None
    d = pd.read_csv(path)
    if d[POINTS].isna().all().all() or (d[POINTS].astype(str) == "").all().all():
        return None
    for p in POINTS:
        d[p] = pd.to_numeric(d[p], errors="coerce")
    if d[POINTS].isna().any().any():
        print(f"  ! {path.name} has blank cells — those cases are skipped")
    d["pass"] = d[POINTS].sum(axis=1) == len(POINTS)
    return d


def score():
    sheets = {r: read_sheet(HERE / f"usability_rater_{r}.csv") for r in RATERS}
    judge = json.loads(JUDGE_FILE.read_text()) if JUDGE_FILE.exists() else None
    filled = {r: d for r, d in sheets.items() if d is not None}

    print("=" * 70)
    print("USABILITY — Part B criterion 4")
    print("=" * 70)

    if not filled and not judge:
        print("  Nothing scored yet. Run --sheets, hand usability_cases.md to two")
        print("  readers, and have each fill in their CSV.")
        return

    for r, d in filled.items():
        rate = d["pass"].mean()
        print(f"\n  Rater {r}: {int(d['pass'].sum())}/{len(d)} = {rate:.0%} "
              f"({'PASS' if rate >= 0.8 else 'FAIL'} against the 80% bar)")
        for p in POINTS:
            print(f"      {p:20} {int(d[p].sum())}/{len(d)}")

    if len(filled) == 2:
        a, b = (filled[r].set_index("case") for r in RATERS)
        common = a.index.intersection(b.index)
        agree = (a.loc[common, "pass"] == b.loc[common, "pass"]).mean()
        per_point = {p: (a.loc[common, p] == b.loc[common, p]).mean() for p in POINTS}
        print(f"\n  Raw agreement on the overall verdict: {agree:.0%} "
              f"({int((a.loc[common,'pass'] == b.loc[common,'pass']).sum())}/{len(common)})")
        for p, v in per_point.items():
            print(f"      {p:20} {v:.0%}")
        split = common[a.loc[common, "pass"] != b.loc[common, "pass"]]
        if len(split):
            print(f"\n  Split decisions — send these to a third reader: "
                  f"{', '.join(split)}")

    if judge:
        jp = pd.Series({k: all(v[p] for p in POINTS) for k, v in judge.items()})
        print(f"\n  LLM judge (not authoritative): {int(jp.sum())}/{len(jp)} = "
              f"{jp.mean():.0%}")
        for r, d in filled.items():
            s = d.set_index("case")["pass"]
            common = s.index.intersection(jp.index)
            print(f"      agrees with rater {r} on {(s.loc[common] == jp.loc[common]).mean():.0%} "
                  f"of {len(common)} cases")
        if not filled:
            print("      No human scores yet — this number cannot be used on its own.")


def run_judge():
    """Optional pre-rating, to be validated against the human scores."""
    import anthropic

    cases = load_cases()
    client = anthropic.Anthropic()
    schema = {
        "type": "object",
        "properties": {**{p: {"type": "boolean"} for p in POINTS},
                       "comment": {"type": "string"}},
        "required": POINTS + ["comment"],
        "additionalProperties": False,
    }
    out = {}
    for a, v in cases:
        text = (f"EXPLANATION\n{v['explanation_text']}\n\n"
                f"RECOMMENDED ACTION\n{v['recommended_action']} — {v['next_action']}")
        resp = client.messages.create(
            model="claude-opus-5", max_tokens=4000,
            system=RUBRIC + "\n\nScore the output below. Judge only how it reads.",
            output_config={"effort": "low",
                           "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": text}],
        )
        out[a] = json.loads(next(b.text for b in resp.content if b.type == "text"))
        print(".", end="", flush=True)
    JUDGE_FILE.write_text(json.dumps(out, indent=2))
    print(f"\n  wrote {JUDGE_FILE.name} — validate against human scores before quoting it")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheets", action="store_true")
    ap.add_argument("--judge", action="store_true")
    ap.add_argument("--score", action="store_true")
    a = ap.parse_args()
    if a.sheets:
        write_sheets()
    if a.judge:
        run_judge()
    if a.score or not (a.sheets or a.judge):
        score()
