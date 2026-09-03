import { useQuery } from '@tanstack/react-query';
import { personalizationApi } from '../api/personalization';
import { eventsApi } from '../api/events';
import { qk, toApiError } from '../api/queryClient';
import { useDemoUser } from '../context/DemoUserContext';

/** GET /users/{id}/personalization -- Module 7's behavior-driven offset on
 * top of the base Module 4 target. 409s until both a risk tier and an
 * allocation suggestion exist (NoRiskTierError / NoAllocationSuggestionError). */
export function usePersonalization() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.personalization(userId),
    queryFn: () => personalizationApi.get(userId),
    retry: false,
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}

/** The most recent allocation suggestion_event, purely to get its
 * event_id -- POST /allocation/{event_id}/outcome needs it, and there is
 * no other way to learn it (GET /allocation itself doesn't return one). */
export function useLatestAllocationEvent() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.events(userId, 'allocation'),
    queryFn: () => eventsApi.getEvents(userId, { module_source: 'allocation', limit: 1 }),
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}
