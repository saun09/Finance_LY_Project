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
import { InfoTooltip } from '../../components/InfoTooltip';
import { IconChip } from '../../components/IconChip';
import { Reveal } from '../../components/Reveal';
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
 *
 * Every metric's definition (what it is, how it's calculated) now lives
 * behind its own info icon rather than as on-screen body copy -- same
 * underlying facts as before, just one tap away instead of always-on
 * paragraph text.
 */
export function HomeScreen() {
  const position = useFinancialPosition();
  const snapshots = useSnapshotHistory();
  const debtLeak = useDebtLeak();

  if (position.isPending) {
    return (
      <ScreenContainer>
        <Text variant="h1">Overview</Text>
        <SkeletonCard />
        <SkeletonCard />
      </ScreenContainer>
    );
  }

  if (position.error) {
    return (
      <ScreenContainer onRefresh={() => position.refetch()} refreshing={position.isRefetching}>
        <Text variant="h1">Overview</Text>
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
      <Reveal index={0}>
        <View style={styles.greetingRow}>
          <View>
            <Text variant="caption" tone="muted">
              Your financial overview
            </Text>
            <Text variant="h1">Good to see you</Text>
          </View>
        </View>
      </Reveal>

      <Reveal index={1}>
        <View style={styles.grid}>
          <MetricCard
            label="Net worth"
            value={formatPaise(data.net_worth_paise)}
            icon="wallet-outline"
            info={{
              title: 'Net worth',
              description: 'Your cash balance plus everything you hold (savings, investments, etc.), minus what you currently owe — the outstanding principal on your loans.',
            }}
          />
          <MetricCard
            label="Monthly surplus"
            value={formatPaise(data.monthly_surplus_paise)}
            tone={surplusPositive ? 'positive' : 'danger'}
            helper={surplusPositive ? 'Income exceeds outflow' : 'Outflow exceeds income'}
            icon="trending-up-outline"
            info={{
              title: 'Monthly surplus',
              description: 'Your income this month, minus your expenses and your EMI (loan) payments. Positive means you took in more than you spent; negative means the opposite.',
            }}
          />
          <MetricCard
            label="Emergency buffer"
            value={`${bufferMonths.toFixed(1)} months`}
            tone={bufferHealthy ? 'positive' : 'warning'}
            helper="Liquid cash vs. essential expenses"
            icon="shield-checkmark-outline"
            info={{
              title: 'Emergency buffer',
              description: 'Your cash balance divided by your average monthly essential expenses — how many months of essentials your cash alone could cover if income stopped today.',
            }}
          />
          <MetricCard
            label="EMI-to-income"
            value={formatPercent(emiRatioPct, 1)}
            icon="pie-chart-outline"
            info={{
              title: 'EMI-to-income ratio',
              description: 'Your total monthly loan repayments (EMIs), shown as a share of your monthly income.',
            }}
          />
        </View>
      </Reveal>

      <Reveal index={2}>
        <Card>
          <SectionHeader
            title="What matters now"
            action={
              <InfoTooltip
                title="What matters now"
                description="A short list of concrete, already-computed opportunities from your own numbers — idle cash above your buffer, recurring charges worth a second look, and whether paying down a debt beats investing the same amount. Nothing here is a market prediction."
              />
            }
          />
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
                <View style={styles.recoverableHeadline}>
                  <IconChip name="cash-outline" tone="terracotta" size={30} />
                  <Text variant="bodyMedium" style={styles.recoverableText}>
                    Up to {formatPaise(leak!.total_recoverable_annual_paise)}/year looks recoverable
                  </Text>
                </View>
              ) : null}
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
              {hasPrepayInsight ? (
                <View style={styles.prepayRow}>
                  <Text variant="caption" tone="muted" style={styles.prepayFlex}>
                    Prepay vs. invest: which wins for your debt?
                  </Text>
                  <InfoTooltip title="Prepay vs. invest" description={leak!.prepay_vs_invest!.framing_note} />
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
      </Reveal>

      <Reveal index={3}>
        <Card>
          <SectionHeader
            title="Financial timeline"
            action={
              <InfoTooltip
                title="Financial timeline"
                description="Your monthly surplus (income minus expenses and EMIs) over time, taken from your monthly snapshots."
              />
            }
          />
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
      </Reveal>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  greetingRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.md },
  leakSkeleton: { gap: SPACE.sm, marginTop: SPACE.sm },
  mattersList: { gap: SPACE.sm, marginTop: SPACE.sm },
  recoverableHeadline: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  recoverableText: { flex: 1 },
  componentRow: { marginTop: SPACE.xs, gap: 2 },
  prepayRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm, marginTop: SPACE.xs },
  prepayFlex: { flex: 1 },
  moreInInsights: { marginTop: SPACE.xs },
  chartWrap: { marginTop: SPACE.sm, gap: SPACE.xs },
  chartSkeleton: { marginTop: SPACE.sm },
});
