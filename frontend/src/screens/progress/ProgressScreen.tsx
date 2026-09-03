import React, { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import type { AwardedMilestoneOut } from '../../api/types';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { ReasoningTree } from '../../components/ReasoningTree';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useAppTheme } from '../../theme/ThemeContext';
import { useCheckMilestones, useMilestoneHistory } from '../../hooks/useGamification';
import { MILESTONE_CATEGORY_LABEL } from '../../utils/labels';
import { SPACE } from '../../theme/tokens';

function MilestoneCard({ milestone, isNew }: { milestone: AwardedMilestoneOut; isNew?: boolean }) {
  const { colors } = useAppTheme();
  const hasDetails = Object.keys(milestone.details ?? {}).length > 0;

  return (
    <Card>
      <View style={styles.cardHeader}>
        <View style={[styles.pill, { backgroundColor: colors.terracottaSoft }]}>
          <Text variant="label" tone="terracotta">
            {(MILESTONE_CATEGORY_LABEL[milestone.category] ?? milestone.category).toUpperCase()}
          </Text>
        </View>
        {isNew ? (
          <View style={[styles.pill, { backgroundColor: colors.positiveSoft }]}>
            <Text variant="label" tone="positive">
              NEW
            </Text>
          </View>
        ) : null}
      </View>
      <Text variant="bodyMedium" style={styles.headline}>
        {milestone.headline}
      </Text>
      {hasDetails ? (
        <View style={styles.details}>
          <ReasoningTree data={milestone.details} />
        </View>
      ) : null}
    </Card>
  );
}

export function ProgressScreen() {
  const { data, isPending, isRefetching, error, refetch } = useMilestoneHistory();
  const checkMutation = useCheckMilestones();
  const [newlyAwardedIds, setNewlyAwardedIds] = useState<Set<string>>(new Set());
  const [checked, setChecked] = useState(false);

  const runCheck = () =>
    checkMutation.mutate(undefined, {
      onSuccess: (awarded) => setNewlyAwardedIds(new Set(awarded.map((m) => m.milestone_id))),
    });

  useEffect(() => {
    if (checked) return;
    setChecked(true);
    runCheck();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checked]);

  const milestones = (data?.milestones ?? []).slice().reverse();

  return (
    <ScreenContainer onRefresh={runCheck} refreshing={isRefetching || checkMutation.isPending}>
      <View>
        <Text variant="caption" tone="muted">
          Your journey
        </Text>
        <Text variant="display">Progress</Text>
        <Text variant="body" tone="muted" style={styles.subtitle}>
          Milestones for what you've actually done — building a buffer, clearing debt, cutting a leak —
          never for market moves you didn't control.
        </Text>
      </View>

      {isPending ? (
        <>
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : milestones.length === 0 ? (
        <Card>
          <EmptyState
            title="No milestones yet"
            message="These are awarded automatically as you build your buffer, unlock more capacity, clear debt, or cut a recurring cost — nothing to do here directly."
          />
        </Card>
      ) : (
        milestones.map((m) => (
          <MilestoneCard key={m.milestone_id} milestone={m} isNew={newlyAwardedIds.has(m.milestone_id)} />
        ))
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  subtitle: { marginTop: SPACE.xs },
  cardHeader: { flexDirection: 'row', gap: SPACE.sm, alignItems: 'center' },
  pill: { paddingHorizontal: SPACE.sm, paddingVertical: 4, borderRadius: 6, alignSelf: 'flex-start' },
  headline: { marginTop: SPACE.sm },
  details: { marginTop: SPACE.md },
});
