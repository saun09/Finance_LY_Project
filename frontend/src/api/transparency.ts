import { apiClient } from './client';
import type {
  AvailableDecisionTypesOut,
  ContestDecisionIn,
  DecisionEventSummaryOut,
  TraceComparisonOut,
  TraceResultOut,
} from './types';

/** Every module_source Module 9 knows how to trace (mirrors
 * backend/app/services/transparency.py::DECISION_TYPES).
 *
 * Both Module 5 engines appear here, deliberately and separately: they make
 * different claims, and the index showing "explainable retrieval: 3" beside
 * "rumour verification: 5" is itself honest information about which engine
 * actually answered a user's questions. */
export const TRANSPARENCY_DECISION_TYPES = [
  'risk_profile',
  'allocation',
  'debt_leak_engine',
  'personalization',
  'gamification',
  'rumour_verification_local',
  'rumour_verification',
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

  /** Every recorded decision of this type, newest first. */
  getHistory: (userId: string, moduleSource: TransparencyDecisionType, limit = 50) =>
    apiClient
      .get<DecisionEventSummaryOut[]>(`/users/${userId}/transparency/${moduleSource}/history`, {
        params: { limit },
      })
      .then((r) => r.data),

  /** Field-level diff between two decisions -- what actually moved. */
  compare: (
    userId: string,
    moduleSource: TransparencyDecisionType,
    beforeEventId: string,
    afterEventId: string,
  ) =>
    apiClient
      .get<TraceComparisonOut>(`/users/${userId}/transparency/${moduleSource}/compare`, {
        params: { before_event_id: beforeEventId, after_event_id: afterEventId },
      })
      .then((r) => r.data),

  /** The closed set of contest reasons, served rather than hardcoded here
   * so the two can't drift apart. */
  getContestReasons: (userId: string) =>
    apiClient.get<string[]>(`/users/${userId}/transparency/contest-reasons`).then((r) => r.data),

  contest: (userId: string, moduleSource: TransparencyDecisionType, body: ContestDecisionIn) =>
    apiClient
      .post<TraceResultOut>(`/users/${userId}/transparency/${moduleSource}/contest`, body)
      .then((r) => r.data),
};
