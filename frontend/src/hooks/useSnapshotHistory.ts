import { useQuery } from '@tanstack/react-query';
import { eventsApi } from '../api/events';
import { qk, toApiError } from '../api/queryClient';
import { useDemoUser } from '../context/DemoUserContext';

/** GET /users/{id}/snapshots -- real monthly history only. If there's
 * fewer than 2 points, screens should show the "your timeline will
 * appear as you build history" empty state rather than a one-dot chart. */
export function useSnapshotHistory() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.snapshots(userId),
    queryFn: () => eventsApi.getSnapshots(userId, { limit: 24 }),
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}
