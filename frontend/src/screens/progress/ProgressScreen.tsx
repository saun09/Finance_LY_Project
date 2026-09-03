import React, { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import type { AwardedMilestoneOut, EducationProgressOut } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { ReasoningTree } from '../../components/ReasoningTree';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useAppTheme } from '../../theme/ThemeContext';
import { useCheckMilestones, useCompleteEducation, useEducationProgress, useMilestoneHistory } from '../../hooks/useGamification';
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

function EducationHub({ education }: { education: EducationProgressOut }) {
  const complete = useCompleteEducation();
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [quizFeedback, setQuizFeedback] = useState<Record<string, { correct: boolean; explanation: string }>>({});
  const completeItem = (itemId: string, kind: 'lesson' | 'quiz' | 'checklist') =>
    complete.mutate({ itemId, kind, answerIndex: kind === 'quiz' ? selectedAnswers[itemId] : undefined }, {
      onSuccess: (result) => {
        if (kind === 'quiz' && result) setQuizFeedback((current) => ({ ...current, [itemId]: result }));
      },
    });

  return (
    <View style={styles.education}>
      <View>
        <Text variant="caption" tone="muted">Financial literacy roadmap</Text>
        <Text variant="h1">Learn with purpose</Text>
        <Text variant="body" tone="muted" style={styles.sectionIntro}>
          Short lessons move from financial hygiene to investing. Your progress reflects learning, never wealth or returns.
        </Text>
      </View>
      <Card raised>
        <View style={styles.progressHeader}>
          <Text variant="bodyMedium">Roadmap progress</Text>
          <Text variant="figure" tone="petrol">{education.progress_pct}%</Text>
        </View>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${education.progress_pct}%` }]} />
        </View>
        <Text variant="caption" tone="muted">
          {education.completed_topics} of {education.total_topics} topics complete · {education.learning_streak_days}-day learning streak
        </Text>
      </Card>
      {education.roadmap.map((level) => (
        <Card key={level.level}>
          <Text variant="label" tone="terracotta">LEVEL {level.level}</Text>
          <Text variant="h2" style={styles.levelTitle}>{level.title}</Text>
          {level.topics.map((topic) => (
            <View key={topic.topic_id} style={styles.topicRow}>
              <View style={styles.topicCopy}>
                <Text variant="bodyMedium">{topic.completed ? '✓ ' : ''}{topic.title}</Text>
                <Text variant="caption" tone="muted">{topic.description}</Text>
              </View>
              <Button
                label={topic.completed ? 'Done' : 'Learn'}
                variant={topic.completed ? 'secondary' : 'ghost'}
                disabled={topic.completed || complete.isPending}
                onPress={() => completeItem(topic.topic_id, 'lesson')}
              />
              {topic.completed && topic.quiz_question ? (
                <View style={styles.quiz}>
                  <Text variant="label" tone="petrol">QUICK CHECK</Text>
                  <Text variant="bodyMedium">{topic.quiz_question.prompt}</Text>
                  {topic.quiz_question.options.map((option, index) => (
                    <Button
                      key={option}
                      label={`${String.fromCharCode(65 + index)}. ${option}`}
                      variant={selectedAnswers[topic.topic_id] === index ? 'secondary' : 'ghost'}
                      disabled={topic.quiz_question?.passed || complete.isPending}
                      onPress={() => setSelectedAnswers((current) => ({ ...current, [topic.topic_id]: index }))}
                      fullWidth
                    />
                  ))}
                  {!topic.quiz_question.passed ? (
                    <Button
                      label="Check answer"
                      disabled={selectedAnswers[topic.topic_id] === undefined || complete.isPending}
                      loading={complete.isPending}
                      onPress={() => completeItem(topic.topic_id, 'quiz')}
                      fullWidth
                    />
                  ) : null}
                  {topic.quiz_question.passed ? <Text variant="caption" tone="positive">Passed. Knowledge milestone recorded.</Text> : null}
                  {quizFeedback[topic.topic_id] ? (
                    <Text variant="caption" tone={quizFeedback[topic.topic_id].correct ? 'positive' : 'warning'}>
                      {quizFeedback[topic.topic_id].correct ? 'Correct. ' : 'Not quite. '}{quizFeedback[topic.topic_id].explanation}
                    </Text>
                  ) : null}
                </View>
              ) : null}
            </View>
          ))}
        </Card>
      ))}
      <Card>
        <Text variant="h2">Beginner journey checklist</Text>
        {['Financial foundation', 'Savings', 'Investing', 'Financial literacy'].map((section) => {
          const items = education.checklist.filter((item) => item.section === section);
          return (
            <View key={section} style={styles.checklistSection}>
              <Text variant="label" tone="petrol">{section.toUpperCase()}</Text>
              {items.map((item) => (
                <View key={item.item_id} style={styles.checkRow}>
                  <Text variant="body" style={styles.checkTitle}>{item.completed ? '✓ ' : '○ '}{item.title}</Text>
                  {!item.completed ? <Button label="Complete" variant="ghost" disabled={complete.isPending} onPress={() => completeItem(item.item_id, 'checklist')} /> : null}
                </View>
              ))}
            </View>
          );
        })}
      </Card>
      <Card>
        <Text variant="h2">Educational badges</Text>
        {education.badges.map((badge) => (
          <View key={badge.badge_id} style={styles.badgeRow}>
            <Text variant="bodyMedium" tone={badge.earned ? 'positive' : 'faint'}>{badge.earned ? '✓' : '○'} {badge.title}</Text>
            <Text variant="caption" tone="muted">{badge.description}</Text>
          </View>
        ))}
      </Card>
    </View>
  );
}

export function ProgressScreen() {
  const { data, isPending, isRefetching, error, refetch } = useMilestoneHistory();
  const educationQuery = useEducationProgress();
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

      {educationQuery.data ? <EducationHub education={educationQuery.data} /> : null}

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
  education: { gap: SPACE.lg, marginTop: SPACE.xxl },
  sectionIntro: { marginTop: SPACE.xs },
  progressHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  progressTrack: { height: 8, backgroundColor: '#DCE9E7', borderRadius: 4, overflow: 'hidden', marginVertical: SPACE.md },
  progressFill: { height: '100%', backgroundColor: '#1F4B4C', borderRadius: 4 },
  levelTitle: { marginTop: SPACE.xs },
  topicRow: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: '#DCD3BE', paddingTop: SPACE.md, marginTop: SPACE.md },
  topicCopy: { marginBottom: SPACE.sm, gap: SPACE.xs },
  quiz: { gap: SPACE.sm, marginTop: SPACE.sm, paddingTop: SPACE.md, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: '#DCD3BE' },
  checklistSection: { marginTop: SPACE.lg, gap: SPACE.sm },
  checkRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: SPACE.sm },
  checkTitle: { flex: 1 },
  badgeRow: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: '#DCD3BE', paddingTop: SPACE.md, marginTop: SPACE.md, gap: SPACE.xs },
  cardHeader: { flexDirection: 'row', gap: SPACE.sm, alignItems: 'center' },
  pill: { paddingHorizontal: SPACE.sm, paddingVertical: 4, borderRadius: 6, alignSelf: 'flex-start' },
  headline: { marginTop: SPACE.sm },
  details: { marginTop: SPACE.md },
});
