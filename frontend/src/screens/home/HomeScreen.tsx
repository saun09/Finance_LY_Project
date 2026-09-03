import React from 'react';
import { StyleSheet, View } from 'react-native';
import { ScreenContainer } from '../../components/ScreenContainer';
import { Text } from '../../components/Text';
import { MetricCard } from '../../components/MetricCard';
import { SkeletonCard } from '../../components/Skeleton';
import { ErrorState } from '../../components/ErrorState';
import { EmptyState } from '../../components/EmptyState';
import { Card } from '../../components/Card';
import { SectionHeader } from '../../components/SectionHeader';
import { useFinancialPosition } from '../../hooks/useFinancialPosition';
import { useSnapshotHistory } from '../../hooks/useSnapshotHistory';
import { formatPaise, formatPercent } from '../../utils/currency';
import { SPACE } from '../../theme/tokens';

/**
 * The dashboard shows exactly what Module 2's /financial-position
 * endpoint returns -- no frontend-side thresholds decide whether a
 * number is "good" (Section 7: "do NOT invent financial advice based on
 * arbitrary frontend thresholds"). The only interpretation happening here
 * is a plain sign check (surplus positive/negative) and a buffer >= 6
 * months check, both restating what the backend's own capacity rule
 * table (Module 3) already treats as its top, uncapped band -- not a
 * frontend opinion invented independently.
 */
export function HomeScreen() {
  const position = useFinancialPosition();
  const snapshots = useSnapshotHistory();

  if (position.isPending) {
    return (
      <ScreenContainer>
        <Text variant="display">Overview</Text>
        <SkeletonCard />
        <SkeletonCard />
      </ScreenContainer>
    );
  }

  if (position.error) {
    return (
      <ScreenContainer onRefresh={() => position.refetch()} refreshing={position.isRefetching}>
        <Text variant="display">Overview</Text>
        <ErrorState message={position.error.message} onRetry={() => position.refetch()} />
      </ScreenContainer>
    );
  }

  const data = position.data!;
  const surplusPositive = data.monthly_surplus_paise >= 0;
  const bufferMonths = Number(data.buffer_coverage_months);
  const bufferHealthy = bufferMonths >= 6;
  const emiRatioPct = Number(data.emi_to_income_ratio) * 100;

  return (
    <ScreenContainer onRefresh={() => position.refetch()} refreshing={position.isRefetching}>
      <View>
        <Text variant="caption" tone="muted">
          Your financial overview
        </Text>
        <Text variant="display">Good to see you</Text>
      </View>

      <View style={styles.grid}>
        <MetricCard label="Net worth" value={formatPaise(data.net_worth_paise)} />
        <MetricCard
          label="Monthly surplus"
          value={formatPaise(data.monthly_surplus_paise)}
          tone={surplusPositive ? 'positive' : 'danger'}
          helper={surplusPositive ? 'Income exceeds outflow' : 'Outflow exceeds income'}
        />
        <MetricCard
          label="Emergency buffer"
          value={`${bufferMonths.toFixed(1)} months`}
          tone={bufferHealthy ? 'positive' : 'warning'}
          helper="Liquid cash vs. essential expenses"
        />
        <MetricCard label="EMI-to-income" value={formatPercent(emiRatioPct, 1)} />
      </View>

      <Card>
        <SectionHeader title="What matters now" subtitle="Prioritized by the backend, not this screen" />
        <EmptyState
          title="Coming in Phase 5"
          message="This section will surface Module 6's debt and leak-detection results, ranked certain-return-first."
        />
      </Card>

      <Card>
        <SectionHeader title="Financial timeline" />
        {snapshots.data && snapshots.data.length >= 2 ? (
          <Text variant="caption" tone="muted" style={{ marginTop: SPACE.sm }}>
            {snapshots.data.length} monthly snapshots recorded — chart coming in Phase 3.
          </Text>
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

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.md },
});
