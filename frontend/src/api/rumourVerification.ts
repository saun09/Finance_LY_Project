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
      })
      .then((r) => r.data),
};
