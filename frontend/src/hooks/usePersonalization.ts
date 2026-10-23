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

/** Allocation choices the user kept or set but hasn't invested yet. Each
 * counts at half weight until marked as invested, so the screen offers a
 * one-tap follow-up. (The suggestion currently on screen comes with its own
 * event_id from GET /allocation -- this is only for earlier ones.) */
export function usePendingInvestments() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.events(userId, 'allocation'),
    queryFn: () => eventsApi.getEvents(userId, { module_source: 'allocation', limit: 50 }),
    select: (events) =>
      events.filter(
        (e) => (e.action_taken === 'accepted' || e.action_taken === 'edited') && e.funded === false,
      ),
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}
