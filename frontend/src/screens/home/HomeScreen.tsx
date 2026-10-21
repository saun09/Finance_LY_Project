import type { CompositeNavigationProp } from '@react-navigation/native';
import { useNavigation } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import type { RecoverableComponentOut } from '../../api/types';
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
import { formatPaise } from '../../utils/currency';

type Nav = CompositeNavigationProp<
  NativeStackNavigationProp<HomeStackParamList, 'Home'>,
  BottomTabNavigationProp<MainTabParamList>
>;

type IconTone = 'terracotta' | 'warning' | 'petrol';
type IconName = 'cash-outline' | 'card-outline' | 'repeat-outline';

/** component_id is "idle_cash", "fee_drag:<item>", or "recurring:<item>"
 * (see backend/app/services/leak_engine.py::build_leak_report) -- an
 * icon per prefix, not per exact id, since the suffix is per-user data. */
function iconForComponent(componentId: string): { icon: IconName; tone: IconTone } {
  if (componentId === 'idle_cash') return { icon: 'cash-outline', tone: 'terracotta' };
  if (componentId.startsWith('fee_drag:')) return { icon: 'card-outline', tone: 'warning' };
  return { icon: 'repeat-outline', tone: 'petrol' };
}

interface GroupedInsight {
  key: string;
  icon: IconName;
  tone: IconTone;
  title: string;
  explanation: string;
  amountPaise: number;
  count: number;
}

/** Collapses repeat records of the same recommendation (e.g. several
 * "Recurring charge to review: rent" rows, which happens with real
 * duplicate-category expense entries) into one card with a combined
 * amount and a "(x2)" count -- the underlying per-record detail is still
 * exactly what Leaks shows; this is a display-only grouping for the
 * dashboard preview, by `label` (same category), not a data change. */
function groupByLabel(components: RecoverableComponentOut[]): GroupedInsight[] {
  const byLabel = new Map<string, GroupedInsight>();
  for (const c of components) {
    const existing = byLabel.get(c.label);
    if (existing) {
      existing.amountPaise += c.annual_amount_paise;
      existing.count += 1;
    } else {
      const { icon, tone } = iconForComponent(c.component_id);
      byLabel.set(c.label, {
        key: c.label,
        icon,
        tone,
        title: c.label,
        explanation: c.explanation,
        amountPaise: c.annual_amount_paise,
        count: 1,
      });
    }
  }
  return Array.from(byLabel.values()).sort((a, b) => b.amountPaise - a.amountPaise);
}

const TOP_INSIGHTS_SHOWN = 3;

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
 * "What matters now" shows the top few grouped recommendations, ranked
 * by annual amount (plain arithmetic ordering, not a judgment call), with
 * a "View all" link to Leaks for the complete, ungrouped, per-record
 * list -- condensing the preview never hides a number, since the full
 * total is still stated and the full detail is one tap away.
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
  const groupedInsights = groupByLabel(components);
  const topInsights = groupedInsights.slice(0, TOP_INSIGHTS_SHOWN);
  const hasMoreInsights = groupedInsights.length > topInsights.length;
  const hasRecoverable = !!leak && leak.total_recoverable_annual_paise > 0;
  const hasPrepayInsight = !!leak?.prepay_vs_invest;
  const prepay = leak?.prepay_vs_invest;

  const goToLeaks = () => navigation.navigate('InsightsTab', { screen: 'Leaks' });
  const goToDebt = () => navigation.navigate('InsightsTab', { screen: 'Debt' });
  const goToInsightsHub = () => navigation.navigate('InsightsTab', { screen: 'Insights' });

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
            size={32}
          />
          <View style={styles.heroFigureCol}>
            <Text variant="label" tone="muted">
              {surplusPositive ? 'SURPLUS' : 'DEFICIT'}
            </Text>
            <Text
              variant="figureLarge"
              tone={surplusPositive ? 'positive' : 'danger'}
              numberOfLines={1}
              style={styles.heroFigureText}
            >
              {formatPaise(Math.abs(data.monthly_surplus_paise))}
            </Text>
          </View>
          {surplusDeltaPaise !== null ? (
            <Text variant="caption" tone="muted">
              {surplusDeltaPaise >= 0 ? '▲' : '▼'} {formatPaise(Math.abs(surplusDeltaPaise))}
            </Text>
          ) : null}
        </View>

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
      </View>

      <Card>
        <SectionHeader
          title="What matters now"
          action={
            <InfoTooltip
              title="What matters now"
              description="Your top recommendations from your own numbers, ranked by annual amount — idle cash above your buffer, recurring charges worth a second look, and whether paying down a debt beats investing the same amount. Nothing here is a market prediction. Repeated records of the same recommendation are combined into one card; see Leaks for every individual record."
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
                Up to {formatPaise(leak!.total_recoverable_annual_paise)}/year looks recoverable.
              </Text>
            ) : null}
            {topInsights.map((item) => (
              <View key={item.key} style={[styles.insightCard, { borderColor: colors.border }]}>
                <IconChip name={item.icon} tone={item.tone} size={32} />
                <View style={styles.insightCopy}>
                  <Text variant="bodyMedium">
                    {item.title}
                    {item.count > 1 ? ` (×${item.count})` : ''}
                  </Text>
                  <Text variant="caption" tone="muted" style={styles.insightExplanation} numberOfLines={2}>
                    {item.explanation}
                  </Text>
                  <View style={styles.insightFooter}>
                    <Text variant="figure" tone="terracotta">
                      {formatPaise(item.amountPaise)}/yr
                    </Text>
                    <Button label="View breakdown" variant="ghost" onPress={goToLeaks} />
                  </View>
                </View>
              </View>
            ))}
            {hasPrepayInsight && prepay ? (
              <View style={[styles.insightCard, { borderColor: colors.border }]}>
                <IconChip name="trending-down-outline" tone="petrol" size={32} />
                <View style={styles.insightCopy}>
                  <Text variant="bodyMedium">Paying off this debt early could beat investing</Text>
                  <Text variant="caption" tone="muted" style={styles.insightExplanation} numberOfLines={2}>
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
            {hasMoreInsights ? (
              <Button label="View all" variant="ghost" onPress={goToLeaks} />
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
              description="Your monthly surplus (income minus expenses and EMIs) over time. The full timeline, with every month, is in Insights."
            />
          }
        />
        {snapshots.isPending ? (
          <Skeleton height={60} style={styles.chartSkeleton} />
        ) : snapshots.error ? (
          <ErrorState message={snapshots.error.message} onRetry={() => snapshots.refetch()} />
        ) : chartPoints.length >= 2 ? (
          <>
            <LineChart points={chartPoints} formatValue={formatPaise} height={60} />
            <Button label="View full timeline" variant="ghost" onPress={goToInsightsHub} />
          </>
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
  greetingRow: { gap: 2 },
  heroCard: { gap: 4 },
  heroMain: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  heroFigureCol: { flex: 1 },
  heroFigureText: { marginTop: 2 },
  heroBreakdown: {
    flexDirection: 'row',
    marginTop: SPACE.xs,
    paddingTop: SPACE.sm,
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
  chartSkeleton: { marginTop: SPACE.sm },
});
