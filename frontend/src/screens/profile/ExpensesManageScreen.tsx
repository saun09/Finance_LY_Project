import { useMutation, useQueryClient } from '@tanstack/react-query';
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { onboardingApi } from '../../api/onboarding';
import { invalidateFinancialData, qk } from '../../api/queryClient';
import type { ExpenseFrequency } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ChoiceGroup } from '../../components/ChoiceGroup';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { InlineError } from '../../components/InlineError';
import { ListRow } from '../../components/ListRow';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { Toggle } from '../../components/Toggle';
import { useDemoUser } from '../../context/DemoUserContext';
import { useExpenses } from '../../hooks/useProfileManagement';
import { SPACE } from '../../theme/tokens';
import { formatPaise, rupeeInputToPaise } from '../../utils/currency';

const FREQUENCY_OPTIONS: { value: ExpenseFrequency; label: string }[] = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'annual', label: 'Annual' },
  { value: 'one_time', label: 'One-time' },
];

export function ExpensesManageScreen() {
  const { userId } = useDemoUser();
  const queryClient = useQueryClient();
  const { data, isPending, error, refetch } = useExpenses();

  const [category, setCategory] = useState('');
  const [amountInput, setAmountInput] = useState('');
  const [frequency, setFrequency] = useState<ExpenseFrequency | null>(null);
  const [isEssential, setIsEssential] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: qk.expenses(userId) });
    invalidateFinancialData(queryClient, userId);
  };

  const addMutation = useMutation({
    mutationFn: async () => {
      const amount_paise = rupeeInputToPaise(amountInput);
      if (!category.trim() || amount_paise === null || !frequency) throw new Error('validation');
      return onboardingApi.postExpenseItem(userId, {
        category: category.trim(),
        amount_paise,
        frequency,
        is_essential: isEssential,
      });
    },
    onSuccess: () => {
      setCategory('');
      setAmountInput('');
      setFrequency(null);
      setIsEssential(true);
      invalidateAll();
    },
    onError: (err) =>
      setFormError(err instanceof Error && err.message === 'validation' ? 'Enter a category, a valid amount, and a frequency.' : toApiError(err).message),
  });

  const removeMutation = useMutation({
    mutationFn: async (itemId: string) => {
      setRemovingId(itemId);
      return onboardingApi.removeExpenseItem(userId, itemId);
    },
    onSuccess: invalidateAll,
    onSettled: () => setRemovingId(null),
  });

  const active = data?.filter((e) => e.removed_at === null) ?? [];
  const removed = data?.filter((e) => e.removed_at !== null) ?? [];

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Profile
        </Text>
        <Text variant="display">Expenses</Text>
      </View>

      {isPending ? (
        <SkeletonCard />
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : (
        <>
          {active.length === 0 && removed.length === 0 ? (
            <Card>
              <EmptyState title="No expenses yet" message="Add your recurring expenses below." />
            </Card>
          ) : (
            <Card>
              {active.map((item) => (
                <ListRow
                  key={item.id}
                  title={item.category}
                  subtitle={`${item.frequency}${item.is_essential ? ' · essential' : ''}`}
                  trailing={formatPaise(item.amount_paise)}
                  onRemove={() => removeMutation.mutate(item.id)}
                  removing={removingId === item.id}
                />
              ))}
            </Card>
          )}

          {removed.length > 0 ? (
            <Card>
              <SectionHeader title="Removed" subtitle="Kept for history — no longer counted" />
              {removed.map((item) => (
                <ListRow
                  key={item.id}
                  title={item.category}
                  subtitle={`${item.frequency} · removed`}
                  trailing={formatPaise(item.amount_paise)}
                />
              ))}
            </Card>
          ) : null}
        </>
      )}

      <Card style={styles.formCard}>
        <Text variant="label" tone="muted">
          ADD AN EXPENSE
        </Text>
        <TextField label="Category" value={category} onChangeText={setCategory} placeholder="Rent" />
        <TextField
          label="Amount"
          value={amountInput}
          onChangeText={setAmountInput}
          placeholder="15000"
          keyboardType="numeric"
          prefix="₹"
        />
        <ChoiceGroup label="Frequency" options={FREQUENCY_OPTIONS} value={frequency} onChange={setFrequency} />
        <Toggle label="Essential" value={isEssential} onChange={setIsEssential} />
        {formError ? <InlineError message={formError} /> : null}
        <Button
          label="Add expense"
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
