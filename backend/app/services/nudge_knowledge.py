"""The knowledge base behind Nudge, the ElevenLabs voice assistant.

The voice agent itself runs on ElevenLabs and knows nothing about the user.
This module turns everything the app already knows about one user -- loans,
debt-payoff strategy, expenses, leaks, emergency buffer, insurance,
holdings, risk tier, target allocation, milestones, and what they talked
to Nudge about before -- into short plain-text `KnowledgeChunk`s, and
retrieves the ones relevant to a question. That gives the agent two ways
to see the user's whole picture:

1. `build_session_briefing` -- a compact summary sent once as a contextual
   update when a conversation starts, so every answer is holistic by
   default (a question about investing is answered knowing about the 18%
   personal loan).
2. `retrieve` -- TF-IDF retrieval over the chunks, behind the agent's
   `search_user_finances` client tool, for detail the briefing leaves out
   (one loan's exact tenure, a past conversation, a specific leak).

TF-IDF rather than embeddings: one user's corpus is a few dozen short
chunks, rebuilt fresh on every call, so a vector database or an embedding
API would add a network dependency and a second copy of the user's
finances without improving recall at this size. Each topic also carries a
keyword list (`TOPIC_KEYWORDS`) indexed alongside its text, so "how much do
I owe" still finds the loans chunk without the word "loan" in the query.

Read-only: nothing here writes a suggestion_event. The debt/leak and
allocation services log a row whenever their output changes, so this
module calls their pure engines (or reads their latest logged row)
instead of their `compute_and_log_*` entry points -- asking Nudge a
question must not look like the user viewed a new suggestion.

Holding `description`s are freeform user text and, per Module 4's
constraint, never leave the app -- holdings are described by
`holding_type` only.
"""

from dataclasses import dataclass
from datetime import date

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.nudge import NudgeConversation, NudgeMessage
from app.models.onboarding import EmiEntry, ExpenseItem, Holding, InsurancePolicy
from app.services.debt_engine import DebtInput, compare_avalanche_vs_snowball, prepay_vs_invest_analysis
from app.services.event_log import get_user_event_history
from app.services.financial_position import EmiInput, ExpenseFrequency, compute_outstanding_principal
from app.services.gamification_service import get_milestone_history
from app.services.leak_engine import ExpenseItemInput, build_leak_report
from app.services.onboarding import compute_financial_position, get_profile

DEFAULT_TOP_K = 4
# past conversations folded into the session briefing, and how much of each
BRIEFING_PAST_CONVERSATIONS = 2
BRIEFING_LINES_PER_CONVERSATION = 6
MAX_LINE_CHARS = 300

TOPIC_KEYWORDS: dict[str, str] = {
    "overview": "overview summary net worth surplus savings income cash buffer emergency fund financial health position",
    "profile": "income salary job employment dependents family age stability",
    "loans": "loan loans debt debts emi borrowing owe interest rate lender outstanding principal repay repayment tenure",
    "debt_strategy": "debt payoff strategy avalanche snowball prepay prepayment invest extra payment interest saved clear debt free",
    "closed_loans": "closed loan repaid paid off cleared debt history",
    "expenses": "expenses spending budget rent bills essential discretionary monthly costs",
    "leaks": "leak leaks waste save money recoverable fees idle cash subscriptions recurring charges cut",
    "insurance": "insurance cover life health term policy protection sum assured",
    "holdings": "holdings investments portfolio savings mutual fund fixed deposit stocks equity ppf epf nps",
    "risk_profile": "risk profile tier tolerance capacity appetite conservative aggressive",
    "allocation": "allocation target mix rebalance equity debt cash asset class portfolio drift",
    "milestones": "milestones achievements progress badges goals",
    "conversation": "previous conversation earlier discussed talked asked said last time remember",
}


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    topic: str
    text: str


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: KnowledgeChunk
    score: float


def _indian_grouping(rupees: int) -> str:
    sign = "-" if rupees < 0 else ""
    digits = str(abs(rupees))
    if len(digits) <= 3:
        return sign + digits
    last3, rest = digits[-3:], digits[:-3]
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return sign + ",".join(groups) + "," + last3


def _rupees(paise: int) -> str:
    return f"Rs {_indian_grouping(round(paise / 100))}"


def _pct_from_bps(bps: int) -> str:
    return f"{bps / 100:.2f}%"


def _label(value) -> str:
    raw = value.value if hasattr(value, "value") else str(value)
    return raw.replace("_", " ")


def _monthly_equivalent(amount_paise: int, frequency: ExpenseFrequency) -> int:
    if frequency == ExpenseFrequency.MONTHLY:
        return amount_paise
    if frequency == ExpenseFrequency.ANNUAL:
        return round(amount_paise / 12)
    return 0


def _age(dob: date | None) -> int | None:
    if dob is None:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _truncate(text: str, limit: int = MAX_LINE_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# --------------------------------------------------------------------------
# Chunk builders
# --------------------------------------------------------------------------


def build_financial_chunks(session: Session, user_id: str) -> list[KnowledgeChunk]:
    profile = get_profile(session, user_id)
    if profile is None:
        return [
            KnowledgeChunk(
                "overview",
                "overview",
                "This user has not completed onboarding yet, so the app has no income, loan, expense or "
                "savings details for them. Answer generally and suggest finishing onboarding for personalised advice.",
            )
        ]

    chunks: list[KnowledgeChunk] = []
    position = compute_financial_position(session, user_id)

    buffer_months = position["buffer_coverage_months"]
    chunks.append(
        KnowledgeChunk(
            "overview",
            "overview",
            f"Financial overview: monthly take-home income {_rupees(profile.income_paise)}; "
            f"total monthly expenses {_rupees(position['total_monthly_expenses_paise'])} "
            f"(essential {_rupees(position['essential_monthly_expense_paise'])}); "
            f"total monthly EMIs {_rupees(position['total_monthly_emi_paise'])}; "
            f"monthly surplus after expenses and EMIs {_rupees(position['monthly_surplus_paise'])}. "
            f"Cash balance {_rupees(profile.cash_balance_paise)}, which covers {buffer_months} months of essential "
            f"expenses (emergency buffer). EMI-to-income ratio {float(position['emi_to_income_ratio']) * 100:.1f}%. "
            f"Net worth (cash + holdings - outstanding loans) {_rupees(position['net_worth_paise'])}.",
        )
    )

    age = _age(profile.date_of_birth)
    chunks.append(
        KnowledgeChunk(
            "profile",
            "profile",
            "Profile: "
            + (f"{profile.full_name}, " if profile.full_name else "")
            + (f"age {age}, " if age is not None else "")
            + f"employment {_label(profile.employment_type)}, income stability {_label(profile.income_stability)}, "
            f"{profile.dependents_count} dependent(s).",
        )
    )

    chunks.extend(_loan_chunks(session, user_id, position["monthly_surplus_paise"]))
    chunks.extend(_expense_and_leak_chunks(session, user_id, profile.cash_balance_paise, position))
    chunks.extend(_insurance_chunks(session, user_id, profile.dependents_count, profile.income_paise))
    chunks.extend(_holding_chunks(session, user_id))
    chunks.extend(_risk_and_allocation_chunks(session, user_id))

    milestones = get_milestone_history(session, user_id)
    if milestones:
        chunks.append(
            KnowledgeChunk(
                "milestones",
                "milestones",
                "Milestones earned in the app: " + "; ".join(m.headline for m in milestones) + ".",
            )
        )
    return chunks


def _loan_chunks(session: Session, user_id: str, monthly_surplus_paise: int) -> list[KnowledgeChunk]:
    rows = session.execute(select(EmiEntry).where(EmiEntry.user_id == user_id)).scalars().all()
    active = [e for e in rows if e.closed_at is None]
    closed = [e for e in rows if e.closed_at is not None]
    chunks: list[KnowledgeChunk] = []

    if not active:
        chunks.append(KnowledgeChunk("loans", "loans", "Loans: the user has no active loans or EMIs recorded."))

    names: dict[str, str] = {}
    debts: list[DebtInput] = []
    for e in sorted(active, key=lambda e: -e.annual_rate_bps):
        name = f"{e.lender}" + (f" ({_label(e.purpose)} loan)" if e.purpose else "")
        names[e.id] = name
        principal = compute_outstanding_principal(
            EmiInput(amount_paise=e.amount_paise, remaining_tenure_months=e.remaining_tenure_months, annual_rate_bps=e.annual_rate_bps)
        )
        remaining_interest = max(0, e.amount_paise * e.remaining_tenure_months - principal)
        debts.append(DebtInput(debt_id=e.id, outstanding_principal_paise=principal, monthly_payment_paise=e.amount_paise, annual_rate_bps=e.annual_rate_bps))
        chunks.append(
            KnowledgeChunk(
                f"loan:{e.id}",
                "loans",
                f"Loan from {name}: EMI {_rupees(e.amount_paise)} per month at {_pct_from_bps(e.annual_rate_bps)} a year, "
                f"{e.remaining_tenure_months} months remaining, about {_rupees(principal)} outstanding principal and "
                f"about {_rupees(remaining_interest)} of interest still to pay if run to term.",
            )
        )

    if active:
        chunks.append(
            KnowledgeChunk(
                "loans:summary",
                "loans",
                f"Loans summary: {len(active)} active loan(s), highest rate first: "
                + "; ".join(f"{names[d.debt_id]} at {_pct_from_bps(d.annual_rate_bps)}" for d in debts)
                + f". Total outstanding about {_rupees(sum(d.outstanding_principal_paise for d in debts))}.",
            )
        )

    surplus = max(0, monthly_surplus_paise)
    if debts and surplus > 0:
        comparison = compare_avalanche_vs_snowball(debts, surplus)
        top = max(debts, key=lambda d: d.annual_rate_bps)
        prepay = prepay_vs_invest_analysis(top, surplus)
        order = ", ".join(names.get(d, d) for d in comparison.avalanche.payoff_order)
        chunks.append(
            KnowledgeChunk(
                "debt_strategy",
                "debt_strategy",
                f"Debt payoff strategy (putting the full monthly surplus of {_rupees(surplus)} toward debt): "
                f"avalanche (highest rate first, order: {order}) clears everything in {comparison.avalanche.months_to_clear_all} months "
                f"with {_rupees(comparison.avalanche.total_interest_paise)} total interest; snowball (smallest balance first) takes "
                f"{comparison.snowball.months_to_clear_all} months with {_rupees(comparison.snowball.total_interest_paise)} interest. "
                f"Avalanche saves {_rupees(comparison.interest_saved_by_avalanche_paise)} and {comparison.months_saved_by_avalanche} months. "
                f"Prepaying the highest-rate loan ({names[top.debt_id]}) with that surplus is a guaranteed "
                f"{prepay.guaranteed_annual_rate_pct}% return, saving {_rupees(prepay.interest_saved_paise)} interest and "
                f"{prepay.months_saved} months. {prepay.framing_note}",
            )
        )
    elif debts:
        chunks.append(
            KnowledgeChunk(
                "debt_strategy",
                "debt_strategy",
                "Debt payoff strategy: the user currently has no monthly surplus, so there is no spare cash for "
                "extra loan payments; freeing up surplus (cutting expenses or leaks) comes before faster payoff.",
            )
        )

    if closed:
        chunks.append(
            KnowledgeChunk(
                "closed_loans",
                "closed_loans",
                "Loans already closed/repaid: "
                + "; ".join(f"{e.lender} (closed {e.closed_at.date().isoformat()})" for e in closed)
                + ".",
            )
        )
    return chunks


def _expense_and_leak_chunks(session: Session, user_id: str, cash_balance_paise: int, position: dict) -> list[KnowledgeChunk]:
    rows = session.execute(
        select(ExpenseItem).where(ExpenseItem.user_id == user_id, ExpenseItem.removed_at.is_(None))
    ).scalars().all()
    chunks: list[KnowledgeChunk] = []
    if rows:
        def _describe(items):
            items = sorted(items, key=lambda e: -_monthly_equivalent(e.amount_paise, e.frequency))
            return "; ".join(
                f"{e.category} {_rupees(e.amount_paise)} {_label(e.frequency)}" for e in items
            ) or "none"

        chunks.append(
            KnowledgeChunk(
                "expenses",
                "expenses",
                f"Expenses -- essential: {_describe([e for e in rows if e.is_essential])}. "
                f"Discretionary: {_describe([e for e in rows if not e.is_essential])}.",
            )
        )

    leak = build_leak_report(
        cash_balance_paise,
        position["essential_monthly_expense_paise"],
        [
            ExpenseItemInput(item_id=e.id, category=e.category, amount_paise=e.amount_paise, frequency=e.frequency, is_essential=e.is_essential)
            for e in rows
        ],
    )
    if leak.components:
        chunks.append(
            KnowledgeChunk(
                "leaks",
                "leaks",
                f"Money leaks: about {_rupees(leak.total_recoverable_annual_paise)} a year is recoverable. "
                + " ".join(
                    f"{c.label}: {_rupees(c.annual_amount_paise)}/year -- {c.explanation} Action: {c.concrete_action}"
                    for c in leak.components
                ),
            )
        )
    if leak.recurring_candidates:
        chunks.append(
            KnowledgeChunk(
                "leaks:recurring",
                "leaks",
                "Recurring charges worth reviewing: "
                + "; ".join(f"{c.category} ({_rupees(c.annual_amount_paise)}/year)" for c in leak.recurring_candidates)
                + ".",
            )
        )
    return chunks


def _insurance_chunks(session: Session, user_id: str, dependents: int, income_paise: int) -> list[KnowledgeChunk]:
    policies = session.execute(select(InsurancePolicy).where(InsurancePolicy.user_id == user_id)).scalars().all()
    if not policies:
        return [
            KnowledgeChunk(
                "insurance",
                "insurance",
                f"Insurance: no life or health insurance policies are recorded for this user ({dependents} dependent(s)).",
            )
        ]
    text = "Insurance: " + "; ".join(f"{_label(p.policy_type)} cover of {_rupees(p.sum_assured_paise)}" for p in policies) + "."
    types = {p.policy_type.value for p in policies}
    missing = [t for t in ("life", "health") if t not in types]
    if missing:
        text += f" No {' or '.join(missing)} insurance recorded."
    life_cover = sum(p.sum_assured_paise for p in policies if p.policy_type.value == "life")
    if life_cover and income_paise:
        text += f" Life cover equals about {life_cover / (income_paise * 12):.1f} years of income."
    return [KnowledgeChunk("insurance", "insurance", text)]


def _holding_chunks(session: Session, user_id: str) -> list[KnowledgeChunk]:
    holdings = session.execute(select(Holding).where(Holding.user_id == user_id)).scalars().all()
    if not holdings:
        return [KnowledgeChunk("holdings", "holdings", "Holdings: no savings or investment holdings are recorded.")]
    by_type: dict[str, int] = {}
    for h in holdings:
        key = _label(h.holding_type) if h.holding_type else "unclassified"
        by_type[key] = by_type.get(key, 0) + h.value_paise
    total = sum(by_type.values())
    return [
        KnowledgeChunk(
            "holdings",
            "holdings",
            f"Holdings (total {_rupees(total)}): "
            + "; ".join(f"{k} {_rupees(v)}" for k, v in sorted(by_type.items(), key=lambda kv: -kv[1]))
            + ".",
        )
    ]


def _risk_and_allocation_chunks(session: Session, user_id: str) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    risk = get_user_event_history(session, user_id, module_source="risk_profile", limit=1)
    if risk:
        v = risk[0].suggested_value
        text = (
            f"Risk profile: stated risk tier {v['stated_tier']} of 5, financial capacity ceiling {v['capacity_ceiling']}, "
            f"final tier {v['final_tier']}."
        )
        if v.get("capped"):
            text += f" The tier was capped by: {', '.join(v.get('binding_constraints', []))}."
            if v.get("unlock_conditions"):
                text += f" To unlock a higher tier: {v['unlock_conditions']}."
        chunks.append(KnowledgeChunk("risk_profile", "risk_profile", text))
    else:
        chunks.append(KnowledgeChunk("risk_profile", "risk_profile", "Risk profile: the user has not taken the risk questionnaire yet."))

    allocation = get_user_event_history(session, user_id, module_source="allocation", limit=1)
    if allocation:
        v = allocation[0].suggested_value
        target = v.get("displayed_target_pct") or v.get("target_pct", {})
        current = v.get("current_exposure_pct", {})
        classes = sorted(set(target) | set(current))
        chunks.append(
            KnowledgeChunk(
                "allocation",
                "allocation",
                f"Target asset allocation for tier {v.get('final_tier')}: "
                + "; ".join(
                    f"{_label(ac)} target {float(target.get(ac, 0)):.0f}% vs current {float(current.get(ac, 0)):.0f}%"
                    for ac in classes
                )
                + ".",
            )
        )
    return chunks


def build_conversation_chunks(
    session: Session, user_id: str, *, exclude_conversation_id: str | None = None, limit: int = 20
) -> list[KnowledgeChunk]:
    """One chunk per user question + Nudge's reply, from the user's most
    recent stored conversations, so the agent can recall what was said."""
    conversations = session.execute(
        select(NudgeConversation)
        .where(NudgeConversation.user_id == user_id)
        .order_by(NudgeConversation.started_at.desc())
        .limit(limit)
    ).scalars().all()

    chunks: list[KnowledgeChunk] = []
    for conv in conversations:
        if conv.id == exclude_conversation_id:
            continue
        messages = list_messages(session, conv.id)
        day = conv.started_at.date().isoformat()
        for i, msg in enumerate(messages):
            if msg.role != "user":
                continue
            reply = next((m for m in messages[i + 1 :] if m.role == "agent"), None)
            text = f"In a past conversation on {day}, the user said: \"{_truncate(msg.text)}\""
            if reply is not None:
                text += f" Nudge replied: \"{_truncate(reply.text)}\""
            chunks.append(KnowledgeChunk(f"conversation:{msg.id}", "conversation", text))
    return chunks


def list_messages(session: Session, conversation_id: str) -> list[NudgeMessage]:
    return list(
        session.execute(
            select(NudgeMessage)
            .where(NudgeMessage.conversation_id == conversation_id)
            .order_by(NudgeMessage.created_at, NudgeMessage.id)
        ).scalars()
    )


# --------------------------------------------------------------------------
# Retrieval and briefing
# --------------------------------------------------------------------------


def retrieve(chunks: list[KnowledgeChunk], query: str, k: int = DEFAULT_TOP_K) -> list[RetrievedChunk]:
    """Top-k chunks by TF-IDF cosine similarity to `query`. Falls back to
    the overview chunk when nothing matches at all, so the agent always gets
    *something* grounded back rather than an empty tool result."""
    if not chunks:
        return []
    documents = [f"{TOPIC_KEYWORDS.get(c.topic, '')} {c.text}" for c in chunks]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    try:
        matrix = vectorizer.fit_transform(documents)
    except ValueError:  # every document was stop words only
        return [RetrievedChunk(chunks[0], 0.0)]
    scores = linear_kernel(vectorizer.transform([query]), matrix).ravel()

    ranked = sorted(range(len(chunks)), key=lambda i: -scores[i])
    hits = [RetrievedChunk(chunks[i], float(scores[i])) for i in ranked[:k] if scores[i] > 0]
    if hits:
        return hits
    overview = next((c for c in chunks if c.topic == "overview"), chunks[0])
    return [RetrievedChunk(overview, 0.0)]


def search_user_knowledge(
    session: Session, user_id: str, query: str, *, k: int = DEFAULT_TOP_K, exclude_conversation_id: str | None = None
) -> list[RetrievedChunk]:
    chunks = build_financial_chunks(session, user_id) + build_conversation_chunks(
        session, user_id, exclude_conversation_id=exclude_conversation_id
    )
    return retrieve(chunks, query, k)


# topics the briefing always includes -- the ones that change what "good
# advice" is for almost any question (debt and buffer before investing, etc.)
BRIEFING_TOPICS = ("overview", "profile", "loans", "debt_strategy", "leaks", "insurance", "risk_profile", "allocation", "holdings")


def build_session_briefing(session: Session, user_id: str, surface: str, *, exclude_conversation_id: str | None = None) -> str:
    chunks = build_financial_chunks(session, user_id)
    by_topic = [c for topic in BRIEFING_TOPICS for c in chunks if c.topic == topic and not c.chunk_id.startswith("loan:")]
    # individual loan lines go in too when there are only a few; otherwise
    # the loans summary is enough and the tool can fetch the details
    loan_lines = [c for c in chunks if c.chunk_id.startswith("loan:")]
    if len(loan_lines) <= 4:
        by_topic += loan_lines

    lines = [
        "USER FINANCIAL CONTEXT (from the app's own records; amounts in Indian rupees).",
        "Use this to give holistic advice: weigh any question against the user's loans, buffer, expenses, insurance "
        "and risk tier, and point out conflicts (e.g. investing while carrying high-interest debt). "
        "Quote the user's own numbers where helpful. For details not listed here -- a specific loan, expense, "
        "or something discussed before -- call the search_user_finances tool with a short query.",
        f"The user opened this conversation from the '{surface}' screen.",
        "",
    ]
    lines += [c.text for c in by_topic]

    memory = _recent_conversation_memory(session, user_id, exclude_conversation_id)
    if memory:
        lines += ["", "RECENT CONVERSATIONS WITH NUDGE (most recent first):", *memory]
    return "\n".join(lines)


def _recent_conversation_memory(session: Session, user_id: str, exclude_conversation_id: str | None) -> list[str]:
    conversations = session.execute(
        select(NudgeConversation)
        .where(NudgeConversation.user_id == user_id)
        .order_by(NudgeConversation.started_at.desc())
        .limit(BRIEFING_PAST_CONVERSATIONS + 1)
    ).scalars().all()
    memory: list[str] = []
    shown = 0
    for conv in conversations:
        if conv.id == exclude_conversation_id or shown >= BRIEFING_PAST_CONVERSATIONS:
            continue
        messages = list_messages(session, conv.id)[-BRIEFING_LINES_PER_CONVERSATION:]
        if not messages:
            continue
        shown += 1
        memory.append(f"- {conv.started_at.date().isoformat()} (from {conv.surface}):")
        memory += [f"    {'User' if m.role == 'user' else 'Nudge'}: {_truncate(m.text)}" for m in messages]
    return memory


def format_search_results(results: list[RetrievedChunk]) -> str:
    """The plain-text tool result handed back to the voice agent."""
    if not results:
        return "No matching information about this user was found in the app."
    return "\n".join(f"- {r.chunk.text}" for r in results)
