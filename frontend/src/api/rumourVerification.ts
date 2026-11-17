import { ApiError, apiClient } from './client';
import type {
  LocalRumourVerificationOut,
  RumourVerificationIn,
  RumourVerificationJobOut,
  RumourVerificationOut,
  VerificationEngineOut,
} from './types';

const VERIFY_POLL_INTERVAL_MS = 4_000;
// The backend marks a job failed after 10 minutes without a callback; stop
// a little after that in case a poll is lost.
const VERIFY_MAX_WAIT_MS = 11 * 60_000;

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

  /** Runs the n8n workflow, resolving once it has a verdict. The workflow
   * takes minutes and n8n Cloud cuts any request at ~100s, so this can't be
   * one request: the backend starts a job (n8n reports back to it by
   * callback) and this polls the job until it finishes. */
  verify: async (userId: string, body: RumourVerificationIn, logEvent = true): Promise<RumourVerificationOut> => {
    const started = await apiClient
      .post<RumourVerificationJobOut>(`/users/${userId}/rumour-verification`, body, {
        params: { log_event: logEvent },
        // only covers handing the rumour to n8n (backend waits up to 30s)
        timeout: 45_000,
      })
      .then((r) => r.data);

    const deadline = Date.now() + VERIFY_MAX_WAIT_MS;
    let job = started;
    while (job.status === 'pending') {
      if (Date.now() > deadline) {
        throw new ApiError('The broader workflow is taking unusually long. Please try again.', null);
      }
      await new Promise((resolve) => setTimeout(resolve, VERIFY_POLL_INTERVAL_MS));
      job = await apiClient
        .get<RumourVerificationJobOut>(`/users/${userId}/rumour-verification/jobs/${started.job_id}`)
        .then((r) => r.data);
    }
    if (job.status === 'failed' || !job.result) {
      throw new ApiError(job.error ?? 'The broader workflow failed. Please try again.', null);
    }
    return job.result;
  },

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
