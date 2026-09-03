import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useAppTheme } from '../../theme/ThemeContext';
import { useDebtLeak } from '../../hooks/useDebtLeak';
import { SPACE } from '../../theme/tokens';
import { formatPaise } from '../../utils/currency';

export function DebtScreen() {
  const { colors } = useAppTheme();
  const { data, isPending, error, refetch } = useDebtLeak();

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Insights
        </Text>
        <Text variant="display">Debt payoff</Text>
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
          <EmptyState title="No active loans" message="You haven't recorded any EMIs, so there's no payoff strategy to compare." />
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
  compareRow: { flexDirection: 'row', gap: SPACE.lg, marginTop: SPACE.sm },
  compareCol: { flex: 1, gap: 2 },
  spaced: { marginTop: SPACE.sm },
  metricRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: SPACE.xs },
});
