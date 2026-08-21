"""
The cost model, in one place.

These four numbers decide whether the product is worth running, so they must not
drift between the dashboard and the batch scorer. They previously lived in three
places under two different names, which meant changing the assumption would have
left the Settings screen quoting one break-even and the History screen pricing
against another.

Figures come from the team's problem specification:
  - a technician dispatch costs approximately $300
  - a missed refrigeration fault costs $2,000-$8,000 in excess consumption alone,
    before spoiled inventory; we take the conservative end

BREAK_EVEN follows from those two. Dispatching costs DISPATCH_COST for certain;
not dispatching costs p x MISS_COST. A visit therefore pays whenever
p > DISPATCH_COST / MISS_COST.

COMMIT_THRESHOLD_DEFAULT is what the product actually ships with, and every
figure in the README and the evaluation is scored against it. It is five times
BREAK_EVEN, which is the product's largest known defect; it stays as the default
so the reported numbers keep describing real behaviour, and Settings lets a user
move it.

This module imports nothing, so both the Streamlit app and the command-line
scorer can read it without dragging in each other's dependencies.
"""

DISPATCH_COST = 300.0
MISS_COST = 2000.0
BREAK_EVEN = DISPATCH_COST / MISS_COST      # 0.15
COMMIT_THRESHOLD_DEFAULT = 0.75

# Spec horizon: a classification must come back within five minutes.
TIMELINESS_LIMIT_S = 300
