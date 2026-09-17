import { useMutation } from '@tanstack/react-query';
import React, { useState } from 'react';
import { Linking, StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { rumourVerificationApi } from '../../api/rumourVerification';
import type {
  LocalRumourVerificationOut,
  RumourVerificationOut,
  RumourStatus,
} from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { InlineError } from '../../components/InlineError';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { useDemoUser } from '../../context/DemoUserContext';
import { useAppTheme } from '../../theme/ThemeContext';
import { SPACE } from '../../theme/tokens';

const STATUS_LABEL: Record<RumourStatus, string> = {
  confirmed: 'Confirmed',
  denied: 'Denied',
  unaddressed: 'Unaddressed',
  not_yet_due: 'Not yet due',
};

const STATUS_TONE: Record<RumourStatus, 'petrol' | 'warning' | 'muted'> = {
  confirmed: 'petrol',
  denied: 'petrol',
  unaddressed: 'warning',
  not_yet_due: 'muted',
};

function StatusBadge({ status }: { status: RumourStatus }) {
  const { colors } = useAppTheme();
  const tone = STATUS_TONE[status];
  const bg = tone === 'petrol' ? colors.petrolSoft : tone === 'warning' ? colors.warningSoft : colors.paperSunken;
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <Text variant="label" tone={tone}>
        {STATUS_LABEL[status].toUpperCase()}
      </Text>
    </View>
  );
}

export function RumourVerificationScreen() {
  const { userId } = useDemoUser();
  const { colors } = useAppTheme();

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

  /** The explainable path. Kept as its own call and its own result type so
   * neither engine's output can ever be rendered under the other's label --
   * only this one can name the constraint that ruled out each candidate. */
  const explainMutation = useMutation({
    mutationFn: () => rumourVerificationApi.explain(userId, body()),
    onSuccess: (data) => setExplanation(data),
    onError: (err) => setSubmitError(toApiError(err).message),
  });

  const dateValid = rumourDate.trim() === '' || /^\d{4}-\d{2}-\d{2}$/.test(rumourDate.trim());

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Verify
        </Text>
        <Text variant="display">Rumour verification</Text>
      </View>

      <Card style={{ backgroundColor: colors.petrolSoft, borderColor: colors.petrolSoft }}>
        <Text variant="bodyMedium" tone="petrol">
          This tool verifies a rumour you provide. It does not monitor social media or detect rumours
          automatically.
        </Text>
      </Card>

      <Card style={styles.formCard}>
        <TextField
          label="Rumour"
          value={rumourText}
          onChangeText={setRumourText}
          placeholder="Paste or type the rumour you've heard, as close to the original wording as possible..."
          multiline
        />
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

        {submitError ? <InlineError message={submitError} /> : null}

        <Button
          label="Check against filings, and show the working"
          fullWidth
          loading={explainMutation.isPending}
          disabled={!rumourText.trim() || !dateValid}
          onPress={() => {
            clear();
            explainMutation.mutate();
          }}
        />
        <Text variant="caption" tone="faint">
          Searches our corpus of exchange filings and shows every candidate it considered, including
          the ones it ruled out and why.
        </Text>

        <Button
          label="Search wider (external workflow)"
          variant="ghost"
          fullWidth
          loading={mutation.isPending}
          disabled={!rumourText.trim() || !dateValid}
          onPress={() => {
            clear();
            mutation.mutate();
          }}
        />
        <Text variant="caption" tone="faint">
          Not limited to our corpus, but it returns its own written rationale rather than a list of
          candidates we can check — so there is no ruled-out list to show you.
        </Text>
      </Card>

      {explanation ? <ExplanationCard explanation={explanation} /> : null}
      {result ? <ResultCard result={result} /> : null}
    </ScreenContainer>
  );
}

const CONSTRAINT_LABEL: Record<string, string> = {
  entity: 'Wrong company',
  temporal: 'Outside the response window',
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
    <>
      <Card style={{ backgroundColor: colors.petrolSoft, borderColor: colors.petrolSoft }}>
        <Text variant="label" tone="petrol">
          {explanation.framing_label.toUpperCase()}
        </Text>
        <Text variant="caption" tone="petrol" style={styles.spaced}>
          {explanation.claim_note}
        </Text>
      </Card>

      {explanation.matched_filing && explanation.status ? (
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
          <SectionHeader title="No confident match found" />
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
          <Button
            label={`Show all ${eliminated.length}`}
            variant="ghost"
            onPress={() => setShowAll(true)}
          />
        ) : null}
      </Card>
    </>
  );
}

function ResultCard({ result }: { result: RumourVerificationOut }) {
  const { colors } = useAppTheme();

  if (!result.matched_filing || !result.status) {
    return (
      <Card>
        <SectionHeader title="No confident match found" />
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

  return (
    <Card>
      <View style={styles.resultHeader}>
        <SectionHeader title={filing.company_name} />
        <StatusBadge status={result.status} />
      </View>

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
        <Text variant="figure">{filing.source_authority}</Text>
      </View>
      {filing.determination ? (
        <View style={styles.metricRow}>
          <Text variant="caption" tone="muted">
            Filing says
          </Text>
          <Text variant="figure">{filing.determination.replace('_', ' ')}</Text>
        </View>
      ) : null}
      <View style={styles.metricRow}>
        <Text variant="caption" tone="muted">
          Match similarity
        </Text>
        <Text variant="figure">{result.matched_score?.toFixed(3)}</Text>
      </View>

      {filing.source_url ? (
        <Button
          label="View source filing"
          variant="ghost"
          onPress={() => Linking.openURL(filing.source_url!)}
        />
      ) : null}

      {result.top_candidate_reasons.length > 0 ? (
        <Card style={{ backgroundColor: colors.paperSunken, borderColor: colors.border, marginTop: SPACE.sm }}>
          <Text variant="caption" tone="muted">
            WHAT THE EXTERNAL WORKFLOW REPORTED
          </Text>
          <Text variant="caption" tone="faint">
            This is the workflow's own written rationale. It is not a record of which candidates were
            ruled out, or why — for that, use “show the working” above.
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
  formCard: { gap: SPACE.md },
  badge: { paddingHorizontal: SPACE.sm, paddingVertical: 4, borderRadius: 6, alignSelf: 'flex-start' },
  resultHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: SPACE.md },
  metricRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: SPACE.xs },
  spaced: { marginTop: SPACE.sm },
  reasonsList: { marginTop: SPACE.sm, gap: 2 },
  reasonItem: { lineHeight: 18 },
  candidate: { paddingTop: SPACE.sm, marginTop: SPACE.sm, borderTopWidth: StyleSheet.hairlineWidth * 1.5 },
});
