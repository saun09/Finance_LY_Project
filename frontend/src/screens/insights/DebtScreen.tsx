import React from 'react';
import { StyleSheet, View } from 'react-native';
import { BackHeader } from '../../components/BackHeader';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useAppTheme } from '../../theme/ThemeContext';
import { useDebtLeak } from '../../hooks/useDebtLeak';
import { useEmis } from '../../hooks/useProfileManagement';
import { SPACE } from '../../theme/tokens';
import { formatPaise } from '../../utils/currency';

export function DebtScreen() {
  const { colors } = useAppTheme();
  const { data, isPending, error, refetch } = useDebtLeak();
  // Same query (qk.emis) Profile > Loans & EMIs reads -- not a second,
  // divergent source of truth. Needed because the backend only computes
  // avalanche_snowball when there's a positive monthly surplus to put
  // toward extra payments (compute_and_log_debt_leak_report's `if debts
  // and surplus_paise > 0`); a null avalanche_snowball on its own doesn't
  // tell us whether that's because there are no loans, or because there
  // are loans but no surplus right now. Reading the actual EMI list here
  // resolves that ambiguity instead of assuming "no loans" either way.
  const emis = useEmis();
  const activeLoanCount = emis.data?.filter((e) => e.closed_at === null).length ?? 0;

  return (
    <ScreenContainer>
      <View>
        <BackHeader label="Insights" />
        <Text variant="display" style={styles.title}>Debt payoff</Text>
      </View>

      {isPending ? (
        <>
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : !data!.avalanche_snowball ? (
        <Card>
          <EmptyState
            title={activeLoanCount > 0 ? 'No payoff comparison yet' : 'No active loans'}
            message={
              activeLoanCount > 0
                ? `You have ${activeLoanCount} active loan${activeLoanCount === 1 ? '' : 's'} recorded, but no monthly surplus right now to put toward extra payments. This comparison appears once you have surplus to allocate.`
                : "You haven't recorded any EMIs, so there's no payoff strategy to compare."
            }
          />
        </Card>
      ) : (
        <>
          <Card>
            <SectionHeader title="Avalanche vs. snowball" subtitle="Two ways to order paying off multiple loans" />
            <View style={styles.compareRow}>
              <View style={styles.compareCol}>
                <Text variant="label" tone="terracotta">
                  AVALANCHE
                </Text>
                <Text variant="caption" tone="faint">
                  Highest interest rate first
                </Text>
                <Text variant="figure" style={styles.spaced}>
                  {data!.avalanche_snowball.avalanche.months_to_clear_all} months
                </Text>
                <Text variant="caption" tone="muted">
                  {formatPaise(data!.avalanche_snowball.avalanche.total_interest_paise)} interest
                </Text>
              </View>
              <View style={styles.compareCol}>
                <Text variant="label" tone="petrol">
                  SNOWBALL
                </Text>
                <Text variant="caption" tone="faint">
                  Smallest balance first
                </Text>
                <Text variant="figure" style={styles.spaced}>
                  {data!.avalanche_snowball.snowball.months_to_clear_all} months
                </Text>
                <Text variant="caption" tone="muted">
                  {formatPaise(data!.avalanche_snowball.snowball.total_interest_paise)} interest
                </Text>
              </View>
            </View>
            {data!.avalanche_snowball.interest_saved_by_avalanche_paise > 0 ? (
              <Card style={{ backgroundColor: colors.positiveSoft, borderColor: colors.positiveSoft, marginTop: SPACE.md }}>
                <Text variant="bodyMedium" tone="positive">
                  Avalanche saves {formatPaise(data!.avalanche_snowball.interest_saved_by_avalanche_paise)} in
                  interest and {data!.avalanche_snowball.months_saved_by_avalanche} months versus snowball.
                </Text>
              </Card>
            ) : (
              <Text variant="caption" tone="faint" style={styles.spaced}>
                Both orderings finish at the same time with a single loan.
              </Text>
            )}
          </Card>

          {data!.prepay_vs_invest ? (
            <Card>
              <SectionHeader title="Prepay vs. invest" subtitle={`Guaranteed rate: ${data!.prepay_vs_invest.guaranteed_annual_rate_pct}% p.a.`} />
              <Text variant="body" tone="muted" style={styles.spaced}>
                {data!.prepay_vs_invest.framing_note}
              </Text>
              <View style={styles.metricRow}>
                <Text variant="caption" tone="muted">
                  Extra paid monthly
                </Text>
                <Text variant="figure">{formatPaise(data!.prepay_vs_invest.extra_monthly_paise)}</Text>
              </View>
              <View style={styles.metricRow}>
                <Text variant="caption" tone="muted">
                  Interest saved
                </Text>
                <Text variant="figure" tone="positive">
                  {formatPaise(data!.prepay_vs_invest.interest_saved_paise)}
                </Text>
              </View>
              <View style={styles.metricRow}>
                <Text variant="caption" tone="muted">
                  Time saved
                </Text>
                <Text variant="figure">{data!.prepay_vs_invest.months_saved} months</Text>
              </View>
            </Card>
          ) : null}
        </>
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  title: { marginTop: SPACE.xs },
  compareRow: { flexDirection: 'row', gap: SPACE.lg, marginTop: SPACE.sm },
  compareCol: { flex: 1, gap: 2 },
  spaced: { marginTop: SPACE.sm },
  metricRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: SPACE.xs },
});
