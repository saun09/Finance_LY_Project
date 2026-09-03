import { useQuery } from '@tanstack/react-query';
import { transparencyApi, TransparencyDecisionType } from '../api/transparency';
import { qk, toApiError } from '../api/queryClient';
import { useDemoUser } from '../context/DemoUserContext';

/** GET /users/{id}/transparency -- how many traceable decisions exist per
 * module. Always 200s (an empty user just gets all-zero counts). */
export function useTransparencyIndex() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.transparencyIndex(userId),
    queryFn: () => transparencyApi.listAvailable(userId),
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}

/** GET /users/{id}/transparency/{module_source} -- the full trace for the
 * most recent decision of that type. 404s if none exists yet. */
export function useTransparencyTrace(moduleSource: TransparencyDecisionType) {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.transparencyTrace(userId, moduleSource),
    queryFn: () => transparencyApi.getTrace(userId, moduleSource),
    retry: false,
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}
