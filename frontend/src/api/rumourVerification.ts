import { apiClient } from './client';
import type { RumourVerificationIn, RumourVerificationOut } from './types';

/** Bridges to Module 5 (modules/rumour_verification/), which the backend
 * calls unchanged -- see backend/app/services/rumour_verification_bridge.py.
 * This only ever verifies text the user pastes in; there is no endpoint
 * for automatic detection or monitoring, and there never will be. */
export const rumourVerificationApi = {
  verify: (userId: string, body: RumourVerificationIn, logEvent = true) =>
    apiClient
      .post<RumourVerificationOut>(`/users/${userId}/rumour-verification`, body, {
        params: { log_event: logEvent },
        // This calls out to an LLM-backed n8n workflow, not a local DB lookup
        // -- the backend's own timeout waiting on n8n is 60s (see
        // rumour_verification_bridge.py), so the client-wide 15s default is
        // far too short and aborts before the backend even gives up.
        timeout: 65_000,
      })
      .then((r) => r.data),
};
