import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import React, { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { personalizationApi } from '../../api/personalization';
import { qk } from '../../api/queryClient';
import type { AssetClass, EditActionTaken, Liquidity } from '../../api/types';
import { ASSET_CLASSES } from '../../api/types';
import { ASSET_CLASS_LABEL, LIQUIDITY_LABEL } from '../../utils/labels';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
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
import { useLatestAllocationEvent } from '../../hooks/usePersonalization';
import { useDemoUser } from '../../context/DemoUserContext';
import { useAppTheme } from '../../theme/ThemeContext';
import { ASSET_CLASS_COLOR_KEY, SPACE } from '../../theme/tokens';
import type { Palette } from '../../theme/tokens';
import type { PlanStackParamList } from '../../navigation/types';
import { formatPaise } from '../../utils/currency';

const OUTCOME_OPTIONS: { value: EditActionTaken; label: string }[] = [
  { value: 'accepted', label: 'I followed it as-is' },
  { value: 'edited', label: 'I used a different mix' },
  { value: 'rejected', label: "I didn't use it" },
  { value: 'ignored', label: 'Not decided yet' },
];

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

  const targetSegments = ASSET_CLASSES.map((ac) => ({
    key: ac,
    pct: Number(data!.target_pct[ac] ?? '0'),
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
                  <Text variant="bodyMedium">{Number(data!.target_pct[ac] ?? '0').toFixed(0)}%</Text>
                </View>
              ))}
            </View>
          </View>
        </Card>
      </Reveal>

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
                  targetPct={Number(data!.target_pct[ac] ?? '0')}
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

      {hasHoldings ? (
        <Reveal index={5}>
          <Card>
            <SectionHeader
              title="What did you do with this?"
              subtitle="Helps future suggestions reflect how you actually invest, not just this one"
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
        </Reveal>
      ) : null}

      <Button label="Back to risk profile" variant="ghost" onPress={() => navigation.navigate('RiskProfile')} />
    </ScreenContainer>
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
  outcomeButtons: { gap: SPACE.sm, marginTop: SPACE.sm },
  recordedNote: { marginTop: SPACE.sm },
});
