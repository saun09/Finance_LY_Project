import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { personalizationApi } from '../../api/personalization';
import { qk } from '../../api/queryClient';
import type { AllocationReportOut, Liquidity, RecordAllocationOutcomeIn, RejectReason } from '../../api/types';
import { ASSET_CLASSES } from '../../api/types';
import { ASSET_CLASS_LABEL, CAPACITY_CONSTRAINT_LABEL, LIQUIDITY_LABEL, REJECT_REASON_LABEL } from '../../utils/labels';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ChoiceGroup } from '../../components/ChoiceGroup';
import { DonutChart } from '../../components/DonutChart';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { InlineError } from '../../components/InlineError';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useAllocation } from '../../hooks/useAllocation';
import { usePendingInvestments } from '../../hooks/usePersonalization';
import { useDemoUser } from '../../context/DemoUserContext';
import { useAppTheme } from '../../theme/ThemeContext';
import { ASSET_CLASS_COLOR_KEY, SPACE } from '../../theme/tokens';
import type { PlanStackParamList } from '../../navigation/types';
import { formatPaise } from '../../utils/currency';
import { mixWithEquity } from '../../utils/allocationMix';

type Nav = NativeStackNavigationProp<PlanStackParamList, 'Allocation'>;

const REJECT_OPTIONS = (Object.keys(REJECT_REASON_LABEL) as RejectReason[]).map((value) => ({
  value,
  label: REJECT_REASON_LABEL[value],
}));

/** "+4 points", "-2.5 points" -- the offset as a person would say it. */
function points(value: string | number): string {
  const n = Number(value);
  const rounded = Math.round(n * 10) / 10;
  return `${rounded > 0 ? '+' : ''}${rounded} point${Math.abs(rounded) === 1 ? '' : 's'}`;
}

function pct(value: string | number | undefined): string {
  return `${Math.round(Number(value ?? 0) * 10) / 10}%`;
}

function joinedLabels(codes: string[]): string {
  const labels = codes.map((c) => CAPACITY_CONSTRAINT_LABEL[c] ?? 'your finances');
  if (labels.length <= 1) return labels[0] ?? '';
  return `${labels.slice(0, -1).join(', ')} and ${labels[labels.length - 1]}`;
}

/** Everything a recorded response can change: the next plan, the offset,
 * the pending-investment list and the transparency traces. */
function useInvalidateAfterResponse() {
  const queryClient = useQueryClient();
  const { userId } = useDemoUser();
  return () => {
    queryClient.invalidateQueries({ queryKey: qk.allocation(userId) });
    queryClient.invalidateQueries({ queryKey: qk.personalization(userId) });
    queryClient.invalidateQueries({ queryKey: qk.events(userId, 'allocation') });
    queryClient.invalidateQueries({ queryKey: ['transparency-trace', userId] });
    queryClient.invalidateQueries({ queryKey: qk.transparencyIndex(userId) });
  };
}

export function AllocationScreen() {
  const navigation = useNavigation<Nav>();
  const { colors } = useAppTheme();
  const { data, isPending, error, refetch } = useAllocation();
  const [savedNote, setSavedNote] = useState<string | null>(null);

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

  const report = data!;
  const segments = ASSET_CLASSES.map((ac) => ({
    key: ac,
    pct: Number(report.current_exposure_pct[ac] ?? '0'),
    color: colors[ASSET_CLASS_COLOR_KEY[ac]],
  }));

  const liquidityEntries = (Object.keys(LIQUIDITY_LABEL) as Liquidity[]).filter(
    (l) => (report.liquidity_breakdown_paise[l] ?? 0) > 0,
  );

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Allocation · Tier {report.final_tier} of 5
        </Text>
        <Text variant="display">Your target mix</Text>
      </View>

      {/* The rule-table lookup text ("Looked up tier 1 bounds ...") is an
          audit detail, not something a user reads; it stays available on
          the Transparency screen's "Target allocation" trace. */}
      <PersonalAdjustmentCard report={report} />

      <Card style={styles.donutCard}>
        <SectionHeader title="Current exposure → your plan" subtitle={formatPaise(report.total_value_paise)} />
        {report.total_value_paise === 0 ? (
          <Text variant="caption" tone="muted">
            No holdings recorded yet — this shows your plan for Tier {report.final_tier} only.
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
                  {Number(report.current_exposure_pct[ac] ?? '0').toFixed(0)}%
                </Text>
                <Text variant="caption" tone="faint">
                  → {pct(report.displayed_target_pct[ac])}
                </Text>
              </View>
            ))}
          </View>
        </View>
      </Card>

      {savedNote ? (
        <Text variant="bodyMedium" tone="positive">
          {savedNote}
        </Text>
      ) : null}

      {/* keyed by event: a recorded response loads the next plan as a new
          suggestion, and this card starts fresh for it */}
      <PlanResponseCard key={report.event_id} report={report} onSaved={setSavedNote} />

      <PendingInvestmentsCard onSaved={setSavedNote} />

      <Card>
        <SectionHeader title="Concentration" />
        <View style={styles.metricRow}>
          <Text variant="caption" tone="muted">
            Largest single holding
          </Text>
          <Text variant="figure">{Number(report.concentration.largest_holding_pct).toFixed(1)}%</Text>
        </View>
        <View style={styles.metricRow}>
          <Text variant="caption" tone="muted">
            Asset-class HHI
          </Text>
          <Text variant="figure">{report.concentration.asset_class_hhi_bps} bps</Text>
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
              <Text variant="figure">{formatPaise(report.liquidity_breakdown_paise[l] ?? 0)}</Text>
            </View>
          ))}
        </Card>
      ) : null}

      <Button label="Back to risk profile" variant="ghost" onPress={() => navigation.navigate('RiskProfile')} />
    </ScreenContainer>
  );
}

/** Module 7, surfaced: how the user's own choices moved the plan, and --
 * when the capacity cap holds it back -- what is limiting it and what would
 * lift the limit. Never silent about the cap. */
function PersonalAdjustmentCard({ report }: { report: AllocationReportOut }) {
  const p = report.personalization;
  if (p.edits_considered === 0 && !p.capped) return null;

  const base = report.target_pct.equity;
  const shown = report.displayed_target_pct.equity;
  const choices = `${p.edits_considered} choice${p.edits_considered === 1 ? '' : 's'}`;

  let body: string;
  if (p.capped && p.cap_reason === 'zero_floor') {
    body = `Your choices lean ${points(p.requested_offset_pct_points)}, but equity can't go below 0%, so we show ${pct(shown)}.`;
  } else if (p.capped) {
    const lift = p.capacity_binding_constraints.length
      ? ` Improving ${joinedLabels(p.capacity_binding_constraints)} would raise this limit.`
      : '';
    body =
      `Your choices lean ${points(p.requested_offset_pct_points)} on equity, but your finances currently support ` +
      `at most ${pct(p.max_equity_pct)}, so we show ${pct(shown)}.${lift}`;
  } else if (Number(p.offset_pct_points) !== 0) {
    body = `Your tier's plan has ${pct(base)} in equity. Based on ${choices} you've made, we show ${pct(shown)} (${points(p.offset_pct_points)}).`;
  } else {
    body = `Based on ${choices} you've made, your plan matches your tier's mix (${pct(base)} in equity).`;
  }

  return (
    <Card>
      <SectionHeader
        title={p.capped ? 'Adjusted to your choices — up to a limit' : 'Adjusted to your choices'}
        subtitle={`Your risk tier stays Tier ${report.final_tier}`}
      />
      <Text variant="body">{body}</Text>
    </Card>
  );
}

type Step = 'choose' | 'edit' | 'reject' | 'invested';

function PlanResponseCard({ report, onSaved }: { report: AllocationReportOut; onSaved: (note: string) => void }) {
  const { userId } = useDemoUser();
  const invalidate = useInvalidateAfterResponse();
  const shownEquity = Math.round(Number(report.displayed_target_pct.equity));

  const [step, setStep] = useState<Step>('choose');
  const [pendingAction, setPendingAction] = useState<'accepted' | 'edited'>('accepted');
  const [equity, setEquity] = useState(shownEquity);
  const [reason, setReason] = useState<RejectReason | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const ownMix = mixWithEquity(report.displayed_target_pct, equity);

  const record = useMutation({
    mutationFn: (body: RecordAllocationOutcomeIn) => personalizationApi.recordAllocationOutcome(userId, report.event_id, body),
    onSuccess: (_r, body) => {
      onSaved(
        body.action_taken === 'rejected'
          ? 'Noted — thanks. Your next plan is below.'
          : body.funded
            ? 'Saved. Your next plan reflects this choice in full.'
            : "Saved. It counts at half strength until you mark it as invested.",
      );
      invalidate();
    },
    onError: () => setSaveError('Could not save that — please try again.'),
  });

  const submitInvested = (funded: boolean) => {
    setSaveError(null);
    record.mutate(
      pendingAction === 'edited'
        ? { action_taken: 'edited', chosen_target_pct: ownMix, funded }
        : { action_taken: 'accepted', funded },
    );
  };

  return (
    <Card>
      <SectionHeader
        title="What will you do with this plan?"
        subtitle="Your answers lean future plans toward how you actually invest. They never change your risk tier."
      />

      {step === 'choose' ? (
        <View style={styles.actions}>
          <Button
            label="Use this plan"
            onPress={() => {
              setPendingAction('accepted');
              setStep('invested');
            }}
          />
          <Button label="Set my own mix" variant="secondary" onPress={() => setStep('edit')} />
          <Button label="Not for me" variant="ghost" onPress={() => setStep('reject')} />
        </View>
      ) : null}

      {step === 'edit' ? (
        <View style={styles.actions}>
          <Text variant="bodyMedium">How much in equity?</Text>
          <View style={styles.stepper}>
            <Button label="−5" variant="ghost" disabled={equity <= 0} onPress={() => setEquity((e) => Math.max(0, e - 5))} />
            <Button label="−1" variant="ghost" disabled={equity <= 0} onPress={() => setEquity((e) => Math.max(0, e - 1))} />
            <Text variant="figureLarge" style={styles.stepperValue}>
              {equity}%
            </Text>
            <Button label="+1" variant="ghost" disabled={equity >= 100} onPress={() => setEquity((e) => Math.min(100, e + 1))} />
            <Button label="+5" variant="ghost" disabled={equity >= 100} onPress={() => setEquity((e) => Math.min(100, e + 5))} />
          </View>
          <Text variant="caption" tone="muted">
            The plan shows {shownEquity}%. The rest is spread in the same proportions as the plan:
          </Text>
          {ASSET_CLASSES.filter((ac) => ac !== 'equity').map((ac) => (
            <View key={ac} style={styles.metricRow}>
              <Text variant="caption" tone="muted">
                {ASSET_CLASS_LABEL[ac]}
              </Text>
              <Text variant="figure">{pct(ownMix[ac])}</Text>
            </View>
          ))}
          <Button
            label="Continue"
            disabled={equity === shownEquity}
            onPress={() => {
              setPendingAction('edited');
              setStep('invested');
            }}
          />
          {equity === shownEquity ? (
            <Text variant="caption" tone="faint">
              That's the same as the plan — use “Use this plan” instead, or change the equity share.
            </Text>
          ) : null}
          <Button label="Back" variant="ghost" onPress={() => setStep('choose')} />
        </View>
      ) : null}

      {step === 'reject' ? (
        <View style={styles.actions}>
          <ChoiceGroup label="What's the main reason?" uppercaseLabel={false} options={REJECT_OPTIONS} value={reason} onChange={setReason} />
          {reason === 'too_risky' || reason === 'too_safe' ? (
            <Text variant="caption" tone="muted">
              A reason alone doesn't tell the plan how much to change. If you know the mix you'd prefer, “Set my own
              mix” is what future plans learn from.
            </Text>
          ) : null}
          <Button
            label="Save"
            disabled={!reason}
            loading={record.isPending}
            onPress={() => {
              setSaveError(null);
              record.mutate({ action_taken: 'rejected', reason_code: reason });
            }}
          />
          <Button label="Back" variant="ghost" onPress={() => setStep('choose')} />
        </View>
      ) : null}

      {step === 'invested' ? (
        <View style={styles.actions}>
          <Text variant="bodyMedium">
            {pendingAction === 'edited' ? `Have you invested with ${equity}% in equity?` : 'Have you invested this plan?'}
          </Text>
          <Text variant="caption" tone="muted">
            A choice you've actually invested counts in full. Otherwise it counts at half strength until you mark it as
            invested below.
          </Text>
          <Button label="Yes, I've invested it" loading={record.isPending && record.variables?.funded === true} onPress={() => submitInvested(true)} />
          <Button
            label="Not yet"
            variant="secondary"
            loading={record.isPending && record.variables?.funded === false}
            onPress={() => submitInvested(false)}
          />
          <Button label="Back" variant="ghost" onPress={() => setStep(pendingAction === 'edited' ? 'edit' : 'choose')} />
        </View>
      ) : null}

      {saveError ? <InlineError message={saveError} /> : null}
    </Card>
  );
}

/** Earlier choices recorded as "not invested yet". Marking one as invested
 * raises its weight from half to full; the plan is replayed from history,
 * so the next plan reflects it immediately. */
function PendingInvestmentsCard({ onSaved }: { onSaved: (note: string) => void }) {
  const { userId } = useDemoUser();
  const invalidate = useInvalidateAfterResponse();
  const { data } = usePendingInvestments();
  const [saveError, setSaveError] = useState<string | null>(null);

  const markFunded = useMutation({
    mutationFn: (eventId: string) => personalizationApi.markFunded(userId, eventId),
    onSuccess: () => {
      onSaved('Marked as invested — that choice now counts in full.');
      invalidate();
    },
    onError: () => setSaveError('Could not save that — please try again.'),
  });

  if (!data || data.length === 0) return null;

  return (
    <Card>
      <SectionHeader title="Waiting to be invested" subtitle="These count at half strength until you've invested them" />
      {data.map((event) => {
        const chosenEquity = (event.chosen_value as Record<string, string> | null)?.equity;
        const when = new Date(event.timestamp).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
        return (
          <View key={event.event_id} style={styles.pendingRow}>
            <View style={styles.pendingText}>
              <Text variant="bodyMedium">
                {event.action_taken === 'edited' ? 'Your own mix' : 'The plan as shown'} · {pct(chosenEquity)} equity
              </Text>
              <Text variant="caption" tone="faint">
                Chosen {when}
              </Text>
            </View>
            <Button
              label="I've invested it"
              variant="secondary"
              loading={markFunded.isPending && markFunded.variables === event.event_id}
              onPress={() => {
                setSaveError(null);
                markFunded.mutate(event.event_id);
              }}
            />
          </View>
        );
      })}
      {saveError ? <InlineError message={saveError} /> : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  donutCard: { gap: SPACE.md },
  donutRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.lg, flexWrap: 'wrap' },
  legend: { flex: 1, minWidth: 160, gap: SPACE.sm },
  legendRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.xs },
  dot: { width: 8, height: 8, borderRadius: 4 },
  legendLabel: { flex: 1 },
  metricRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: SPACE.xs },
  gapNote: { marginTop: SPACE.md, textAlign: 'center' },
  actions: { gap: SPACE.sm, marginTop: SPACE.sm },
  stepper: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: SPACE.xs, flexWrap: 'wrap' },
  stepperValue: { minWidth: 72, textAlign: 'center' },
  pendingRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: SPACE.sm, paddingVertical: SPACE.xs },
  pendingText: { flex: 1 },
});
