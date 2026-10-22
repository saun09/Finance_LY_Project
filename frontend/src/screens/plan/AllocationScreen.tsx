import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import React, { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { personalizationApi } from '../../api/personalization';
import { qk } from '../../api/queryClient';
import type { AllocationReportOut, AssetClass, Liquidity, RecordAllocationOutcomeIn, RejectReason } from '../../api/types';
import { ASSET_CLASSES } from '../../api/types';
import { ASSET_CLASS_LABEL, CAPACITY_CONSTRAINT_LABEL, LIQUIDITY_LABEL, REJECT_REASON_LABEL } from '../../utils/labels';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ChoiceGroup } from '../../components/ChoiceGroup';
import { DonutChart } from '../../components/DonutChart';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { InlineError } from '../../components/InlineError';
import { Reveal } from '../../components/Reveal';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useAllocation } from '../../hooks/useAllocation';
import { useChevronRotation } from '../../hooks/useChevronRotation';
import { useReducedMotion } from '../../hooks/useReducedMotion';
import { usePendingInvestments } from '../../hooks/usePersonalization';
import { useDemoUser } from '../../context/DemoUserContext';
import { useAppTheme } from '../../theme/ThemeContext';
import { ASSET_CLASS_COLOR_KEY, SPACE } from '../../theme/tokens';
import type { Palette } from '../../theme/tokens';
import type { PlanStackParamList } from '../../navigation/types';
import { formatPaise } from '../../utils/currency';
import { mixWithEquity } from '../../utils/allocationMix';

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

// Each asset class's comparison bar fills with its own color (current,
// solid) over its own soft tint (target) -- the exact pair IconChip
// already uses for that tone, so "target" always means "the lighter half
// of this class's own color" everywhere in the app, never a new hue.
const SOFT_KEY: Record<keyof typeof ASSET_CLASS_COLOR_KEY, keyof Palette> = {
  cash: 'petrolSoft',
  debt: 'warningSoft',
  equity: 'terracottaSoft',
  real_assets: 'positiveSoft',
  alternatives: 'dangerSoft',
};

type Nav = NativeStackNavigationProp<PlanStackParamList, 'Allocation'>;

/** Collapsed by default -- an audit trail, not something most people need
 * to read to use the page (same disclosure pattern as Plan's tier legend
 * and Progress's checklist sections). Plain-English explanation plus a
 * clean per-asset-class range grid, built from the backend's own
 * structured `target_bounds_pct` -- never a raw dump of the internal
 * reasoning string (which has bracket/variable-name syntax meant for
 * logs, not this screen) and never the internal rule-table version,
 * which stays out of the primary user view entirely. */
function MethodologyDisclosure({ finalTier, boundsPct }: { finalTier: number; boundsPct: Record<AssetClass, [string, string]> }) {
  const { colors } = useAppTheme();
  const [open, setOpen] = useState(false);
  const chevronRotation = useChevronRotation(open);

  return (
    <Card>
      <Pressable
        onPress={() => setOpen((v) => !v)}
        style={styles.disclosureHeader}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel="How this mix was calculated"
      >
        <Ionicons name="information-circle-outline" size={20} color={colors.inkFaint} />
        <Text variant="bodyMedium" style={styles.disclosureTitle}>
          How this mix was calculated
        </Text>
        <Animated.View style={{ transform: [{ rotate: chevronRotation }] }}>
          <Ionicons name="chevron-down" size={20} color={colors.inkFaint} />
        </Animated.View>
      </Pressable>
      {open ? (
        <Reveal>
          <View style={styles.disclosureBody}>
            <Text variant="body" tone="muted">
              This mix uses your Tier {finalTier} risk guardrails — a minimum and maximum range for each asset
              class — to keep your portfolio stable while aiming for the best possible return within those limits.
            </Text>
            <View style={styles.boundsGrid}>
              {(ASSET_CLASSES as AssetClass[]).map((ac) => {
                const [lo, hi] = boundsPct[ac] ?? ['0', '0'];
                return (
                  <View key={ac} style={[styles.boundsRow, { borderTopColor: colors.border }]}>
                    <Text variant="body">{ASSET_CLASS_LABEL[ac]}</Text>
                    <Text variant="bodyMedium" tone="muted">
                      {Number(lo).toFixed(0)}%–{Number(hi).toFixed(0)}%
                    </Text>
                  </View>
                );
              })}
            </View>
          </View>
        </Reveal>
      ) : null}
    </Card>
  );
}

/** One asset class's current-vs-target comparison: a single track with
 * the target shown as a soft tint underneath and the current holding as a
 * solid fill on top, both in the same hue -- so overshoot/undershoot past
 * the target reads directly from the bar shape, not a second number to
 * parse. Both fills animate in together on mount. */
function ComparisonBar({
  label,
  color,
  softColor,
  currentPct,
  targetPct,
  duration = 800,
}: {
  label: string;
  color: string;
  softColor: string;
  currentPct: number;
  targetPct: number;
  duration?: number;
}) {
  const { colors } = useAppTheme();
  const reducedMotion = useReducedMotion();
  const currentAnim = useRef(new Animated.Value(0)).current;
  const targetAnim = useRef(new Animated.Value(0)).current;
  const currentFrac = Math.max(0, Math.min(1, currentPct / 100));
  const targetFrac = Math.max(0, Math.min(1, targetPct / 100));

  useEffect(() => {
    if (reducedMotion) {
      currentAnim.setValue(currentFrac);
      targetAnim.setValue(targetFrac);
      return;
    }
    currentAnim.setValue(0);
    targetAnim.setValue(0);
    const a1 = Animated.timing(currentAnim, { toValue: currentFrac, duration, useNativeDriver: false });
    const a2 = Animated.timing(targetAnim, { toValue: targetFrac, duration, useNativeDriver: false });
    Animated.parallel([a1, a2]).start();
    return () => {
      a1.stop();
      a2.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentFrac, targetFrac, duration, reducedMotion]);

  const currentWidth = currentAnim.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] });
  const targetWidth = targetAnim.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] });

  return (
    <View style={styles.comparisonRow}>
      <View style={styles.comparisonHeaderRow}>
        <View style={styles.comparisonLabelRow}>
          <View style={[styles.dot, { backgroundColor: color }]} />
          <Text variant="bodyMedium">{label}</Text>
        </View>
        <View style={styles.comparisonValues}>
          <View style={styles.comparisonValueItem}>
            <Text variant="caption" tone="faint">
              CURRENT
            </Text>
            <Text variant="bodyMedium">{currentPct.toFixed(0)}%</Text>
          </View>
          <View style={styles.comparisonValueItem}>
            <Text variant="caption" tone="faint">
              TARGET
            </Text>
            <Text variant="bodyMedium" tone="terracotta">
              {targetPct.toFixed(0)}%
            </Text>
          </View>
        </View>
      </View>
      <View style={[styles.comparisonTrack, { backgroundColor: colors.paperSunken }]}>
        <Animated.View style={[styles.comparisonFill, { width: targetWidth, backgroundColor: softColor }]} />
        <Animated.View style={[styles.comparisonFill, { width: currentWidth, backgroundColor: color }]} />
        {/* A tick at the target position, on top of both fills -- without
            it, "current" overshooting "target" hides the target fill
            entirely underneath the solid current bar. */}
        <Animated.View style={[styles.comparisonTargetTick, { left: targetWidth, backgroundColor: colors.ink }]} />
      </View>
    </View>
  );
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

  // The plan the user is shown: the tier's mix plus their learned
  // adjustment (Module 7), capped by capacity. Identical to target_pct
  // until they've made a choice.
  const shownPct = data!.displayed_target_pct;
  const targetSegments = ASSET_CLASSES.map((ac) => ({
    key: ac,
    pct: Number(shownPct[ac] ?? '0'),
    color: colors[ASSET_CLASS_COLOR_KEY[ac]],
  }));

  const hasHoldings = data!.total_value_paise > 0;

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
        <Text variant="body" tone="muted" style={styles.headerSubtitle}>
          Your recommended allocation
        </Text>
      </View>

      <Reveal index={0}>
        <MethodologyDisclosure finalTier={data!.final_tier} boundsPct={data!.target_bounds_pct} />
      </Reveal>

      <Reveal index={1}>
        <Card style={styles.donutCard}>
          <SectionHeader title="Target allocation" subtitle={`For tier ${data!.final_tier} of 5`} />
          <View style={styles.totalValueRow}>
            <Text variant="caption" tone="faint">
              TOTAL PORTFOLIO VALUE
            </Text>
            <Text variant="figure" tone="muted">
              {formatPaise(data!.total_value_paise)}
            </Text>
          </View>
          <View style={styles.donutRow}>
            <DonutChart segments={targetSegments} trackColor={colors.paperSunken} />
            <View style={styles.legend}>
              {(ASSET_CLASSES as AssetClass[]).map((ac) => (
                <View key={ac} style={styles.legendRow}>
                  <View style={[styles.dot, { backgroundColor: colors[ASSET_CLASS_COLOR_KEY[ac]] }]} />
                  <Text variant="body" style={styles.legendLabel}>
                    {ASSET_CLASS_LABEL[ac]}
                  </Text>
                  <Text variant="bodyMedium">{pct(shownPct[ac])}</Text>
                </View>
              ))}
            </View>
          </View>
        </Card>
      </Reveal>

      <PersonalAdjustmentCard report={data!} />

      <Reveal index={2}>
        <Card>
          <SectionHeader
            title="Current vs target"
            subtitle={hasHoldings ? 'How your actual holdings compare to the recommendation' : undefined}
          />
          {hasHoldings ? (
            <>
              <Text variant="caption" tone="faint" style={styles.comparisonLegendNote}>
                Solid fill is what you hold now; the lighter fill marks your target.
              </Text>
              {(ASSET_CLASSES as AssetClass[]).map((ac) => (
                <ComparisonBar
                  key={ac}
                  label={ASSET_CLASS_LABEL[ac]}
                  color={colors[ASSET_CLASS_COLOR_KEY[ac]]}
                  softColor={colors[SOFT_KEY[ac]]}
                  currentPct={Number(data!.current_exposure_pct[ac] ?? '0')}
                  targetPct={Number(shownPct[ac] ?? '0')}
                />
              ))}
            </>
          ) : (
            <Text variant="caption" tone="muted">
              No holdings recorded yet — this shows your target mix for Tier {data!.final_tier} only.
            </Text>
          )}
        </Card>
      </Reveal>

      <Reveal index={3}>
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
      </Reveal>

      {liquidityEntries.length > 0 ? (
        <Reveal index={4}>
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
        </Reveal>
      ) : null}

      {savedNote ? (
        <Text variant="bodyMedium" tone="positive">
          {savedNote}
        </Text>
      ) : null}

      {/* keyed by event: a recorded response loads the next plan as a new
          suggestion, and this card starts fresh for it */}
      <Reveal index={5}>
        <PlanResponseCard key={data!.event_id} report={data!} onSaved={setSavedNote} />
      </Reveal>

      <PendingInvestmentsCard onSaved={setSavedNote} />

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
  headerSubtitle: { marginTop: SPACE.xs },

  disclosureHeader: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  disclosureTitle: { flex: 1 },
  disclosureBody: { marginTop: SPACE.md },
  boundsGrid: { marginTop: SPACE.md },
  boundsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: SPACE.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
  },

  donutCard: { gap: SPACE.md },
  totalValueRow: { gap: 2 },
  donutRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.lg, flexWrap: 'wrap' },
  legend: { flex: 1, minWidth: 160, gap: SPACE.sm },
  legendRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  dot: { width: 8, height: 8, borderRadius: 4 },
  legendLabel: { flex: 1 },

  comparisonLegendNote: { marginTop: SPACE.xs, marginBottom: SPACE.sm },
  comparisonRow: { marginTop: SPACE.md },
  comparisonHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: SPACE.xs },
  comparisonLabelRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  comparisonValues: { flexDirection: 'row', gap: SPACE.lg },
  comparisonValueItem: { alignItems: 'flex-end' },
  comparisonTrack: { height: 10, borderRadius: 5, overflow: 'hidden', width: '100%' },
  comparisonFill: { position: 'absolute', left: 0, top: 0, bottom: 0, borderRadius: 5 },
  comparisonTargetTick: { position: 'absolute', top: 0, bottom: 0, width: 2, marginLeft: -1 },

  metricRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: SPACE.xs },
  gapNote: { marginTop: SPACE.md, textAlign: 'center' },
  actions: { gap: SPACE.sm, marginTop: SPACE.sm },
  stepper: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: SPACE.xs, flexWrap: 'wrap' },
  stepperValue: { minWidth: 72, textAlign: 'center' },
  pendingRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: SPACE.sm, paddingVertical: SPACE.xs },
  pendingText: { flex: 1 },
});
