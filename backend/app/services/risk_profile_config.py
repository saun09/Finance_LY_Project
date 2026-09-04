"""Versioned configuration for Module 3 (risk profiling): the stated-risk
questionnaire and the capacity-constraint rule table. Both are plain data,
not embedded in the scoring/capacity logic, so a future revision is a new
version here rather than an edit buried in a function — matching the
project convention that tiers/caps live in explicit, documented,
versioned config, not a black box.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class QuestionOption:
    value: str
    label: str
    points: int


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    weight: int
    options: tuple[QuestionOption, ...]


@dataclass(frozen=True)
class Questionnaire:
    version: str
    effective_date: str
    questions: tuple[Question, ...]
    tier_breakpoints: tuple[int, ...]  # ascending score cutoffs for tiers 2..5

    def option_points(self, question_id: str, value: str) -> int:
        for q in self.questions:
            if q.id == question_id:
                for opt in q.options:
                    if opt.value == value:
                        return opt.points
                raise ValueError(f"question {question_id!r} has no option {value!r}")
        raise ValueError(f"unknown question id {question_id!r}")

    def weight_of(self, question_id: str) -> int:
        for q in self.questions:
            if q.id == question_id:
                return q.weight
        raise ValueError(f"unknown question id {question_id!r}")

    @property
    def max_score(self) -> int:
        return sum(q.weight * max(o.points for o in q.options) for q in self.questions)

    @property
    def min_score(self) -> int:
        return sum(q.weight * min(o.points for o in q.options) for q in self.questions)


_SCALE_5 = (
    QuestionOption("1", "Strongly disagree / lowest", 1),
    QuestionOption("2", "Disagree / low", 2),
    QuestionOption("3", "Neutral / moderate", 3),
    QuestionOption("4", "Agree / high", 4),
    QuestionOption("5", "Strongly agree / highest", 5),
)

QUESTIONNAIRE_V1 = Questionnaire(
    version="v1",
    effective_date="2026-01-01",
    questions=(
        Question(
            id="horizon",
            text="When will you need most of this money?",
            weight=3,
            options=(
                QuestionOption("lt_1y", "Within 1 year", 1),
                QuestionOption("1_3y", "1-3 years", 2),
                QuestionOption("3_7y", "3-7 years", 3),
                QuestionOption("7_15y", "7-15 years", 4),
                QuestionOption("gt_15y", "More than 15 years", 5),
            ),
        ),
        Question(
            id="drawdown_reaction",
            text="If your investments fell 20% in a month, what would you do?",
            weight=3,
            options=(
                QuestionOption("sell_all", "Sell everything immediately", 1),
                QuestionOption("sell_some", "Sell some to limit further loss", 2),
                QuestionOption("hold", "Hold and wait it out", 3),
                QuestionOption("buy_a_little", "Buy a little more if I can", 4),
                QuestionOption("buy_a_lot", "Buy significantly more", 5),
            ),
        ),
        Question(
            id="experience",
            text="How much experience do you have with market-linked investments (equity, mutual funds)?",
            weight=2,
            options=(
                QuestionOption("none", "None", 1),
                QuestionOption("little", "A little (under 2 years)", 2),
                QuestionOption("moderate", "Moderate (2-5 years)", 3),
                QuestionOption("significant", "Significant (5-10 years)", 4),
                QuestionOption("extensive", "Extensive (10+ years)", 5),
            ),
        ),
        Question(
            id="goal",
            text="What best describes your primary goal for this money?",
            weight=2,
            options=(
                QuestionOption("preserve", "Preserve what I have, minimize any loss", 1),
                QuestionOption("income", "Generate steady income", 2),
                QuestionOption("balanced", "Balanced growth and stability", 3),
                QuestionOption("growth", "Grow it meaningfully over time", 4),
                QuestionOption("maximize", "Maximize long-term growth; short-term swings don't bother me", 5),
            ),
        ),
    ),
    # total weight = 10, score range [10, 50]; 4 breakpoints split it into
    # 5 equal-width tiers of 8 points each: [10,18) [18,26) [26,34) [34,42) [42,50]
    tier_breakpoints=(18, 26, 34, 42),
)


QUESTIONNAIRE_V2 = Questionnaire(
    version="v2",
    effective_date="2026-09-04",
    questions=QUESTIONNAIRE_V1.questions
    + (
        Question(
            id="windfall_allocation",
            text="You unexpectedly receive Rs 20,000. What would you do with it?",
            weight=4,
            options=(
                QuestionOption("fd_or_savings", "Put it in a bank FD or savings account", 1),
                QuestionOption("debt_funds", "Invest it in high-quality debt/bond funds", 2),
                QuestionOption("split_debt_equity", "Split it between debt and equity funds", 3),
                QuestionOption("equity_funds", "Invest it in equity mutual funds", 4),
                QuestionOption("equity_plus_borrow", "Invest it in equities, and consider borrowing more to invest further", 5),
            ),
        ),
        # Grable & Lytton (1999)-inspired forced-choice risk item: a
        # guaranteed amount vs. escalating (lower-probability, higher-payout)
        # gambles of roughly similar expected value.
        Question(
            id="sure_gain_tradeoff",
            text="Which would you choose: a guaranteed amount, or a chance at more?",
            weight=4,
            options=(
                QuestionOption("guaranteed_5000", "A guaranteed Rs 5,000", 1),
                QuestionOption("chance_70pct_7000", "A 70% chance at Rs 7,000, otherwise nothing", 2),
                QuestionOption("chance_50pct_10000", "A 50% chance at Rs 10,000, otherwise nothing", 3),
                QuestionOption("chance_30pct_17000", "A 30% chance at Rs 17,000, otherwise nothing", 4),
                QuestionOption("chance_10pct_50000", "A 10% chance at Rs 50,000, otherwise nothing", 5),
            ),
        ),
        Question(
            id="friend_description",
            text="In general, how would your closest friend describe you as a risk-taker with money?",
            weight=2,
            options=(
                QuestionOption("real_risk_avoider", "A real risk avoider", 1),
                QuestionOption("cautious", "Cautious", 2),
                QuestionOption("calculated_after_research", "Willing to take calculated risks after some research", 3),
                QuestionOption("comfortable_for_bigger_rewards", "Comfortable taking risks for a shot at bigger rewards", 4),
                QuestionOption("real_gambler", "A real gambler", 5),
            ),
        ),
    ),
    # total weight = 20 (10 existing + 4 + 4 + 2), score range [20, 100];
    # 4 breakpoints split it into 5 equal-width tiers of 16 points each:
    # [20,36) [36,52) [52,68) [68,84) [84,100]
    tier_breakpoints=(36, 52, 68, 84),
)

assert QUESTIONNAIRE_V2.min_score == 20
assert QUESTIONNAIRE_V2.max_score == 100


@dataclass(frozen=True)
class Band:
    """A half-open [min_value, max_value) band mapping to a ceiling tier.
    max_value=None means unbounded above (the top, uncapped band)."""

    min_value: float
    max_value: float | None
    ceiling: int


@dataclass(frozen=True)
class CapacityRuleTable:
    """Explicit, documented thresholds for each independently-scored
    capacity dimension. Every band is inclusive of `min_value` and
    exclusive of `max_value`, i.e. [min_value, max_value). These are the
    product's own conservative policy, not a regulatory limit — EMI/income
    bands echo common Indian lender eligibility norms (40-50% EMI/income is
    widely treated as a stress threshold) but are this app's own choice.
    """

    version: str
    effective_date: str

    # emergency-fund coverage, in months of essential expense
    buffer_months_bands: tuple[Band, ...]
    # EMI-to-income ratio (0.0-1.0+); LOWER ratio -> HIGHER ceiling, so
    # bands are ordered by descending ratio with ascending ceiling
    emi_to_income_bands: tuple[Band, ...]
    # life-cover-to-required-cover ratio, only evaluated when dependents > 0
    insurance_coverage_bands: tuple[Band, ...]
    # income stability is binary in the data Module 2 captures, so this is
    # a flat ceiling per state rather than a banded table
    irregular_income_ceiling: int
    regular_income_ceiling: int
    # standard personal-finance thumb rule: life cover should be >= this
    # multiple of annual income when there are dependents to protect
    required_life_cover_income_multiple: int


CAPACITY_RULE_TABLE_V1 = CapacityRuleTable(
    version="v1",
    effective_date="2026-01-01",
    buffer_months_bands=(
        Band(0, 1, 1),
        Band(1, 2, 2),
        Band(2, 4, 3),
        Band(4, 6, 4),
        Band(6, None, 5),
    ),
    emi_to_income_bands=(
        Band(0.50, None, 1),  # >= 50% -> most severe
        Band(0.40, 0.50, 2),
        Band(0.30, 0.40, 3),
        Band(0.20, 0.30, 4),
        Band(0.0, 0.20, 5),  # < 20% -> no ceiling
    ),
    insurance_coverage_bands=(
        Band(0.0, 0.25, 1),
        Band(0.25, 0.5, 2),
        Band(0.5, 0.75, 3),
        Band(0.75, 1.0, 4),
        Band(1.0, None, 5),
    ),
    irregular_income_ceiling=3,
    regular_income_ceiling=5,
    required_life_cover_income_multiple=10,
)
