import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View } from 'react-native';
import { ASSET_CLASSES, EditActionTaken, OffsetStepOut } from '../../api/types';
import { AnimatedFigure } from '../../components/AnimatedFigure';
import { BackHeader } from '../../components/BackHeader';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { IconChip } from '../../components/IconChip';
import { Reveal } from '../../components/Reveal';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useReducedMotion } from '../../hooks/useReducedMotion';
import { usePersonalization } from '../../hooks/usePersonalization';
import { ASSET_CLASS_LABEL } from '../../utils/labels';
import { useAppTheme } from '../../theme/ThemeContext';
import { ASSET_CLASS_COLOR_KEY, Palette, RADIUS, SPACE } from '../../theme/tokens';

// Each asset class's comparison bar fills with its own color (personalized,
// solid) over its own soft tint (base, lighter) -- the same color pairing
// AllocationScreen's own comparison bars use, so "lighter fill = where you
// started from" means the same thing everywhere in the app.
const SOFT_KEY: Record<keyof typeof ASSET_CLASS_COLOR_KEY, keyof Palette> = {
  cash: 'petrolSoft',
  debt: 'warningSoft',
  equity: 'terracottaSoft',
  real_assets: 'positiveSoft',
  alternatives: 'dangerSoft',
};

const ACTION_VERB: Record<EditActionTaken, string> = {
  accepted: 'Accepted the suggested mix',
  edited: 'Adjusted the suggested mix',
  rejected: 'Rejected the suggested mix',
  ignored: "Didn't act on the suggested mix",
};

function formatSignedPts(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return `${rounded >= 0 ? '+' : ''}${rounded.toFixed(1)}`;
}

/** Turns one replayed allocation-outcome event into plain language --
 * never a questionnaire answer (this module has no link to those), always
 * the real accept/edit/reject/ignore decision + funded status actually
 * recorded against that suggestion_event. */
function describeStep(step: OffsetStepOut): { headline: string; fundedTag: string | null } {
  const suggested = step.suggested_equity_pct !== null ? Number(step.suggested_equity_pct) : null;
  const chosen = step.chosen_equity_pct !== null ? Number(step.chosen_equity_pct) : null;
  const action = step.action_taken;

  if (!action) {
    return { headline: `Allocation decision #${step.step}`, fundedTag: null };
  }

  let headline = ACTION_VERB[action];
  if (action === 'edited' && chosen !== null && suggested !== null) {
    headline = `Chose ${chosen.toFixed(0)}% equity instead of the suggested ${suggested.toFixed(0)}%`;
  } else if (suggested !== null) {
    headline = `${ACTION_VERB[action]} — ${suggested.toFixed(0)}% equity`;
  }

  const fundedTag =
    action === 'accepted' || action === 'edited'
      ? step.funded === true
        ? 'Funded'
        : step.funded === false
          ? 'Not yet funded'
          : null
      : null;

  return { headline, fundedTag };
}

function weightLabel(weight: string): string {
  const n = Number(weight);
  if (n >= 1) return 'Full weight';
  if (n > 0) return 'Half weight';
  return "No weight — didn't move the estimate";
}

interface HeroCardProps {
  icon: keyof typeof Ionicons.glyphMap;
  tone: 'positive' | 'warning' | 'danger' | 'petrol';
  label: string;
  target: number;
  formatter: (n: number) => string;
  helper: string;
}

const GRADIENT_SOFT_KEY: Record<HeroCardProps['tone'], keyof Palette> = {
  positive: 'positiveSoft',
  warning: 'warningSoft',
  danger: 'dangerSoft',
  petrol: 'petrolSoft',
};

/** An elevated, gently-glowing hero metric -- a soft tone-tinted gradient
 * fading into the ordinary card surface (never a drop shadow or a loud
 * color block), with an icon chip anchoring what the figure means. Same
 * gradient-into-paperRaised technique LeaksScreen's hero total already
 * uses, just sized for two side-by-side cards instead of one full-width
 * one. */
function HeroCard({ icon, tone, label, target, formatter, helper }: HeroCardProps) {
  const { colors } = useAppTheme();
  return (
    <LinearGradient
      colors={[colors[GRADIENT_SOFT_KEY[tone]], colors.paperRaised]}
      start={{ x: 0, y: 0 }}
      end={{ x: 0.7, y: 1 }}
      style={[styles.heroCard, { borderColor: colors.borderStrong }]}
    >
      <IconChip name={icon} tone={tone} size={32} />
      <Text variant="label" tone="muted" style={styles.heroLabel}>
        {label.toUpperCase()}
      </Text>
      <AnimatedFigure target={target} formatter={formatter} variant="figureLarge" />
      <Text variant="caption" tone="faint" style={styles.heroHelper}>
        {helper}
      </Text>
    </LinearGradient>
  );
}

interface ComparisonRowProps {
  label: string;
  color: string;
  softColor: string;
  basePct: number;
  personalizedPct: number;
  duration?: number;
}

/** One asset class's base-vs-personalized target, drawn exactly like
 * AllocationScreen's own current-vs-target bar (lighter fill = base, solid
 * fill = personalized, a tick marking the base position so a shift past it
 * is still visible underneath), plus a delta pill -- the one new piece
 * this screen needs that Allocation's version doesn't. */
function ComparisonRow({ label, color, softColor, basePct, personalizedPct, duration = 800 }: ComparisonRowProps) {
  const { colors } = useAppTheme();
  const reducedMotion = useReducedMotion();
  const baseAnim = useRef(new Animated.Value(0)).current;
  const personalizedAnim = useRef(new Animated.Value(0)).current;
  const baseFrac = Math.max(0, Math.min(1, basePct / 100));
  const personalizedFrac = Math.max(0, Math.min(1, personalizedPct / 100));
  const delta = personalizedPct - basePct;

  useEffect(() => {
    if (reducedMotion) {
      baseAnim.setValue(baseFrac);
      personalizedAnim.setValue(personalizedFrac);
      return;
    }
    baseAnim.setValue(0);
    personalizedAnim.setValue(0);
    const a1 = Animated.timing(baseAnim, { toValue: baseFrac, duration, useNativeDriver: false });
    const a2 = Animated.timing(personalizedAnim, { toValue: personalizedFrac, duration, useNativeDriver: false });
    Animated.parallel([a1, a2]).start();
    return () => {
      a1.stop();
      a2.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseFrac, personalizedFrac, duration, reducedMotion]);

  const baseWidth = baseAnim.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] });
  const personalizedWidth = personalizedAnim.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] });

  return (
    <View style={styles.comparisonRow}>
      <View style={styles.comparisonHeaderRow}>
        <View style={styles.comparisonLabelRow}>
          <View style={[styles.dot, { backgroundColor: color }]} />
          <Text variant="bodyMedium">{label}</Text>
        </View>
        <View style={styles.comparisonValuesRow}>
          <Text variant="figure" tone="faint">
            {basePct.toFixed(0)}%
          </Text>
          <Text variant="caption" tone="faint"> → </Text>
          <Text variant="figure">{personalizedPct.toFixed(0)}%</Text>
          {delta !== 0 ? (
            <View style={[styles.deltaPill, { backgroundColor: delta > 0 ? colors.positiveSoft : colors.dangerSoft }]}>
              <Text variant="caption" tone={delta > 0 ? 'positive' : 'danger'}>
                {formatSignedPts(delta)}%
              </Text>
            </View>
          ) : null}
        </View>
      </View>
      <View style={[styles.comparisonTrack, { backgroundColor: colors.paperSunken }]}>
        <Animated.View style={[styles.comparisonFill, { width: baseWidth, backgroundColor: softColor }]} />
        <Animated.View style={[styles.comparisonFill, { width: personalizedWidth, backgroundColor: color }]} />
        <Animated.View style={[styles.comparisonBaseTick, { left: baseWidth, backgroundColor: colors.ink }]} />
      </View>
    </View>
  );
}

function StepRow({ step, index, isLast }: { step: OffsetStepOut; index: number; isLast: boolean }) {
  const { colors } = useAppTheme();
  const { headline, fundedTag } = describeStep(step);
  const dateLabel = step.timestamp
    ? new Date(step.timestamp).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
    : null;

  return (
    <View style={styles.stepRow}>
      <View style={styles.stepRailCol}>
        <View style={[styles.stepDot, { backgroundColor: colors.petrol }]}>
          <Text variant="caption" tone="onDark" style={styles.stepDotText}>
            {step.step}
          </Text>
        </View>
        {!isLast ? <View style={[styles.stepRailLine, { backgroundColor: colors.border }]} /> : null}
      </View>
      <View style={styles.stepBody}>
        <Text variant="bodyMedium">{headline}</Text>
        <View style={styles.stepMetaRow}>
          {dateLabel ? (
            <Text variant="caption" tone="faint">
              {dateLabel}
            </Text>
          ) : null}
          {fundedTag ? (
            <View
              style={[
                styles.weightPill,
                { backgroundColor: fundedTag === 'Funded' ? colors.positiveSoft : colors.paperSunken },
              ]}
            >
              <Text variant="caption" tone={fundedTag === 'Funded' ? 'positive' : 'muted'}>
                {fundedTag}
              </Text>
            </View>
          ) : null}
          <View style={[styles.weightPill, { backgroundColor: colors.paperSunken }]}>
            <Text variant="caption" tone="muted">
              {weightLabel(step.weight)}
            </Text>
          </View>
        </View>
        <Text variant="caption" tone="faint" style={styles.stepShift}>
          Offset moved {formatSignedPts(Number(step.offset_before))} → {formatSignedPts(Number(step.offset_after))} pts
        </Text>
      </View>
    </View>
  );
}

export function PersonalizationScreen() {
  const { data, isPending, error, refetch } = usePersonalization();
  const { colors } = useAppTheme();

  const offsetValue = data ? Number(data.offset_pct_points) : 0;
  const offsetTone: HeroCardProps['tone'] = offsetValue > 0 ? 'positive' : offsetValue < 0 ? 'danger' : 'petrol';

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
        // ScreenContainer only puts its own gap between ITS direct children
        // -- this whole block is one of those (a bare fragment before),
        // so without an explicit gap here every card below rendered flush
        // against the next with nothing but two stacked hairline borders
        // between them (same bug already fixed on the Leaks and Risk
        // Profile screens).
        <View style={styles.resultsGroup}>
          <Reveal index={0}>
            <View style={styles.heroRow}>
              <HeroCard
                icon="locate-outline"
                tone={offsetTone}
                label="Offset applied"
                target={offsetValue}
                formatter={(n) => `${formatSignedPts(n)} pts`}
                helper="Shift from your base target, based on past decisions"
              />
              <HeroCard
                icon="create-outline"
                tone="petrol"
                label="Edits considered"
                target={data!.edits_considered}
                formatter={(n) => `${Math.round(n)}`}
                helper="Past allocation outcomes used"
              />
            </View>
          </Reveal>

          <Reveal index={1}>
            <Card>
              <SectionHeader title="Base vs. personalized target" subtitle={`Tier ${data!.final_tier} of 5`} />
              <Text variant="caption" tone="faint" style={styles.comparisonLegendNote}>
                Lighter fill is your base target; the solid fill is what's actually shown to you now.
              </Text>
              {ASSET_CLASSES.map((ac) => (
                <ComparisonRow
                  key={ac}
                  label={ASSET_CLASS_LABEL[ac]}
                  color={colors[ASSET_CLASS_COLOR_KEY[ac]]}
                  softColor={colors[SOFT_KEY[ac]]}
                  basePct={Number(data!.base_target_pct[ac] ?? '0')}
                  personalizedPct={Number(data!.displayed_target_pct[ac] ?? '0')}
                />
              ))}
            </Card>
          </Reveal>

          {data!.trace.length > 0 ? (
            <Reveal index={2}>
              <Card>
                <SectionHeader
                  title="How the offset was built"
                  subtitle="Each past decision, in order — the real evidence behind the number above"
                />
                <View style={styles.stepList}>
                  {data!.trace.map((step, i) => (
                    <StepRow key={step.step} step={step} index={i} isLast={i === data!.trace.length - 1} />
                  ))}
                </View>
              </Card>
            </Reveal>
          ) : null}
        </View>
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  title: { marginTop: SPACE.xs },
  resultsGroup: { gap: SPACE.lg },
  heroRow: { flexDirection: 'row', gap: SPACE.md },
  heroCard: {
    flex: 1,
    minWidth: 150,
    gap: SPACE.xs,
    borderRadius: RADIUS.lg,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    padding: SPACE.lg,
  },
  heroLabel: { marginTop: SPACE.xs },
  heroHelper: { marginTop: SPACE.xs },
  comparisonLegendNote: { marginTop: SPACE.sm, marginBottom: SPACE.sm },
  dot: { width: 8, height: 8, borderRadius: 4 },
  comparisonRow: { marginTop: SPACE.md },
  comparisonHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: SPACE.xs, flexWrap: 'wrap', gap: SPACE.xs },
  comparisonLabelRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  comparisonValuesRow: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  deltaPill: { marginLeft: SPACE.xs, paddingHorizontal: SPACE.sm, paddingVertical: 2, borderRadius: RADIUS.pill },
  comparisonTrack: { height: 10, borderRadius: 5, overflow: 'hidden', width: '100%' },
  comparisonFill: { position: 'absolute', left: 0, top: 0, bottom: 0, borderRadius: 5 },
  comparisonBaseTick: { position: 'absolute', top: 0, bottom: 0, width: 2, marginLeft: -1 },
  stepList: { marginTop: SPACE.sm },
  stepRow: { flexDirection: 'row', gap: SPACE.sm },
  stepRailCol: { alignItems: 'center', width: 28 },
  stepDot: { width: 24, height: 24, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  stepDotText: { fontSize: 11, lineHeight: 14 },
  stepRailLine: { width: 2, flex: 1, marginTop: 2, marginBottom: 2 },
  stepBody: { flex: 1, paddingBottom: SPACE.lg },
  stepMetaRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm, marginTop: 4, flexWrap: 'wrap' },
  weightPill: { paddingHorizontal: SPACE.sm, paddingVertical: 2, borderRadius: RADIUS.pill },
  stepShift: { marginTop: 4 },
});
