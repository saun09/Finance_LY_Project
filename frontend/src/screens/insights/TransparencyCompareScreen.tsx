import { useRoute } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useAppTheme } from '../../theme/ThemeContext';
import { useTransparencyComparison } from '../../hooks/useTransparency';
import { SPACE } from '../../theme/tokens';
import { formatTraceValue, humanizeKey } from '../../utils/traceValues';
import type { InsightsStackParamList } from '../../navigation/types';

type Props = NativeStackScreenProps<InsightsStackParamList, 'TransparencyCompare'>;

/** Turns a dotted leaf path ("questionnaire.answers.horizon") into
 * something readable, keeping the full path underneath so the reader can
 * still locate the field in the trace itself. */
function readablePath(path: string): { leaf: string; context: string } {
  const parts = path.split('.');
  const leaf = parts[parts.length - 1].replace(/\[(\d+)\]/, ' #$1');
  return { leaf: humanizeKey(leaf), context: parts.slice(0, -1).map(humanizeKey).join(' › ') };
}

/**
 * What actually moved between two versions of the same decision.
 *
 * This is the question a trace of a single decision cannot answer. "Your
 * tier is 3 because your buffer covers 2 months" explains today; "your tier
 * dropped from 5 to 3 because your buffer coverage went from 9 months to 2"
 * explains the thing the user actually noticed. Both sides are read from the
 * event log, so this is a diff of two historical records, never a
 * recomputation of either.
 */
export function TransparencyCompareScreen() {
  const { colors } = useAppTheme();
  const { params } = useRoute<Props['route']>();
  const { data, isPending, error, refetch } = useTransparencyComparison(
    params.moduleSource,
    params.beforeEventId,
    params.afterEventId,
  );

  if (isPending) {
    return (
      <ScreenContainer>
        <Text variant="display">What changed</Text>
        <SkeletonCard />
        <SkeletonCard />
      </ScreenContainer>
    );
  }

  if (error) {
    return (
      <ScreenContainer>
        <Text variant="display">What changed</Text>
        <ErrorState message={error.message} onRetry={() => refetch()} />
      </ScreenContainer>
    );
  }

  const comparison = data!;

  return (
    <ScreenContainer>
      <View>
        <View style={[styles.badge, { backgroundColor: colors.petrolSoft }]}>
          <Text variant="label" tone="petrol">
            {comparison.framing_label.toUpperCase()}
          </Text>
        </View>
        <Text variant="display" style={styles.title}>
          What changed
        </Text>
        <Text variant="body" tone="muted" style={styles.subtitle}>
          {comparison.display_name}, between two recorded decisions
        </Text>
      </View>

      <Card>
        <SectionHeader title="Before" subtitle={new Date(comparison.before_timestamp).toLocaleString('en-IN')} />
        <Text variant="bodyMedium">{comparison.before_headline}</Text>
      </Card>

      <Card>
        <SectionHeader title="After" subtitle={new Date(comparison.after_timestamp).toLocaleString('en-IN')} />
        <Text variant="bodyMedium">{comparison.after_headline}</Text>
      </Card>

      {(comparison.changes ?? []).length === 0 ? (
        <EmptyState
          title="Nothing changed"
          message={`All ${comparison.unchanged_field_count} recorded fields are identical across these two decisions.`}
        />
      ) : (
        <Card>
          <SectionHeader
            title={`${(comparison.changes ?? []).length} field${(comparison.changes ?? []).length === 1 ? '' : 's'} moved`}
            subtitle={`${comparison.unchanged_field_count} stayed the same`}
          />
          {(comparison.changes ?? []).map((change) => {
            const { leaf, context } = readablePath(change.path);
            const before = formatTraceValue(change.before, change.hint ?? undefined);
            const after = formatTraceValue(change.after, change.hint ?? undefined);
            return (
              <View key={change.path} style={[styles.change, { borderTopColor: colors.border }]}>
                <Text variant="bodyMedium">{leaf}</Text>
                {context ? (
                  <Text variant="caption" tone="faint">
                    {context}
                  </Text>
                ) : null}
                <View style={styles.values}>
                  <Text variant="figure" tone="muted">
                    {before.display}
                  </Text>
                  <Text variant="figure" tone="faint">
                    →
                  </Text>
                  <Text variant="figure">{after.display}</Text>
                </View>
              </View>
            );
          })}
        </Card>
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  badge: { alignSelf: 'flex-start', paddingHorizontal: SPACE.sm, paddingVertical: 4, borderRadius: 6, marginBottom: SPACE.sm },
  title: { marginTop: 2 },
  subtitle: { marginTop: SPACE.xs },
  change: { paddingTop: SPACE.sm, marginTop: SPACE.sm, borderTopWidth: StyleSheet.hairlineWidth * 1.5 },
  values: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm, marginTop: 4, flexWrap: 'wrap' },
});
