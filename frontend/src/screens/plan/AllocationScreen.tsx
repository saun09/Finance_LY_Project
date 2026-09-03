import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { personalizationApi } from '../../api/personalization';
import { qk } from '../../api/queryClient';
import type { EditActionTaken, Liquidity } from '../../api/types';
import { ASSET_CLASSES } from '../../api/types';
import { ASSET_CLASS_LABEL, LIQUIDITY_LABEL } from '../../utils/labels';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { DonutChart } from '../../components/DonutChart';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { InlineError } from '../../components/InlineError';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useAllocation } from '../../hooks/useAllocation';
import { useLatestAllocationEvent } from '../../hooks/usePersonalization';
import { useDemoUser } from '../../context/DemoUserContext';
import { useAppTheme } from '../../theme/ThemeContext';
import { ASSET_CLASS_COLOR_KEY, SPACE } from '../../theme/tokens';
import type { PlanStackParamList } from '../../navigation/types';
import { formatPaise } from '../../utils/currency';

const OUTCOME_OPTIONS: { value: EditActionTaken; label: string }[] = [
  { value: 'accepted', label: 'I followed it as-is' },
  { value: 'edited', label: 'I used a different mix' },
  { value: 'rejected', label: "I didn't use it" },
  { value: 'ignored', label: 'Not decided yet' },
];

type Nav = NativeStackNavigationProp<PlanStackParamList, 'Allocation'>;

export function AllocationScreen() {
  const navigation = useNavigation<Nav>();
  const { colors } = useAppTheme();
  const { userId } = useDemoUser();
  const queryClient = useQueryClient();
  const { data, isPending, error, refetch } = useAllocation();
  const latestEvent = useLatestAllocationEvent();
  const [recorded, setRecorded] = useState<EditActionTaken | null>(null);
  const [recordError, setRecordError] = useState<string | null>(null);

  const recordMutation = useMutation({
    mutationFn: (action: EditActionTaken) => {
      const eventId = latestEvent.data?.[0]?.event_id;
      if (!eventId) throw new Error('no-event');
      return personalizationApi.recordAllocationOutcome(userId, eventId, { action_taken: action });
    },
    onSuccess: (_result, action) => {
      setRecorded(action);
      queryClient.invalidateQueries({ queryKey: qk.personalization(userId) });
    },
    onError: (err) =>
      setRecordError(err instanceof Error && err.message === 'no-event' ? 'No allocation suggestion found yet.' : 'Could not record that — please try again.'),
  });

  if (isPending) {
    return (
      <ScreenContainer>
        <Text variant="display">Allocation</Text>
        <SkeletonCard />
        <SkeletonCard />
      </ScreenContainer>
    );
  }

  if (error?.status === 409) {
    return (
      <ScreenContainer>
        <Text variant="display">Allocation</Text>
        <Card>
          <EmptyState
            title="Complete your risk profile first"
            message={error.message}
            actionLabel="Go to risk profile"
            onAction={() => navigation.navigate('RiskProfile')}
          />
        </Card>
      </ScreenContainer>
    );
  }

  if (error) {
    return (
      <ScreenContainer>
        <Text variant="display">Allocation</Text>
        <ErrorState message={error.message} onRetry={() => refetch()} />
        {error.status === 422 ? (
          <Text variant="caption" tone="faint" style={styles.gapNote}>
            Holdings can currently only be added during onboarding, not edited or reclassified afterward — this
            will move to your Profile tab in a later update.
          </Text>
        ) : null}
      </ScreenContainer>
    );
  }

  const segments = ASSET_CLASSES.map((ac) => ({
    key: ac,
    pct: Number(data!.current_exposure_pct[ac] ?? '0'),
    color: colors[ASSET_CLASS_COLOR_KEY[ac]],
  }));

  const liquidityEntries = (Object.keys(LIQUIDITY_LABEL) as Liquidity[]).filter(
    (l) => (data!.liquidity_breakdown_paise[l] ?? 0) > 0,
  );

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Allocation · Tier {data!.final_tier} of 5
        </Text>
        <Text variant="display">Your target mix</Text>
      </View>

      <Card>
        <Text variant="bodyMedium" tone="muted">
          {data!.reasoning}
        </Text>
        <Text variant="caption" tone="faint" style={styles.ruleVersion}>
          Rule table {data!.rule_table_version}
        </Text>
      </Card>

      <Card style={styles.donutCard}>
        <SectionHeader title="Current exposure" subtitle={formatPaise(data!.total_value_paise)} />
        {data!.total_value_paise === 0 ? (
          <Text variant="caption" tone="muted">
            No holdings recorded yet — this shows your target mix for Tier {data!.final_tier} only.
          </Text>
        ) : null}
        <View style={styles.donutRow}>
          <DonutChart segments={segments} trackColor={colors.border} />
          <View style={styles.legend}>
            {ASSET_CLASSES.map((ac) => (
              <View key={ac} style={styles.legendRow}>
                <View style={[styles.dot, { backgroundColor: colors[ASSET_CLASS_COLOR_KEY[ac]] }]} />
                <Text variant="caption" style={styles.legendLabel}>
                  {ASSET_CLASS_LABEL[ac]}
                </Text>
                <Text variant="figure" tone="muted">
                  {Number(data!.current_exposure_pct[ac] ?? '0').toFixed(0)}%
                </Text>
                <Text variant="caption" tone="faint">
                  → {Number(data!.target_pct[ac] ?? '0').toFixed(0)}%
                </Text>
              </View>
            ))}
          </View>
        </View>
      </Card>

      <Card>
        <SectionHeader title="Concentration" />
        <View style={styles.metricRow}>
          <Text variant="caption" tone="muted">
            Largest single holding
          </Text>
          <Text variant="figure">{Number(data!.concentration.largest_holding_pct).toFixed(1)}%</Text>
        </View>
        <View style={styles.metricRow}>
          <Text variant="caption" tone="muted">
            Asset-class HHI
          </Text>
          <Text variant="figure">{data!.concentration.asset_class_hhi_bps} bps</Text>
        </View>
      </Card>

      {liquidityEntries.length > 0 ? (
        <Card>
          <SectionHeader title="Liquidity" />
          {liquidityEntries.map((l) => (
            <View key={l} style={styles.metricRow}>
              <Text variant="caption" tone="muted">
                {LIQUIDITY_LABEL[l]}
              </Text>
              <Text variant="figure">{formatPaise(data!.liquidity_breakdown_paise[l] ?? 0)}</Text>
            </View>
          ))}
        </Card>
      ) : null}

      {data!.total_value_paise > 0 ? (
        <Card>
          <SectionHeader
            title="What did you do with this?"
            subtitle="Helps future suggestions reflect how you actually invest, not just this rule table"
          />
          {recorded ? (
            <Text variant="bodyMedium" tone="positive" style={styles.recordedNote}>
              Recorded — thanks.
            </Text>
          ) : (
            <View style={styles.outcomeButtons}>
              {OUTCOME_OPTIONS.map((opt) => (
                <Button
                  key={opt.value}
                  label={opt.label}
                  variant="secondary"
                  loading={recordMutation.isPending && recordMutation.variables === opt.value}
                  onPress={() => {
                    setRecordError(null);
                    recordMutation.mutate(opt.value);
                  }}
                />
              ))}
            </View>
          )}
          {recordError ? <InlineError message={recordError} /> : null}
        </Card>
      ) : null}

      <Button label="Back to risk profile" variant="ghost" onPress={() => navigation.navigate('RiskProfile')} />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  ruleVersion: { marginTop: SPACE.sm },
  donutCard: { gap: SPACE.md },
  donutRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.lg, flexWrap: 'wrap' },
  legend: { flex: 1, minWidth: 160, gap: SPACE.sm },
  legendRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.xs },
  dot: { width: 8, height: 8, borderRadius: 4 },
  legendLabel: { flex: 1 },
  metricRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: SPACE.xs },
  gapNote: { marginTop: SPACE.md, textAlign: 'center' },
  outcomeButtons: { gap: SPACE.sm, marginTop: SPACE.sm },
  recordedNote: { marginTop: SPACE.sm },
});
