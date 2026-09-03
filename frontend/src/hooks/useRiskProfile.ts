import { useQuery } from '@tanstack/react-query';
import { riskProfileApi } from '../api/riskProfile';
import { qk, toApiError } from '../api/queryClient';
import { useDemoUser } from '../context/DemoUserContext';

/** GET /risk-profile/questionnaire -- static config, not user-scoped, so
 * it's fetched once and cached indefinitely for the app session (there's
 * no reason to re-fetch it per user). */
export function useQuestionnaire() {
  const query = useQuery({
    queryKey: qk.questionnaire(),
    queryFn: () => riskProfileApi.getQuestionnaire(),
    staleTime: Infinity,
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}

/** GET /users/{id}/risk-profile/latest -- 404s until the user has
 * submitted the questionnaire at least once; screens should treat a 404
 * here as "not yet taken", not as a real error. */
export function useRiskProfileLatest() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.riskProfileLatest(userId),
    queryFn: () => riskProfileApi.getLatest(userId),
    retry: false,
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}
