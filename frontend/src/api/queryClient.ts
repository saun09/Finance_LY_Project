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
