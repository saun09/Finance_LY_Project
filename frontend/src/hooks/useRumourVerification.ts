import { useQuery } from '@tanstack/react-query';
import { rumourVerificationApi } from '../api/rumourVerification';
import { qk } from '../api/queryClient';
import { useDemoUser } from '../context/DemoUserContext';

/** GET /users/{id}/rumour-verification/engines -- which Module 5 engines
 * this deployment can actually run, and what each one honestly claims.
 * Used for the live "is the filing archive up" status badge and the mode
 * selector's "Search Mode Details" popover, rather than hardcoding either. */
export function useRumourEngines() {
  const { userId } = useDemoUser();
  return useQuery({
    queryKey: qk.verificationEngines(userId),
    queryFn: () => rumourVerificationApi.listEngines(userId),
  });
}
