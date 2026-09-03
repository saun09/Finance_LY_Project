import { useQuery } from '@tanstack/react-query';
import { onboardingApi } from '../api/onboarding';
import { qk, toApiError } from '../api/queryClient';
import { useDemoUser } from '../context/DemoUserContext';

/** Read hooks backing the Profile tab's management screens -- GET
 * /profile, /emis, /insurance-policies, /holdings, /expenses. All 404 for
 * a user with no profile yet, which screens should treat as "nothing
 * recorded", not a real error. */

export function useProfile() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.profile(userId),
    queryFn: () => onboardingApi.getProfile(userId),
    retry: false,
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}

export function useEmis() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.emis(userId),
    queryFn: () => onboardingApi.getEmis(userId),
    retry: false,
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}

export function useInsurancePolicies() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.insurancePolicies(userId),
    queryFn: () => onboardingApi.getInsurancePolicies(userId),
    retry: false,
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}

export function useHoldings() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.holdings(userId),
    queryFn: () => onboardingApi.getHoldings(userId),
    retry: false,
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}

export function useExpenses() {
  const { userId } = useDemoUser();
  const query = useQuery({
    queryKey: qk.expenses(userId),
    queryFn: () => onboardingApi.getExpenseItems(userId),
    retry: false,
  });
  return { ...query, error: query.error ? toApiError(query.error) : null };
}
