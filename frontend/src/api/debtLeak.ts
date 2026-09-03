import { apiClient } from './client';
import type {
  CreditCardRevolvingCostIn,
  CreditCardRevolvingCostOut,
  DebtLeakReportOut,
  RefinanceBreakevenIn,
  RefinanceBreakevenOut,
} from './types';

export const debtLeakApi = {
  get: (userId: string) => apiClient.get<DebtLeakReportOut>(`/users/${userId}/debt-leak`).then((r) => r.data),

  creditCardRevolvingCost: (userId: string, body: CreditCardRevolvingCostIn) =>
    apiClient
      .post<CreditCardRevolvingCostOut>(`/users/${userId}/debt-leak/credit-card-revolving-cost`, body)
      .then((r) => r.data),

  refinanceBreakeven: (userId: string, body: RefinanceBreakevenIn) =>
    apiClient
      .post<RefinanceBreakevenOut>(`/users/${userId}/debt-leak/refinance-breakeven`, body)
      .then((r) => r.data),
};
