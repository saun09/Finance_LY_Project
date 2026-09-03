import React from 'react';
import { StyleSheet, View } from 'react-native';
import { ASSET_CLASSES } from '../../api/types';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { MetricCard } from '../../components/MetricCard';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { usePersonalization } from '../../hooks/usePersonalization';
import { ASSET_CLASS_LABEL } from '../../utils/labels';
import { SPACE } from '../../theme/tokens';

export function PersonalizationScreen() {
  const { data, isPending, error, refetch } = usePersonalization();

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Insights
        </Text>
        <Text variant="display">Personalization</Text>
      </View>

      {isPending ? (
        <>
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : error?.status === 409 ? (
        <Card>
          <EmptyState
            title="Nothing to personalize yet"
            message={error.message}
          />
        </Card>
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : (
        <>
          <View style={styles.grid}>
            <MetricCard
              label="Offset applied"
              value={`${Number(data!.offset_pct_points) >= 0 ? '+' : ''}${Number(data!.offset_pct_points).toFixed(1)} pts`}
              helper="Shift from your base target, based on past decisions"
            />
            <MetricCard label="Edits considered" value={String(data!.edits_considered)} helper="Past allocation outcomes used" />
          </View>

          <Card>
            <SectionHeader title="Base vs. personalized target" subtitle={`Tier ${data!.final_tier} of 5`} />
            {ASSET_CLASSES.map((ac) => {
              const base = Number(data!.base_target_pct[ac] ?? '0');
              const displayed = Number(data!.displayed_target_pct[ac] ?? '0');
              const delta = displayed - base;
              return (
                <View key={ac} style={styles.row}>
                  <Text variant="caption" tone="muted" style={styles.rowLabel}>
                    {ASSET_CLASS_LABEL[ac]}
                  </Text>
                  <Text variant="figure" tone="faint">
                    {base.toFixed(0)}%
                  </Text>
                  <Text variant="figure">→ {displayed.toFixed(0)}%</Text>
                  {delta !== 0 ? (
                    <Text variant="caption" tone={delta > 0 ? 'positive' : 'danger'}>
                      {delta > 0 ? '+' : ''}
                      {delta.toFixed(1)}
                    </Text>
                  ) : null}
                </View>
              );
            })}
          </Card>

          {data!.trace.length > 0 ? (
            <Card>
              <SectionHeader title="How the offset was built" subtitle="Each step, in order — transparent reasoning, not a black box" />
              {data!.trace.map((step) => (
                <View key={step.step} style={styles.traceRow}>
                  <Text variant="caption" tone="faint">
                    Step {step.step}
                  </Text>
                  <Text variant="caption" tone="muted">
                    weight {step.weight} · Δ{step.delta_pct}
                  </Text>
                  <Text variant="figure">
                    {step.offset_before} → {step.offset_after}
                  </Text>
                </View>
              ))}
            </Card>
          ) : null}
        </>
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.md },
  row: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm, paddingVertical: SPACE.xs },
  rowLabel: { flex: 1 },
  traceRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: SPACE.xs },
});
