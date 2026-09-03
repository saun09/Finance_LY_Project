import { apiClient } from './client';
import type { SuggestionEventRead, UserMonthlySnapshotRead } from './types';

export const eventsApi = {
  getEvents: (
    userId: string,
    params?: { module_source?: string; since?: string; until?: string; limit?: number; offset?: number },
  ) => apiClient.get<SuggestionEventRead[]>(`/users/${userId}/events`, { params }).then((r) => r.data),

  getSnapshots: (userId: string, params?: { since_month?: string; until_month?: string; limit?: number }) =>
    apiClient.get<UserMonthlySnapshotRead[]>(`/users/${userId}/snapshots`, { params }).then((r) => r.data),
};
