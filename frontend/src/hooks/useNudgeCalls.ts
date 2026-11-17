import { useQuery } from '@tanstack/react-query';
import { nudgeApi } from '../api/nudge';
import { qk } from '../api/queryClient';
import { useDemoUser } from '../context/DemoUserContext';

/** GET /users/{id}/nudge/conversations -- every saved Nudge call, most
 * recent first, for the "Your calls" list. */
export function useNudgeCalls() {
  const { userId } = useDemoUser();
  return useQuery({
    queryKey: qk.nudgeCalls(userId),
    queryFn: () => nudgeApi.listConversations(userId),
  });
}

/** One saved call with its full transcript. */
export function useNudgeCall(conversationId: string) {
  const { userId } = useDemoUser();
  return useQuery({
    queryKey: qk.nudgeCall(userId, conversationId),
    queryFn: () => nudgeApi.getConversation(userId, conversationId),
  });
}
