"""Human-readable vocabulary for Module 9's traces.

WHY THIS FILE EXISTS. The transparency layer originally rendered stored
values verbatim, on the argument that reformatting them would be a
reinterpretation the backend never sanctioned. That instinct was right
about *auditability* and wrong about *transparency*: it produced screens
reading `horizon: gt_15y`, `drawdown_reaction: buy_a_lot` and
`emi_to_income_ratio: 0.3`, which are faithful and unreadable at the same
time. Transparency a person cannot read is not transparency.

The resolution is layering, not compromise. This module turns stored
codes into the sentences a person would actually say; the raw stored
record stays reachable underneath every fact, so nothing is paraphrased
away. Translation lives on the server, not the client, so it is versioned
alongside the configs it describes and both halves of the app agree.

VERSION-AWARENESS IS THE POINT. A stored `risk_profile` event records
which `questionnaire_version` produced it. Translating an old event's
answers with today's questionnaire would put words in the user's mouth
that they were never shown -- the exact failure this module exists to
prevent, just moved into the display layer. `answer_label` therefore
looks up the version recorded on the event, and falls back to the raw
code (never to a guess) when it cannot.
"""

from decimal import Decimal, InvalidOperation

from app.services.risk_profile_config import (
    QUESTIONNAIRE_V1,
    QUESTIONNAIRE_V2,
    Questionnaire,
)

# --------------------------------------------------------------------------
# Version-aware questionnaire vocabulary
# --------------------------------------------------------------------------

QUESTIONNAIRES_BY_VERSION: dict[str, Questionnaire] = {
    QUESTIONNAIRE_V1.version: QUESTIONNAIRE_V1,
    QUESTIONNAIRE_V2.version: QUESTIONNAIRE_V2,
}


def question_text(version: str | None, question_id: str) -> str:
    """The question as it was actually put to the user, at that version."""
    questionnaire = QUESTIONNAIRES_BY_VERSION.get(version or "")
    if questionnaire is not None:
        for question in questionnaire.questions:
            if question.id == question_id:
                return question.text
    return field_label(question_id)


def answer_label(version: str | None, question_id: str, value: str) -> str:
    """The answer as it was shown to the user, at that version.

    Falls back to the raw code rather than guessing from a newer
    questionnaire: showing someone a phrasing they were never offered is
    worse than showing them the code.
    """
    questionnaire = QUESTIONNAIRES_BY_VERSION.get(version or "")
    if questionnaire is not None:
        for question in questionnaire.questions:
            if question.id == question_id:
                for option in question.options:
                    if option.value == value:
                        return option.label
    return str(value)


# --------------------------------------------------------------------------
# Risk tiers
#
# The backend stores tiers as bare integers 1-5 and has never named them.
# These are display-only names for the transparency screens; they change
# no scoring, no cap and no rule, and nothing reads them back.
# --------------------------------------------------------------------------

TIER_LABEL: dict[int, str] = {
    1: "Very conservative",
    2: "Conservative",
    3: "Balanced",
    4: "Growth",
    5: "Aggressive",
}


def tier(value) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return str(value)
    name = TIER_LABEL.get(n)
    return f"Tier {n} — {name}" if name else f"Tier {n}"


# --------------------------------------------------------------------------
# Field names
# --------------------------------------------------------------------------

FIELD_LABEL: dict[str, str] = {
    # risk tier
    "answers": "Your answers",
    "questionnaire_version": "Which questionnaire you answered",
    "stated_score": "Your willingness score",
    "stated_tier": "The tier your answers alone give",
    "final_tier": "The tier you ended up on",
    "capped": "Whether you were held back",
    "capacity_ceiling": "What your finances support",
    "capacity_components": "Each limit, one by one",
    "binding_constraints": "What's holding you back",
    "unlock_conditions": "How to lift your tier",
    "rule_table_version": "Which rule table applied",
    # allocation
    "target_pct": "Your target mix",
    "current_exposure_pct": "What you hold today",
    "concentration": "How concentrated you are",
    "holdings": "Your individual investments",
    "reasoning": "The rule we applied",
    "allocation_config_version": "Which investment-mix rules applied",
    "asset_classification_config_version": "Which classification rules applied",
    # leaks
    "leak_components": "The itemised list",
    "data_source_note": "What this can't see",
    "idle_cash": "Idle cash working",
    "expense_source_mode": "Where the expense data came from",
    # personalization
    "trace": "Your edits, step by step",
    "base_target_pct": "The plan before your edits",
    "displayed_target_pct": "The plan you're shown",
    # milestones
    "milestone_id": "Which milestone",
    "headline": "What you earned",
    "details": "What you did",
    "config_version": "Which milestone rules applied",
    # rumour verification
    "query_text": "What you asked about",
    "status": "The verdict",
    "candidate_explanations": "The reason each filing was ruled out",
    "eliminated_by_constraint": "How many filings each check ruled out",
    "why_ranked_first": "Why the top filing won",
    "full_trace_text": "The full written trace",
    "top_candidate_reasons": "What the workflow reported",
    "constraints_applied": "Which checks were applied",
    "official_evidence_count": "Official filings returned",
    "news_evidence_count": "News articles returned",
    "engine": "Which engine ran",
    # risk capacity
    "buffer_coverage_months": "Emergency buffer",
    "emi_to_income_ratio": "Share of income going to EMIs",
    "income_stability": "How steady your income is",
    "dependents_count": "People who depend on you",
    "total_life_cover_paise": "Life insurance cover",
    "monthly_income_paise": "Monthly income",
    "cash_balance_paise": "Cash in hand",
    "essential_monthly_expense_paise": "Essential monthly spending",
    "total_monthly_emi_paise": "Total monthly EMIs",
    "buffer_months": "Emergency buffer",
    "insurance_adequacy": "Life insurance cover",
    # allocation
    "largest_holding_pct": "Biggest single holding",
    "largest_holding_id": "Which holding that is",
    "asset_class_hhi_bps": "How concentrated your portfolio is",
    "total_value_paise": "Total portfolio value",
    "holding_type": "Kind of investment",
    "value_paise": "Value",
    "liquidity": "How quickly you can access it",
    "lock_in_months": "Locked in for",
    "tax_treatment_category": "Taxed as",
    # leaks
    "total_recoverable_annual_paise": "Recoverable each year",
    "required_buffer_paise": "Buffer you should keep",
    "idle_cash_paise": "Cash sitting idle",
    "reference_rate_annual_pct": "Reference savings rate",
    "opportunity_cost_annual_paise": "What that idle cash costs you a year",
    "fee_drag_total_annual_paise": "Recurring fees a year",
    "recurring_candidate_count": "Recurring expenses spotted",
    # personalization
    "offset_pct_points": "How far we shifted your plan",
    "alpha": "How much recent edits count",
    "edits_considered": "Edits we learned from",
    # rumour verification
    "candidates_considered": "Filings checked",
    "candidates_passing": "Filings that survived every check",
    "candidates_eliminated": "Filings ruled out",
    "matched_score": "How closely it matched",
    "filing_id": "Filing reference",
    "company_name": "Company",
    "filing_date": "Filed on",
    "filing_type": "Kind of filing",
    "source_authority": "Where it came from",
    "determination": "What the filing says",
    "corpus_size": "Filings in our records",
}


def field_label(key: str) -> str:
    """A readable label for a stored field name. Falls back to a
    sentence-cased de-underscoring rather than showing snake_case."""
    if key in FIELD_LABEL:
        return FIELD_LABEL[key]
    words = key.replace("_paise", "").replace("_pct", "").replace("_", " ").strip()
    return words[:1].upper() + words[1:] if words else key


# --------------------------------------------------------------------------
# Enum vocabularies
# --------------------------------------------------------------------------

INCOME_STABILITY_LABEL = {"regular": "Regular and predictable", "irregular": "Irregular"}

EMPLOYMENT_TYPE_LABEL = {
    "salaried": "Salaried",
    "self_employed": "Self-employed",
    "business_owner": "Business owner",
    "freelancer": "Freelancer",
    "unemployed": "Not currently employed",
    "other": "Other",
}

ASSET_CLASS_LABEL = {
    "cash": "Cash",
    "debt": "Debt",
    "equity": "Equity",
    "real_assets": "Real assets",
    "alternatives": "Alternatives",
}

LIQUIDITY_LABEL = {
    "liquid": "Available any time",
    "semi_liquid": "Takes a little while to access",
    "locked_in": "Locked in",
}

MILESTONE_CATEGORY_LABEL = {
    "buffer": "Emergency buffer",
    "capacity_unlock": "Capacity unlocked",
    "debt": "Debt cleared",
    "subscriptions": "Subscription cancelled",
    "consistency": "Consistency",
}

RUMOUR_STATUS_LABEL = {
    "confirmed": "Confirmed by the company",
    "denied": "Denied by the company",
    "unaddressed": "The company has not addressed it",
    "not_yet_due": "Too soon — the company still has time to respond",
}

#: The capacity constraints that can cap a tier.
CONSTRAINT_LABEL = {
    "buffer_months": "your emergency buffer",
    "buffer_coverage_months": "your emergency buffer",
    "emi_to_income_ratio": "how much of your income goes to EMIs",
    "income_stability": "how steady your income is",
    "insurance_adequacy": "your life insurance cover",
}

#: The four checks Module 5's local retriever applies, in order.
RETRIEVAL_CHECK_LABEL = {
    "entity": "Different company",
    "temporal": "Filed outside the response window",
    "source_authority": "Not an official exchange filing",
    "score_floor": "Too dissimilar to the rumour",
}

#: The same four checks phrased as the question being asked, rather than
#: as the reason for rejection. "Check applied: Different company" reads
#: like a verdict; "Is it the same company?" reads like a step.
RETRIEVAL_CHECK_QUESTION = {
    "entity": "Is it the same company?",
    "temporal": "Was it filed within the response window?",
    "source_authority": "Is it an official exchange filing?",
    "score_floor": "Is the wording close enough to the rumour?",
}

EXPENSE_SOURCE_MODE_LABEL = {
    "manual_only": "Only the expenses you entered yourself",
    "manual": "Expenses you entered yourself",
    "manual_entry": "Expenses you entered yourself",
    "statement": "Parsed from statements",
}

#: Which vocabulary applies to which stored field.
ENUM_LABELS_BY_FIELD: dict[str, dict[str, str]] = {
    "income_stability": INCOME_STABILITY_LABEL,
    "employment_type": EMPLOYMENT_TYPE_LABEL,
    "liquidity": LIQUIDITY_LABEL,
    "category": MILESTONE_CATEGORY_LABEL,
    "status": RUMOUR_STATUS_LABEL,
    "determination": {
        "confirms": "It confirms the rumour",
        "denies": "It denies the rumour",
        "non_committal": "It neither confirms nor denies",
    },
    "source_authority": {
        "official_exchange_filing": "Official exchange filing",
        "news_article": "News article",
    },
    "expense_source_mode": EXPENSE_SOURCE_MODE_LABEL,
}


def enum_label(field: str, value) -> str:
    """Translate a stored enum code for a known field, else return it as-is."""
    if value is None:
        return "Not recorded"
    vocabulary = ENUM_LABELS_BY_FIELD.get(field)
    if vocabulary and str(value) in vocabulary:
        return vocabulary[str(value)]
    return str(value)


def constraint_label(constraint: str) -> str:
    return CONSTRAINT_LABEL.get(constraint, field_label(constraint).lower())


def holding_type_label(value) -> str:
    """Holding types are a long, config-driven enum; de-underscoring them
    reads correctly ("equity_mutual_fund" -> "Equity mutual fund") without
    a hand-maintained map that would drift from the config."""
    if value is None:
        return "Not recorded"
    text = str(value).replace("_", " ")
    return text[:1].upper() + text[1:]


# --------------------------------------------------------------------------
# Number formatting
#
# Mirrors the frontend's currency.ts (Indian digit grouping) so a figure
# reads identically whether it was formatted here or there.
# --------------------------------------------------------------------------


def _group_indian(digits: str) -> str:
    if len(digits) <= 3:
        return digits
    last3, rest = digits[-3:], digits[:-3]
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return f"{','.join(groups)},{last3}"


def rupees(paise) -> str:
    """Integer paise -> '₹1,20,000'."""
    try:
        value = int(paise)
    except (TypeError, ValueError):
        return "Not recorded"
    sign = "-" if value < 0 else ""
    return f"{sign}₹{_group_indian(str(abs(value) // 100))}"


def _decimal(value) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _trim(value: Decimal) -> str:
    normalized = value.normalize()
    text = format(normalized, "f")
    return text


def percent(value) -> str:
    """A stored percentage ('40.00') -> '40%'."""
    d = _decimal(value)
    return f"{_trim(d)}%" if d is not None else str(value)


def ratio_as_percent(value) -> str:
    """A stored 0-1 ratio ('0.3') -> '30%'. Used for emi_to_income_ratio,
    which is the single most misread number on the old screens."""
    d = _decimal(value)
    if d is None:
        return str(value)
    return f"{_trim((d * 100).quantize(Decimal('0.1')).normalize())}%"


def months(value) -> str:
    d = _decimal(value)
    if d is None:
        return str(value)
    text = _trim(d)
    return f"{text} month" if text == "1" else f"{text} months"


def count(value, singular: str, plural: str | None = None) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return str(value)
    word = singular if n == 1 else (plural or f"{singular}s")
    return f"{n} {word}"


def yes_no(value) -> str:
    if value is None:
        return "Not recorded"
    return "Yes" if value else "No"


def joined(values, empty: str = "None") -> str:
    items = [str(v) for v in (values or [])]
    if not items:
        return empty
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


def number(value) -> str:
    """A stored decimal string -> the way a person writes it ('49.00' ->
    '49'). Trailing zeros are an artifact of Decimal storage, not
    precision the user should read meaning into."""
    d = _decimal(value)
    return _trim(d) if d is not None else str(value)


def plural_marker(text: str) -> str:
    """Older backend copy writes 'month(s)'. On a screen a person reads,
    the count is right there, so pick one."""
    return text.replace("month(s)", "months").replace("(s)", "s")
