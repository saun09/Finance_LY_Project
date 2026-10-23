import { Ionicons } from '@expo/vector-icons';
import type { CompositeNavigationProp } from '@react-navigation/native';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import type { NativeStackNavigationProp, NativeStackScreenProps } from '@react-navigation/native-stack';
import React, { useEffect, useRef } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import type { MLFeatureContributionOut, MLPredictionSectionOut, TraceResultOut } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { DonutChart } from '../../components/DonutChart';
import { ErrorState } from '../../components/ErrorState';
import { FactList } from '../../components/FactList';
import { InlineError } from '../../components/InlineError';
import { Reveal } from '../../components/Reveal';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { useAppTheme } from '../../theme/ThemeContext';
import { useReducedMotion } from '../../hooks/useReducedMotion';
import { useContestDecision, useContestReasons, useTransparencyTrace } from '../../hooks/useTransparency';
import { formatPercent } from '../../utils/currency';
import { SPACE, RADIUS } from '../../theme/tokens';
import { CONTEST_REASON_LABEL } from '../../utils/labels';
import type { InsightsStackParamList, MainTabParamList } from '../../navigation/types';

/** "a, b and c" — reads as a sentence, since these labels are now words
 * rather than field names. */
function joinLabels(labels: string[]): string {
  if (labels.length === 0) return 'part of this';
  if (labels.length === 1) return labels[0].toLowerCase();
  const lower = labels.map((l) => l.toLowerCase());
  return `${lower.slice(0, -1).join(', ')} and ${lower[lower.length - 1]}`;
}

type Props = NativeStackScreenProps<InsightsStackParamList, 'TransparencyDetail'>;
type Nav = CompositeNavigationProp<
  NativeStackNavigationProp<InsightsStackParamList, 'TransparencyDetail'>,
  BottomTabNavigationProp<MainTabParamList>
>;

export function TransparencyDetailScreen() {
  const { colors } = useAppTheme();
  const navigation = useNavigation<Nav>();
  const { params } = useRoute<Props['route']>();
  const { data, isPending, error, refetch } = useTransparencyTrace(params.moduleSource, params.eventId);
  const [contestOpen, setContestOpen] = React.useState(false);

  if (isPending) {
    return (
      <ScreenContainer>
        <Text variant="display">Transparency</Text>
        <SkeletonCard />
        <SkeletonCard />
      </ScreenContainer>
    );
  }

  if (error) {
    return (
      <ScreenContainer>
        <Text variant="display">Transparency</Text>
        <ErrorState message={error.message} onRetry={() => refetch()} />
      </ScreenContainer>
    );
  }

  const trace = data!;

  return (
    <ScreenContainer>
      <View>
        <View style={[styles.badge, { backgroundColor: colors.petrolSoft }]}>
          <Text variant="label" tone="petrol">
            {trace.framing_label.toUpperCase()}
          </Text>
        </View>
        <Text variant="display" style={styles.title}>
          {trace.display_name}
        </Text>
        <Text variant="caption" tone="faint">
          {new Date(trace.timestamp).toLocaleString('en-IN')}
          {params.eventId ? ' · viewing a past decision' : ' · most recent decision'}
        </Text>
      </View>

      {trace.module_source === 'risk_profile_ml' ? (
        <RiskMlTrace
          trace={trace}
          navigation={navigation}
          contestOpen={contestOpen}
          onToggleContest={() => setContestOpen((v) => !v)}
        />
      ) : (
        <>
          <Card>
            <Text variant="bodyMedium">{trace.headline}</Text>
          </Card>

          {/* What this trace is and isn't -- shown whenever the decision type's
              claim needs qualifying, e.g. the n8n workflow's self-reported prose
              versus the local engine's computed elimination trace. */}
          {trace.claim_note ? (
            <Card style={{ backgroundColor: colors.petrolSoft, borderColor: colors.petrolSoft }}>
              <Text variant="caption" tone="petrol">
                {trace.claim_note}
              </Text>
            </Card>
          ) : null}

          {trace.gap_detected ? (
            <Card style={{ backgroundColor: colors.warningSoft, borderColor: colors.warningSoft }}>
              <Text variant="bodyMedium" tone="warning">
                Part of this decision wasn’t recorded at the time, so part of the reasoning below is
                missing. Everything that was recorded properly is shown in full — we don’t fill a gap by
                recalculating it now, because that would show you a decision we never actually made.
              </Text>
            </Card>
          ) : null}

          {trace.contested ? (
            <Card style={{ backgroundColor: colors.warningSoft, borderColor: colors.warningSoft }}>
              <Text variant="caption" tone="warning">
                You flagged this decision as “{CONTEST_REASON_LABEL[trace.contest_reason_code ?? ''] ??
                  trace.contest_reason_code}”. It stays on your record and feeds the personalization
                loop.
              </Text>
            </Card>
          ) : null}

          {/* One card per reasoning section, so a single missing field costs the
              reader that block and not the whole trace. Every row is the server's
              own plain-English rendering — the underlying record is still on the
              payload and in the event log for anyone auditing it, but a screen a
              person reads is not the place to dump it. */}
          {(trace.sections ?? []).map((section) => (
            <Card key={section.key}>
              <SectionHeader
                title={section.title}
                subtitle={
                  section.available
                    ? section.summary ?? undefined
                    : 'Some of this wasn’t recorded, so we’re not writing it up as if it were'
                }
              />
              {section.available ? (
                <FactList facts={section.facts} />
              ) : (
                <Text variant="body" tone="warning" style={styles.missing}>
                  We didn’t record {joinLabels(section.missing_field_labels ?? section.missing_fields ?? [])}{' '}
                  for this decision, so we can’t show you this part of the reasoning. We’d rather leave a
                  gap than fill it in after the fact.
                </Text>
              )}
            </Card>
          ))}

          <Card>
            <SectionHeader
              title="This decision over time"
              subtitle="Every version of this decision is kept, so you can see what changed and when"
            />
            <View style={styles.actions}>
              <Button
                label="View history"
                variant="secondary"
                onPress={() => navigation.navigate('TransparencyHistory', { moduleSource: params.moduleSource })}
              />
            </View>
          </Card>

          {!trace.contested ? (
            <Card>
              <SectionHeader title="Does this look wrong?" subtitle="Flag it and we’ll keep your objection on the record" />
              {contestOpen ? (
                <ContestForm moduleSource={params.moduleSource} eventId={trace.event_id} onDone={() => setContestOpen(false)} />
              ) : (
                <View style={styles.actions}>
                  <Button label="Flag this decision" variant="ghost" onPress={() => setContestOpen(true)} />
                </View>
              )}
            </Card>
          ) : null}
        </>
      )}
    </ScreenContainer>
  );
}

// --------------------------------------------------------------------------
// risk_profile_ml specialized view
// --------------------------------------------------------------------------

const TIER_TONE: Record<number, 'petrol' | 'positive' | 'warning' | 'terracotta'> = {
  1: 'petrol',
  2: 'petrol',
  3: 'positive',
  4: 'warning',
  5: 'terracotta',
};
const TIER_SOFT_KEY: Record<number, 'petrolSoft' | 'positiveSoft' | 'warningSoft' | 'terracottaSoft'> = {
  1: 'petrolSoft',
  2: 'petrolSoft',
  3: 'positiveSoft',
  4: 'warningSoft',
  5: 'terracottaSoft',
};
const TOTAL_QUESTIONS = 7;

/** A circular gauge for the model's confidence in its predicted tier --
 * reuses DonutChart's existing single-segment stroke-dashoffset draw-on
 * animation (the same primitive Allocation's target-mix ring uses) rather
 * than building a second animated-ring implementation, with the percentage
 * overlaid in the center. */
function ConfidenceGauge({ fraction, color, trackColor }: { fraction: number; color: string; trackColor: string }) {
  const pct = Math.round(fraction * 100);
  return (
    <View style={styles.gauge}>
      <DonutChart segments={[{ key: 'confidence', pct: fraction * 100, color }]} trackColor={trackColor} size={132} strokeWidth={14} />
      <View style={styles.gaugeCenter} pointerEvents="none">
        <Text variant="figureLarge">{pct}%</Text>
        <Text variant="caption" tone="faint">
          confidence
        </Text>
      </View>
    </View>
  );
}

/** One factor as a compact card: the question, the user's own answer in a
 * subtle tag, and a direction badge with a one-time pop-in (not continuous
 * motion) on its arrow -- replacing a FactList row's single run-on
 * sentence ("You answered X — this pushed your tier up") with the same
 * information split into scannable pieces. */
function FactorCard({ index, contribution }: { index: number; contribution: MLFeatureContributionOut }) {
  const { colors } = useAppTheme();
  const reducedMotion = useReducedMotion();
  const badgeScale = useRef(new Animated.Value(reducedMotion ? 1 : 0)).current;

  useEffect(() => {
    if (reducedMotion) {
      badgeScale.setValue(1);
      return;
    }
    const animation = Animated.spring(badgeScale, {
      toValue: 1,
      useNativeDriver: true,
      speed: 16,
      bounciness: 10,
      delay: Math.min(index, 6) * 60,
    });
    animation.start();
    return () => animation.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reducedMotion]);

  const isUp = contribution.direction === 'increases';
  const isDown = contribution.direction === 'decreases';
  const tone = isUp ? 'positive' : isDown ? 'terracotta' : 'faint';
  const badgeBg = isUp ? colors.positiveSoft : isDown ? colors.terracottaSoft : colors.paperSunken;
  const badgeFg = isUp ? colors.positive : isDown ? colors.terracotta : colors.inkFaint;
  const icon = isUp ? 'arrow-up' : isDown ? 'arrow-down' : 'remove';
  const label = isUp ? 'Pushed tier up' : isDown ? 'Pulled tier down' : 'No real difference';

  return (
    <Reveal index={index}>
      <Card style={styles.factorCard}>
        <Text variant="bodyMedium" style={styles.factorQuestion}>
          {contribution.question_text}
        </Text>
        <View style={[styles.answerTag, { backgroundColor: colors.paperSunken }]}>
          <Text variant="caption" tone="muted">
            {contribution.answer_label}
          </Text>
        </View>
        <Animated.View style={[styles.impactBadge, { backgroundColor: badgeBg, transform: [{ scale: badgeScale }] }]}>
          <Ionicons name={icon} size={14} color={badgeFg} />
          <Text variant="caption" tone={tone}>
            {label}
          </Text>
        </Animated.View>
      </Card>
    </Reveal>
  );
}

function RiskMlTrace({
  trace,
  navigation,
  contestOpen,
  onToggleContest,
}: {
  trace: TraceResultOut;
  navigation: Nav;
  contestOpen: boolean;
  onToggleContest: () => void;
}) {
  const { colors } = useAppTheme();
  const section = trace.reasoning.ml_prediction as MLPredictionSectionOut | undefined;

  if (!section) {
    // Gap-detected / missing data -- fall back to the same generic,
    // honest "can't show this" treatment every other decision type uses,
    // rather than rendering a hero banner around numbers that aren't there.
    return (
      <Card style={{ backgroundColor: colors.warningSoft, borderColor: colors.warningSoft }}>
        <Text variant="bodyMedium" tone="warning">
          Part of this decision wasn’t recorded at the time, so the prediction details below are
          missing.
        </Text>
      </Card>
    );
  }

  const answeredCount = section.feature_contributions.length;
  const complete = answeredCount >= TOTAL_QUESTIONS;
  const tierTone = TIER_TONE[section.predicted_tier] ?? 'petrol';
  const tierSoftKey = TIER_SOFT_KEY[section.predicted_tier] ?? 'petrolSoft';
  const confidenceFraction = section.class_probabilities[String(section.predicted_tier)] ?? 0;
  const rankedFactors = [...section.feature_contributions].sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value));

  return (
    <>
      <Reveal index={0}>
        <Card raised style={styles.heroCard}>
          <View style={styles.heroTopRow}>
            <View style={[styles.tierBadge, { backgroundColor: colors[tierSoftKey] }]}>
              <Text variant="label" tone={tierTone}>
                {section.predicted_tier_label.toUpperCase()}
              </Text>
            </View>
            <View style={[styles.progressChip, { backgroundColor: complete ? colors.positiveSoft : colors.warningSoft }]}>
              <Ionicons
                name={complete ? 'checkmark-circle' : 'ellipse-outline'}
                size={14}
                color={complete ? colors.positive : colors.warning}
              />
              <Text variant="caption" tone={complete ? 'positive' : 'warning'}>
                {answeredCount} of {TOTAL_QUESTIONS} questions{complete ? '' : ' · incomplete'}
              </Text>
            </View>
          </View>

          <ConfidenceGauge fraction={confidenceFraction} color={colors[tierTone]} trackColor={colors.paperSunken} />

          <Text variant="body" tone="muted" style={styles.heroHeadline}>
            {trace.headline}
          </Text>
          {trace.claim_note ? (
            <Text variant="caption" tone="faint" style={styles.heroClaimNote}>
              {trace.claim_note}
            </Text>
          ) : null}

          {!complete ? (
            <Button
              label="Answer remaining 3 questions"
              fullWidth
              onPress={() => navigation.navigate('PlanTab', { screen: 'RiskQuestionnaire' })}
            />
          ) : null}
        </Card>
      </Reveal>

      {trace.gap_detected ? (
        <Reveal index={1}>
          <Card style={{ backgroundColor: colors.warningSoft, borderColor: colors.warningSoft }}>
            <Text variant="bodyMedium" tone="warning">
              Part of this decision wasn’t recorded at the time, so part of the reasoning below is
              missing. Everything that was recorded properly is shown in full.
            </Text>
          </Card>
        </Reveal>
      ) : null}

      {trace.contested ? (
        <Reveal index={2}>
          <Card style={{ backgroundColor: colors.warningSoft, borderColor: colors.warningSoft }}>
            <Text variant="caption" tone="warning">
              You flagged this decision as “{CONTEST_REASON_LABEL[trace.contest_reason_code ?? ''] ??
                trace.contest_reason_code}”. It stays on your record and feeds the personalization loop.
            </Text>
          </Card>
        </Reveal>
      ) : null}

      <View style={styles.factorSection}>
        <SectionHeader title="What moved this prediction" subtitle="Ranked by how much each answer actually mattered" />
        {rankedFactors.map((c, i) => (
          <FactorCard key={c.question_id} index={i} contribution={c} />
        ))}
      </View>

      <Reveal index={3}>
        <Card>
          <SectionHeader title="More about this decision" />
          <View style={styles.footerGrid}>
            <Pressable
              style={[styles.footerTile, { borderColor: colors.border }]}
              accessibilityRole="button"
              accessibilityLabel="View history"
              onPress={() => navigation.navigate('TransparencyHistory', { moduleSource: 'risk_profile_ml' })}
            >
              <Ionicons name="time-outline" size={22} color={colors.petrol} />
              <Text variant="bodyMedium">View history</Text>
            </Pressable>
            {trace.contested ? (
              <View style={[styles.footerTile, { borderColor: colors.border }]}>
                <Ionicons name="flag" size={22} color={colors.warning} />
                <Text variant="bodyMedium" tone="warning">
                  Flagged
                </Text>
              </View>
            ) : (
              <Pressable
                style={[styles.footerTile, { borderColor: colors.border }]}
                accessibilityRole="button"
                accessibilityLabel="Flag decision"
                accessibilityState={{ expanded: contestOpen }}
                onPress={onToggleContest}
              >
                <Ionicons name="flag-outline" size={22} color={colors.terracotta} />
                <Text variant="bodyMedium" tone="terracotta">
                  Flag decision
                </Text>
              </Pressable>
            )}
          </View>
          {contestOpen && !trace.contested ? (
            <Reveal>
              <ContestForm moduleSource="risk_profile_ml" eventId={trace.event_id} onDone={onToggleContest} />
            </Reveal>
          ) : null}
        </Card>
      </Reveal>
    </>
  );
}

// --------------------------------------------------------------------------
// Shared: contest form
// --------------------------------------------------------------------------

/** Lets the reader push back on what they just read. Without it a trace is a
 * one-way mirror: the user can see the reasoning but has nowhere to say it's
 * wrong. Submissions go through Module 1's event log, which is where Module
 * 7's feedback loop already reads -- so an objection changes something
 * instead of dying on a read-only screen. Shared between the generic
 * trace's own collapsible card and the risk_profile_ml footer's "Flag
 * decision" tile, so both expand into the identical form. */
function ContestForm({
  moduleSource,
  eventId,
  onDone,
}: {
  moduleSource: Props['route']['params']['moduleSource'];
  eventId: string;
  onDone: () => void;
}) {
  const { data: reasons } = useContestReasons();
  const contest = useContestDecision(moduleSource);
  const [reasonCode, setReasonCode] = React.useState<string | null>(null);
  const [note, setNote] = React.useState('');

  return (
    <View style={styles.contestForm}>
      <SectionHeader title="What’s wrong with it?" subtitle="Pick the closest reason" />
      <View style={styles.reasons}>
        {(reasons ?? []).map((code) => {
          const selected = reasonCode === code;
          return (
            <Button
              key={code}
              label={CONTEST_REASON_LABEL[code] ?? code}
              variant={selected ? 'primary' : 'ghost'}
              onPress={() => setReasonCode(code)}
            />
          );
        })}
      </View>

      <TextField
        label="Anything else? (optional)"
        value={note}
        onChangeText={setNote}
        placeholder="e.g. my emergency buffer is larger than this shows"
        multiline
      />

      {contest.isError ? <InlineError message="Could not record that. Try again." /> : null}
      {contest.isSuccess ? (
        <Text variant="caption" tone="petrol">
          Recorded. Thanks — this feeds back into how your plan is personalized.
        </Text>
      ) : null}

      <View style={styles.actions}>
        <Button
          label="Submit"
          loading={contest.isPending}
          disabled={!reasonCode}
          onPress={() => contest.mutate({ eventId, reasonCode: reasonCode!, note: note.trim() || undefined })}
        />
        <Button label="Cancel" variant="ghost" onPress={onDone} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: { alignSelf: 'flex-start', paddingHorizontal: SPACE.sm, paddingVertical: 4, borderRadius: 6, marginBottom: SPACE.sm },
  title: { marginTop: 2 },
  missing: { marginTop: SPACE.sm },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.sm, marginTop: SPACE.sm },
  reasons: { gap: SPACE.xs, marginTop: SPACE.sm, marginBottom: SPACE.sm },
  contestForm: { marginTop: SPACE.md, paddingTop: SPACE.md, borderTopWidth: StyleSheet.hairlineWidth, gap: SPACE.sm },

  heroCard: { alignItems: 'center', gap: SPACE.md },
  heroTopRow: { flexDirection: 'row', alignSelf: 'stretch', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: SPACE.xs },
  tierBadge: { paddingHorizontal: SPACE.md, paddingVertical: SPACE.xs, borderRadius: RADIUS.pill },
  progressChip: { flexDirection: 'row', alignItems: 'center', gap: SPACE.xs, paddingHorizontal: SPACE.sm, paddingVertical: 4, borderRadius: RADIUS.pill },
  gauge: { width: 132, height: 132, alignItems: 'center', justifyContent: 'center' },
  gaugeCenter: { position: 'absolute', alignItems: 'center' },
  heroHeadline: { textAlign: 'center' },
  heroClaimNote: { textAlign: 'center' },

  factorSection: { gap: SPACE.sm },
  factorCard: { gap: SPACE.sm },
  factorQuestion: {},
  answerTag: { alignSelf: 'flex-start', paddingHorizontal: SPACE.sm, paddingVertical: 4, borderRadius: RADIUS.sm },
  impactBadge: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: SPACE.xs, paddingHorizontal: SPACE.sm, paddingVertical: 4, borderRadius: RADIUS.pill },

  footerGrid: { flexDirection: 'row', gap: SPACE.sm, marginTop: SPACE.sm },
  footerTile: {
    flex: 1,
    alignItems: 'center',
    gap: SPACE.xs,
    paddingVertical: SPACE.md,
    borderRadius: RADIUS.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
  },
});
