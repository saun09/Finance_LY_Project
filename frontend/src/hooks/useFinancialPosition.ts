import { useQuery } from '@tanstack/react-query';
import { onboardingApi } from '../api/onboarding';
import { qk, toApiError } from '../api/queryClient';
import { useDemoUser } from '../context/DemoUserContext';

/** GET /users/{id}/financial-position -- Module 2's authoritative net
 * worth / surplus / buffer / EMI-ratio. This hook never recomputes any of
 * these from raw expense/EMI data; it only displays what the backend
 * already derived. */
export function useFinancialPosition() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.financialPosition(userId),
    queryFn: () => onboardingApi.getFinancialPosition(userId),
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}
