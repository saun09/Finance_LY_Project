"""Module 10: versioned milestone catalog and thresholds.

HARD RULE, ENFORCED HERE AT IMPORT TIME, NOT JUST DOCUMENTED: every
milestone rewards an EFFORT signal (a contribution, an action taken, a
consistency streak) and NEVER an OUTCOME signal (market returns, holding
or portfolio value change). Conflating the two is a bug, not a style
choice — see `SignalType` and `_assert_all_effort_signals` below, which
runs the instant this module is imported. A future contributor adding an
outcome-typed milestone to `MILESTONE_CATALOG` doesn't get a code-review
comment; the app fails to start.

Concretely, this module never reads Module 4's `current_exposure_paise`,
`current_exposure_pct`, or `total_value_paise` (portfolio value / market
exposure), and never will — every signal below comes from Module 2's own
declared inputs (buffer months, EMI principal, expense line items,
monthly surplus) or Module 3's rule-table output (capacity ceiling), none
of which move because a market did.

Hard exclusions (also enforced structurally, not just by omission): no
leaderboard or cross-user comparison — every function in this module
takes exactly one `user_id` and never queries across users. No streak for
merely opening the app — this module has no access to any "app opened"
event type in Module 1's schema in the first place, and never will.
"""

from dataclasses import dataclass
from enum import Enum

CONFIG_VERSION = "v1"
CONFIG_EFFECTIVE_DATE = "2026-01-01"

# Buffer-month milestones deliberately reuse Module 3's own capacity rule
# table band edges (see risk_profile_config.py), rather than introducing a
# second, potentially-drifting set of "meaningful" buffer thresholds.
BUFFER_MONTHS_THRESHOLDS: tuple[int, ...] = (1, 2, 4, 6)

SUBSCRIPTION_CANCELLED_COUNT_THRESHOLDS: tuple[int, ...] = (1, 3, 5)
CONSISTENCY_MONTH_THRESHOLDS: tuple[int, ...] = (3, 6, 12)


class SignalType(str, Enum):
    EFFORT = "effort"
    OUTCOME = "outcome"  # exists only so the import-time guard has something to reject; no real milestone may use this


class Category(str, Enum):
    BUFFER = "buffer"
    CAPACITY_UNLOCK = "capacity_unlock"  # the one "real" progression mechanic -- see module docstring
    DEBT = "debt"
    SUBSCRIPTIONS = "subscriptions"
    CONSISTENCY = "consistency"


@dataclass(frozen=True)
class RoadmapTopic:
    topic_id: str
    title: str
    description: str


@dataclass(frozen=True)
class RoadmapLevel:
    level: int
    title: str
    topics: tuple[RoadmapTopic, ...]


@dataclass(frozen=True)
class QuizQuestion:
    topic_id: str
    prompt: str
    options: tuple[str, ...]
    answer_index: int
    explanation: str


ROADMAP: tuple[RoadmapLevel, ...] = (
    RoadmapLevel(1, "Financial Basics", tuple(RoadmapTopic(*topic) for topic in (
        ("income-expenses", "Income vs expenses", "See where money comes from and where it goes."),
        ("needs-wants", "Needs vs wants", "Separate essentials from choices you can adjust."),
        ("budgeting", "Budgeting and cash flow", "Plan a realistic month and track expenses."),
        ("emergency-fund", "Emergency funds", "Protect everyday life from unexpected costs."),
        ("inflation-interest", "Inflation and interest", "Understand purchasing power, simple interest, and compound interest."),
    ))),
    RoadmapLevel(2, "Financial Safety", tuple(RoadmapTopic(*topic) for topic in (
        ("buffer-insurance", "Buffers and insurance", "Build resilience with an emergency buffer and appropriate cover."),
        ("health-life-insurance", "Health and life insurance", "Learn what each type of cover is for."),
        ("high-interest-debt", "High-interest debt", "Spot expensive debt and make a payoff plan."),
        ("credit-score", "Credit scores", "Understand the habits that support a healthy credit history."),
        ("subscriptions-documents", "Subscriptions and documents", "Review recurring costs and organise important records."),
    ))),
    RoadmapLevel(3, "Banking & Saving", tuple(RoadmapTopic(*topic) for topic in (
        ("savings-accounts", "Savings accounts", "Compare access, safety, and interest for available cash."),
        ("fd-rd", "FDs and RDs", "Understand fixed and recurring deposits."),
        ("sweep-liquidity", "Sweep-in FDs and liquidity", "Match access to money with the goal's time horizon."),
        ("post-tax-returns", "Interest, tax, and post-tax returns", "Compare what remains after tax, not only advertised rates."),
        ("tax-efficient-savings", "Tax-efficient savings", "Explore legally applicable options and verify current Indian tax rules."),
    ))),
    RoadmapLevel(4, "Investing Basics", tuple(RoadmapTopic(*topic) for topic in (
        ("saving-investing", "Saving vs investing", "Know why investing carries uncertainty beyond saving."),
        ("risk-return", "Risk, return, and volatility", "Connect time horizon and uncertainty without chasing returns."),
        ("asset-classes", "Equity, debt, gold, and securities", "Meet the main asset classes, including government securities."),
        ("funds-etfs", "Mutual funds, index funds, and ETFs", "Understand pooled and index-tracking approaches."),
        ("diversification-allocation", "Diversification and asset allocation", "Spread risk and set a deliberate mix."),
        ("sips-goals", "SIPs and time horizons", "Use manageable contributions for suitable long-term goals."),
    ))),
    RoadmapLevel(5, "Taxes & Retirement", tuple(RoadmapTopic(*topic) for topic in (
        ("income-tax", "Income-tax basics", "Learn the vocabulary before making tax decisions."),
        ("tax-saving-capital-gains", "Tax-saving investments and capital gains", "Understand that treatment differs by product and can change."),
        ("epf-ppf-nps", "EPF, PPF, and NPS", "Compare the purpose and broad features of retirement accounts."),
        ("retirement-planning", "Retirement planning", "Turn a future need into a time-bound goal."),
        ("pre-tax-post-tax", "Pre-tax vs post-tax returns", "Verify current rules and your circumstances before acting."),
    )))
)

QUIZ_QUESTIONS: tuple[QuizQuestion, ...] = (
    QuizQuestion("income-expenses", "Which statement best describes cash flow?", ("Money in minus money out", "Only your salary", "Your investment returns"), 0, "Cash flow is the money entering and leaving your household."),
    QuizQuestion("budgeting", "What is the main purpose of a budget?", ("To spend every rupee", "To plan how income will be used", "To predict market returns"), 1, "A budget gives each rupee a job before the month unfolds."),
    QuizQuestion("emergency-fund", "What is an emergency fund mainly for?", ("Planned holidays", "Unexpected essential costs", "Buying risky investments"), 1, "It protects essential spending when income or plans are disrupted."),
    QuizQuestion("inflation-interest", "What does inflation generally do to purchasing power?", ("Increases it", "Leaves it unchanged", "Reduces it over time"), 2, "As prices rise, the same amount of money usually buys less."),
    QuizQuestion("buffer-insurance", "Insurance is primarily designed to transfer which risk?", ("The cost of a covered loss", "The risk of every investment", "The need to budget"), 0, "Insurance helps protect against specified, financially significant losses."),
    QuizQuestion("high-interest-debt", "Which debt usually deserves earlier attention?", ("The highest-interest debt", "The newest debt regardless of rate", "Debt with the smallest balance only"), 0, "Paying down expensive interest can prevent the balance from compounding."),
    QuizQuestion("credit-score", "Which habit generally supports a healthy credit history?", ("Missing payments", "Paying obligations on time", "Applying for every card"), 1, "Payment history and responsible borrowing matter to credit health."),
    QuizQuestion("savings-accounts", "What is a key feature of a savings account?", ("Usually easier access to cash", "Guaranteed equity returns", "No bank rules"), 0, "Savings accounts are generally intended for accessible cash, subject to account terms."),
    QuizQuestion("fd-rd", "What is an RD designed for?", ("Regular periodic deposits", "Daily stock trading", "Insurance claims"), 0, "A recurring deposit accepts regular contributions for a defined period."),
    QuizQuestion("post-tax-returns", "Why compare post-tax returns?", ("Tax can change what you keep", "Advertised rates are always wrong", "Taxes only affect equity"), 0, "The useful comparison is the amount left after applicable tax."),
    QuizQuestion("saving-investing", "How does investing differ from saving?", ("Investing usually involves more uncertainty", "Saving always loses money", "They are identical"), 0, "Investing can grow over time but values may fluctuate and losses are possible."),
    QuizQuestion("risk-return", "What is volatility?", ("A measure of price movement", "A guaranteed loss", "A type of bank account"), 0, "Volatility describes how much and how quickly an investment value moves."),
    QuizQuestion("funds-etfs", "What does diversification aim to do?", ("Spread exposure across investments", "Guarantee a profit", "Remove every risk"), 0, "Holding different assets can reduce reliance on one investment or risk."),
    QuizQuestion("diversification-allocation", "Asset allocation means deciding the mix between what?", ("Asset classes", "Bank branches", "Tax forms"), 0, "It is the deliberate split across assets such as cash, debt, and equity."),
    QuizQuestion("sips-goals", "A time horizon is the period until what?", ("You need the goal's money", "The market opens", "A bank statement arrives"), 0, "Goals with different timelines may need different levels of uncertainty."),
    QuizQuestion("income-tax", "Why should current tax rules be verified?", ("Rules and circumstances can change", "Tax never changes", "Only banks know tax"), 0, "Tax treatment depends on current law and the user's circumstances."),
    QuizQuestion("epf-ppf-nps", "What is a common purpose of EPF, PPF, and NPS?", ("Long-term retirement planning", "Short-term grocery spending", "Daily trading"), 0, "These instruments are commonly used as part of long-term retirement planning."),
    QuizQuestion("retirement-planning", "What makes a retirement goal more useful?", ("A time horizon and an estimated need", "No target at all", "Following daily market prices"), 0, "A timeframe and estimated spending need make planning more concrete."),
)

CHECKLIST: tuple[tuple[str, str, str], ...] = (
    ("foundation", "Track monthly income and expenses", "Financial foundation"),
    ("budget", "Create a basic monthly budget", "Financial foundation"),
    ("recurring-costs", "Identify unnecessary recurring expenses", "Financial foundation"),
    ("debt-plan", "Pay off or plan for high-interest debt", "Financial foundation"),
    ("initial-buffer", "Build an initial emergency fund", "Financial foundation"),
    ("buffer-3-6", "Work towards 3–6 months of essential expenses", "Financial foundation"),
    ("health-cover", "Have adequate health insurance", "Financial foundation"),
    ("life-cover", "Evaluate whether life insurance is required", "Financial foundation"),
    ("documents", "Organise important financial documents", "Financial foundation"),
    ("beneficiaries", "Nominate beneficiaries where applicable", "Financial foundation"),
    ("savings-balance", "Maintain an appropriate savings balance", "Savings"),
    ("fd-rd-basics", "Understand FDs, RDs, rates, liquidity, and tax", "Savings"),
    ("short-long-term", "Keep short-term money separate from long-term investments", "Savings"),
    ("goals-horizon", "Define goals and assign a time horizon", "Investing"),
    ("risk-tolerance", "Understand your risk tolerance", "Investing"),
    ("diversification", "Learn about diversification and asset allocation", "Investing"),
    ("manageable-contribution", "Start with an appropriate, manageable contribution", "Investing"),
    ("consistent-contributions", "Set up consistent contributions where appropriate", "Investing"),
    ("periodic-review", "Review allocation periodically, not daily market moves", "Investing"),
    ("roadmap-complete", "Complete the beginner financial-literacy roadmap", "Financial literacy"),
    ("module-quizzes", "Complete short quizzes after each topic", "Financial literacy"),
    ("final-assessment", "Complete a final financial-health assessment", "Financial literacy"),
)

BADGES: tuple[tuple[str, str, str], ...] = (
    ("budget-beginner", "Budget Beginner", "Completed the budgeting module"),
    ("emergency-ready", "Emergency Ready", "Learned how emergency funds work"),
    ("debt-aware", "Debt Aware", "Completed the debt-management module"),
    ("investing-101", "Investing 101", "Completed investing fundamentals"),
    ("tax-smart", "Tax Smart", "Completed basic tax education"),
    ("diversification-pro", "Diversification Pro", "Passed the diversification quiz"),
    ("foundations-complete", "Financial Foundations Complete", "Completed the beginner roadmap"),
)


@dataclass(frozen=True)
class MilestoneDefinition:
    category: Category
    signal_type: SignalType
    description: str


# One entry per *category* (not per threshold instance -- individual
# thresholds are generated at detection time from the tuples above). This
# is the thing _assert_all_effort_signals checks.
MILESTONE_CATALOG: tuple[MilestoneDefinition, ...] = (
    MilestoneDefinition(
        Category.BUFFER, SignalType.EFFORT,
        "Emergency-buffer months reached a new threshold -- built from Module 2's own declared cash/expenses.",
    ),
    MilestoneDefinition(
        Category.CAPACITY_UNLOCK, SignalType.EFFORT,
        "Module 3's capacity ceiling rose -- the underlying cause is always an effort signal (more buffer, "
        "lower EMI burden, more insurance cover, or income becoming regular), never a market outcome.",
    ),
    MilestoneDefinition(
        Category.DEBT, SignalType.EFFORT,
        "All EMI debt closed (via Module 2's close_emi) -- an action taken, not a balance that happened to rise.",
    ),
    MilestoneDefinition(
        Category.SUBSCRIPTIONS, SignalType.EFFORT,
        "A recurring, subscription-like expense item was explicitly removed (Module 2's remove_expense_item) "
        "-- an action taken in response to Module 6's leak detection, not an automatic saving.",
    ),
    MilestoneDefinition(
        Category.CONSISTENCY, SignalType.EFFORT,
        "Consecutive months of positive surplus -- a cash-flow discipline signal, not a return.",
    ),
)


class GamificationOutcomeSignalError(RuntimeError):
    pass


def _assert_all_effort_signals(catalog: tuple[MilestoneDefinition, ...]) -> None:
    offending = [m.category.value for m in catalog if m.signal_type != SignalType.EFFORT]
    if offending:
        raise GamificationOutcomeSignalError(
            f"milestone categor(y/ies) {offending} declare a non-effort signal_type. Outcome-based "
            "milestones (market returns, portfolio/holding value change) are a bug in this module, not "
            "a style choice -- see gamification_config.py's module docstring before changing this."
        )


_assert_all_effort_signals(MILESTONE_CATALOG)
