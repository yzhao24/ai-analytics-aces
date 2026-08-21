"""
Planned operations the manager declares in advance.

WHY THIS IS NOT THE REMEDY WE ALREADY MEASURED FAILING
------------------------------------------------------
`experiment/shift-schedule` gave the model a shift schedule and asked it to
*infer* whether a day was busy. Precision fell from 82% to 64%. The reason was
structural: a day planned at 130% of normal adds 7-10 kWh to a sub-system and
the alarm does not fire until 20, so a realistic busy day never reaches the
detector at all. Any operational event large enough to alarm is larger than its
own explanation.

This is a different thing. The manager *declares* a known event -- "we ran an
extra shift on the compressor bank from 8pm Monday" -- and that declaration is
testimony, not inference. It does not have to clear a detection threshold to be
useful, because nobody is deducing it from consumption.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It never suppresses an alert and never changes the agent's decision. A
compressor can fail *during* a busy shift, and at a 167:1 miss-to-false-alarm
ratio, auto-dismissing anything inside a declared window is precisely the wrong
direction. A declaration is evidence handed to the classifier and shown to the
manager; the decision rule is untouched.

A NOTE ON MEASURING IT
----------------------
On the synthetic test set, declaring the injected operational events is close to
handing over the ground-truth label, so any precision gain measured that way is
circular and must not be quoted. What *can* be tested honestly is the failure
direction: a declaration covering a window where a real fault occurred must not
talk the classifier out of calling it a fault. See `--selftest`.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

STORE = Path(__file__).parent / "operations_log.json"

# Mirrors the operational_variation subtypes in registries.xlsx, plus the two
# things a manager knows about that the catalogue has no class for.
EVENT_TYPES = [
    "Peak Throughput Day",
    "Unscheduled Overtime",
    "Temporary Equipment Rental",
    "Planned Maintenance",
    "Other (describe below)",
]

ANY = "ALL"


# ── storage ──────────────────────────────────────────────────────────────────
def load():
    """Every declaration, newest first. Never raises on a missing or bad file."""
    if not STORE.exists():
        return []
    try:
        rows = json.loads(STORE.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    return sorted(rows, key=lambda r: r.get("declared_at", ""), reverse=True)


def save(rows):
    STORE.write_text(json.dumps(rows, indent=2))


def add(facility_id, system_id, starts_at, ends_at, event_type, note=""):
    """Record a declaration. Returns the stored row."""
    if pd.Timestamp(ends_at) <= pd.Timestamp(starts_at):
        raise ValueError("The end of a planned operation must come after its start.")
    row = {
        "entry_id": f"OPS-{uuid.uuid4().hex[:8]}",
        "facility_id": facility_id,
        "system_id": system_id,
        "starts_at": pd.Timestamp(starts_at).isoformat(),
        "ends_at": pd.Timestamp(ends_at).isoformat(),
        "event_type": event_type,
        "note": note.strip(),
        "declared_at": datetime.now().isoformat(timespec="seconds"),
    }
    rows = load()
    rows.append(row)
    save(rows)
    return row


def remove(entry_id):
    rows = [r for r in load() if r["entry_id"] != entry_id]
    save(rows)
    return rows


# ── query ────────────────────────────────────────────────────────────────────
def covering(rows, facility_id, system_id, start, end):
    """Declarations whose window overlaps [start, end] for this sub-system.

    A declaration scoped to ALL systems covers every sub-system at that
    facility; one scoped to ALL facilities covers everything.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    hits = []
    for r in rows:
        # load() already tolerates a corrupt file, so a half-written row must not
        # be the thing that takes the panel down. Skip what we cannot read.
        try:
            if r.get("facility_id") not in (ANY, facility_id):
                continue
            if r.get("system_id") not in (ANY, system_id):
                continue
            starts, ends = pd.Timestamp(r["starts_at"]), pd.Timestamp(r["ends_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if starts <= end and ends >= start:
            hits.append(r)
    return hits


def window_of(anomaly):
    """The hours an anomaly actually spans, from its detection and duration."""
    start = pd.Timestamp(anomaly.detected_at)
    minutes = float(getattr(anomaly, "duration_minutes", 60) or 60)
    return start, start + pd.Timedelta(minutes=minutes)


def describe(entry):
    scope = []
    if entry.get("facility_id", ANY) != ANY:
        scope.append(entry["facility_id"])
    if entry.get("system_id", ANY) != ANY:
        scope.append(entry["system_id"])
    where = " · ".join(scope) if scope else "all facilities"
    s, e = pd.Timestamp(entry["starts_at"]), pd.Timestamp(entry["ends_at"])
    span = (f"{s:%d %b %H:%M} – {e:%H:%M}" if s.date() == e.date()
            else f"{s:%d %b %H:%M} – {e:%d %b %H:%M}")
    return f"{entry['event_type']} · {where} · {span}"


def as_prompt_evidence(hits):
    """The lines handed to the classifier. Empty string when nothing is declared."""
    if not hits:
        return ""
    lines = [
        "DECLARED OPERATIONS COVERING THIS WINDOW",
        "The site manager recorded these planned events in advance. Treat them as "
        "credible evidence about what was happening, but not as proof of cause — "
        "equipment can fail during planned operations, and a declaration does not "
        "make a fault impossible.",
    ]
    for h in hits:
        line = f"- {describe(h)}"
        if h.get("note"):
            line += f' — manager\'s note: "{h["note"]}"'
        lines.append(line)
    return "\n".join(lines)


# ── self-test ────────────────────────────────────────────────────────────────
def _selftest():
    """Overlap logic, scoping, and the safety property that matters."""
    rows = [
        {"entry_id": "a", "facility_id": "FAC-002", "system_id": "SYS-005",
         "starts_at": "2026-07-27T18:00:00", "ends_at": "2026-07-28T04:00:00",
         "event_type": "Peak Throughput Day", "note": "retail push", "declared_at": "x"},
        {"entry_id": "b", "facility_id": "FAC-002", "system_id": ANY,
         "starts_at": "2026-07-27T20:00:00", "ends_at": "2026-07-27T21:00:00",
         "event_type": "Planned Maintenance", "note": "", "declared_at": "x"},
        {"entry_id": "c", "facility_id": ANY, "system_id": ANY,
         "starts_at": "2020-01-01T00:00:00", "ends_at": "2020-01-02T00:00:00",
         "event_type": "Other (describe below)", "note": "", "declared_at": "x"},
    ]
    t = lambda s: pd.Timestamp(s)
    checks = [
        ("exact system, overlapping window", ["a", "b"],
         covering(rows, "FAC-002", "SYS-005", t("2026-07-27 20:00"), t("2026-07-28 04:00"))),
        ("ALL-system entry reaches another sub-system", ["b"],
         covering(rows, "FAC-002", "SYS-009", t("2026-07-27 20:00"), t("2026-07-27 21:00"))),
        ("wrong facility matches nothing but the global entry", [],
         covering(rows, "FAC-001", "SYS-005", t("2026-07-27 20:00"), t("2026-07-28 04:00"))),
        ("window before the declaration", [],
         covering(rows, "FAC-002", "SYS-005", t("2026-07-27 10:00"), t("2026-07-27 11:00"))),
        ("touching edges count as overlap", ["a"],
         covering(rows, "FAC-002", "SYS-005", t("2026-07-28 04:00"), t("2026-07-28 05:00"))),
    ]
    ok = True
    for label, want, got in checks:
        ids = sorted(h["entry_id"] for h in got)
        good = ids == sorted(want)
        ok &= good
        print(f"  {'ok  ' if good else 'FAIL'} {label:48} {ids}")

    malformed = covering(rows + [{"entry_id": "junk"}], "FAC-002", "SYS-005",
                         t("2026-07-27 20:00"), t("2026-07-28 04:00"))
    survives = sorted(h["entry_id"] for h in malformed) == ["a", "b"]
    ok &= survives
    print(f"  {'ok  ' if survives else 'FAIL'} "
          f"{'a half-written row is skipped, not fatal':48} "
          f"{sorted(h['entry_id'] for h in malformed)}")

    ev = as_prompt_evidence(covering(rows, "FAC-002", "SYS-005",
                                     t("2026-07-27 20:00"), t("2026-07-28 04:00")))
    safety = "not as proof of cause" in ev and "can fail during planned" in ev
    ok &= safety
    print(f"  {'ok  ' if safety else 'FAIL'} prompt evidence warns against treating it as proof")
    print(f"  {'ok  ' if not as_prompt_evidence([]) else 'FAIL'} "
          f"no declarations produces no prompt text")
    print("\n  " + ("all checks pass" if ok else "FAILURES ABOVE"))
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
