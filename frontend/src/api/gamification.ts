import { apiClient } from './client';
import type { AwardedMilestoneOut, EducationProgressOut, MilestoneHistoryOut, QuizResultOut } from './types';

export const gamificationApi = {
  check: (userId: string) =>
    apiClient.post<AwardedMilestoneOut[]>(`/users/${userId}/gamification/check`).then((r) => r.data),

  history: (userId: string) =>
    apiClient.get<MilestoneHistoryOut>(`/users/${userId}/gamification/history`).then((r) => r.data),

  education: (userId: string) =>
    apiClient.get<EducationProgressOut>(`/users/${userId}/gamification/education`).then((r) => r.data),

  completeEducation: (userId: string, itemId: string, kind: 'lesson' | 'quiz' | 'checklist', answerIndex?: number) =>
    apiClient.post<QuizResultOut | null>(`/users/${userId}/gamification/education/complete`, {
      item_id: itemId,
      kind,
      answer_index: answerIndex,
    }).then((r) => r.data),
};
