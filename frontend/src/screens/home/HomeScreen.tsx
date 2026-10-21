import type { CompositeNavigationProp } from '@react-navigation/native';
import { useNavigation } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { IconChip } from '../../components/IconChip';
import { InfoTooltip } from '../../components/InfoTooltip';
import { LineChart } from '../../components/LineChart';
import { MetricCard } from '../../components/MetricCard';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { Skeleton, SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useDebtLeak } from '../../hooks/useDebtLeak';
import { useFinancialPosition } from '../../hooks/useFinancialPosition';
import { useSnapshotHistory } from '../../hooks/useSnapshotHistory';
import type { HomeStackParamList, MainTabParamList } from '../../navigation/types';
import { useAppTheme } from '../../theme/ThemeContext';
import { SPACE } from '../../theme/tokens';
import { formatPaise, formatPercent } from '../../utils/currency';

type Nav = CompositeNavigationProp<
  NativeStackNavigationProp<HomeStackParamList, 'Home'>,
  BottomTabNavigationProp<MainTabParamList>
>;

/** component_id is "idle_cash", "fee_drag:<item>", or "recurring:<item>"
 * (see backend/app/services/leak_engine.py::build_leak_report) -- an
 * icon per prefix, not per exact id, since the suffix is per-user data. */
function iconForComponent(componentId: string): { icon: 'cash-outline' | 'card-outline' | 'repeat-outline'; tone: 'terracotta' | 'warning' | 'petrol' } {
  if (componentId === 'idle_cash') return { icon: 'cash-outline', tone: 'terracotta' };
  if (componentId.startsWith('fee_drag:')) return { icon: 'card-outline', tone: 'warning' };
  return { icon: 'repeat-outline', tone: 'petrol' };
}

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
 * "What matters now" shows every recoverable component the backend
 * found, not a slice of the first two -- total_recoverable_annual_paise
 * is exactly sum(components) (see leak_engine.py), so showing a partial
 * list while quoting the full total would look like it doesn't add up
 * even though the underlying math is correct.
 */
export function HomeScreen() {
  const navigation = useNavigation<Nav>();
  const { colors } = useAppTheme();
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
  const totalOutflowPaise = data.total_monthly_expenses_paise + data.total_monthly_emi_paise;
  // Derived, not fetched separately: income isn't its own field on
  // FinancialPositionOut, but monthly_surplus = income - expenses - emi
  // on the backend (financial_position.py::compute_monthly_surplus), so
  // this is exact arithmetic on numbers already in hand, not an estimate.
  const incomePaise = data.monthly_surplus_paise + totalOutflowPaise;

  // Oldest-first for the chart; the backend returns most-recent-first.
  const history = (snapshots.data ?? []).slice().reverse();
  const chartPoints = history.map((s) => ({
    label: new Date(s.month).toLocaleDateString('en-IN', { month: 'short' }),
    value: s.surplus,
  }));
  const latestSnapshot = snapshots.data?.[0];
  const periodLabel = latestSnapshot
    ? new Date(latestSnapshot.month).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })
    : undefined;
  // Only stated when real history supports it -- never fabricated.
  const previousSurplus = history.length >= 2 ? history[history.length - 2].surplus : null;
  const surplusDeltaPaise = previousSurplus !== null ? data.monthly_surplus_paise - previousSurplus : null;

  const leak = debtLeak.data;
  const components = leak?.components ?? [];
  const hasRecoverable = !!leak && leak.total_recoverable_annual_paise > 0;
  const hasPrepayInsight = !!leak?.prepay_vs_invest;
  const prepay = leak?.prepay_vs_invest;

  const goToLeaks = () => navigation.navigate('InsightsTab', { screen: 'Leaks' });
  const goToDebt = () => navigation.navigate('InsightsTab', { screen: 'Debt' });

  return (
    <ScreenContainer onRefresh={() => position.refetch()} refreshing={position.isRefetching}>
      <View style={styles.greetingRow}>
        <Text variant="caption" tone="muted">
          Your financial overview
        </Text>
        <Text variant="h1">Good to see you</Text>
      </View>

      <Card raised style={styles.heroCard}>
        <SectionHeader
          title="Monthly cash flow"
          subtitle={periodLabel}
          action={
            <InfoTooltip
              title="Monthly cash flow"
              description="Income minus your expenses and EMI payments this month. Income here is derived from your surplus plus your outflow — the same numbers below, not a separate estimate."
            />
          }
        />
        <View style={styles.heroMain}>
          <IconChip
            name={surplusPositive ? 'trending-up-outline' : 'trending-down-outline'}
            tone={surplusPositive ? 'positive' : 'danger'}
            size={40}
          />
          <View style={styles.heroFigureCol}>
            <Text variant="label" tone="muted">
              {surplusPositive ? 'SURPLUS' : 'DEFICIT'}
            </Text>
            <MetricFigure
              value={Math.abs(data.monthly_surplus_paise)}
              tone={surplusPositive ? 'positive' : 'danger'}
            />
          </View>
        </View>
        {surplusDeltaPaise !== null ? (
          <Text variant="caption" tone="muted" style={styles.trendNote}>
            {surplusDeltaPaise >= 0 ? '▲' : '▼'} {formatPaise(Math.abs(surplusDeltaPaise))} vs. last month
          </Text>
        ) : null}

        <View style={[styles.heroBreakdown, { borderTopColor: colors.border }]}>
          <View style={styles.heroBreakdownItem}>
            <Text variant="caption" tone="muted">
              Income
            </Text>
            <Text variant="figure">{formatPaise(incomePaise)}</Text>
          </View>
          <View style={[styles.heroBreakdownDivider, { backgroundColor: colors.border }]} />
          <View style={styles.heroBreakdownItem}>
            <Text variant="caption" tone="muted">
              Expenses &amp; EMIs
            </Text>
            <Text variant="figure">{formatPaise(totalOutflowPaise)}</Text>
          </View>
        </View>
      </Card>

      <View style={styles.grid}>
        <MetricCard
          label="Net worth"
          animated={{ target: data.net_worth_paise, formatter: formatPaise }}
          icon="wallet-outline"
          info={{
            title: 'Net worth',
            description: 'Your cash balance plus everything you hold (savings, investments, etc.), minus what you currently owe — the outstanding principal on your loans.',
          }}
        />
        <MetricCard
          label="Emergency buffer"
          animated={{ target: bufferMonths, formatter: (n) => `${n.toFixed(1)} mo` }}
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
          animated={{ target: emiRatioPct, formatter: (n) => formatPercent(n, 1) }}
          icon="pie-chart-outline"
          info={{
            title: 'EMI-to-income ratio',
            description: 'Your total monthly loan repayments (EMIs), shown as a share of your monthly income.',
          }}
        />
      </View>

      <Card>
        <SectionHeader
          title="What matters now"
          action={
            <InfoTooltip
              title="What matters now"
              description="Every concrete, already-computed opportunity from your own numbers — idle cash above your buffer, recurring charges worth a second look, and whether paying down a debt beats investing the same amount. Nothing here is a market prediction, and nothing is hidden: this is the full list, not a preview."
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
          <View style={styles.insightList}>
            {hasRecoverable ? (
              <Text variant="caption" tone="muted">
                Up to {formatPaise(leak!.total_recoverable_annual_paise)}/year looks recoverable, across{' '}
                {components.length} item{components.length === 1 ? '' : 's'}:
              </Text>
            ) : null}
            {components.map((c) => {
              const { icon, tone } = iconForComponent(c.component_id);
              return (
                <View key={c.component_id} style={[styles.insightCard, { borderColor: colors.border }]}>
                  <IconChip name={icon} tone={tone} size={32} />
                  <View style={styles.insightCopy}>
                    <Text variant="bodyMedium">{c.label}</Text>
                    <Text variant="caption" tone="muted" style={styles.insightExplanation}>
                      {c.explanation}
                    </Text>
                    <View style={styles.insightFooter}>
                      <Text variant="figure" tone="terracotta">
                        {formatPaise(c.annual_amount_paise)}/yr
                      </Text>
                      <Button label="View breakdown" variant="ghost" onPress={goToLeaks} />
                    </View>
                  </View>
                </View>
              );
            })}
            {hasPrepayInsight && prepay ? (
              <View style={[styles.insightCard, { borderColor: colors.border }]}>
                <IconChip name="trending-down-outline" tone="petrol" size={32} />
                <View style={styles.insightCopy}>
                  <Text variant="bodyMedium">Paying off this debt early could beat investing</Text>
                  <Text variant="caption" tone="muted" style={styles.insightExplanation}>
                    At a guaranteed {prepay.guaranteed_annual_rate_pct}% p.a., clearing it {prepay.months_saved}{' '}
                    month{prepay.months_saved === 1 ? '' : 's'} sooner avoids interest with no market risk.
                  </Text>
                  <View style={styles.insightFooter}>
                    <Text variant="figure" tone="terracotta">
                      {formatPaise(prepay.interest_saved_paise)} saved
                    </Text>
                    <Button label="View breakdown" variant="ghost" onPress={goToDebt} />
                  </View>
                </View>
              </View>
            ) : null}
          </View>
        ) : (
          <EmptyState
            title="Nothing urgent right now"
            message="No recoverable costs or debt-payoff opportunities were found from what you've entered."
          />
        )}
      </Card>

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
    </ScreenContainer>
  );
}

/** The hero figure specifically: larger than MetricCard's figureLarge, so
 * the cash-flow number is unambiguously the dashboard's one focal point
 * rather than competing evenly with the supporting metrics below it. */
function MetricFigure({ value, tone }: { value: number; tone: 'positive' | 'danger' }) {
  return (
    <Text variant="hero" tone={tone} numberOfLines={1} style={styles.heroFigureText}>
      {formatPaise(value)}
    </Text>
  );
}

const styles = StyleSheet.create({
  greetingRow: { gap: 2 },
  heroCard: { gap: SPACE.sm },
  heroMain: { flexDirection: 'row', alignItems: 'center', gap: SPACE.md, marginTop: SPACE.xs },
  heroFigureCol: { flex: 1 },
  heroFigureText: { marginTop: 2 },
  trendNote: { marginTop: -SPACE.xs },
  heroBreakdown: {
    flexDirection: 'row',
    marginTop: SPACE.sm,
    paddingTop: SPACE.md,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  heroBreakdownItem: { flex: 1, gap: 2 },
  heroBreakdownDivider: { width: StyleSheet.hairlineWidth, marginHorizontal: SPACE.md },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.md },
  leakSkeleton: { gap: SPACE.sm, marginTop: SPACE.sm },
  insightList: { gap: SPACE.sm, marginTop: SPACE.sm },
  insightCard: {
    flexDirection: 'row',
    gap: SPACE.sm,
    padding: SPACE.md,
    borderRadius: 14,
    borderWidth: StyleSheet.hairlineWidth,
  },
  insightCopy: { flex: 1, gap: 2 },
  insightExplanation: { marginBottom: SPACE.xs },
  insightFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: SPACE.xs },
  chartWrap: { marginTop: SPACE.sm, gap: SPACE.xs },
  chartSkeleton: { marginTop: SPACE.sm },
});
