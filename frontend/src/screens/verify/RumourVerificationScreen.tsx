import { useMutation } from '@tanstack/react-query';
import React, { useState } from 'react';
import { Linking, StyleSheet, View } from 'react-native';
import { toApiError } from '../../api/client';
import { rumourVerificationApi } from '../../api/rumourVerification';
import type { RumourVerificationOut, RumourStatus } from '../../api/types';
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

  const mutation = useMutation({
    mutationFn: () =>
      rumourVerificationApi.verify(userId, {
        rumour_text: rumourText.trim(),
        rumour_date: rumourDate.trim() || null,
        company_name: companyName.trim() || null,
      }),
    onSuccess: (data) => setResult(data),
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
          label="Verify this rumour"
          fullWidth
          loading={mutation.isPending}
          disabled={!rumourText.trim() || !dateValid}
          onPress={() => {
            setSubmitError(null);
            mutation.mutate();
          }}
        />
      </Card>

      {result ? <ResultCard result={result} /> : null}
    </ScreenContainer>
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
            WHY THIS FILING RANKED FIRST
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
});
