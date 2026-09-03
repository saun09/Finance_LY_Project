import { useQuery } from '@tanstack/react-query';
import { debtLeakApi } from '../api/debtLeak';
import { qk, toApiError } from '../api/queryClient';
import { useDemoUser } from '../context/DemoUserContext';

/** GET /users/{id}/debt-leak -- Module 6's recoverable-cost and debt-payoff
 * analysis. Used both by the dedicated Insights > Debt & Leaks screen and,
 * summarized, by Home's "what matters now" card -- same query key, so
 * both share one cached fetch instead of hitting the endpoint twice. */
export function useDebtLeak() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.debtLeak(userId),
    queryFn: () => debtLeakApi.get(userId),
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}
