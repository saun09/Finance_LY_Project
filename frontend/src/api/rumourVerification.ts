import { apiClient } from './client';
import type {
  LocalRumourVerificationOut,
  RumourVerificationIn,
  RumourVerificationOut,
  VerificationEngineOut,
} from './types';

/** Module 5 (modules/rumour_verification/) has two engines, and they make
 * different claims. This client keeps them as two separate calls rather
 * than one call with a flag, so a screen cannot accidentally present one
 * engine's output under the other's label:
 *
 *   `verify`  -> the n8n LLM workflow. Not limited to a fixed corpus, but
 *                returns a verdict and its own prose. No candidate list,
 *                so no elimination trace this project can verify.
 *   `explain` -> the local constrained-retrieval pipeline. Limited to the
 *                filings corpus, and in exchange it can show every
 *                candidate considered and the constraint that eliminated
 *                each one. This is the path the project's explainability
 *                claim attaches to.
 *
 * This only ever verifies text the user pastes in; there is no endpoint
 * for automatic detection or monitoring, and there never will be. */
export const rumourVerificationApi = {
  listEngines: (userId: string) =>
    apiClient
      .get<{ engines: VerificationEngineOut[] }>(`/users/${userId}/rumour-verification/engines`)
      .then((r) => r.data.engines),

  verify: (userId: string, body: RumourVerificationIn, logEvent = true) =>
    apiClient
      .post<RumourVerificationOut>(`/users/${userId}/rumour-verification`, body, {
        params: { log_event: logEvent },
      })
      .then((r) => r.data),

  /** 503s if the local engine's research dependencies aren't installed --
   * deliberately, rather than falling back to `verify`, which would hand
   * the user something other than the explanation they asked for. */
  explain: (userId: string, body: RumourVerificationIn, logEvent = true) =>
    apiClient
      .post<LocalRumourVerificationOut>(`/users/${userId}/rumour-verification/explain`, body, {
        params: { log_event: logEvent },
      })
      .then((r) => r.data),
};
