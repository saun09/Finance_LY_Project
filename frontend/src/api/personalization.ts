import { apiClient } from './client';
import type { PersonalizationOut, RecordAllocationOutcomeIn } from './types';

export const personalizationApi = {
  get: (userId: string) =>
    apiClient.get<PersonalizationOut>(`/users/${userId}/personalization`).then((r) => r.data),

  recordAllocationOutcome: (userId: string, eventId: string, body: RecordAllocationOutcomeIn) =>
    apiClient.post(`/users/${userId}/allocation/${eventId}/outcome`, body).then((r) => r.data),
};
