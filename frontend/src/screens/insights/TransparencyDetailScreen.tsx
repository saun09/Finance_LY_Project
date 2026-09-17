import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp, NativeStackScreenProps } from '@react-navigation/native-stack';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ErrorState } from '../../components/ErrorState';
import { InlineError } from '../../components/InlineError';
import { ReasoningTree } from '../../components/ReasoningTree';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { TextField } from '../../components/TextField';
import { useAppTheme } from '../../theme/ThemeContext';
import { useContestDecision, useContestReasons, useTransparencyTrace } from '../../hooks/useTransparency';
import { SPACE } from '../../theme/tokens';
import { CONTEST_REASON_LABEL } from '../../utils/labels';
import { asUnavailableSection } from '../../utils/traceValues';
import type { InsightsStackParamList } from '../../navigation/types';

type Props = NativeStackScreenProps<InsightsStackParamList, 'TransparencyDetail'>;
type Nav = NativeStackNavigationProp<InsightsStackParamList, 'TransparencyDetail'>;

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
            Part of this trace is incomplete — the stored decision is missing:{' '}
            {trace.missing_fields.join(', ')}. The sections that were recorded properly are shown in
            full below; only the affected ones are held back, rather than filling the gap with a
            freshly computed value.
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
          reader that block and not the whole trace. */}
      {trace.sections.map((section) => {
        const payload = (trace.reasoning as Record<string, unknown>)[section.key];
        const unavailable = asUnavailableSection(payload);
        return (
          <Card key={section.key}>
            <SectionHeader
              title={section.title}
              subtitle={
                section.available
                  ? 'Exactly what was stored when this decision was made'
                  : `Not fully recorded: ${section.missing_fields.join(', ')}`
              }
            />
            <View style={styles.treeWrap}>
              {unavailable ? (
                <>
                  <Text variant="caption" tone="warning">
                    This part of the decision wasn’t recorded in full, so it isn’t reconstructed
                    here. What was recorded:
                  </Text>
                  <ReasoningTree data={unavailable.recorded_values} hints={trace.value_hints} />
                </>
              ) : (
                <ReasoningTree data={payload} hints={trace.value_hints} />
              )}
            </View>
          </Card>
        );
      })}

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
        <ContestCard
          moduleSource={params.moduleSource}
          eventId={trace.event_id}
          open={contestOpen}
          onToggle={() => setContestOpen((v) => !v)}
        />
      ) : null}
    </ScreenContainer>
  );
}

/** Lets the reader push back on what they just read. Without it a trace is a
 * one-way mirror: the user can see the reasoning but has nowhere to say it's
 * wrong. Submissions go through Module 1's event log, which is where Module
 * 7's feedback loop already reads -- so an objection changes something
 * instead of dying on a read-only screen. */
function ContestCard({
  moduleSource,
  eventId,
  open,
  onToggle,
}: {
  moduleSource: Props['route']['params']['moduleSource'];
  eventId: string;
  open: boolean;
  onToggle: () => void;
}) {
  const { data: reasons } = useContestReasons();
  const contest = useContestDecision(moduleSource);
  const [reasonCode, setReasonCode] = React.useState<string | null>(null);
  const [note, setNote] = React.useState('');

  if (!open) {
    return (
      <Card>
        <SectionHeader
          title="Does this look wrong?"
          subtitle="Flag it and we’ll keep your objection on the record"
        />
        <View style={styles.actions}>
          <Button label="Flag this decision" variant="ghost" onPress={onToggle} />
        </View>
      </Card>
    );
  }

  return (
    <Card>
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
          onPress={() =>
            contest.mutate({ eventId, reasonCode: reasonCode!, note: note.trim() || undefined })
          }
        />
        <Button label="Cancel" variant="ghost" onPress={onToggle} />
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  badge: { alignSelf: 'flex-start', paddingHorizontal: SPACE.sm, paddingVertical: 4, borderRadius: 6, marginBottom: SPACE.sm },
  title: { marginTop: 2 },
  treeWrap: { marginTop: SPACE.sm },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.sm, marginTop: SPACE.sm },
  reasons: { gap: SPACE.xs, marginTop: SPACE.sm, marginBottom: SPACE.sm },
});
