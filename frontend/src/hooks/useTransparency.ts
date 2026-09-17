import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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

/** GET /users/{id}/transparency/{module_source} -- the full trace.
 *
 * `eventId` selects one specific past decision; omitted, the server returns
 * the most recent. Every decision is already stored by Module 1, so being
 * able to address an older one is the difference between "here is your
 * current tier" and "here is the tier you had in March, and why". 404s if
 * no decision of this type exists yet. */
export function useTransparencyTrace(moduleSource: TransparencyDecisionType, eventId?: string) {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.transparencyTrace(userId, moduleSource, eventId),
    queryFn: () => transparencyApi.getTrace(userId, moduleSource, eventId),
    retry: false,
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}

/** GET /users/{id}/transparency/{module_source}/history -- every recorded
 * decision of this type, newest first. */
export function useTransparencyHistory(moduleSource: TransparencyDecisionType) {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.transparencyHistory(userId, moduleSource),
    queryFn: () => transparencyApi.getHistory(userId, moduleSource),
    retry: false,
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}

/** GET .../compare -- which stored input actually moved between two
 * decisions. Disabled until both event ids are chosen. */
export function useTransparencyComparison(
  moduleSource: TransparencyDecisionType,
  beforeEventId: string | null,
  afterEventId: string | null,
) {
  const { userId } = useDemoUser();
  const enabled = Boolean(beforeEventId && afterEventId);
  const query = useQuery({
    queryKey: qk.transparencyCompare(userId, moduleSource, beforeEventId ?? '', afterEventId ?? ''),
    queryFn: () => transparencyApi.compare(userId, moduleSource, beforeEventId!, afterEventId!),
    enabled,
    retry: false,
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}

/** The server's closed set of contest reasons. Fetched rather than
 * hardcoded so the picker can never offer a code the API would reject. */
export function useContestReasons() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.transparencyContestReasons(userId),
    queryFn: () => transparencyApi.getContestReasons(userId),
    staleTime: Infinity,
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}

/** POST .../contest -- records the user's objection through Module 1's
 * event log, which is where Module 7's feedback loop already reads. A
 * trace the user can read but not answer back to is a one-way mirror. */
export function useContestDecision(moduleSource: TransparencyDecisionType) {
  const { userId } = useDemoUser();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ eventId, reasonCode, note }: { eventId: string; reasonCode: string; note?: string }) =>
      transparencyApi.contest(userId, moduleSource, { event_id: eventId, reason_code: reasonCode, note }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transparency-trace', userId, moduleSource] });
      queryClient.invalidateQueries({ queryKey: qk.transparencyHistory(userId, moduleSource) });
    },
  });
}
