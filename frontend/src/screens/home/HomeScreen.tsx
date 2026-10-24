import type { CompositeNavigationProp } from '@react-navigation/native';
import { useNavigation } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { AnimatedFigure } from '../../components/AnimatedFigure';
import { AvatarBadge, initialsFrom } from '../../components/AvatarBadge';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { IconChip } from '../../components/IconChip';
import { InfoTooltip } from '../../components/InfoTooltip';
import { LineChart } from '../../components/LineChart';
import { MenuList } from '../../components/MenuList';
import { MetricCard } from '../../components/MetricCard';
import { NudgeEntryButton } from '../../components/NudgeAssistant';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { Skeleton, SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useDemoUser } from '../../context/DemoUserContext';
import { useDebtLeak } from '../../hooks/useDebtLeak';
import { useFinancialPosition } from '../../hooks/useFinancialPosition';
import { useProfile } from '../../hooks/useProfileManagement';
import { useSnapshotHistory } from '../../hooks/useSnapshotHistory';
import type { HomeStackParamList, MainTabParamList } from '../../navigation/types';
import { useAppTheme } from '../../theme/ThemeContext';
import { SPACE } from '../../theme/tokens';
import { formatPaise, formatPaiseCompact } from '../../utils/currency';
import { groupByLabel, type GroupedInsight } from '../../utils/recoverableInsights';

type Nav = CompositeNavigationProp<
  NativeStackNavigationProp<HomeStackParamList, 'Home'>,
  BottomTabNavigationProp<MainTabParamList>
>;

/** "3 entries · ₹3L/year" -- the amount is always plain, muted secondary
 * text (never worded as savings or recoverable money). Each flagged
 * thing is a declared expense *entry* (this app has no bank/card
 * statement feed, see leak_engine.py's DATA_SOURCE_NOTE) -- "entries",
 * not "transactions", matches what the data actually is. */
function shortSubtitle(item: GroupedInsight): string {
  const amount = `${formatPaiseCompact(item.amountPaise)}/year`;
  if (item.kind === 'idle_cash') return amount;
  const countPhrase = `${item.count} entr${item.count === 1 ? 'y' : 'ies'}`;
  return `${countPhrase} · ${amount}`;
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
 * "Spending to review" shows the top few grouped recommendations, ranked
 * by annual amount (plain arithmetic ordering, not a judgment call), with
 * a "See all recommendations" link to Leaks for the complete, per-record
 * list. Grouping only ever sums and counts real stored rows for display;
 * it never claims same-category entries are confirmed duplicate
 * payments, and the count shown always matches what Leaks lists.
 */
export function HomeScreen() {
  const navigation = useNavigation<Nav>();
  const { colors } = useAppTheme();
  const { username } = useDemoUser();
  const profile = useProfile();
  const position = useFinancialPosition();
  const snapshots = useSnapshotHistory();
  const debtLeak = useDebtLeak();
  const goToProfile = () => navigation.navigate('ProfileTab', { screen: 'ProfileHome' });

  if (position.isPending) {
    return (
      <ScreenContainer>
        <Text variant="h1">Overview</Text>
        <NudgeEntryButton surface="home" />
        <SkeletonCard />
        <SkeletonCard />
      </ScreenContainer>
    );
  }

  if (position.error) {
    return (
      <ScreenContainer onRefresh={() => position.refetch()} refreshing={position.isRefetching}>
        <Text variant="h1">Overview</Text>
        <NudgeEntryButton surface="home" />
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
        <View style={styles.greetingSpacer} />
        <Text variant="h1" style={styles.greetingText}>
          Your money, in focus.
        </Text>
        <Pressable
          onPress={goToProfile}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel="Open your profile"
        >
          <AvatarBadge initials={initialsFrom(profile.data?.full_name, username)} size={40} />
        </Pressable>
      </View>

      <NudgeEntryButton surface="home" />

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
            <AnimatedFigure
              target={Math.abs(data.monthly_surplus_paise)}
              formatter={formatPaise}
              tone={surplusPositive ? 'positive' : 'danger'}
              style={styles.heroFigureText}
            />
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
          label="Emergency savings"
          animated={{ target: bufferMonths, formatter: (n) => `${n.toFixed(1)} mo` }}
          tone={bufferHealthy ? 'positive' : 'warning'}
          helper="Liquid cash vs. essential expenses"
          icon="shield-checkmark-outline"
          info={{
            title: 'Emergency savings',
            description: 'Your cash balance divided by your average monthly essential expenses — how many months of essentials your cash alone could cover if income stopped today.',
          }}
        />
      </View>

      <View style={styles.checkSection}>
        <SectionHeader
          title="Spending to review"
          action={
            <InfoTooltip
              title="Spending to review"
              description="Patterns from your own declared expenses, ranked by annual amount — idle cash above your buffer, recurring entries worth a second look, and whether paying down a debt beats investing the same amount. These are starting points to review, not confirmed duplicate payments, and nothing here is a market prediction."
            />
          }
        />
        {debtLeak.isPending ? (
          <Card>
            <View style={styles.leakSkeleton}>
              <Skeleton width="80%" height={14} />
              <Skeleton width="60%" height={14} />
            </View>
          </Card>
        ) : debtLeak.error ? (
          <Card>
            <ErrorState message={debtLeak.error.message} onRetry={() => debtLeak.refetch()} />
          </Card>
        ) : hasRecoverable || hasPrepayInsight ? (
          <>
            <MenuList
              items={[
                ...topInsights.map((item) => ({
                  key: item.key,
                  title: item.title,
                  subtitle: shortSubtitle(item),
                  icon: item.icon,
                  iconTone: item.tone,
                  onPress: goToLeaks,
                })),
                ...(hasPrepayInsight && prepay
                  ? [
                      {
                        key: 'prepay',
                        title: 'Debt payoff opportunity',
                        subtitle: `Could save ${formatPaise(prepay.interest_saved_paise)}`,
                        icon: 'trending-down-outline' as const,
                        iconTone: 'petrol' as const,
                        onPress: goToDebt,
                      },
                    ]
                  : []),
              ]}
            />
            <View style={styles.checkFooter}>
              {hasMoreInsights ? (
                <Pressable
                  onPress={goToLeaks}
                  hitSlop={8}
                  style={styles.seeAllLink}
                  accessibilityRole="button"
                  accessibilityLabel="See all recommendations"
                >
                  <Text variant="caption" tone="terracotta">
                    See all recommendations
                  </Text>
                  <Text variant="caption" tone="terracotta">
                    ›
                  </Text>
                </Pressable>
              ) : null}
              <Text variant="caption" tone="faint" style={styles.disclaimer}>
                Flagged patterns, not confirmed duplicate payments.
              </Text>
            </View>
          </>
        ) : (
          <Card>
            <EmptyState
              title="Nothing to check right now"
              message="No recoverable costs or debt-payoff opportunities were found from what you've entered."
            />
          </Card>
        )}
      </View>

      <Card>
        <SectionHeader
          title="Cash-flow trend"
          action={
            <InfoTooltip
              title="Cash-flow trend"
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
  greetingRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  greetingText: { flex: 1, textAlign: 'center' },
  greetingSpacer: { width: 40 },
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
  checkSection: { gap: SPACE.sm },
  leakSkeleton: { gap: SPACE.sm, marginTop: SPACE.sm },
  checkFooter: { gap: SPACE.xs, paddingHorizontal: SPACE.xs },
  seeAllLink: { flexDirection: 'row', alignItems: 'center', gap: 2, alignSelf: 'flex-start' },
  disclaimer: { fontStyle: 'italic' },
  chartSkeleton: { marginTop: SPACE.sm },
});
