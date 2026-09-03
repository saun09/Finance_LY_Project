import { useMutation, useQueryClient } from '@tanstack/react-query';
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { onboardingApi } from '../../api/onboarding';
import { invalidateFinancialData, qk } from '../../api/queryClient';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { InlineError } from '../../components/InlineError';
import { ListRow } from '../../components/ListRow';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { useDemoUser } from '../../context/DemoUserContext';
import { useEmis } from '../../hooks/useProfileManagement';
import { SPACE } from '../../theme/tokens';
import { formatPaise, percentInputToBps, rupeeInputToPaise } from '../../utils/currency';

export function DebtManageScreen() {
  const { userId } = useDemoUser();
  const queryClient = useQueryClient();
  const { data, isPending, error, refetch } = useEmis();

  const [lender, setLender] = useState('');
  const [amountInput, setAmountInput] = useState('');
  const [tenureInput, setTenureInput] = useState('');
  const [rateInput, setRateInput] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [closingId, setClosingId] = useState<string | null>(null);

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: qk.emis(userId) });
    invalidateFinancialData(queryClient, userId);
  };

  const addMutation = useMutation({
    mutationFn: async () => {
      const amount_paise = rupeeInputToPaise(amountInput);
      const remaining_tenure_months = /^\d+$/.test(tenureInput.trim()) ? Number(tenureInput.trim()) : null;
      const annual_rate_bps = percentInputToBps(rateInput);
      if (!lender.trim() || amount_paise === null || remaining_tenure_months === null || annual_rate_bps === null) {
        throw new Error('validation');
      }
      return onboardingApi.postEmi(userId, { lender: lender.trim(), amount_paise, remaining_tenure_months, annual_rate_bps });
    },
    onSuccess: () => {
      setLender('');
      setAmountInput('');
      setTenureInput('');
      setRateInput('');
      invalidateAll();
    },
    onError: (err) =>
      setFormError(
        err instanceof Error && err.message === 'validation'
          ? 'Enter a lender, monthly EMI, remaining months, and rate.'
          : toApiError(err).message,
      ),
  });

  const closeMutation = useMutation({
    mutationFn: async (emiId: string) => {
      setClosingId(emiId);
      return onboardingApi.closeEmi(userId, emiId);
    },
    onSuccess: invalidateAll,
    onSettled: () => setClosingId(null),
  });

  const active = data?.filter((e) => e.closed_at === null) ?? [];
  const closed = data?.filter((e) => e.closed_at !== null) ?? [];

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Profile
        </Text>
        <Text variant="display">Loans & EMIs</Text>
      </View>

      {isPending ? (
        <SkeletonCard />
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : (
        <>
          {active.length === 0 && closed.length === 0 ? (
            <Card>
              <EmptyState title="No loans recorded" message="Add a loan below if you have one." />
            </Card>
          ) : (
            <Card>
              {active.map((item) => (
                <ListRow
                  key={item.id}
                  title={item.lender}
                  subtitle={`${item.remaining_tenure_months} months left · ${(item.annual_rate_bps / 100).toFixed(2)}% p.a.`}
                  trailing={`${formatPaise(item.amount_paise)}/mo`}
                  onRemove={() => closeMutation.mutate(item.id)}
                  removing={closingId === item.id}
                />
              ))}
            </Card>
          )}

          {closed.length > 0 ? (
            <Card>
              <SectionHeader title="Closed" subtitle="Fully paid off" />
              {closed.map((item) => (
                <ListRow key={item.id} title={item.lender} subtitle="Closed" trailing={`${formatPaise(item.amount_paise)}/mo`} />
              ))}
            </Card>
          ) : null}
        </>
      )}

      <Card style={styles.formCard}>
        <Text variant="label" tone="muted">
          ADD A LOAN
        </Text>
        <TextField label="Lender" value={lender} onChangeText={setLender} placeholder="HDFC Bank" />
        <TextField label="Monthly EMI" value={amountInput} onChangeText={setAmountInput} placeholder="18000" keyboardType="numeric" prefix="₹" />
        <TextField label="Remaining tenure (months)" value={tenureInput} onChangeText={setTenureInput} placeholder="36" keyboardType="numeric" />
        <TextField label="Interest rate (annual %)" value={rateInput} onChangeText={setRateInput} placeholder="9.5" keyboardType="decimal-pad" />
        {formError ? <InlineError message={formError} /> : null}
        <Button
          label="Add loan"
          variant="secondary"
          loading={addMutation.isPending}
          onPress={() => {
            setFormError(null);
            addMutation.mutate();
          }}
        />
      </Card>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  formCard: { gap: SPACE.md },
});
