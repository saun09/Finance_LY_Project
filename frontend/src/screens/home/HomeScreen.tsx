import React from 'react';
import { StyleSheet, View } from 'react-native';
import { ScreenContainer } from '../../components/ScreenContainer';
import { Text } from '../../components/Text';
import { MetricCard } from '../../components/MetricCard';
import { SkeletonCard, Skeleton } from '../../components/Skeleton';
import { ErrorState } from '../../components/ErrorState';
import { EmptyState } from '../../components/EmptyState';
import { Card } from '../../components/Card';
import { SectionHeader } from '../../components/SectionHeader';
import { LineChart } from '../../components/LineChart';
import { useFinancialPosition } from '../../hooks/useFinancialPosition';
import { useSnapshotHistory } from '../../hooks/useSnapshotHistory';
import { useDebtLeak } from '../../hooks/useDebtLeak';
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
  const debtLeak = useDebtLeak();

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

  // Oldest-first for the chart; the backend returns most-recent-first.
  const chartPoints = (snapshots.data ?? [])
    .slice()
    .reverse()
    .map((s) => ({
      label: new Date(s.month).toLocaleDateString('en-IN', { month: 'short' }),
      value: s.surplus,
    }));

  const leak = debtLeak.data;
  const topComponents = leak?.components.slice(0, 2) ?? [];
  const hasRecoverable = !!leak && leak.total_recoverable_annual_paise > 0;
  const hasPrepayInsight = !!leak?.prepay_vs_invest;

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
        {debtLeak.isPending ? (
          <View style={styles.leakSkeleton}>
            <Skeleton width="80%" height={14} />
            <Skeleton width="60%" height={14} />
          </View>
        ) : debtLeak.error ? (
          <ErrorState message={debtLeak.error.message} onRetry={() => debtLeak.refetch()} />
        ) : hasRecoverable || hasPrepayInsight ? (
          <View style={styles.mattersList}>
            {hasRecoverable ? (
              <View>
                <Text variant="bodyMedium">
                  Up to {formatPaise(leak!.total_recoverable_annual_paise)}/year looks recoverable
                </Text>
                {topComponents.map((c) => (
                  <View key={c.component_id} style={styles.componentRow}>
                    <Text variant="caption" tone="muted">
                      {c.label} — {formatPaise(c.annual_amount_paise)}/yr
                    </Text>
                    <Text variant="caption" tone="terracotta">
                      {c.concrete_action}
                    </Text>
                  </View>
                ))}
              </View>
            ) : null}
            {hasPrepayInsight ? (
              <View style={hasRecoverable ? styles.componentRow : undefined}>
                <Text variant="caption" tone="muted">
                  {leak!.prepay_vs_invest!.framing_note}
                </Text>
              </View>
            ) : null}
            <Text variant="caption" tone="faint" style={styles.moreInInsights}>
              Full breakdown available in Insights.
            </Text>
          </View>
        ) : (
          <EmptyState
            title="Nothing urgent right now"
            message="No recoverable costs or debt-payoff opportunities were found from what you've entered."
          />
        )}
      </Card>

      <Card>
        <SectionHeader title="Financial timeline" />
        {snapshots.isPending ? (
          <Skeleton height={140} style={styles.chartSkeleton} />
        ) : snapshots.error ? (
          <ErrorState message={snapshots.error.message} onRetry={() => snapshots.refetch()} />
        ) : chartPoints.length >= 2 ? (
          <View style={styles.chartWrap}>
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

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.md },
  leakSkeleton: { gap: SPACE.sm, marginTop: SPACE.sm },
  mattersList: { gap: SPACE.sm, marginTop: SPACE.sm },
  componentRow: { marginTop: SPACE.xs, gap: 2 },
  moreInInsights: { marginTop: SPACE.xs },
  chartWrap: { marginTop: SPACE.sm, gap: SPACE.xs },
  chartSkeleton: { marginTop: SPACE.sm },
});
