import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { MetricCard } from '../../components/MetricCard';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useAppTheme } from '../../theme/ThemeContext';
import { useRiskProfileLatest } from '../../hooks/useRiskProfile';
import { SPACE } from '../../theme/tokens';
import type { PlanStackParamList } from '../../navigation/types';

type Nav = NativeStackNavigationProp<PlanStackParamList, 'RiskProfile'>;

function tierLabel(tier: number) {
  return `Tier ${tier} of 5`;
}

export function RiskProfileScreen() {
  const navigation = useNavigation<Nav>();
  const { colors } = useAppTheme();
  const { data, isPending, error, refetch } = useRiskProfileLatest();

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Risk profile
        </Text>
        <Text variant="display">Your risk tier</Text>
      </View>

      {isPending ? (
        <>
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : error && error.status !== 404 ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : !data ? (
        <Card>
          <EmptyState
            title="You haven't taken the risk questionnaire yet"
            message="Four short questions determine your stated risk tolerance, which is then checked against your financial capacity."
            actionLabel="Take the questionnaire"
            onAction={() => navigation.navigate('RiskQuestionnaire')}
          />
        </Card>
      ) : (
        <>
          <View style={styles.grid}>
            <MetricCard label="Stated tier" value={tierLabel(data.stated_tier)} helper="From your questionnaire answers" />
            <MetricCard
              label="Capacity ceiling"
              value={tierLabel(data.capacity_ceiling)}
              helper="What your finances can currently support"
            />
          </View>

          <MetricCard
            label="Final tier"
            value={tierLabel(data.final_tier)}
            tone={data.capped ? 'warning' : 'positive'}
            helper={data.capped ? 'Capped by financial capacity, not by your stated tolerance' : 'Matches your stated tolerance'}
          />

          {data.capped ? (
            <Card style={{ backgroundColor: colors.warningSoft, borderColor: colors.warningSoft }}>
              <Text variant="bodyMedium" tone="warning">
                Your final tier is lower than your stated tier because your current financial capacity doesn't
                support it yet — not because of anything about your risk tolerance itself.
              </Text>
            </Card>
          ) : (
            <Card style={{ backgroundColor: colors.positiveSoft, borderColor: colors.positiveSoft }}>
              <Text variant="bodyMedium" tone="positive">
                No financial-capacity constraint is currently limiting your tier.
              </Text>
            </Card>
          )}

          {data.unlock_conditions.length > 0 ? (
            <View style={styles.unlockSection}>
              <Text variant="h2">What would raise your tier</Text>
              {data.unlock_conditions.map((u) => (
                <Card key={u.constraint}>
                  <Text variant="bodyMedium">{u.message}</Text>
                  <View style={styles.unlockValues}>
                    <Text variant="caption" tone="muted">
                      Current: {u.current_value}
                    </Text>
                    <Text variant="caption" tone="terracotta">
                      Target: {u.target_value}
                    </Text>
                  </View>
                </Card>
              ))}
            </View>
          ) : null}

          <View style={styles.footer}>
            <Button label="See your target allocation" fullWidth onPress={() => navigation.navigate('Allocation')} />
            <Button label="Retake the questionnaire" variant="ghost" fullWidth onPress={() => navigation.navigate('RiskQuestionnaire')} />
          </View>
        </>
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.md },
  unlockSection: { gap: SPACE.md },
  unlockValues: { flexDirection: 'row', justifyContent: 'space-between', marginTop: SPACE.xs },
  footer: { gap: SPACE.sm, marginTop: SPACE.md },
});
