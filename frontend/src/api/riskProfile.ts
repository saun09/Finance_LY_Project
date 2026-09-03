import { apiClient } from './client';
import type { QuestionnaireOut, RiskTierOut } from './types';

export const riskProfileApi = {
  getQuestionnaire: () => apiClient.get<QuestionnaireOut>('/risk-profile/questionnaire').then((r) => r.data),

  submitAnswers: (userId: string, answers: Record<string, string>) =>
    apiClient.post<RiskTierOut>(`/users/${userId}/risk-profile`, { answers }).then((r) => r.data),

  getLatest: (userId: string) =>
    apiClient.get<RiskTierOut>(`/users/${userId}/risk-profile/latest`).then((r) => r.data),
};
