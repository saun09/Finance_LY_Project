import type { AssetClass, Liquidity } from '../api/types';
import type { TransparencyDecisionType } from '../api/transparency';

/** Display labels for backend enums that have no server-provided label
 * (unlike the risk questionnaire, whose option labels always come from
 * the API). Snake_case -> readable text only, never a semantic claim the
 * backend doesn't itself make. */
export const ASSET_CLASS_LABEL: Record<AssetClass, string> = {
  cash: 'Cash',
  debt: 'Debt',
  equity: 'Equity',
  real_assets: 'Real assets',
  alternatives: 'Alternatives',
};

export const LIQUIDITY_LABEL: Record<Liquidity, string> = {
  liquid: 'Liquid',
  semi_liquid: 'Semi-liquid',
  locked_in: 'Locked-in',
};

/** Mirrors backend/app/services/gamification_config.py's Category enum --
 * every milestone category is an effort signal (buffer built, capacity
 * unlocked, debt cleared, a leak-driving subscription cancelled, months of
 * positive surplus), enforced at import time on the backend. Never add a
 * category here that isn't one of these five without checking that file's
 * module docstring first. */
export const MILESTONE_CATEGORY_LABEL: Record<string, string> = {
  buffer: 'Emergency buffer',
  capacity_unlock: 'Capacity unlocked',
  debt: 'Debt cleared',
  subscriptions: 'Subscription cancelled',
  consistency: 'Consistency',
};

/** Mirrors backend/app/services/transparency.py's DECISION_TYPES
 * display_name strings exactly, so the index list (which only gets counts,
 * not names, from AvailableDecisionTypesOut) reads identically to what the
 * detail trace itself reports. */
export const TRANSPARENCY_DISPLAY_NAME: Record<TransparencyDecisionType, string> = {
  risk_profile: 'Risk tier',
  allocation: 'Target allocation',
  debt_leak_engine: 'Recoverable ₹/year',
  personalization: 'Personalization offset',
  gamification: 'Milestone awarded',
  rumour_verification_local: 'Rumour verification (explainable retrieval)',
  rumour_verification: 'Rumour verification',
};

/** Why a user might dispute a trace. Labels only -- the codes themselves
 * come from the server (GET /transparency/contest-reasons), so this map is
 * for display and never decides what may be submitted. */
export const CONTEST_REASON_LABEL: Record<string, string> = {
  input_wrong: 'An input here is wrong',
  rule_wrong: "The rule doesn't make sense for me",
  outcome_unfair: 'The outcome feels unfair',
  dont_understand: "I don't understand this",
  other: 'Something else',
};
