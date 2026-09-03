import { useMutation, useQueryClient } from '@tanstack/react-query';
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { onboardingApi } from '../../api/onboarding';
import { qk } from '../../api/queryClient';
import type { InsuranceType } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ChoiceGroup } from '../../components/ChoiceGroup';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { InlineError } from '../../components/InlineError';
import { ListRow } from '../../components/ListRow';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { useDemoUser } from '../../context/DemoUserContext';
import { useInsurancePolicies } from '../../hooks/useProfileManagement';
import { SPACE } from '../../theme/tokens';
import { formatPaise, rupeeInputToPaise } from '../../utils/currency';

const POLICY_TYPE_OPTIONS: { value: InsuranceType; label: string }[] = [
  { value: 'life', label: 'Life' },
  { value: 'health', label: 'Health' },
];

export function InsuranceManageScreen() {
  const { userId } = useDemoUser();
  const queryClient = useQueryClient();
  const { data, isPending, error, refetch } = useInsurancePolicies();

  const [policyType, setPolicyType] = useState<InsuranceType | null>(null);
  const [sumAssuredInput, setSumAssuredInput] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const addMutation = useMutation({
    mutationFn: async () => {
      const sum_assured_paise = rupeeInputToPaise(sumAssuredInput);
      if (!policyType || sum_assured_paise === null) throw new Error('validation');
      return onboardingApi.postInsurancePolicy(userId, { policy_type: policyType, sum_assured_paise });
    },
    onSuccess: () => {
      setPolicyType(null);
      setSumAssuredInput('');
      queryClient.invalidateQueries({ queryKey: qk.insurancePolicies(userId) });
    },
    onError: (err) =>
      setFormError(err instanceof Error && err.message === 'validation' ? 'Choose a policy type and enter the sum assured.' : toApiError(err).message),
  });

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Profile
        </Text>
        <Text variant="display">Insurance</Text>
      </View>

      {isPending ? (
        <SkeletonCard />
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : !data || data.length === 0 ? (
        <Card>
          <EmptyState title="No policies yet" message="Add your life and health insurance policies below." />
        </Card>
      ) : (
        <Card>
          {data.map((item) => (
            <ListRow
              key={item.id}
              title={item.policy_type === 'life' ? 'Life insurance' : 'Health insurance'}
              trailing={formatPaise(item.sum_assured_paise)}
            />
          ))}
        </Card>
      )}

      <Card style={styles.formCard}>
        <Text variant="label" tone="muted">
          ADD A POLICY
        </Text>
        <ChoiceGroup label="Type" options={POLICY_TYPE_OPTIONS} value={policyType} onChange={setPolicyType} />
        <TextField label="Sum assured" value={sumAssuredInput} onChangeText={setSumAssuredInput} placeholder="1000000" keyboardType="numeric" prefix="₹" />
        {formError ? <InlineError message={formError} /> : null}
        <Button
          label="Add policy"
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
