import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation } from '@tanstack/react-query';
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { onboardingApi } from '../../api/onboarding';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { InlineError } from '../../components/InlineError';
import { MetricCard } from '../../components/MetricCard';
import { OnboardingProgress } from '../../components/OnboardingProgress';
import { ScreenContainer } from '../../components/ScreenContainer';
import { Skeleton } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useDemoUser } from '../../context/DemoUserContext';
import { useFinancialPosition } from '../../hooks/useFinancialPosition';
import { SPACE } from '../../theme/tokens';
import type { OnboardingStackParamList } from '../../navigation/types';
import { formatPaise, formatPercent } from '../../utils/currency';

type Nav = NativeStackNavigationProp<OnboardingStackParamList, 'Review'>;

export function ReviewScreen() {
  const navigation = useNavigation<Nav>();
  const { userId } = useDemoUser();
  const { data, isLoading, error, refetch } = useFinancialPosition();
  const [completeError, setCompleteError] = useState<string | null>(null);

  const completeMutation = useMutation({
    mutationFn: () => onboardingApi.completeOnboarding(userId),
    onSuccess: (snapshot) => navigation.navigate('Snapshot', { snapshot }),
    onError: (err) => setCompleteError(toApiError(err).message),
  });

  return (
    <ScreenContainer>
      <OnboardingProgress
        step={6}
        total={7}
        title="Here's what we calculated"
        subtitle="Everything below comes straight from what you entered — nothing here is a guess."
      />

      {isLoading ? (
        <View style={styles.grid}>
          <Skeleton height={92} style={styles.half} />
          <Skeleton height={92} style={styles.half} />
          <Skeleton height={92} style={styles.half} />
          <Skeleton height={92} style={styles.half} />
        </View>
      ) : error ? (
        <Card>
          <Text variant="bodyMedium" tone="danger">
            {error.message}
          </Text>
          <Button label="Try again" variant="ghost" onPress={() => refetch()} />
        </Card>
      ) : data ? (
        <View style={styles.grid}>
          <MetricCard
            label="Net worth"
            value={formatPaise(data.net_worth_paise)}
            tone={data.net_worth_paise >= 0 ? 'positive' : 'danger'}
          />
          <MetricCard
            label="Monthly surplus"
            value={formatPaise(data.monthly_surplus_paise)}
            tone={data.monthly_surplus_paise >= 0 ? 'positive' : 'danger'}
          />
          <MetricCard
            label="Emergency buffer"
            value={`${Number(data.buffer_coverage_months).toFixed(1)} mo`}
            tone={Number(data.buffer_coverage_months) >= 6 ? 'positive' : 'warning'}
          />
          <MetricCard
            label="EMI-to-income"
            value={formatPercent(Number(data.emi_to_income_ratio) * 100, 1)}
          />
        </View>
      ) : null}

      <Card>
        <Text variant="bodyMedium" tone="muted">
          You can add or adjust expenses, loans, insurance, and holdings any time from your Profile tab —
          this isn't the last chance to get it right.
        </Text>
      </Card>

      {completeError ? <InlineError message={completeError} /> : null}

      <View style={styles.footer}>
        <Button
          label="Confirm & finish setup"
          fullWidth
          loading={completeMutation.isPending}
          disabled={isLoading || !!error}
          onPress={() => {
            setCompleteError(null);
            completeMutation.mutate();
          }}
        />
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.md },
  half: { flexBasis: '47%' },
  footer: { marginTop: SPACE.md },
});
