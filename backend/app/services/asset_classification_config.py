"""Versioned asset-classification taxonomy for Module 4.

`HoldingType` is a controlled vocabulary of what a holding *is* (the
category the user selects when entering it in Module 2 — e.g. "PPF",
"ELSS", "ULIP" — never a named fund/scheme/stock). `HOLDING_TYPE_PROFILES`
is the versioned lookup from each holding type to:

- `decomposition`: its asset-class exposure as fractions summing to 1.
  For simple types this is 100% one class. For hybrid funds and
  insurance-linked products, this is the look-through split — the whole
  point of this module is that this is *not* the wrapper's own label.
- `liquidity`: LIQUID (redeemable near-instantly at no cost), SEMI_LIQUID
  (redeemable, but with a delay, exit load, or practical friction), or
  LOCKED_IN (contractually/statutorily unavailable before a term).
- `lock_in_months`: only meaningful for LOCKED_IN types with a fixed term;
  None where the constraint is event-based (e.g. EPF) or fund-specific
  rather than a fixed duration.
- `tax_treatment_category`: a qualitative label, not a rate. Actual tax
  slabs/percentages are deliberately NOT encoded here — per the project's
  convention that regulatory constants live in their own versioned config
  keyed by assessment year, and because rates change with each Finance
  Act. Verify current thresholds against the latest CBDT circular before
  using this for anything beyond a descriptive category label.

DECOMPOSITION ASSUMPTIONS (the detail this module deliberately does not
hand-wave):

- Hybrid mutual fund sub-types use SEBI's own scheme-categorization equity
  bands (Aggressive Hybrid: 65-80% equity; Balanced Hybrid: 40-60%;
  Conservative Hybrid: 10-25%), each represented here at the band's
  midpoint. A real holding's actual split varies within its band and can
  drift with markets — this is a documented illustrative default, not a
  fact about any specific scheme.
- NPS uses an illustrative default for a mid-career subscriber under the
  "Auto Choice - Moderate" life-cycle option (roughly 50% equity, 50%
  government/corporate debt, 0% alternatives). Real NPS allocation is
  subscriber-chosen and glides down with age; this is a placeholder, not
  a computation of any individual's actual NPS asset mix.
- ULIP uses an illustrative "balanced" fund-option default (50% equity /
  50% debt), since a ULIP's actual look-through depends entirely on which
  internal fund option the policyholder selected, which this module has
  no way to know from a category label alone.
- Endowment / money-back (traditional participating) policies use an
  illustrative 15% equity / 85% debt split, reflecting that Indian
  insurers' participating funds are regulated to hold the bulk of assets
  in government securities and approved (debt-like) investments, with
  limited equity exposure.

Any of these can be superseded by a more precise, scheme-specific
decomposition in a future config version — that would be a new `version`
here, not a silent edit to this one.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class AssetClass(str, Enum):
    CASH = "cash"
    DEBT = "debt"
    EQUITY = "equity"
    REAL_ASSETS = "real_assets"
    ALTERNATIVES = "alternatives"


class Liquidity(str, Enum):
    LIQUID = "liquid"
    SEMI_LIQUID = "semi_liquid"
    LOCKED_IN = "locked_in"


class HoldingType(str, Enum):
    SAVINGS_ACCOUNT = "savings_account"
    LIQUID_OR_OVERNIGHT_FUND = "liquid_or_overnight_fund"
    FIXED_DEPOSIT = "fixed_deposit"
    RECURRING_DEPOSIT = "recurring_deposit"
    DEBT_MUTUAL_FUND = "debt_mutual_fund"
    PPF = "ppf"
    EPF = "epf"
    DIRECT_EQUITY = "direct_equity"
    EQUITY_MUTUAL_FUND = "equity_mutual_fund"
    ELSS = "elss"
    HYBRID_MUTUAL_FUND_AGGRESSIVE = "hybrid_mutual_fund_aggressive"
    HYBRID_MUTUAL_FUND_BALANCED = "hybrid_mutual_fund_balanced"
    HYBRID_MUTUAL_FUND_CONSERVATIVE = "hybrid_mutual_fund_conservative"
    NPS = "nps"
    GOLD_ETF = "gold_etf"
    SOVEREIGN_GOLD_BOND = "sovereign_gold_bond"
    PHYSICAL_GOLD = "physical_gold"
    REAL_ESTATE_DIRECT = "real_estate_direct"
    REIT_INVIT = "reit_invit"
    P2P_LENDING = "p2p_lending"
    CRYPTOCURRENCY = "cryptocurrency"
    UNLISTED_EQUITY_OR_AIF = "unlisted_equity_or_aif"
    ULIP = "ulip"
    ENDOWMENT_OR_MONEYBACK_POLICY = "endowment_or_moneyback_policy"


@dataclass(frozen=True)
class HoldingTypeProfile:
    decomposition: dict[AssetClass, Decimal]  # fractions summing to 1
    liquidity: Liquidity
    lock_in_months: int | None
    tax_treatment_category: str
    decomposition_notes: str | None = None  # only set for look-through (multi-class) types

    @property
    def is_look_through(self) -> bool:
        return len(self.decomposition) > 1


def _pure(asset_class: AssetClass) -> dict[AssetClass, Decimal]:
    return {asset_class: Decimal("1")}


HOLDING_TYPE_PROFILES_V1: dict[HoldingType, HoldingTypeProfile] = {
    HoldingType.SAVINGS_ACCOUNT: HoldingTypeProfile(
        decomposition=_pure(AssetClass.CASH),
        liquidity=Liquidity.LIQUID,
        lock_in_months=None,
        tax_treatment_category="savings_interest_slab_rate",
    ),
    HoldingType.LIQUID_OR_OVERNIGHT_FUND: HoldingTypeProfile(
        decomposition=_pure(AssetClass.CASH),
        liquidity=Liquidity.LIQUID,
        lock_in_months=None,
        tax_treatment_category="debt_mf_slab_rate_all_gains",
        decomposition_notes=(
            "Structurally a debt-market-instrument fund, but treated as a cash "
            "equivalent here for its near-zero volatility and same/next-day redemption."
        ),
    ),
    HoldingType.FIXED_DEPOSIT: HoldingTypeProfile(
        decomposition=_pure(AssetClass.DEBT),
        liquidity=Liquidity.SEMI_LIQUID,
        lock_in_months=None,
        tax_treatment_category="fd_interest_slab_rate",
        decomposition_notes="Premature withdrawal is usually allowed at an interest-rate penalty, not legally locked.",
    ),
    HoldingType.RECURRING_DEPOSIT: HoldingTypeProfile(
        decomposition=_pure(AssetClass.DEBT),
        liquidity=Liquidity.SEMI_LIQUID,
        lock_in_months=None,
        tax_treatment_category="rd_interest_slab_rate",
    ),
    HoldingType.DEBT_MUTUAL_FUND: HoldingTypeProfile(
        decomposition=_pure(AssetClass.DEBT),
        liquidity=Liquidity.SEMI_LIQUID,
        lock_in_months=None,
        tax_treatment_category="debt_mf_slab_rate_all_gains",
    ),
    HoldingType.PPF: HoldingTypeProfile(
        decomposition=_pure(AssetClass.DEBT),
        liquidity=Liquidity.LOCKED_IN,
        lock_in_months=180,  # 15-year statutory term (partial withdrawal permitted from year 7)
        tax_treatment_category="eee_exempt",
    ),
    HoldingType.EPF: HoldingTypeProfile(
        decomposition=_pure(AssetClass.DEBT),
        liquidity=Liquidity.SEMI_LIQUID,
        lock_in_months=None,  # event-based (job change/retirement), not a fixed term
        tax_treatment_category="eee_exempt_subject_to_continuous_service_condition",
    ),
    HoldingType.DIRECT_EQUITY: HoldingTypeProfile(
        decomposition=_pure(AssetClass.EQUITY),
        liquidity=Liquidity.LIQUID,
        lock_in_months=None,
        tax_treatment_category="equity_ltcg_stcg_stt_paid",
    ),
    HoldingType.EQUITY_MUTUAL_FUND: HoldingTypeProfile(
        decomposition=_pure(AssetClass.EQUITY),
        liquidity=Liquidity.SEMI_LIQUID,
        lock_in_months=None,
        tax_treatment_category="equity_ltcg_stcg_stt_paid",
    ),
    HoldingType.ELSS: HoldingTypeProfile(
        decomposition=_pure(AssetClass.EQUITY),
        liquidity=Liquidity.LOCKED_IN,
        lock_in_months=36,
        tax_treatment_category="equity_ltcg_stcg_stt_paid",
    ),
    HoldingType.HYBRID_MUTUAL_FUND_AGGRESSIVE: HoldingTypeProfile(
        decomposition={AssetClass.EQUITY: Decimal("0.70"), AssetClass.DEBT: Decimal("0.30")},
        liquidity=Liquidity.SEMI_LIQUID,
        lock_in_months=None,
        tax_treatment_category="equity_ltcg_stcg_stt_paid",
        decomposition_notes="Midpoint of SEBI's Aggressive Hybrid Fund category band (65-80% equity). >=65% equity gets equity tax treatment.",
    ),
    HoldingType.HYBRID_MUTUAL_FUND_BALANCED: HoldingTypeProfile(
        decomposition={AssetClass.EQUITY: Decimal("0.50"), AssetClass.DEBT: Decimal("0.50")},
        liquidity=Liquidity.SEMI_LIQUID,
        lock_in_months=None,
        tax_treatment_category="debt_mf_slab_rate_all_gains",
        decomposition_notes="Midpoint of SEBI's Balanced Hybrid Fund category band (40-60% equity). <65% equity gets debt-fund tax treatment.",
    ),
    HoldingType.HYBRID_MUTUAL_FUND_CONSERVATIVE: HoldingTypeProfile(
        decomposition={AssetClass.EQUITY: Decimal("0.15"), AssetClass.DEBT: Decimal("0.85")},
        liquidity=Liquidity.SEMI_LIQUID,
        lock_in_months=None,
        tax_treatment_category="debt_mf_slab_rate_all_gains",
        decomposition_notes="Midpoint of SEBI's Conservative Hybrid Fund category band (10-25% equity).",
    ),
    HoldingType.NPS: HoldingTypeProfile(
        decomposition={AssetClass.EQUITY: Decimal("0.50"), AssetClass.DEBT: Decimal("0.50")},
        liquidity=Liquidity.LOCKED_IN,
        lock_in_months=None,  # locked until retirement age, not a fixed month count from purchase
        tax_treatment_category="nps_eet_partial_exempt_annuity_condition",
        decomposition_notes=(
            "Illustrative default for a mid-career subscriber under Auto Choice - Moderate "
            "life-cycle allocation (E/C/G combined into equity/debt here). Actual NPS allocation "
            "is subscriber-chosen and glides down with age."
        ),
    ),
    HoldingType.GOLD_ETF: HoldingTypeProfile(
        decomposition=_pure(AssetClass.REAL_ASSETS),
        liquidity=Liquidity.LIQUID,
        lock_in_months=None,
        tax_treatment_category="gold_etf_capital_gains_slab_rate",
    ),
    HoldingType.SOVEREIGN_GOLD_BOND: HoldingTypeProfile(
        decomposition=_pure(AssetClass.REAL_ASSETS),
        liquidity=Liquidity.LOCKED_IN,
        lock_in_months=96,  # 8-year tenor; RBI premature-exit windows open from year 5
        tax_treatment_category="sgb_capital_gains_exempt_if_held_to_rbi_maturity",
    ),
    HoldingType.PHYSICAL_GOLD: HoldingTypeProfile(
        decomposition=_pure(AssetClass.REAL_ASSETS),
        liquidity=Liquidity.SEMI_LIQUID,
        lock_in_months=None,
        tax_treatment_category="physical_gold_capital_gains",
        decomposition_notes="Sellable readily, but typically at a making-charge/purity spread loss versus quoted price.",
    ),
    HoldingType.REAL_ESTATE_DIRECT: HoldingTypeProfile(
        decomposition=_pure(AssetClass.REAL_ASSETS),
        liquidity=Liquidity.SEMI_LIQUID,
        lock_in_months=None,
        tax_treatment_category="real_estate_capital_gains",
        decomposition_notes="No legal lock-in, but practically illiquid: typically months to sell, with significant transaction cost.",
    ),
    HoldingType.REIT_INVIT: HoldingTypeProfile(
        decomposition=_pure(AssetClass.REAL_ASSETS),
        liquidity=Liquidity.LIQUID,
        lock_in_months=None,
        tax_treatment_category="reit_invit_distribution_mixed_treatment",
        decomposition_notes="Exchange-traded; distributions can combine dividend, interest, and capital-repayment components, each taxed differently.",
    ),
    HoldingType.P2P_LENDING: HoldingTypeProfile(
        decomposition=_pure(AssetClass.ALTERNATIVES),
        liquidity=Liquidity.LOCKED_IN,
        lock_in_months=None,  # tied to underlying loan tenure, which varies by platform/loan
        tax_treatment_category="p2p_interest_income_slab_rate",
    ),
    HoldingType.CRYPTOCURRENCY: HoldingTypeProfile(
        decomposition=_pure(AssetClass.ALTERNATIVES),
        liquidity=Liquidity.LIQUID,
        lock_in_months=None,
        tax_treatment_category="vda_flat_rate_no_loss_offset",
    ),
    HoldingType.UNLISTED_EQUITY_OR_AIF: HoldingTypeProfile(
        decomposition=_pure(AssetClass.ALTERNATIVES),
        liquidity=Liquidity.LOCKED_IN,
        lock_in_months=None,  # typically multi-year fund lock-up; varies by fund
        tax_treatment_category="unlisted_shares_or_aif_capital_gains_category_dependent",
    ),
    HoldingType.ULIP: HoldingTypeProfile(
        decomposition={AssetClass.EQUITY: Decimal("0.50"), AssetClass.DEBT: Decimal("0.50")},
        liquidity=Liquidity.LOCKED_IN,
        lock_in_months=60,  # IRDAI-mandated minimum lock-in
        tax_treatment_category="ulip_10d_conditional_exemption_or_capital_gains_if_premium_exceeds_threshold",
        decomposition_notes=(
            "Illustrative 'balanced' fund-option default. A ULIP's real look-through depends "
            "entirely on which internal fund option (equity/debt/balanced) the policyholder "
            "selected, which is not derivable from the product category alone."
        ),
    ),
    HoldingType.ENDOWMENT_OR_MONEYBACK_POLICY: HoldingTypeProfile(
        decomposition={AssetClass.EQUITY: Decimal("0.15"), AssetClass.DEBT: Decimal("0.85")},
        liquidity=Liquidity.LOCKED_IN,
        lock_in_months=36,
        tax_treatment_category="life_insurance_10d_conditional_exemption",
        decomposition_notes=(
            "Illustrative split reflecting that Indian insurers' traditional participating funds "
            "are regulated to hold the bulk of assets in government securities and other approved "
            "(debt-like) investments, with limited equity exposure. Lock-in shown is an illustrative "
            "minimum surrender-value term, not a fact about any specific policy."
        ),
    ),
}

CONFIG_VERSION = "v1"
CONFIG_EFFECTIVE_DATE = "2026-01-01"
