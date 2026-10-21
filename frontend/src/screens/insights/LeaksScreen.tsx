import type { CompositeNavigationProp } from '@react-navigation/native';
import { useNavigation } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { IconChip } from '../../components/IconChip';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useAppTheme } from '../../theme/ThemeContext';
import { useDebtLeak } from '../../hooks/useDebtLeak';
import type { InsightsStackParamList, MainTabParamList } from '../../navigation/types';
import { SPACE } from '../../theme/tokens';
import { formatPaise } from '../../utils/currency';
import { groupByLabel, groupExplanation } from '../../utils/recoverableInsights';

type Nav = CompositeNavigationProp<
  NativeStackNavigationProp<InsightsStackParamList, 'Leaks'>,
  BottomTabNavigationProp<MainTabParamList>
>;

export function LeaksScreen() {
  const navigation = useNavigation<Nav>();
  const { colors } = useAppTheme();
  const { data, isPending, error, refetch } = useDebtLeak();

  // Grouped by category (same shared logic Home's preview uses, so the
  // two never disagree on how many unique things are flagged) -- the
  // total above is still the exact sum of every individual stored
  // record, not recomputed from the grouped view.
  const grouped = data ? groupByLabel(data.components) : [];

  const goToExpenses = () => navigation.navigate('ProfileTab', { screen: 'ExpensesManage' });

  return (
    <ScreenContainer>
      <View>
        <BackHeader label="Insights" />
        <Text variant="display" style={styles.title}>Spending to review</Text>
      </View>

      {isPending ? (
        <>
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : grouped.length === 0 ? (
        <Card>
          <EmptyState
            title="Nothing flagged right now"
            message="Based on what you've entered, there's no idle cash or recurring-spending pattern worth a second look."
          />
        </Card>
      ) : (
        <>
          <Card style={{ backgroundColor: colors.terracottaSoft, borderColor: colors.terracottaSoft }}>
            <Text variant="caption" tone="muted">
              ANNUAL SPENDING IN THESE CATEGORIES
            </Text>
            <Text variant="figureLarge">{formatPaise(data!.total_recoverable_annual_paise)}/year</Text>
            <Text variant="caption" tone="faint" style={styles.totalNote}>
              Sum of every entry below — {data!.components.length} total, {grouped.length} unique categor
              {grouped.length === 1 ? 'y' : 'ies'}.
            </Text>
          </Card>

          {grouped.map((item) => (
            <Card key={item.key}>
              <View style={styles.componentHeader}>
                <IconChip name={item.icon} tone={item.tone} size={32} />
                <View style={styles.componentCopy}>
                  <Text variant="h2">{item.title}</Text>
                  <Text variant="caption" tone="muted">
                    {item.count} entr{item.count === 1 ? 'y' : 'ies'}
                  </Text>
                </View>
                <Text variant="figure" tone="terracotta">
                  {formatPaise(item.amountPaise)}/yr
                </Text>
              </View>
              <Text variant="body" tone="muted" style={styles.spaced}>
                {groupExplanation(item)}
              </Text>
              <Button label="Review entry" variant="secondary" onPress={goToExpenses} />
            </Card>
          ))}
        </>
      )}

      <Card style={{ backgroundColor: colors.paperSunken, borderColor: colors.border }}>
        <Text variant="caption" tone="faint">
          {data?.data_source_note ??
            'Based only on manually entered recurring expenses — this app has no bank or card statement parser.'}
        </Text>
      </Card>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  title: { marginTop: SPACE.xs },
  totalNote: { marginTop: SPACE.xs },
  componentHeader: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  componentCopy: { flex: 1, gap: 2 },
  spaced: { marginTop: SPACE.sm, marginBottom: SPACE.md },
});
