from decimal import Decimal

import pytest

from app.services.asset_classification import (
    aggregate_classifications,
    classify_holding,
)
from app.services.asset_classification_config import AssetClass, HoldingType, Liquidity

# --- single-holding classification ---


def test_savings_account_is_pure_cash_liquid():
    result = classify_holding("h1", HoldingType.SAVINGS_ACCOUNT, 50_000_00)
    assert result.decomposition_paise == {AssetClass.CASH: 50_000_00}
    assert result.liquidity == Liquidity.LIQUID
    assert result.lock_in_months is None
    assert result.is_look_through is False


def test_ppf_is_pure_debt_locked_in_15_years():
    result = classify_holding("h1", HoldingType.PPF, 300_000_00)
    assert result.decomposition_paise == {AssetClass.DEBT: 300_000_00}
    assert result.liquidity == Liquidity.LOCKED_IN
    assert result.lock_in_months == 180
    assert result.tax_treatment_category == "eee_exempt"


def test_elss_is_pure_equity_locked_in_3_years():
    result = classify_holding("h1", HoldingType.ELSS, 100_000_00)
    assert result.decomposition_paise == {AssetClass.EQUITY: 100_000_00}
    assert result.liquidity == Liquidity.LOCKED_IN
    assert result.lock_in_months == 36


def test_unknown_holding_type_raises():
    with pytest.raises(ValueError):
        classify_holding("h1", "not_a_real_type", 1000)


# --- look-through decomposition of hybrid / insurance-linked products ---


def test_ulip_look_through_splits_50_50():
    result = classify_holding("h1", HoldingType.ULIP, 200_000_00)
    assert result.is_look_through is True
    assert result.decomposition_paise == {AssetClass.EQUITY: 100_000_00, AssetClass.DEBT: 100_000_00}
    assert result.liquidity == Liquidity.LOCKED_IN
    assert result.lock_in_months == 60
    assert result.decomposition_notes is not None  # the assumption must be documented, not silent


def test_endowment_policy_look_through_splits_15_85():
    result = classify_holding("h1", HoldingType.ENDOWMENT_OR_MONEYBACK_POLICY, 100_000_00)
    assert result.decomposition_paise == {AssetClass.EQUITY: 15_000_00, AssetClass.DEBT: 85_000_00}
    assert result.decomposition_notes is not None


def test_aggressive_hybrid_fund_look_through_splits_70_30():
    result = classify_holding("h1", HoldingType.HYBRID_MUTUAL_FUND_AGGRESSIVE, 100_000_00)
    assert result.decomposition_paise == {AssetClass.EQUITY: 70_000_00, AssetClass.DEBT: 30_000_00}
    # >=65% equity -> equity tax treatment, a real Indian tax-law nuance
    assert result.tax_treatment_category == "equity_ltcg_stcg_stt_paid"


def test_balanced_hybrid_fund_gets_debt_tax_treatment_not_equity():
    # <65% equity -> debt-fund tax treatment, even though it's still a
    # "hybrid" fund with meaningful equity exposure
    result = classify_holding("h1", HoldingType.HYBRID_MUTUAL_FUND_BALANCED, 100_000_00)
    assert result.decomposition_paise == {AssetClass.EQUITY: 50_000_00, AssetClass.DEBT: 50_000_00}
    assert result.tax_treatment_category == "debt_mf_slab_rate_all_gains"


def test_nps_look_through_splits_and_is_not_lock_in_month_counted():
    result = classify_holding("h1", HoldingType.NPS, 500_000_00)
    assert result.decomposition_paise == {AssetClass.EQUITY: 250_000_00, AssetClass.DEBT: 250_000_00}
    assert result.liquidity == Liquidity.LOCKED_IN
    assert result.lock_in_months is None  # locked to retirement age, not a fixed month count


def test_decomposition_rounding_residual_stays_conserved():
    # 333 paise split 70/30 doesn't divide evenly; the parts must still
    # sum back to the whole exactly (no paise created or lost to rounding)
    result = classify_holding("h1", HoldingType.HYBRID_MUTUAL_FUND_AGGRESSIVE, 333)
    assert sum(result.decomposition_paise.values()) == 333


# --- portfolio aggregation: the definition-of-done scenario ---
# Holdings include at least one hybrid AND one insurance-linked product;
# the aggregate equity/debt exposure must reflect their look-through
# slices, not their wrapper label.


def _definition_of_done_portfolio():
    return [
        classify_holding("equity_fund", HoldingType.EQUITY_MUTUAL_FUND, 100_000_00),
        classify_holding("savings", HoldingType.SAVINGS_ACCOUNT, 50_000_00),
        classify_holding("ulip", HoldingType.ULIP, 200_000_00),
        classify_holding("endowment", HoldingType.ENDOWMENT_OR_MONEYBACK_POLICY, 100_000_00),
    ]


def test_aggregate_look_through_exposure_is_not_the_label_exposure():
    portfolio = _definition_of_done_portfolio()
    result = aggregate_classifications(portfolio)

    assert result.total_value_paise == 450_000_00

    # hand-checked look-through totals:
    # equity = 100,000_00 (pure fund) + 100,000_00 (ULIP 50%) + 15,000_00 (endowment 15%) = 215,000_00
    # debt   = 100,000_00 (ULIP 50%) + 85,000_00 (endowment 85%) = 185,000_00
    # cash   = 50,000_00
    assert result.exposure_by_asset_class_paise[AssetClass.EQUITY] == 215_000_00
    assert result.exposure_by_asset_class_paise[AssetClass.DEBT] == 185_000_00
    assert result.exposure_by_asset_class_paise[AssetClass.CASH] == 50_000_00
    assert result.exposure_by_asset_class_paise[AssetClass.REAL_ASSETS] == 0
    assert result.exposure_by_asset_class_paise[AssetClass.ALTERNATIVES] == 0

    # the whole point: look-through equity is NOT the same as naively
    # summing only holdings labeled "equity" -- it's 115,000_00 more,
    # hidden inside the ULIP and endowment wrappers
    label_only_equity = 100_000_00  # what you'd get ignoring ULIP/endowment entirely
    assert result.exposure_by_asset_class_paise[AssetClass.EQUITY] != label_only_equity
    assert result.exposure_by_asset_class_paise[AssetClass.EQUITY] - label_only_equity == 115_000_00

    # exposures still sum back to the total portfolio value
    assert sum(result.exposure_by_asset_class_paise.values()) == result.total_value_paise


def test_aggregate_exposure_pct_sums_to_100():
    portfolio = _definition_of_done_portfolio()
    result = aggregate_classifications(portfolio)
    assert sum(result.exposure_by_asset_class_pct.values()) == Decimal("100.00")


# --- liquidity and tax are wrapper-level, NOT look-through decomposed ---


def test_liquidity_breakdown_is_not_decomposed():
    portfolio = _definition_of_done_portfolio()
    result = aggregate_classifications(portfolio)

    # the ULIP's full value is LOCKED_IN, not split into a "50% locked,
    # 50% semi-liquid" the way its asset-class exposure is
    assert result.liquidity_breakdown_paise[Liquidity.LOCKED_IN] == 200_000_00 + 100_000_00  # ULIP + endowment
    assert result.liquidity_breakdown_paise[Liquidity.LIQUID] == 50_000_00  # savings account
    assert result.liquidity_breakdown_paise[Liquidity.SEMI_LIQUID] == 100_000_00  # equity fund
    assert sum(result.liquidity_breakdown_paise.values()) == result.total_value_paise


def test_tax_treatment_breakdown_is_not_decomposed():
    portfolio = _definition_of_done_portfolio()
    result = aggregate_classifications(portfolio)

    assert result.tax_treatment_breakdown_paise["ulip_10d_conditional_exemption_or_capital_gains_if_premium_exceeds_threshold"] == 200_000_00
    assert result.tax_treatment_breakdown_paise["life_insurance_10d_conditional_exemption"] == 100_000_00
    assert sum(result.tax_treatment_breakdown_paise.values()) == result.total_value_paise


# --- concentration ---


def test_concentration_largest_holding_and_hhi_hand_checked():
    portfolio = _definition_of_done_portfolio()
    result = aggregate_classifications(portfolio)

    # largest single holding: ULIP at 200,000_00 / 450,000_00 = 44.44%
    assert result.concentration.largest_holding_id == "ulip"
    assert result.concentration.largest_holding_pct == Decimal("44.44")

    # asset-class weights: equity 215/450=47.78%, debt 185/450=41.11%,
    # cash 50/450=11.11%, real_assets 0%, alternatives 0%
    # HHI = 47.78^2 + 41.11^2 + 11.11^2 (+0+0) ~= 2283+1690+123 ~= 4096
    assert 4000 <= result.concentration.asset_class_hhi_bps <= 4200


def test_empty_portfolio_aggregates_to_zero_without_crashing():
    result = aggregate_classifications([])
    assert result.total_value_paise == 0
    assert result.concentration.largest_holding_pct == Decimal("0.00")
    assert result.concentration.largest_holding_id is None
    assert result.concentration.asset_class_hhi_bps == 0
