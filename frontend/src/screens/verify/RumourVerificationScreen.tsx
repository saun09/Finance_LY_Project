import { Ionicons } from '@expo/vector-icons';
import { useMutation } from '@tanstack/react-query';
import { LinearGradient } from 'expo-linear-gradient';
import React, { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Animated, Pressable, StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { rumourVerificationApi } from '../../api/rumourVerification';
import type { LocalRumourVerificationOut, RumourVerificationOut, RumourStatus } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { IconChip } from '../../components/IconChip';
import { InfoTooltip } from '../../components/InfoTooltip';
import { InlineError } from '../../components/InlineError';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { useDemoUser } from '../../context/DemoUserContext';
import { useReducedMotion } from '../../hooks/useReducedMotion';
import { useRumourEngines } from '../../hooks/useRumourVerification';
import { useAppTheme } from '../../theme/ThemeContext';
import { Palette, RADIUS, SPACE } from '../../theme/tokens';

type IconName = keyof typeof Ionicons.glyphMap;
type Mode = 'filings' | 'broader';
type Tone = 'positive' | 'danger' | 'warning' | 'neutral' | 'petrol';

// Mirrors backend/app/services/rumour_local_engine.py::ENGINE_NAME and
// rumour_verification_bridge.py::N8N_ENGINE_NAME exactly -- used only to
// read `available`/`description` back off GET /engines for the badge and
// the mode-details popover, never to decide which endpoint to call (that's
// still hardcoded per mode below, same as the two separate API client
// methods already keep the two engines from being conflated).
const LOCAL_ENGINE = 'local_constrained_retrieval';
const N8N_ENGINE = 'n8n_llm_workflow';

const MODE_META: Record<Mode, { title: string; subtitle: string; icon: IconName; tone: 'petrol' | 'warning' }> = {
  filings: {
    title: 'Exchange Filings',
    subtitle: 'Deterministic — checks official disclosures with a full proof chain',
    icon: 'shield-checkmark-outline',
    tone: 'petrol',
  },
  broader: {
    title: 'Broader Workflow',
    subtitle: 'External, self-reported — wider reach, but no candidate list we can verify',
    icon: 'globe-outline',
    tone: 'warning',
  },
};

// A handful of real rumours from the research corpus
// (modules/rumour_verification/data/rumour_dataset.json) -- never invented
// examples, so clicking a chip and verifying actually produces a genuine,
// checkable result instead of a fabricated demo.
const SAMPLE_RUMOURS: { company: string; date: string; text: string }[] = [
  { company: 'Adani Enterprises Ltd', date: '2025-02-11', text: 'Adani Enterprises shares rally 4% on $686 million investment in not-for-profit healthcare initiative' },
  { company: 'Gensol Engineering Ltd', date: '2026-07-13', text: "IREDA has declared Gensol Engineering's ~Rs 673 crore loan accounts as fraud and reported the matter to the RBI" },
  { company: 'Ola Electric Mobility Ltd', date: '2025-05-02', text: 'Ola Electric Likely In SEBI Crosshairs Over Alleged Insider Trading' },
  { company: 'One97 Communications Ltd', date: '2024-05-28', text: 'Adani Group is in talks to acquire a stake in One97 Communications (Paytm)' },
  { company: 'IndusInd Bank Ltd', date: '2025-12-03', text: 'Hinduja Group is seeking a strategic partner to hold a minority stake in IndusInd Bank' },
];

const PILL_BG: Record<Tone, keyof Palette> = {
  positive: 'positiveSoft',
  danger: 'dangerSoft',
  warning: 'warningSoft',
  neutral: 'paperSunken',
  petrol: 'petrolSoft',
};
const PILL_TEXT: Record<Tone, React.ComponentProps<typeof Text>['tone']> = {
  positive: 'positive',
  danger: 'danger',
  warning: 'warning',
  neutral: 'muted',
  petrol: 'petrol',
};

const STATUS_MEANING: Record<string, string> = {
  confirmed: 'The company has officially confirmed this is true.',
  denied: 'The company has officially denied this.',
  not_yet_due: "The company's response window under SEBI's rumour-verification rule hasn't elapsed yet.",
  unaddressed: "The response window has passed and the company hasn't filed a substantive confirm or deny.",
};

const DETERMINATION_LABEL: Record<string, string> = {
  confirms: 'Confirms the rumour',
  denies: 'Denies the rumour',
  non_committal: 'Neither confirms nor denies',
};

const FILINGS_STEPS = [
  'Querying the local exchange filing archive…',
  'Running entity, timing & source checks…',
  'Building the audit trail…',
];
const BROADER_STEPS = [
  "Sending the claim to the external workflow…",
  "Waiting on the workflow's analysis…",
  'Compiling the verdict & rationale…',
];

interface Verdict {
  label: string;
  tone: Tone;
  icon: IconName;
}

function verdictFor(matchedFiling: unknown, status: RumourStatus | null): Verdict {
  if (!matchedFiling) return { label: 'NO MATCHING FILING', tone: 'danger', icon: 'close-circle' };
  switch (status) {
    case 'confirmed':
      return { label: 'VERIFIED BY FILING', tone: 'positive', icon: 'checkmark-circle' };
    case 'denied':
      return { label: 'REFUTED BY FILING', tone: 'danger', icon: 'close-circle' };
    case 'not_yet_due':
      return { label: 'AWAITING RESPONSE', tone: 'warning', icon: 'time-outline' };
    case 'unaddressed':
      return { label: 'UNCONFIRMED — NO RESPONSE FILED', tone: 'warning', icon: 'help-circle-outline' };
    default:
      return { label: 'MATCH FOUND — TIMING UNKNOWN', tone: 'neutral', icon: 'information-circle-outline' };
  }
}

function VerdictBanner({ verdict }: { verdict: Verdict }) {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.verdictBanner, { backgroundColor: colors[PILL_BG[verdict.tone]] }]}>
      <Ionicons name={verdict.icon} size={20} color={colors[verdict.tone === 'neutral' ? 'inkMuted' : verdict.tone]} />
      <Text variant="label" tone={PILL_TEXT[verdict.tone]} style={styles.verdictLabel}>
        {verdict.label}
      </Text>
    </View>
  );
}

/** A fake-but-honest step sequence: the first two steps advance on a fixed
 * timer (a brief flourish), the last stays "in progress" until the real
 * network response actually arrives -- never claims step 3 finished before
 * it did, which matters most for the broader-workflow mode (up to a 60s
 * real wait per rumourVerificationApi.verify's own timeout comment). */
function useScanningStep(active: boolean): number {
  const [step, setStep] = useState(0);
  useEffect(() => {
    if (!active) {
      setStep(0);
      return;
    }
    const t1 = setTimeout(() => setStep(1), 900);
    const t2 = setTimeout(() => setStep(2), 2100);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [active]);
  return step;
}

function ScanningCard({ mode }: { mode: Mode }) {
  const { colors } = useAppTheme();
  const reducedMotion = useReducedMotion();
  const step = useScanningStep(true);
  const labels = mode === 'filings' ? FILINGS_STEPS : BROADER_STEPS;
  const spin = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (reducedMotion) return;
    const loop = Animated.loop(Animated.timing(spin, { toValue: 1, duration: 1400, useNativeDriver: true }));
    loop.start();
    return () => loop.stop();
  }, [spin, reducedMotion]);

  const rotate = spin.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });

  return (
    <Card style={styles.scanCard}>
      <View style={styles.scanHeader}>
        {!reducedMotion ? (
          <Animated.View style={{ transform: [{ rotate }] }}>
            <Ionicons name="radio-outline" size={22} color={colors.petrol} />
          </Animated.View>
        ) : (
          <Ionicons name="radio-outline" size={22} color={colors.petrol} />
        )}
        <Text variant="h2">Verifying…</Text>
      </View>
      <View style={styles.scanList}>
        {labels.map((label, i) => {
          const done = i < step;
          const current = i === step;
          return (
            <View key={label} style={styles.scanRow}>
              {done ? (
                <Ionicons name="checkmark-circle" size={18} color={colors.positive} />
              ) : current ? (
                <ActivityIndicator size="small" color={colors.petrol} />
              ) : (
                <Ionicons name="ellipse-outline" size={18} color={colors.inkFaint} />
              )}
              <Text variant="caption" tone={done || current ? 'muted' : 'faint'} style={styles.scanLabel}>
                {i + 1}/3 {label}
              </Text>
            </View>
          );
        })}
      </View>
    </Card>
  );
}

function ModeCard({ mode, selected, onPress }: { mode: Mode; selected: boolean; onPress: () => void }) {
  const { colors } = useAppTheme();
  const meta = MODE_META[mode];
  const scale = useRef(new Animated.Value(1)).current;
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (reducedMotion) {
      scale.setValue(selected ? 1.02 : 1);
      return;
    }
    Animated.spring(scale, { toValue: selected ? 1.02 : 1, useNativeDriver: true, speed: 20, bounciness: 6 }).start();
  }, [selected, reducedMotion, scale]);

  const softKey = meta.tone === 'petrol' ? 'petrolSoft' : 'warningSoft';

  return (
    <Animated.View style={{ transform: [{ scale }] }}>
      <Pressable
        onPress={onPress}
        accessibilityRole="radio"
        accessibilityState={{ selected }}
        style={[
          styles.modeCard,
          {
            backgroundColor: selected ? colors[softKey] : colors.paperRaised,
            borderColor: selected ? colors[meta.tone] : colors.border,
          },
        ]}
      >
        <IconChip name={meta.icon} tone={meta.tone} size={32} />
        <View style={styles.modeCardText}>
          <Text variant="bodyMedium">{meta.title}</Text>
          <Text variant="caption" tone="muted">
            {meta.subtitle}
          </Text>
        </View>
        <Ionicons
          name={selected ? 'radio-button-on' : 'radio-button-off'}
          size={20}
          color={selected ? colors[meta.tone] : colors.inkFaint}
        />
      </Pressable>
    </Animated.View>
  );
}

export function RumourVerificationScreen() {
  const { userId } = useDemoUser();
  const { colors } = useAppTheme();
  const engines = useRumourEngines();

  const [mode, setMode] = useState<Mode>('filings');
  const [rumourText, setRumourText] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [rumourDate, setRumourDate] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<RumourVerificationOut | null>(null);
  const [explanation, setExplanation] = useState<LocalRumourVerificationOut | null>(null);

  const body = () => ({
    rumour_text: rumourText.trim(),
    rumour_date: rumourDate.trim() || null,
    company_name: companyName.trim() || null,
  });

  const clear = () => {
    setSubmitError(null);
    setResult(null);
    setExplanation(null);
  };

  const mutation = useMutation({
    mutationFn: () => rumourVerificationApi.verify(userId, body()),
    onSuccess: (data) => setResult(data),
    onError: (err) => setSubmitError(toApiError(err).message),
  });

  const explainMutation = useMutation({
    mutationFn: () => rumourVerificationApi.explain(userId, body()),
    onSuccess: (data) => setExplanation(data),
    onError: (err) => setSubmitError(toApiError(err).message),
  });

  const dateValid = rumourDate.trim() === '' || /^\d{4}-\d{2}-\d{2}$/.test(rumourDate.trim());
  const isPending = mode === 'filings' ? explainMutation.isPending : mutation.isPending;
  const localEngine = engines.data?.find((e) => e.engine === LOCAL_ENGINE);
  const n8nEngine = engines.data?.find((e) => e.engine === N8N_ENGINE);
  const localAvailable = localEngine?.available ?? true;

  const applySample = (sample: (typeof SAMPLE_RUMOURS)[number]) => {
    clear();
    setRumourText(sample.text);
    setCompanyName(sample.company);
    setRumourDate(sample.date);
  };

  const handleVerify = () => {
    clear();
    if (mode === 'filings') explainMutation.mutate();
    else mutation.mutate();
  };

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Verify
        </Text>
        <Text variant="display" style={styles.title}> Rumour Fact-Checker</Text>
      </View>

     

      <Card style={styles.formCard}>
          <TextField
            label="The rumour"
            value={rumourText}
            onChangeText={setRumourText}
            placeholder="Paste or type the rumour you've heard, as close to the original wording as possible…"
            multiline
            focusGlow
          />

          <View style={styles.chipsWrap}>
            {SAMPLE_RUMOURS.map((sample) => (
              <Pressable
                key={sample.company + sample.date}
                onPress={() => applySample(sample)}
                style={[styles.chip, { borderColor: colors.border, backgroundColor: colors.paper }]}
              >
                <Text variant="caption" tone="muted" numberOfLines={1} style={styles.chipText}>
                  {sample.company.replace(/ Ltd$/, '')}
                </Text>
              </Pressable>
            ))}
          </View>

          <TextField
            label="Company (optional)"
            value={companyName}
            onChangeText={setCompanyName}
            placeholder="e.g. Adani Enterprises"
            helperText="Helps narrow the match if the rumour doesn't clearly name a company."
          />
          <TextField
            label="Date you heard it (optional)"
            value={rumourDate}
            onChangeText={setRumourDate}
            placeholder="YYYY-MM-DD"
            helperText="Used to check whether the company's response window has elapsed."
            error={!dateValid ? 'Use the format YYYY-MM-DD.' : undefined}
          />
      </Card>

      <Card style={styles.modeSection}>
        <View style={styles.modeHeaderRow}>
          <Text variant="label" tone="muted">
            SEARCH MODE
          </Text>
          <InfoTooltip
            label="Search mode details"
            title="How each search mode works"
            description={[localEngine?.description, n8nEngine?.description].filter(Boolean).join('\n\n') ||
              'Exchange Filings checks our fixed archive of real official disclosures and can show every candidate it ruled out. Broader Workflow is not limited to that archive, but returns its own written verdict with no checkable candidate list.'}
          />
        </View>
        <ModeCard mode="filings" selected={mode === 'filings'} onPress={() => setMode('filings')} />
        <ModeCard mode="broader" selected={mode === 'broader'} onPress={() => setMode('broader')} />

        {submitError ? <InlineError message={submitError} /> : null}

        <Button
          label="Verify rumour"
          fullWidth
          loading={isPending}
          disabled={!rumourText.trim() || !dateValid}
          onPress={handleVerify}
        />
      </Card>

      {isPending ? <ScanningCard mode={mode} /> : null}
      {explanation ? <ExplanationCard explanation={explanation} /> : null}
      {result ? <ResultCard result={result} /> : null}
    </ScreenContainer>
  );
}

/** Mirrors backend/app/services/transparency_labels.py::RETRIEVAL_CHECK_LABEL
 * exactly, so a reason reads identically here and on the transparency trace
 * for the same verification. */
const CONSTRAINT_LABEL: Record<string, string> = {
  entity: 'Different company',
  temporal: 'Filed outside the response window',
  source_authority: 'Not an official exchange filing',
  score_floor: 'Too dissimilar to the rumour',
};

/**
 * Module 5's constraint-elimination trace, as shown to the user.
 *
 * This is the one place in the app that makes a genuine explainability
 * claim, and it earns it by showing the losers: every filing the retriever
 * considered, and for each one it rejected, which of the four checks ruled
 * it out. A view that only justified the winner would be a rationalization,
 * not an explanation.
 */
function ExplanationCard({ explanation }: { explanation: LocalRumourVerificationOut }) {
  const { colors } = useAppTheme();
  const [showAll, setShowAll] = useState(false);

  const eliminated = explanation.candidate_explanations.filter((c) => !c.is_winner);
  const shown = showAll ? eliminated : eliminated.slice(0, 5);

  return (
    <View style={styles.resultsGroup}>
      <Card style={{ backgroundColor: colors.petrolSoft, borderColor: colors.petrolSoft }}>
        <Text variant="label" tone="petrol">
          {explanation.framing_label.toUpperCase()}
        </Text>
        <Text variant="caption" tone="petrol" style={styles.spaced}>
          {explanation.claim_note}
        </Text>
      </Card>

      {explanation.matched_filing ? (
        <ResultCard
          result={{
            query_text: explanation.query_text,
            rumour_date: explanation.rumour_date,
            status: explanation.status as RumourStatus,
            matched_score: explanation.matched_score,
            matched_filing: explanation.matched_filing,
            candidates_considered: explanation.candidates_considered,
            candidates_passing: explanation.candidates_passing,
            top_candidate_reasons: [],
            logged_event_id: explanation.logged_event_id,
            engine: explanation.engine,
            framing_label: explanation.framing_label,
          }}
        />
      ) : (
        <Card>
          <View style={styles.resultHeader}>
            <SectionHeader title="No confident match found" />
            <VerdictBanner verdict={verdictFor(null, null)} />
          </View>
          <Text variant="body" tone="muted" style={styles.spaced}>
            {explanation.why_ranked_first}
          </Text>
        </Card>
      )}

      <Card>
        <SectionHeader
          title="Why this one"
          subtitle={`${explanation.candidates_considered} filings considered, ${explanation.candidates_eliminated} ruled out`}
        />
        <Text variant="body" style={styles.spaced}>
          {explanation.why_ranked_first}
        </Text>

        <View style={styles.reasonsList}>
          {Object.entries(explanation.eliminated_by_constraint).map(([constraint, count]) => (
            <Text key={constraint} variant="caption" tone="faint" style={styles.reasonItem}>
              • {CONSTRAINT_LABEL[constraint] ?? constraint}: ruled out {count} filing
              {count === 1 ? '' : 's'}
            </Text>
          ))}
        </View>
      </Card>

      <Card>
        <SectionHeader
          title="Every filing we ruled out"
          subtitle="Not just the one we picked — the rejected candidates and the check that rejected each"
        />
        {shown.map((candidate) => (
          <View key={candidate.filing_id} style={[styles.candidate, { borderTopColor: colors.border }]}>
            <View style={styles.resultHeader}>
              <Text variant="bodyMedium">{candidate.company_name}</Text>
              <Text variant="figure" tone="faint">
                {candidate.score.toFixed(3)}
              </Text>
            </View>
            <Text variant="caption" tone="faint">
              {candidate.filing_id} · {candidate.filing_date}
            </Text>
            <View style={styles.reasonsList}>
              {candidate.failed_constraints.map((constraint) => (
                <Text key={constraint} variant="caption" tone="warning" style={styles.reasonItem}>
                  ✕ {CONSTRAINT_LABEL[constraint] ?? constraint}
                </Text>
              ))}
              {candidate.reasons.map((reason, i) => (
                <Text key={i} variant="caption" tone="faint" style={styles.reasonItem}>
                  • {reason}
                </Text>
              ))}
            </View>
          </View>
        ))}

        {eliminated.length > shown.length ? (
          <Button label={`Show all ${eliminated.length}`} variant="ghost" onPress={() => setShowAll(true)} />
        ) : null}
      </Card>
    </View>
  );
}

function ResultCard({ result }: { result: RumourVerificationOut }) {
  const { colors } = useAppTheme();

  if (!result.matched_filing) {
    return (
      <Card>
        <View style={styles.resultHeader}>
          <SectionHeader title="No confident match found" />
          <VerdictBanner verdict={verdictFor(null, null)} />
        </View>
        <Text variant="body" tone="muted" style={styles.spaced}>
          Checked {result.candidates_considered} filing{result.candidates_considered === 1 ? '' : 's'}
          {result.candidates_passing > 0
            ? `, ${result.candidates_passing} passed initial checks but none reached a confident match.`
            : ' — none passed the entity, timing, and source-authority checks.'}
        </Text>
        {result.top_candidate_reasons.length > 0 ? (
          <View style={styles.reasonsList}>
            {result.top_candidate_reasons.map((reason, i) => (
              <Text key={i} variant="caption" tone="faint" style={styles.reasonItem}>
                • {reason}
              </Text>
            ))}
          </View>
        ) : null}
      </Card>
    );
  }

  const filing = result.matched_filing;
  const verdict = verdictFor(filing, result.status);

  return (
    <Card>
      <View style={styles.resultHeader}>
        <SectionHeader title={filing.company_name} />
        <VerdictBanner verdict={verdict} />
      </View>

      <Text variant="body" tone="muted" style={styles.spaced}>
        {result.status && STATUS_MEANING[result.status]
          ? STATUS_MEANING[result.status]
          : 'A matching filing was found, but without a rumour date we can’t classify whether the response window applies.'}
      </Text>

      <View style={styles.metricRow}>
        <Text variant="caption" tone="muted">
          Filing date
        </Text>
        <Text variant="figure">{filing.filing_date}</Text>
      </View>
      <View style={styles.metricRow}>
        <Text variant="caption" tone="muted">
          Filing type
        </Text>
        <Text variant="figure">{filing.filing_type}</Text>
      </View>
      <View style={styles.metricRow}>
        <Text variant="caption" tone="muted">
          Source
        </Text>
        <Text variant="figure">
          {filing.source_authority === 'official_exchange_filing' ? 'Official exchange filing' : 'News article'}
        </Text>
      </View>
      {filing.determination ? (
        <View style={styles.metricRow}>
          <Text variant="caption" tone="muted">
            Filing says
          </Text>
          <Text variant="figure">{DETERMINATION_LABEL[filing.determination] ?? filing.determination}</Text>
        </View>
      ) : null}
      <View style={styles.metricRow}>
        <Text variant="caption" tone="muted">
          How closely it matched
        </Text>
        <Text variant="figure">
          {result.matched_score != null ? `${Math.round(result.matched_score * 100)}% similar wording` : '—'}
        </Text>
      </View>

      {result.top_candidate_reasons.length > 0 ? (
        <Card style={{ backgroundColor: colors.paperSunken, borderColor: colors.border, marginTop: SPACE.sm }}>
          <Text variant="caption" tone="muted">
            WHAT THE EXTERNAL WORKFLOW REPORTED
          </Text>
          <Text variant="caption" tone="faint">
            This is the workflow's own written rationale. It is not a record of which candidates were
            ruled out, or why — for that, use Exchange Filings mode above.
          </Text>
          <View style={styles.reasonsList}>
            {result.top_candidate_reasons.map((reason, i) => (
              <Text key={i} variant="caption" tone="faint" style={styles.reasonItem}>
                • {reason}
              </Text>
            ))}
          </View>
        </Card>
      ) : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  title: { marginTop: SPACE.xs },
  heroCard: { gap: SPACE.sm, borderRadius: RADIUS.lg, borderWidth: StyleSheet.hairlineWidth * 1.5, padding: SPACE.lg },
  statusBadge: { flexDirection: 'row', alignItems: 'center', gap: SPACE.xs },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusLabel: { letterSpacing: 0.6 },
  heroCopy: {},
  formCard: { gap: SPACE.md },
  chipsWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.sm, marginTop: -SPACE.xs },
  chip: { paddingHorizontal: SPACE.md, paddingVertical: SPACE.xs, borderRadius: RADIUS.pill, borderWidth: StyleSheet.hairlineWidth * 1.5, maxWidth: 170 },
  chipText: {},
  modeSection: { gap: SPACE.sm },
  modeHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  modeCard: { flexDirection: 'row', alignItems: 'center', gap: SPACE.md, padding: SPACE.md, borderRadius: RADIUS.lg, borderWidth: StyleSheet.hairlineWidth * 1.5 },
  modeCardText: { flex: 1, gap: 2 },
  scanCard: { gap: SPACE.sm },
  scanHeader: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  scanList: { gap: SPACE.sm, marginTop: SPACE.xs },
  scanRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  scanLabel: { flex: 1 },
  resultsGroup: { gap: SPACE.lg },
  verdictBanner: { flexDirection: 'row', flexShrink: 0, alignItems: 'center', gap: SPACE.xs, paddingHorizontal: SPACE.md, paddingVertical: SPACE.sm, borderRadius: RADIUS.pill },
  verdictLabel: { letterSpacing: 0.4 },
  resultHeader: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'flex-start', gap: SPACE.sm },
  metricRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: SPACE.xs },
  spaced: { marginTop: SPACE.sm },
  reasonsList: { marginTop: SPACE.sm, gap: 2 },
  reasonItem: { lineHeight: 18 },
  candidate: { paddingTop: SPACE.sm, marginTop: SPACE.sm, borderTopWidth: StyleSheet.hairlineWidth * 1.5 },
});
