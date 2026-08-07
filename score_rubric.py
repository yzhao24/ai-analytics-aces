"""
Scores the Part B evaluation rubric against the current classifier output.

Every figure quoted in the Assignment 2 rubric comes from here, so the document
and the repository cannot drift apart. Run after any classifier or dataset
change and re-quote whatever moves.

    python score_rubric.py

Usability is deliberately left unscored: "could the manager act unaided" is a
claim about a reader, and the model cannot be both author and marker. Two human
raters score it blind; this script only prepares the sheet they fill in.
"""

import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
DATA_FILE = HERE / "dummy_data_set2.xlsx"
LLM_FILE = HERE / "classifications_llm.json"

DISPATCH_COST = 300.0        # spec: ~$300 per technician dispatch
MISSED_FAULT_COST = 2000.0   # spec: $2,000-$8,000; conservative end
COMMIT_THRESHOLD = 0.75      # the product's auto-classify gate
TIMELINESS_LIMIT_S = 300     # spec horizon: 5 minutes

REQUIRED_FIELDS = [
    "top_level_class", "classification_type_id", "confidence_score",
    "explanation_text", "recommended_action", "next_action", "symptom_to_check",
]


def load():
    xl = pd.ExcelFile(DATA_FILE)
    truth = xl.parse("test_set_15_cases")
    preds = json.loads(LLM_FILE.read_text())
    reg = xl.parse("classification_registry").set_index("classification_id")
    core = truth[truth.stratum == "core"].copy() if "stratum" in truth else truth.copy()
    return core, preds, reg, xl


def score():
    core, preds, reg, xl = load()
    rows = []
    for t in core.itertuples():
        p = preds.get(t.anomaly_id, {})
        right_top = p.get("top_level_class") == t.true_top_level_class
        right_sub = p.get("classification_type_id") == t.true_classification_id
        conf = p.get("confidence_score")
        action = p.get("recommended_action")

        # Completeness: every field present and non-empty, and a symptom
        # whenever the action is dispatch.
        present = all(str(p.get(f, "")).strip() != "" for f in REQUIRED_FIELDS
                      if not (f == "symptom_to_check" and action != "dispatch"))
        symptom_ok = action != "dispatch" or str(p.get("symptom_to_check", "")).strip() != ""

        rows.append(dict(
            case=t.anomaly_id,
            truth_class=t.true_top_level_class, truth_sub=t.true_classification_id,
            pred_class=p.get("top_level_class"), pred_sub=p.get("classification_type_id"),
            right_top=right_top, right_sub=right_sub,
            complete=present and symptom_ok,
            confidence=conf, action=action,
            committed=conf is not None and conf >= COMMIT_THRESHOLD,
            latency_s=p.get("latency_seconds"),
        ))
    d = pd.DataFrame(rows)

    # Calibration: commit when right, hedge when wrong. A wrong label held at or
    # above the gate is an overclaim and fails the case outright.
    d["calibrated"] = (d.right_top & d.committed) | (~d.right_top & ~d.committed)
    d["overclaim"] = ~d.right_top & d.committed

    n = len(d)
    out = {
        "n": n,
        "correct_top": int(d.right_top.sum()),
        "correct_sub": int(d.right_sub.sum()),
        "complete": int(d.complete.sum()),
        "calibrated": int(d.calibrated.sum()),
        "overclaims": int(d.overclaim.sum()),
        "mean_conf_right": float(d.loc[d.right_top, "confidence"].mean()),
        "mean_conf_wrong": float(d.loc[~d.right_top, "confidence"].mean()) if (~d.right_top).any() else float("nan"),
        "latency_mean": float(d.latency_s.mean()),
        "latency_max": float(d.latency_s.max()),
    }

    fault = d.truth_class == "equipment_fault"
    said = d.pred_class == "equipment_fault"
    tp, fp, fn = int((said & fault).sum()), int((said & ~fault).sum()), int((~said & fault).sum())
    out |= {"tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else float("nan"),
            "recall": tp / (tp + fn) if tp + fn else float("nan")}
    return d, out, preds, xl


def decision_value(xl, preds):
    """Cost of following the tool against two fixed policies, over every anomaly."""
    truth = xl.parse("test_set_15_cases").set_index("anomaly_id")
    reg = xl.parse("classification_registry").set_index("classification_id")
    rank = {"dismiss": 0, "monitor": 1, "dispatch": 2}

    rows = []
    for aid, p in preds.items():
        if aid not in truth.index:
            continue
        cap = reg.loc[p["classification_type_id"]].recommended_action
        gate = "dispatch" if p["confidence_score"] >= COMMIT_THRESHOLD else "monitor"
        decision = min(gate, cap, key=lambda k: rank[k])
        rows.append(dict(aid=aid, decision=decision,
                         is_fault=truth.loc[aid].true_top_level_class == "equipment_fault"))
    d = pd.DataFrame(rows)
    n_fault = int(d.is_fault.sum())

    def cost(sent):
        missed = int((d.is_fault & ~sent).sum())
        return dict(sent=int(sent.sum()), caught=int((d.is_fault & sent).sum()),
                    missed=missed, cost=sent.sum() * DISPATCH_COST + missed * MISSED_FAULT_COST)

    return n_fault, len(d), {
        "Follow the tool": cost(d.decision == "dispatch"),
        "Dispatch on every spike": cost(pd.Series(True, index=d.index)),
        "Dispatch on none": cost(pd.Series(False, index=d.index)),
    }


if __name__ == "__main__":
    d, s, preds, xl = score()
    p = lambda label, val, bar, ok: print(
        f"  {label:22} {val:>22}   bar {bar:<14} {'PASS' if ok else 'FAIL'}")

    print("=" * 76)
    print(f"PART B — PER-OUTPUT RUBRIC   (core stratum, n={s['n']})")
    print("=" * 76)
    p("Correctness (class)", f"{s['correct_top']}/{s['n']} = {s['correct_top']/s['n']:.0%}",
      "both exact", s["correct_top"] == s["n"])
    p("Correctness (subtype)", f"{s['correct_sub']}/{s['n']} = {s['correct_sub']/s['n']:.0%}",
      "both exact", s["correct_sub"] == s["n"])
    p("Completeness", f"{s['complete']}/{s['n']}", "all fields", s["complete"] == s["n"])
    p("Calibration", f"{s['calibrated']/s['n']:.0%}, {s['overclaims']} overclaim",
      ">=80%, none", s["calibrated"] / s["n"] >= 0.8 and s["overclaims"] == 0)
    p("Usability", "not scored", ">=80%", False)
    p("Timeliness", f"{s['latency_mean']:.1f}s avg, {s['latency_max']:.1f}s max",
      "< 5 min", s["latency_max"] < TIMELINESS_LIMIT_S)

    print(f"\n  mean confidence when right : {s['mean_conf_right']:.2f}")
    print(f"  mean confidence when wrong : {s['mean_conf_wrong']:.2f}")
    print(f"  -> confidence {'runs against' if s['mean_conf_wrong'] >= s['mean_conf_right'] else 'tracks'} correctness")

    print("\n" + "=" * 76)
    print("AGGREGATES")
    print("=" * 76)
    p("Precision, equip fault", f"{s['tp']} TP / {s['fp']} FP = {s['precision']:.0%}",
      ">= 75%", s["precision"] >= 0.75)
    p("Recall, equip fault", f"{s['fn']} FN = {s['recall']:.0%}", ">= 70%", s["recall"] >= 0.70)

    n_fault, n_all, pol = decision_value(xl, preds)
    print(f"\n  Decision value, all {n_all} anomalies ({n_fault} true faults):")
    for name, v in pol.items():
        print(f"    {name:26} sent={v['sent']:>3}  caught={v['caught']:>2}/{n_fault}  "
              f"missed={v['missed']:>2}  ${v['cost']:>8,.0f}")
    tool = pol["Follow the tool"]["cost"]
    beat = min(v["cost"] for k, v in pol.items() if k != "Follow the tool")
    p("Decision value", f"${tool:,.0f}", f"beat ${beat:,.0f}", tool < beat)

    print("\n" + "=" * 76)
    print("FAILURES — for Part C")
    print("=" * 76)
    wrong = d[~d.right_top]
    for r in wrong.itertuples():
        print(f"  {r.case}  {r.truth_sub} ({r.truth_class}) read as {r.pred_class} "
              f"at {r.confidence:.2f}")
    sub_only = d[d.right_top & ~d.right_sub]
    print(f"  {len(sub_only)} of {s['n']}  right class, wrong subtype")
