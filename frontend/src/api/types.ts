/**
 * Types mirror the backend's Pydantic schemas field-for-field (read
 * directly from backend/app/schemas/*.py — nothing here is invented).
 * `*_paise` fields are always integers; decimal-string fields (ratios,
 * percentages) come back as strings from Pydantic's Decimal JSON encoding
 * and must be parsed with Number(), never assumed to already be numbers.
 */

// ---- shared enums (values must match the backend's str Enums exactly) ----

export type IncomeStability = 'regular' | 'irregular';
export type EmploymentType =
  | 'salaried'
  | 'self_employed'
  | 'business_owner'
  | 'freelancer'
  | 'unemployed'
  | 'other';
export type InsuranceType = 'life' | 'health';
export type ExpenseFrequency = 'monthly' | 'annual' | 'one_time';
export type ExpenseSourceMode = 'manual_only' | 'statement_parsing_enabled';
export type AssetClass = 'cash' | 'debt' | 'equity' | 'real_assets' | 'alternatives';
export type Liquidity = 'liquid' | 'semi_liquid' | 'locked_in';
export type EditActionTaken = 'accepted' | 'edited' | 'rejected' | 'ignored';
export type RumourStatus = 'confirmed' | 'denied' | 'unaddressed' | 'not_yet_due';

export type HoldingType =
  | 'savings_account'
  | 'liquid_or_overnight_fund'
  | 'fixed_deposit'
  | 'recurring_deposit'
  | 'debt_mutual_fund'
  | 'ppf'
  | 'epf'
  | 'direct_equity'
  | 'equity_mutual_fund'
  | 'elss'
  | 'hybrid_mutual_fund_aggressive'
  | 'hybrid_mutual_fund_balanced'
  | 'hybrid_mutual_fund_conservative'
  | 'nps'
  | 'gold_etf'
  | 'sovereign_gold_bond'
  | 'physical_gold'
  | 'real_estate_direct'
  | 'reit_invit'
  | 'p2p_lending'
  | 'cryptocurrency'
  | 'unlisted_equity_or_aif'
  | 'ulip'
  | 'endowment_or_moneyback_policy';

export const ASSET_CLASSES: AssetClass[] = ['cash', 'debt', 'equity', 'real_assets', 'alternatives'];

// ---- Module 2: onboarding ----

export interface ProfileIn {
  income_paise: number;
  income_stability: IncomeStability;
  employment_type: EmploymentType;
  dependents_count: number;
  cash_balance_paise: number;
}

export interface ProfileOut extends ProfileIn {
  user_id: string;
  onboarding_started_at: string;
  onboarding_completed_at: string | null;
}

export interface EmiIn {
  lender: string;
  amount_paise: number;
  remaining_tenure_months: number;
  annual_rate_bps: number;
}

export interface EmiOut extends EmiIn {
  id: string;
  user_id: string;
  closed_at: string | null;
}

export interface InsurancePolicyIn {
  policy_type: InsuranceType;
  sum_assured_paise: number;
}

export interface InsurancePolicyOut extends InsurancePolicyIn {
  id: string;
  user_id: string;
}

export interface HoldingIn {
  description: string;
  value_paise: number;
  holding_type: HoldingType | null;
}

export interface HoldingOut extends HoldingIn {
  id: string;
  user_id: string;
}

export interface ExpenseItemIn {
  category: string;
  amount_paise: number;
  frequency: ExpenseFrequency;
  is_essential: boolean;
}

export interface ExpenseItemOut extends ExpenseItemIn {
  id: string;
  user_id: string;
  removed_at: string | null;
}

export interface ExpenseSourceModeOut {
  mode: ExpenseSourceMode;
  is_explicit_decision: boolean;
  resolved_at: string | null;
}

export interface FinancialPositionOut {
  net_worth_paise: number;
  monthly_surplus_paise: number;
  buffer_coverage_months: string; // Decimal
  emi_to_income_ratio: string; // Decimal
  total_monthly_expenses_paise: number;
  essential_monthly_expense_paise: number;
  total_monthly_emi_paise: number;
}

export interface UserMonthlySnapshotRead {
  snapshot_id: string;
  user_id: string;
  month: string; // date
  /** Paise, despite the missing `_paise` suffix -- the backend ORM comment
   * on UserMonthlySnapshot confirms income/surplus/cash are integer paise.
   * Always go through formatPaise, never treat these as rupees. */
  income: number;
  surplus: number;
  cash: number;
  debt_to_income_ratio: string;
  buffer_coverage_months: string;
  computed_at: string;
}

// ---- Module 3: risk profile ----

export interface QuestionOptionOut {
  value: string;
  label: string;
}
export interface QuestionOut {
  id: string;
  text: string;
  weight: number;
  options: QuestionOptionOut[];
}
export interface QuestionnaireOut {
  version: string;
  effective_date: string;
  questions: QuestionOut[];
}

export interface RiskProfileAnswersIn {
  answers: Record<string, string>;
}

export interface UnlockConditionOut {
  constraint: string;
  message: string;
  current_value: string;
  target_value: string;
}

export interface RiskTierOut {
  stated_tier: number;
  capacity_ceiling: number;
  final_tier: number;
  capped: boolean;
  binding_constraints: string[];
  unlock_conditions: UnlockConditionOut[];
}

// ---- Module 4: allocation ----

export interface ConcentrationOut {
  largest_holding_pct: string;
  largest_holding_id: string | null;
  asset_class_hhi_bps: number;
}

export interface HoldingClassificationOut {
  holding_id: string;
  holding_type: string;
  value_paise: number;
  decomposition_paise: Partial<Record<AssetClass, number>>;
  liquidity: Liquidity;
  lock_in_months: number | null;
  tax_treatment_category: string;
  is_look_through: boolean;
}

export interface AllocationReportOut {
  final_tier: number;
  rule_table_version: string;
  reasoning: string;
  target_pct: Record<AssetClass, string>;
  current_exposure_pct: Record<AssetClass, string>;
  current_exposure_paise: Record<AssetClass, number>;
  total_value_paise: number;
  concentration: ConcentrationOut;
  liquidity_breakdown_paise: Partial<Record<Liquidity, number>>;
  tax_treatment_breakdown_paise: Record<string, number>;
  holdings: HoldingClassificationOut[];
}

// ---- Module 6: debt & leak ----

export interface RecoverableComponentOut {
  component_id: string;
  label: string;
  annual_amount_paise: number;
  explanation: string;
  concrete_action: string;
}

export interface StrategyResultOut {
  strategy: string;
  months_to_clear_all: number;
  total_interest_paise: number;
  payoff_order: string[];
  converged: boolean;
}

export interface AvalancheSnowballOut {
  avalanche: StrategyResultOut;
  snowball: StrategyResultOut;
  interest_saved_by_avalanche_paise: number;
  months_saved_by_avalanche: number;
}

export interface PrepayVsInvestOut {
  debt_id: string;
  guaranteed_annual_rate_pct: string;
  extra_monthly_paise: number;
  baseline_months: number;
  baseline_total_interest_paise: number;
  accelerated_months: number;
  accelerated_total_interest_paise: number;
  interest_saved_paise: number;
  months_saved: number;
  framing_note: string;
}

export interface DebtLeakReportOut {
  total_recoverable_annual_paise: number;
  components: RecoverableComponentOut[];
  data_source_note: string;
  expense_source_mode: string;
  expense_source_is_explicit: boolean;
  avalanche_snowball: AvalancheSnowballOut | null;
  prepay_vs_invest: PrepayVsInvestOut | null;
}

export interface CreditCardRevolvingCostIn {
  balance_paise: number;
  monthly_rate_bps: number;
  min_payment_pct_bps: number;
  min_payment_floor_paise: number;
}

export interface CreditCardRevolvingCostOut {
  nominal_annual_rate_pct: string;
  effective_annual_rate_pct: string;
  months_to_clear_at_minimum: number;
  total_interest_at_minimum_paise: number;
  converged: boolean;
}

export interface RefinanceBreakevenIn {
  emi_id: string;
  new_annual_rate_bps: number;
  fees_paise: number;
}

export interface RefinanceBreakevenOut {
  current_monthly_payment_paise: number;
  new_monthly_payment_paise: number;
  monthly_savings_paise: number;
  fees_paise: number;
  breakeven_month: number | null;
  beneficial: boolean;
}

// ---- Module 7: personalization ----

export interface RecordAllocationOutcomeIn {
  action_taken: EditActionTaken;
  chosen_target_pct?: Record<AssetClass, string> | null;
  funded?: boolean | null;
}

export interface OffsetStepOut {
  step: number;
  weight: string;
  delta_pct: string;
  offset_before: string;
  offset_after: string;
}

export interface PersonalizationOut {
  offset_pct_points: string;
  edits_considered: number;
  final_tier: number;
  capacity_ceiling: number;
  base_target_pct: Record<AssetClass, string>;
  displayed_target_pct: Record<AssetClass, string>;
  trace: OffsetStepOut[];
}

// ---- Module 9: transparency ----

export interface TraceResultOut {
  module_source: string;
  display_name: string;
  framing_label: string; // always "transparent reasoning" for backend decision types
  event_id: string;
  timestamp: string;
  headline: string;
  reasoning: Record<string, unknown>;
  gap_detected: boolean;
  missing_fields: string[];
}

export interface AvailableDecisionTypesOut {
  counts_by_module_source: Record<string, number>;
}

// ---- Module 10: gamification ----

export interface AwardedMilestoneOut {
  milestone_id: string;
  category: string;
  headline: string;
  details: Record<string, unknown>;
}

export interface MilestoneHistoryOut {
  milestones: AwardedMilestoneOut[];
}

export interface RoadmapTopicOut {
  topic_id: string;
  title: string;
  description: string;
  completed: boolean;
  quiz_question: QuizQuestionOut | null;
}

export interface QuizQuestionOut {
  question_id: string;
  prompt: string;
  options: string[];
  passed: boolean;
}

export interface RoadmapLevelOut {
  level: number;
  title: string;
  topics: RoadmapTopicOut[];
}

export interface ChecklistItemOut {
  item_id: string;
  title: string;
  section: string;
  completed: boolean;
}

export interface BadgeOut {
  badge_id: string;
  title: string;
  description: string;
  earned: boolean;
}

export interface EducationProgressOut {
  roadmap: RoadmapLevelOut[];
  checklist: ChecklistItemOut[];
  badges: BadgeOut[];
  completed_topics: number;
  total_topics: number;
  progress_pct: number;
  learning_streak_days: number;
}

export interface QuizResultOut {
  correct: boolean;
  explanation: string;
}

// ---- Module 5 (bridged): rumour verification ----

export interface RumourVerificationIn {
  rumour_text: string;
  rumour_date?: string | null;
  company_name?: string | null;
  evaluated_at?: string | null;
}

export interface MatchedFilingOut {
  filing_id: string;
  company_name: string;
  filing_date: string;
  filing_type: string;
  source_authority: string;
  source_url: string | null;
  determination: string | null;
}

export interface RumourVerificationOut {
  query_text: string;
  rumour_date: string | null;
  status: RumourStatus | null;
  matched_score: number | null;
  matched_filing: MatchedFilingOut | null;
  candidates_considered: number;
  candidates_passing: number;
  top_candidate_reasons: string[];
  logged_event_id: string | null;
}

// ---- Module 1: event log ----

export interface SuggestionEventRead {
  event_id: string;
  user_id: string;
  timestamp: string;
  module_source: string;
  tier: string | null;
  offset: number | null;
  suggested_value: Record<string, unknown>;
  chosen_value: Record<string, unknown> | null;
  delta: Record<string, unknown> | null;
  action_taken: EditActionTaken | null;
  reason_code: string | null;
  funded: boolean | null;
  market_context: Record<string, unknown>;
  created_at: string;
}

/** FastAPI's own request-validation failures (422s raised by Pydantic
 * before a route body even runs) return `detail` as an array of these,
 * not a string -- only application code that raises `HTTPException(detail="...")`
 * gives a plain string. Both shapes are real and must be handled. */
export interface ApiValidationErrorDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ApiErrorBody {
  detail: string | ApiValidationErrorDetail[];
}
