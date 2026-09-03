"""Versioned configuration for Module 6 (debt and leak engine).

SCOPE NOTE — read before touching the leak side of this module:

Module 2 settled on manual-entry-only expenses (see
app/services/expense_source_decision.py — no statement parser exists, and
none is planned without a fresh, explicit decision to build one). That
means `ExpenseItem` rows have no merchant name and no per-transaction
date; a user enters "rent, Rs 20,000/month" as one already-aggregated
recurring line, not a stream of dated card-statement transactions. This
genuinely changes what "recurring-charge detection via merchant-name
clustering and periodicity analysis" can mean here:

- There is no periodicity to *infer* — the user already declares
  `frequency` (monthly/annual/one_time) directly, so "periodicity
  analysis" collapses to reading that field.
- There is no merchant name to cluster on — `category` is a short freeform
  label the user typed for their own reference. This module treats
  `category` as a merchant-name analog for near-duplicate clustering
  (`difflib` string-similarity over normalized category text) and for
  keyword matching against the lists below, which is a real but reduced
  substitute for clustering actual dated transaction merchant strings.

This is a deliberate, documented scope reduction, not a silently dropped
deliverable — see backend/README.md's Module 6 section for the same note
in narrative form.
"""

from decimal import Decimal

from app.services.risk_profile_config import CAPACITY_RULE_TABLE_V1

CONFIG_VERSION = "v1"
CONFIG_EFFECTIVE_DATE = "2026-01-01"

# Keyword fragments (lowercase) matched against ExpenseItem.category to
# flag likely recurring discretionary subscriptions worth a user's review.
# Matching is substring-based over normalized (lowercased, punctuation-
# stripped) category text. This is a heuristic over user-typed labels, not
# a merchant classifier — a category like "misc" or "other" will never
# match, and that's an accepted limitation of manual-entry-only data.
SUBSCRIPTION_KEYWORDS_V1: tuple[str, ...] = (
    "subscription", "streaming", "membership", "gym", "magazine",
    "app store", "play store", "cloud storage", "cloud backup", "ott",
    "music", "news", "software", "saas", "vpn", "domain", "hosting",
)

# Keyword fragments matched against ExpenseItem.category to flag recurring
# bank/investment fee drag. Deliberately does NOT include fund expense
# ratios (TER) — Module 4's holdings don't currently capture a TER field,
# so any embedded fund-fee drag is invisible to this module. That's a
# known gap, not an omission to hide: only fees the user explicitly typed
# as an expense line item are counted here.
FEE_KEYWORDS_V1: tuple[str, ...] = (
    "bank charge", "bank fee", "account maintenance", "amc", "demat",
    "atm fee", "late payment fee", "late fee", "forex markup",
    "annual fee", "processing fee", "service charge", "penalty",
    "overdraft fee", "sms charge", "statement fee",
)

# Two category strings are treated as a likely-duplicate/overlapping pair
# when their normalized text similarity (difflib.SequenceMatcher ratio,
# 0-1) is at or above this threshold. Chosen to catch near-identical retypes
# ("netflix" / "netflix subscription") without flagging genuinely distinct
# categories that merely share a common word.
DUPLICATE_CATEGORY_SIMILARITY_THRESHOLD = 0.72

# Idle-cash opportunity cost is computed against this illustrative annual
# reference rate — what idle cash could plausibly earn if moved into a
# liquid, low-risk cash-equivalent instrument (e.g. a liquid mutual fund
# or a sweep/high-yield savings arrangement), based on prevailing
# short-term rates at the time this config version was set. This is NOT a
# guaranteed return, is not tied to any named product, and should be
# reviewed periodically — bump the version and effective date when it is,
# rather than silently editing this one.
IDLE_CASH_REFERENCE_RATE_ANNUAL_BPS = 650  # 6.50% p.a., illustrative

# The buffer level above which cash is no longer "required" for emergency
# coverage. Deliberately reuses Module 3's own capacity rule table (the
# lower bound of its top, uncapped buffer band) rather than introducing a
# second, potentially-drifting "adequate buffer" constant.
IDLE_CASH_BUFFER_TARGET_MONTHS = Decimal(
    str(next(b.min_value for b in CAPACITY_RULE_TABLE_V1.buffer_months_bands if b.ceiling == 5))
)

# Safety cap for amortization simulations (debt_amortization.py) — 50
# years. A well-formed EMI (payment > accruing interest) always converges
# far sooner; this only guards against genuinely bad input (e.g. an EMI
# too small to cover its own interest) so a simulation can never loop
# forever.
MAX_AMORTIZATION_MONTHS = 600
