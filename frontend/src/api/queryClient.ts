import { QueryClient } from '@tanstack/react-query';
import { toApiError } from './client';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      // React Query passes the raw error through; normalize once here so
      // every screen's `error` is already an ApiError with a human message.
      throwOnError: false,
    },
    mutations: {
      retry: 0,
    },
  },
});

export { toApiError };

/** Query keys, centralized so invalidation after a mutation (Section 22 --
 * "adding an expense should update the expense list, financial position,
 * dashboard, risk capacity, insights") stays consistent across the app
 * instead of hand-typed strings scattered through components. */
export const qk = {
  financialPosition: (userId: string) => ['financial-position', userId] as const,
  snapshots: (userId: string) => ['snapshots', userId] as const,
  events: (userId: string, moduleSource?: string) => ['events', userId, moduleSource] as const,
  profile: (userId: string) => ['profile', userId] as const,
  emis: (userId: string) => ['emis', userId] as const,
  insurancePolicies: (userId: string) => ['insurance-policies', userId] as const,
  holdings: (userId: string) => ['holdings', userId] as const,
  expenses: (userId: string) => ['expenses', userId] as const,
  expenseSourceMode: (userId: string) => ['expense-source-mode', userId] as const,
  questionnaire: () => ['questionnaire'] as const,
  riskProfileLatest: (userId: string) => ['risk-profile-latest', userId] as const,
  allocation: (userId: string) => ['allocation', userId] as const,
  debtLeak: (userId: string) => ['debt-leak', userId] as const,
  personalization: (userId: string) => ['personalization', userId] as const,
  transparencyIndex: (userId: string) => ['transparency-index', userId] as const,
  transparencyTrace: (userId: string, moduleSource: string) => ['transparency-trace', userId, moduleSource] as const,
  gamificationHistory: (userId: string) => ['gamification-history', userId] as const,
};

/** Every profile-management mutation (add/close an EMI, add a holding,
 * add/remove an expense) is a "material edit" server-side -- it
 * recomputes and re-logs the month's snapshot (see onboarding.py). This
 * invalidates every cached query whose numbers could have shifted as a
 * result, so screens across Home/Plan/Insights pick up fresh data instead
 * of showing stale figures until their own next natural refetch. */
export function invalidateFinancialData(queryClient: QueryClient, userId: string) {
  queryClient.invalidateQueries({ queryKey: qk.financialPosition(userId) });
  queryClient.invalidateQueries({ queryKey: qk.snapshots(userId) });
  queryClient.invalidateQueries({ queryKey: qk.debtLeak(userId) });
  queryClient.invalidateQueries({ queryKey: qk.allocation(userId) });
  queryClient.invalidateQueries({ queryKey: qk.personalization(userId) });
}
