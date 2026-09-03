import { useMutation, useQueryClient } from '@tanstack/react-query';
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { onboardingApi } from '../../api/onboarding';
import { invalidateFinancialData, qk } from '../../api/queryClient';
import type { HoldingType } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { HoldingTypePicker } from '../../components/HoldingTypePicker';
import { InlineError } from '../../components/InlineError';
import { ListRow } from '../../components/ListRow';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { useDemoUser } from '../../context/DemoUserContext';
import { useHoldings } from '../../hooks/useProfileManagement';
import { SPACE } from '../../theme/tokens';
import { formatPaise, rupeeInputToPaise } from '../../utils/currency';

export function HoldingsManageScreen() {
  const { userId } = useDemoUser();
  const queryClient = useQueryClient();
  const { data, isPending, error, refetch } = useHoldings();

  const [description, setDescription] = useState('');
  const [valueInput, setValueInput] = useState('');
  const [holdingType, setHoldingType] = useState<HoldingType | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const addMutation = useMutation({
    mutationFn: async () => {
      const value_paise = rupeeInputToPaise(valueInput);
      if (!description.trim() || value_paise === null) throw new Error('validation');
      return onboardingApi.postHolding(userId, { description: description.trim(), value_paise, holding_type: holdingType });
    },
    onSuccess: () => {
      setDescription('');
      setValueInput('');
      setHoldingType(null);
      queryClient.invalidateQueries({ queryKey: qk.holdings(userId) });
      invalidateFinancialData(queryClient, userId);
    },
    onError: (err) =>
      setFormError(err instanceof Error && err.message === 'validation' ? 'Enter a description and a value.' : toApiError(err).message),
  });

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Profile
        </Text>
        <Text variant="display">Holdings</Text>
      </View>

      {isPending ? (
        <SkeletonCard />
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : !data || data.length === 0 ? (
        <Card>
          <EmptyState title="No holdings yet" message="Add your savings and investments below." />
        </Card>
      ) : (
        <Card>
          {data.map((item) => (
            <ListRow key={item.id} title={item.description} subtitle={item.holding_type ?? 'Type not specified'} trailing={formatPaise(item.value_paise)} />
          ))}
        </Card>
      )}

      <Card style={styles.formCard}>
        <Text variant="label" tone="muted">
          ADD A HOLDING
        </Text>
        <TextField label="Description" value={description} onChangeText={setDescription} placeholder="HDFC Flexicap SIP" />
        <TextField label="Current value" value={valueInput} onChangeText={setValueInput} placeholder="250000" keyboardType="numeric" prefix="₹" />
        <HoldingTypePicker value={holdingType} onChange={setHoldingType} />
        {formError ? <InlineError message={formError} /> : null}
        <Button
          label="Add holding"
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
