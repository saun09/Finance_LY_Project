import { apiClient } from './client';
import type {
  NudgeBriefingOut,
  NudgeConversationDetailOut,
  NudgeConversationOut,
  NudgeConversationSummaryOut,
  NudgeMessageOut,
  NudgeRole,
  NudgeSearchIn,
  NudgeSearchOut,
} from './types';

export const nudgeApi = {
  briefing: (userId: string, surface: string, conversationId?: string) =>
    apiClient
      .get<NudgeBriefingOut>(`/users/${userId}/nudge/briefing`, {
        params: { surface, conversation_id: conversationId },
      })
      .then((r) => r.data),

  search: (userId: string, body: NudgeSearchIn) =>
    apiClient.post<NudgeSearchOut>(`/users/${userId}/nudge/search`, body).then((r) => r.data),

  startConversation: (userId: string, surface: string) =>
    apiClient.post<NudgeConversationOut>(`/users/${userId}/nudge/conversations`, { surface }).then((r) => r.data),

  addMessage: (userId: string, conversationId: string, role: NudgeRole, text: string) =>
    apiClient
      .post<NudgeMessageOut>(`/users/${userId}/nudge/conversations/${conversationId}/messages`, { role, text })
      .then((r) => r.data),

  endConversation: (userId: string, conversationId: string, elevenlabsConversationId?: string | null) =>
    apiClient
      .post<NudgeConversationOut>(`/users/${userId}/nudge/conversations/${conversationId}/end`, {
        elevenlabs_conversation_id: elevenlabsConversationId ?? null,
      })
      .then((r) => r.data),

  listConversations: (userId: string) =>
    apiClient.get<NudgeConversationSummaryOut[]>(`/users/${userId}/nudge/conversations`).then((r) => r.data),

  getConversation: (userId: string, conversationId: string) =>
    apiClient
      .get<NudgeConversationDetailOut>(`/users/${userId}/nudge/conversations/${conversationId}`)
      .then((r) => r.data),
};
