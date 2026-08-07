"""
Stability and bias measurement for Part D.

Runs the classifier repeatedly over the same cases and reports whether the
answer changes, then breaks accuracy down by facility, system type, and season
to look for uneven performance.

    python stability_test.py --runs 3

Writes `stability_runs.json` so the numbers can be re-quoted without paying for
the API again.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

import classifier as C

HERE = Path(__file__).parent
OUT = HERE / "stability_runs.json"


def collect(runs):
    """Classify the core stratum `runs` times, keeping every answer."""
    data = C.load_inputs()
    truth = pd.ExcelFile(C.DATA_FILE).parse("test_set_15_cases")
    core = set(truth[truth.stratum == "core"].anomaly_id) if "stratum" in truth else set(truth.anomaly_id)

    import anthropic
    client = anthropic.Anthropic()

    all_runs = []
    for r in range(runs):
        print(f"run {r + 1} of {runs}")
        out = {}
        for anomaly in data["anomalies"].itertuples():
            if anomaly.anomaly_id not in core:
                continue
            sys_rows = data["system_registry"][
                data["system_registry"].system_id == anomaly.system_id]
            system = sys_rows.iloc[0] if not sys_rows.empty else None
            resp = client.messages.create(
                model=C.MODEL, max_tokens=8000, system=C.SYSTEM_PROMPT,
                output_config={"effort": "medium",
                               "format": {"type": "json_schema", "schema": C.SCHEMA}},
                messages=[{"role": "user",
                           "content": C.build_prompt(data, anomaly, system)}],
            )
            text = next(b.text for b in resp.content if b.type == "text")
            out[anomaly.anomaly_id] = json.loads(text)
            print(".", end="", flush=True)
        print()
        all_runs.append(out)

    OUT.write_text(json.dumps(all_runs, indent=2))
    return all_runs


def report(all_runs):
    truth = pd.ExcelFile(C.DATA_FILE).parse("test_set_15_cases").set_index("anomaly_id")
    xl = pd.ExcelFile(C.DATA_FILE)
    ano = xl.parse("anomalies").set_index("anomaly_id")
    sysr = xl.parse("system_registry").set_index("system_id")
    fac = xl.parse("facility_registry").set_index("facility_id")
    cases = list(all_runs[0])
    n_runs = len(all_runs)

    print("\n" + "=" * 74)
    print(f"STABILITY — same input, {n_runs} runs, {len(cases)} cases")
    print("=" * 74)

    unstable_class, unstable_sub, unstable_act, confs = 0, 0, 0, []
    detail = []
    for c in cases:
        cls = [r[c]["top_level_class"] for r in all_runs]
        sub = [r[c]["classification_type_id"] for r in all_runs]
        act = [r[c]["recommended_action"] for r in all_runs]
        cf = [r[c]["confidence_score"] for r in all_runs]
        confs.append(max(cf) - min(cf))
        if len(set(cls)) > 1: unstable_class += 1
        if len(set(sub)) > 1: unstable_sub += 1
        if len(set(act)) > 1: unstable_act += 1
        detail.append((c, Counter(cls).most_common(1)[0][1], Counter(sub).most_common(1)[0][1],
                       min(cf), max(cf), len(set(sub)) > 1))

    print(f"  top-level class identical across runs : {len(cases) - unstable_class}/{len(cases)}")
    print(f"  subtype identical across runs         : {len(cases) - unstable_sub}/{len(cases)}")
    print(f"  recommended action identical          : {len(cases) - unstable_act}/{len(cases)}")
    print(f"  confidence spread, mean               : {sum(confs)/len(confs):.3f}")
    print(f"  confidence spread, worst case         : {max(confs):.2f}")

    if unstable_sub:
        print("\n  cases whose subtype moved between runs:")
        for c, _, _, lo, hi, moved in detail:
            if moved:
                subs = [r[c]["classification_type_id"] for r in all_runs]
                print(f"    {c}  {' / '.join(subs)}   conf {lo:.2f}-{hi:.2f}")

    # ── Bias ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 74)
    print("BIAS — top-level accuracy by group (majority answer across runs)")
    print("=" * 74)
    rows = []
    for c in cases:
        cls = Counter(r[c]["top_level_class"] for r in all_runs).most_common(1)[0][0]
        sid = ano.loc[c].system_id
        rows.append(dict(
            case=c, right=cls == truth.loc[c].true_top_level_class,
            facility=fac.loc[ano.loc[c].facility_id].facility_name,
            system_type=sysr.loc[sid].system_type,
            month=pd.to_datetime(ano.loc[c].detected_at).month,
            truth=truth.loc[c].true_top_level_class,
        ))
    d = pd.DataFrame(rows)
    d["season"] = d.month.map(lambda m: "warm (Apr-Sep)" if 4 <= m <= 9 else "cold (Oct-Mar)")

    for col in ["facility", "system_type", "season", "truth"]:
        print(f"\n  by {col}:")
        for k, g in d.groupby(col):
            print(f"    {str(k):22} {g.right.sum()}/{len(g)} = {g.right.mean():.0%}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    runs = json.loads(OUT.read_text()) if a.report_only else collect(a.runs)
    report(runs)
