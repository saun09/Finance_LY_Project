import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React from 'react';
import { View } from 'react-native';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LineChart } from '../../components/LineChart';
import { MenuList } from '../../components/MenuList';
import { NudgeEntryButton } from '../../components/NudgeAssistant';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { Skeleton } from '../../components/Skeleton';
import { MetricCard } from '../../components/MetricCard';
import { Text } from '../../components/Text';
import { useDebtLeak } from '../../hooks/useDebtLeak';
import { useFinancialPosition } from '../../hooks/useFinancialPosition';
import { usePersonalization } from '../../hooks/usePersonalization';
import { useSnapshotHistory } from '../../hooks/useSnapshotHistory';
import type { InsightsStackParamList } from '../../navigation/types';
import { SPACE } from '../../theme/tokens';
import { formatPaise, formatPercent } from '../../utils/currency';

type Nav = NativeStackNavigationProp<InsightsStackParamList, 'Insights'>;

export function InsightsScreen() {
  const navigation = useNavigation<Nav>();
  const debtLeak = useDebtLeak();
  const personalization = usePersonalization();
  const position = useFinancialPosition();
  const snapshots = useSnapshotHistory();

  const leaksSubtitle = debtLeak.data
    ? debtLeak.data.total_recoverable_annual_paise > 0
      ? `${formatPaise(debtLeak.data.total_recoverable_annual_paise)}/year flagged`
      : 'Nothing flagged right now'
    : 'Spending patterns and idle cash';

  const debtSubtitle = debtLeak.data?.avalanche_snowball
    ? `${debtLeak.data.avalanche_snowball.avalanche.months_to_clear_all} months to clear all loans`
    : 'Payoff strategy comparison';

  const personalizationSubtitle =
    personalization.data && !personalization.error
      ? `${Number(personalization.data.applied_offset_pct_points) >= 0 ? '+' : ''}${Number(personalization.data.applied_offset_pct_points).toFixed(1)} pt shift from ${personalization.data.edits_considered} past choices`
      : 'How your habits tilt your target';

  // Oldest-first for the chart; the backend returns most-recent-first.
  const chartPoints = (snapshots.data ?? [])
    .slice()
    .reverse()
    .map((s) => ({
      label: new Date(s.month).toLocaleDateString('en-IN', { month: 'short' }),
      value: s.surplus,
    }));

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Your insights
        </Text>
        <Text variant="display">Beyond the numbers</Text>
      </View>

      <NudgeEntryButton surface="insights" />

      {position.data ? (
        <MetricCard
          label="EMI-to-income"
          animated={{ target: Number(position.data.emi_to_income_ratio) * 100, formatter: (n) => formatPercent(n, 1) }}
          icon="pie-chart-outline"
          // Same ratio as the figure, just as a bar -- not a different
          // metric, and not rescaled: a ratio of 0.75 fills 75% of the
          // track, full stop.
          progressFraction={Number(position.data.emi_to_income_ratio)}
          info={{
            title: 'EMI-to-income ratio',
            description: 'Your total monthly loan repayments (EMIs), shown as a share of your monthly income.',
          }}
        />
      ) : null}

      <MenuList
        items={[
          { key: 'leaks', title: 'Spending to review', subtitle: leaksSubtitle, onPress: () => navigation.navigate('Leaks') },
          { key: 'debt', title: 'Debt payoff', subtitle: debtSubtitle, onPress: () => navigation.navigate('Debt') },
          {
            key: 'personalization',
            title: 'Personalization',
            subtitle: personalizationSubtitle,
            onPress: () => navigation.navigate('Personalization'),
          },
          {
            key: 'transparency',
            title: 'Transparency',
            subtitle: 'See exactly how each figure was calculated',
            onPress: () => navigation.navigate('Transparency'),
          },
        ]}
      />

      <Card>
        <SectionHeader title="Cash-flow trend" subtitle="Monthly surplus, every month on record" />
        {snapshots.isPending ? (
          <Skeleton height={140} style={{ marginTop: SPACE.sm }} />
        ) : snapshots.error ? (
          <ErrorState message={snapshots.error.message} onRetry={() => snapshots.refetch()} />
        ) : chartPoints.length >= 2 ? (
          <View style={{ marginTop: SPACE.sm, gap: SPACE.xs }}>
            <Text variant="caption" tone="faint">
              MONTHLY SURPLUS
            </Text>
            <LineChart points={chartPoints} formatValue={formatPaise} />
          </View>
        ) : (
          <EmptyState
            title="No history yet"
            message="Your financial timeline will appear here as you build monthly snapshots."
          />
        )}
      </Card>
    </ScreenContainer>
  );
}
