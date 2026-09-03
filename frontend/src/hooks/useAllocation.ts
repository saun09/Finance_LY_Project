import { useQuery } from '@tanstack/react-query';
import { allocationApi } from '../api/allocation';
import { qk, toApiError } from '../api/queryClient';
import { useDemoUser } from '../context/DemoUserContext';

/** GET /users/{id}/allocation -- Module 4's target vs. current exposure.
 * 409s if no risk profile exists yet (NoRiskTierError), 422s if any
 * holding was saved without a holding_type (UnclassifiedHoldingsError) --
 * both are real, expected states the screen must show, not swallow. */
export function useAllocation() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.allocation(userId),
    queryFn: () => allocationApi.get(userId),
    retry: false,
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}
