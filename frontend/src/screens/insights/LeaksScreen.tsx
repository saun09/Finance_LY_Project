import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useAppTheme } from '../../theme/ThemeContext';
import { useDebtLeak } from '../../hooks/useDebtLeak';
import { SPACE } from '../../theme/tokens';
import { formatPaise } from '../../utils/currency';

export function LeaksScreen() {
  const { colors } = useAppTheme();
  const { data, isPending, error, refetch } = useDebtLeak();

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Insights
        </Text>
        <Text variant="display">Recoverable costs</Text>
      </View>

      {isPending ? (
        <>
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : data!.components.length === 0 ? (
        <Card>
          <EmptyState
            title="Nothing recoverable found"
            message="Based on what you've entered, there's no idle cash or duplicate recurring cost flagged right now."
          />
        </Card>
      ) : (
        <>
          <Card style={{ backgroundColor: colors.terracottaSoft, borderColor: colors.terracottaSoft }}>
            <Text variant="caption" tone="muted">
              TOTAL RECOVERABLE
            </Text>
            <Text variant="figureLarge">{formatPaise(data!.total_recoverable_annual_paise)}/year</Text>
          </Card>

          {data!.components.map((c) => (
            <Card key={c.component_id}>
              <View style={styles.componentHeader}>
                <Text variant="h2" style={styles.componentLabel}>
                  {c.label}
                </Text>
                <Text variant="figure" tone="terracotta">
                  {formatPaise(c.annual_amount_paise)}/yr
                </Text>
              </View>
              <Text variant="body" tone="muted" style={styles.spaced}>
                {c.explanation}
              </Text>
              <Card style={{ backgroundColor: colors.petrolSoft, borderColor: colors.petrolSoft }}>
                <Text variant="bodyMedium" tone="petrol">
                  {c.concrete_action}
                </Text>
              </Card>
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
  componentHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: SPACE.md },
  componentLabel: { flex: 1 },
  spaced: { marginTop: SPACE.sm, marginBottom: SPACE.md },
});
