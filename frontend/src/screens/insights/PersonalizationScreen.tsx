import React from 'react';
import { StyleSheet, View } from 'react-native';
import { ASSET_CLASSES } from '../../api/types';
import { BackHeader } from '../../components/BackHeader';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { MetricCard } from '../../components/MetricCard';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { usePersonalization } from '../../hooks/usePersonalization';
import type { OffsetStepOut, PersonalizationOut } from '../../api/types';
import { ASSET_CLASS_LABEL, CAPACITY_CONSTRAINT_LABEL, REJECT_REASON_LABEL } from '../../utils/labels';
import { SPACE } from '../../theme/tokens';

function signedPoints(value: string | number): string {
  const n = Math.round(Number(value) * 10) / 10;
  return `${n > 0 ? '+' : ''}${n} pts`;
}

/** One step of the offset's history, in the user's terms. */
function stepSentence(step: OffsetStepOut): string {
  const delta = signedPoints(step.delta_pct);
  const invested = step.funded ? ', invested' : ', not invested yet';
  switch (step.action_taken) {
    case 'edited':
      return `Set your own mix: equity ${delta} vs. your tier's plan${invested}`;
    case 'accepted':
      return `Kept the plan as shown (${delta})${invested}`;
    case 'rejected':
      return `Turned it down: ${(REJECT_REASON_LABEL as Record<string, string>)[step.reason_code ?? ''] ?? 'no reason given'}`;
    case 'ignored':
      return "Hadn't decided yet";
    default:
      return `Moved by ${delta}`;
  }
}

function stepWeightNote(step: OffsetStepOut): string {
  const weight = Number(step.weight);
  if (weight === 0) return "Not counted — it doesn't say what you'd prefer";
  if (weight < 1) return 'Half strength until invested';
  return 'Counted in full';
}

function capMessage(data: PersonalizationOut): string | null {
  if (!data.offset_capped) return null;
  if (data.cap_reason === 'zero_floor') {
    return `Your choices lean ${signedPoints(data.offset_pct_points)}, but equity can't go below 0%.`;
  }
  const labels = data.capacity_binding_constraints.map((c) => CAPACITY_CONSTRAINT_LABEL[c] ?? 'your finances');
  const lift = labels.length ? ` Improving ${labels.join(' and ')} would raise this limit.` : '';
  return (
    `Your choices lean ${signedPoints(data.offset_pct_points)}, but your finances currently support at most ` +
    `${Math.round(Number(data.max_equity_pct))}% in equity, so we've applied ${signedPoints(data.applied_offset_pct_points)}.${lift}`
  );
}

export function PersonalizationScreen() {
  const { data, isPending, error, refetch } = usePersonalization();

  return (
    <ScreenContainer>
      <View>
        <BackHeader label="Insights" />
        <Text variant="display" style={styles.title}>Personalization</Text>
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
              label="Adjustment shown"
              value={signedPoints(data!.applied_offset_pct_points)}
              helper="Equity shift from your tier's plan, learned from your choices"
            />
            <MetricCard label="Choices considered" value={String(data!.edits_considered)} helper="Your responses to past plans" />
          </View>

          {capMessage(data!) ? (
            <Card>
              <SectionHeader title="Held back by a limit" subtitle="This changes what you're shown, never your risk tier" />
              <Text variant="body">{capMessage(data!)}</Text>
            </Card>
          ) : null}

          <Card>
            <SectionHeader title="Your tier's plan vs. what you're shown" subtitle={`Tier ${data!.final_tier} of 5 — unchanged`} />
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
              <SectionHeader title="How the adjustment was built" subtitle="Each of your choices, in order — transparent reasoning, not a black box" />
              {data!.trace.map((step) => (
                <View key={step.step} style={styles.traceRow}>
                  <View style={styles.traceText}>
                    <Text variant="bodyMedium">
                      {step.step}. {stepSentence(step)}
                    </Text>
                    <Text variant="caption" tone="faint">
                      {stepWeightNote(step)}
                    </Text>
                  </View>
                  <Text variant="figure">
                    {signedPoints(step.offset_before)} → {signedPoints(step.offset_after)}
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
  title: { marginTop: SPACE.xs },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.md },
  row: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm, paddingVertical: SPACE.xs },
  rowLabel: { flex: 1 },
  traceRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: SPACE.sm, paddingVertical: SPACE.xs },
  traceText: { flex: 1 },
});
