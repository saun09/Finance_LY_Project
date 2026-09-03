import type { NavigatorScreenParams } from '@react-navigation/native';
import type { UserMonthlySnapshotRead } from '../api/types';

export type OnboardingStackParamList = {
  Welcome: undefined;
  Profile: undefined;
  Expenses: undefined;
  Debt: undefined;
  Insurance: undefined;
  Holdings: undefined;
  Review: undefined;
  Snapshot: { snapshot: UserMonthlySnapshotRead };
};

export type HomeStackParamList = { Home: undefined };
export type PlanStackParamList = {
  RiskProfile: undefined;
  RiskQuestionnaire: undefined;
  Allocation: undefined;
};
export type InsightsStackParamList = {
  Insights: undefined;
  Debt: undefined;
  Leaks: undefined;
  Personalization: undefined;
  Transparency: undefined;
  TransparencyDetail: { moduleSource: string };
};
export type VerifyStackParamList = {
  RumourVerification: undefined;
};
export type ProgressStackParamList = { Progress: undefined };
export type ProfileStackParamList = {
  ProfileHome: undefined;
  ExpensesManage: undefined;
  DebtManage: undefined;
  InsuranceManage: undefined;
  HoldingsManage: undefined;
  Settings: undefined;
};

export type MainTabParamList = {
  HomeTab: NavigatorScreenParams<HomeStackParamList>;
  PlanTab: NavigatorScreenParams<PlanStackParamList>;
  InsightsTab: NavigatorScreenParams<InsightsStackParamList>;
  VerifyTab: NavigatorScreenParams<VerifyStackParamList>;
  ProgressTab: NavigatorScreenParams<ProgressStackParamList>;
  ProfileTab: NavigatorScreenParams<ProfileStackParamList>;
};

export type RootStackParamList = {
  Onboarding: NavigatorScreenParams<OnboardingStackParamList>;
  Main: NavigatorScreenParams<MainTabParamList>;
};
