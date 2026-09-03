import { apiClient } from './client';
import type {
  EmiIn,
  EmiOut,
  ExpenseItemIn,
  ExpenseItemOut,
  ExpenseSourceMode,
  ExpenseSourceModeOut,
  FinancialPositionOut,
  HoldingIn,
  HoldingOut,
  InsurancePolicyIn,
  InsurancePolicyOut,
  ProfileIn,
  ProfileOut,
  UserMonthlySnapshotRead,
} from './types';

export const onboardingApi = {
  putProfile: (userId: string, body: ProfileIn) =>
    apiClient.put<ProfileOut>(`/users/${userId}/profile`, body).then((r) => r.data),

  postEmi: (userId: string, body: EmiIn) =>
    apiClient.post<EmiOut>(`/users/${userId}/emis`, body).then((r) => r.data),

  closeEmi: (userId: string, emiId: string) =>
    apiClient.post<EmiOut>(`/users/${userId}/emis/${emiId}/close`).then((r) => r.data),

  postInsurancePolicy: (userId: string, body: InsurancePolicyIn) =>
    apiClient.post<InsurancePolicyOut>(`/users/${userId}/insurance-policies`, body).then((r) => r.data),

  postHolding: (userId: string, body: HoldingIn) =>
    apiClient.post<HoldingOut>(`/users/${userId}/holdings`, body).then((r) => r.data),

  postExpenseItem: (userId: string, body: ExpenseItemIn) =>
    apiClient.post<ExpenseItemOut>(`/users/${userId}/expenses`, body).then((r) => r.data),

  removeExpenseItem: (userId: string, itemId: string) =>
    apiClient.post<ExpenseItemOut>(`/users/${userId}/expenses/${itemId}/remove`).then((r) => r.data),

  putExpenseSourceDecision: (userId: string, decision: ExpenseSourceMode) =>
    apiClient
      .put<ExpenseSourceModeOut>(`/users/${userId}/expense-source-decision`, { decision })
      .then((r) => r.data),

  getExpenseSourceDecision: (userId: string) =>
    apiClient.get<ExpenseSourceModeOut>(`/users/${userId}/expense-source-decision`).then((r) => r.data),

  getFinancialPosition: (userId: string) =>
    apiClient.get<FinancialPositionOut>(`/users/${userId}/financial-position`).then((r) => r.data),

  completeOnboarding: (userId: string) =>
    apiClient.post<UserMonthlySnapshotRead>(`/users/${userId}/complete-onboarding`).then((r) => r.data),
};
