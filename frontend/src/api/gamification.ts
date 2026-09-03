import { apiClient } from './client';
import type { AwardedMilestoneOut, MilestoneHistoryOut } from './types';

export const gamificationApi = {
  check: (userId: string) =>
    apiClient.post<AwardedMilestoneOut[]>(`/users/${userId}/gamification/check`).then((r) => r.data),

  history: (userId: string) =>
    apiClient.get<MilestoneHistoryOut>(`/users/${userId}/gamification/history`).then((r) => r.data),
};
