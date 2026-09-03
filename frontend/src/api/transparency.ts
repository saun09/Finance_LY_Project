import { apiClient } from './client';
import type { AvailableDecisionTypesOut, TraceResultOut } from './types';

/** module_source values Module 9 actually knows how to trace (see
 * backend/app/services/transparency.py::DECISION_TYPES) -- Module 5 has
 * its own, separate trace, never fetched through this endpoint. */
export const TRANSPARENCY_DECISION_TYPES = [
  'risk_profile',
  'allocation',
  'debt_leak_engine',
  'personalization',
] as const;
export type TransparencyDecisionType = (typeof TRANSPARENCY_DECISION_TYPES)[number];

export const transparencyApi = {
  listAvailable: (userId: string) =>
    apiClient.get<AvailableDecisionTypesOut>(`/users/${userId}/transparency`).then((r) => r.data),

  getTrace: (userId: string, moduleSource: TransparencyDecisionType, eventId?: string) =>
    apiClient
      .get<TraceResultOut>(`/users/${userId}/transparency/${moduleSource}`, {
        params: eventId ? { event_id: eventId } : undefined,
      })
      .then((r) => r.data),
};
