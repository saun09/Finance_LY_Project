"""Versioned configuration for Module 8 (simulated behavioural drift
detection). Every safeguard threshold lives here, explicit and documented,
not buried inline in the detector logic.

IMPORTANT — read before touching or citing this module anywhere:
This module is validated ONLY against synthetic, hand-authored personas
(see drift_personas.py). It has never been run against real user
behaviour. Nothing here, in drift_detector.py, drift_evaluation.py, or any
docs/UI copy describing this module may claim or imply real-user
validation. See "future work: real-user validation" in this backend's
README for the only place that gap should be mentioned as an intention,
not an accomplishment.
"""

from decimal import Decimal

CONFIG_VERSION = "v1"
CONFIG_EFFECTIVE_DATE = "2026-01-01"

# --- hysteresis: consecutive review cycles of agreeing signal required
# before a tier change actually commits ---

# Asymmetric by design: raising a tier (more risk capacity/willingness
# than before) commits faster than lowering one. The asymmetry itself is a
# documented, deliberate safeguard from the module brief -- being slow to
# take capacity away from someone protects against a transient rough
# patch getting misread as a permanent downgrade, at the cost of being
# slower to reflect genuine deterioration. This tradeoff is stated, not
# proven optimal; it has not been tuned against real behaviour.
HYSTERESIS_CYCLES_TO_RAISE_TIER = 2
HYSTERESIS_CYCLES_TO_LOWER_TIER = 3

# --- freeze window: cycles immediately after a simulated market drawdown
# during which candidate drift signals are not allowed to accumulate ---

# Panic-driven edits right after a drawdown are exactly the kind of noisy,
# non-representative signal the evidence-weighting in Module 7 already
# discounts for personalization; re-tiering is a bigger, stickier decision
# than a displayed-allocation nudge, so it gets its own explicit freeze
# rather than relying on evidence-weighting alone.
DRAWDOWN_FREEZE_WINDOW_CYCLES = 2

# --- signal families: both a behavioural-edit signal (from allocation
# suggestion_event outcomes) and a capacity-snapshot signal (from
# Module 3's own capacity ceiling logic, applied to trailing snapshot
# data) must independently agree on direction before a cycle counts as
# candidate drift evidence at all. A single family moving alone -- even a
# strong, consistent move -- never accumulates hysteresis on its own. ---
MIN_AGREEING_SIGNAL_FAMILIES = 2

# Trailing window (months) of allocation-outcome evidence considered per
# review cycle for the behavioural signal, and of snapshot data for the
# capacity signal. A short window keeps both signals responsive to real
# change; it also means a couple of noisy months can dominate a reading,
# which is exactly why hysteresis across multiple *cycles* -- not just
# smoothing within one -- is the real safeguard against overreacting.
BEHAVIORAL_SIGNAL_WINDOW_MONTHS = 3
CAPACITY_SIGNAL_WINDOW_MONTHS = 3

# A cycle's behavioural signal only counts as "deviating" from the
# reference tier if the evidence-weighted average chosen equity is at
# least this many percentage points from what the reference tier's own
# target allocation would suggest -- filters out noise-level wobble from
# registering as a directional signal at all.
BEHAVIORAL_SIGNAL_DEADBAND_PCT = Decimal("3")
