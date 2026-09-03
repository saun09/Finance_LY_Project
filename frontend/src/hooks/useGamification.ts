import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { gamificationApi } from '../api/gamification';
import { qk, toApiError } from '../api/queryClient';
import { useDemoUser } from '../context/DemoUserContext';

/** GET /users/{id}/gamification/history -- every milestone ever awarded. */
export function useMilestoneHistory() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.gamificationHistory(userId),
    queryFn: () => gamificationApi.history(userId),
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}

/** POST /users/{id}/gamification/check -- evaluates thresholds against
 * current data and awards any newly-qualifying milestones (returns only
 * the newly-awarded ones). Screens call this once on load, then refetch
 * history so the full list reflects anything just awarded. */
export function useCheckMilestones() {
  const { userId } = useDemoUser();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => gamificationApi.check(userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.gamificationHistory(userId) }),
  });
}

export function useEducationProgress() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.gamificationEducation(userId),
    queryFn: () => gamificationApi.education(userId),
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}

export function useCompleteEducation() {
  const { userId } = useDemoUser();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, kind, answerIndex }: { itemId: string; kind: 'lesson' | 'quiz' | 'checklist'; answerIndex?: number }) =>
      gamificationApi.completeEducation(userId, itemId, kind, answerIndex),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.gamificationEducation(userId) }),
  });
}
