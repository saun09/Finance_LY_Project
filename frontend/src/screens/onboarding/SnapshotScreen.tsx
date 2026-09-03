import { useRoute } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { MetricCard } from '../../components/MetricCard';
import { OnboardingProgress } from '../../components/OnboardingProgress';
import { ScreenContainer } from '../../components/ScreenContainer';
import { Text } from '../../components/Text';
import { useOnboardingStatus } from '../../context/OnboardingStatusContext';
import { SPACE } from '../../theme/tokens';
import type { OnboardingStackParamList } from '../../navigation/types';
import { formatPaise } from '../../utils/currency';

type Props = NativeStackScreenProps<OnboardingStackParamList, 'Snapshot'>;

export function SnapshotScreen() {
  const { params } = useRoute<Props['route']>();
  const { snapshot } = params;
  const { markCompleted } = useOnboardingStatus();

  const monthLabel = new Date(snapshot.month).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });

  return (
    <ScreenContainer>
      <OnboardingProgress
        step={7}
        total={7}
        title="You're set up"
        subtitle={`Your first monthly snapshot for ${monthLabel} has been recorded.`}
      />

      <View style={styles.grid}>
        <MetricCard label="Income" value={formatPaise(snapshot.income)} />
        <MetricCard
          label="Surplus"
          value={formatPaise(snapshot.surplus)}
          tone={snapshot.surplus >= 0 ? 'positive' : 'danger'}
        />
        <MetricCard label="Cash" value={formatPaise(snapshot.cash)} />
        <MetricCard
          label="Buffer"
          value={`${Number(snapshot.buffer_coverage_months).toFixed(1)} mo`}
          tone={Number(snapshot.buffer_coverage_months) >= 6 ? 'positive' : 'warning'}
        />
      </View>

      <Card>
        <Text variant="bodyMedium" tone="muted">
          Every month going forward builds on this baseline. Your dashboard, risk profile, and plan all
          start from the numbers you just entered — you can update any of them at any time.
        </Text>
      </Card>

      <View style={styles.footer}>
        <Button
          label="Go to your dashboard"
          fullWidth
          onPress={async () => {
            await markCompleted();
          }}
        />
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.md },
  footer: { marginTop: SPACE.md },
});
