import { Ionicons } from '@expo/vector-icons';
import React, { useEffect, useRef, useState } from 'react';
import { Animated, LayoutChangeEvent, Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import type {
  AwardedMilestoneOut,
  ChecklistItemOut,
  EducationProgressOut,
  RoadmapLevelOut,
  RoadmapTopicOut,
} from '../../api/types';
import { AnimatedFigure } from '../../components/AnimatedFigure';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { IconChip } from '../../components/IconChip';
import { ProgressBar } from '../../components/ProgressBar';
import { ReasoningTree } from '../../components/ReasoningTree';
import { Reveal } from '../../components/Reveal';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useReducedMotion } from '../../hooks/useReducedMotion';
import { useAppTheme } from '../../theme/ThemeContext';
import { useCheckMilestones, useCompleteEducation, useEducationProgress, useMilestoneHistory } from '../../hooks/useGamification';
import { MILESTONE_CATEGORY_LABEL } from '../../utils/labels';
import { RADIUS, SPACE } from '../../theme/tokens';

type QuizFeedbackMap = Record<string, { correct: boolean; explanation: string }>;
type CompleteFn = (itemId: string, kind: 'lesson' | 'quiz' | 'checklist') => void;

const LEVEL_ICON: Record<number, keyof typeof Ionicons.glyphMap> = {
  1: 'wallet-outline',
  2: 'shield-checkmark-outline',
  3: 'business-outline',
  4: 'trending-up-outline',
  5: 'calendar-outline',
};

const CHECKLIST_SECTION_ICON: Record<string, keyof typeof Ionicons.glyphMap> = {
  'Financial foundation': 'home-outline',
  Savings: 'wallet-outline',
  Investing: 'trending-up-outline',
  'Financial literacy': 'book-outline',
};

const BADGE_ICON: Record<string, keyof typeof Ionicons.glyphMap> = {
  'budget-beginner': 'wallet-outline',
  'emergency-ready': 'shield-checkmark-outline',
  'debt-aware': 'trending-down-outline',
  'investing-101': 'trending-up-outline',
  'tax-smart': 'receipt-outline',
  'diversification-pro': 'pie-chart-outline',
  'foundations-complete': 'trophy-outline',
};

const MILESTONE_CATEGORY_ICON: Record<string, keyof typeof Ionicons.glyphMap> = {
  buffer: 'shield-checkmark-outline',
  capacity_unlock: 'lock-open-outline',
  debt: 'trending-down-outline',
  subscriptions: 'cut-outline',
  consistency: 'flame-outline',
};

const CHECKLIST_SECTIONS = ['Financial foundation', 'Savings', 'Investing', 'Financial literacy'];

/** The chevron rotation is local to each disclosure card so every level/
 * section animates independently -- lifted out of the per-item hooks a
 * `.map()` can't call directly (same fix as Plan's TierLegendDisclosure). */
function useChevronRotation(isOpen: boolean) {
  const reducedMotion = useReducedMotion();
  const rotation = useRef(new Animated.Value(isOpen ? 1 : 0)).current;
  useEffect(() => {
    Animated.timing(rotation, {
      toValue: isOpen ? 1 : 0,
      duration: reducedMotion ? 0 : 200,
      useNativeDriver: true,
    }).start();
  }, [isOpen, reducedMotion, rotation]);
  return rotation.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '180deg'] });
}

function QuizOption({
  letter,
  label,
  state,
  onPress,
  disabled,
}: {
  letter: string;
  label: string;
  state: 'default' | 'selected' | 'correct' | 'incorrect';
  onPress: () => void;
  disabled?: boolean;
}) {
  const { colors } = useAppTheme();
  const tone = {
    default: { bg: colors.paperSunken, fg: colors.inkFaint, border: colors.border },
    selected: { bg: colors.terracottaSoft, fg: colors.terracotta, border: colors.terracotta },
    correct: { bg: colors.positiveSoft, fg: colors.positive, border: colors.positive },
    incorrect: { bg: colors.dangerSoft, fg: colors.danger, border: colors.danger },
  }[state];

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityState={{ selected: state !== 'default', disabled }}
      style={[styles.quizOption, { borderColor: tone.border, backgroundColor: colors.paperRaised }]}
    >
      <View style={[styles.quizLetter, { backgroundColor: tone.bg }]}>
        <Text variant="label" style={{ color: tone.fg }}>
          {letter}
        </Text>
      </View>
      <Text variant="body" style={styles.quizOptionLabel}>
        {label}
      </Text>
      {state === 'correct' ? <Ionicons name="checkmark-circle" size={18} color={colors.positive} /> : null}
      {state === 'incorrect' ? <Ionicons name="close-circle" size={18} color={colors.danger} /> : null}
    </Pressable>
  );
}

/** Smooths a sequence of points into a single cubic-bezier path (the
 * standard Catmull-Rom -> bezier conversion) so the roadmap reads as one
 * continuous winding road through every topic node, however irregular the
 * vertical spacing between them (a level banner's gap included). */
function smoothPath(points: { x: number; y: number }[]): string {
  if (points.length === 0) return '';
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] ?? points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] ?? p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2.x} ${p2.y}`;
  }
  return d;
}

function findTopicById(roadmap: RoadmapLevelOut[], topicId: string): { level: RoadmapLevelOut; topic: RoadmapTopicOut } | null {
  for (const level of roadmap) {
    const topic = level.topics.find((t) => t.topic_id === topicId);
    if (topic) return { level, topic };
  }
  return null;
}

const NODE_SIZE = 56;
const ROAD_V_SPACING = 84;
// Vertical space reserved before each level's first node: the banner
// pill's own height (~56px, centered 30px into the slot) plus a clear
// 24px gap so it never overlaps the node sitting right below it.
const ROAD_BANNER_SLOT = 110;
const ROAD_BANNER_CENTER_OFFSET = 30;
const ROAD_PAD_TOP = 28;
const ROAD_PAD_BOTTOM = 36;

/** The whole beginner roadmap as one winding road (an SVG path smoothed
 * through every topic's node), banners marking each level like mile-
 * markers, and a node per topic the user taps to open its lesson + quiz --
 * the "actual roadmap" visual metaphor, in place of 26 topics' worth of
 * always-visible description text. */
function RoadmapPath({
  roadmap,
  currentTopicId,
  onSelectTopic,
}: {
  roadmap: RoadmapLevelOut[];
  currentTopicId: string | null;
  onSelectTopic: (topicId: string) => void;
}) {
  const { colors } = useAppTheme();
  const [width, setWidth] = useState(0);
  const onLayout = (e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width);

  const flat = roadmap.flatMap((level) => level.topics.map((topic) => ({ level, topic })));

  const yPositions: number[] = [];
  const bannerYByLevel: Record<number, number> = {};
  let cursor = ROAD_PAD_TOP;
  roadmap.forEach((level) => {
    bannerYByLevel[level.level] = cursor + ROAD_BANNER_CENTER_OFFSET;
    cursor += ROAD_BANNER_SLOT;
    level.topics.forEach(() => {
      yPositions.push(cursor);
      cursor += ROAD_V_SPACING;
    });
  });
  const totalHeight = cursor - ROAD_V_SPACING + NODE_SIZE / 2 + 36 + ROAD_PAD_BOTTOM;

  if (width === 0) {
    return <View style={{ height: totalHeight }} onLayout={onLayout} />;
  }

  const centerX = width / 2;
  const amplitude = Math.min(width * 0.3, centerX - NODE_SIZE / 2 - 20);
  const roadPoints = flat.map((_, i) => ({ x: centerX + amplitude * Math.sin(i * 0.65 + 0.3), y: yPositions[i] }));
  const roadD = smoothPath(roadPoints);
  const firstIncompleteIndex = flat.findIndex((f) => !f.topic.completed);

  return (
    <View onLayout={onLayout} style={{ height: totalHeight }}>
      <View style={styles.roadmapSvgWrap} pointerEvents="none">
        <Svg width={width} height={totalHeight}>
          <Path d={roadD} stroke={colors.paperSunken} strokeWidth={18} strokeLinecap="round" fill="none" />
          <Path d={roadD} stroke={colors.borderStrong} strokeWidth={2.5} strokeDasharray="10 12" strokeLinecap="round" fill="none" />
        </Svg>
      </View>

      {roadmap.map((level) => {
        const allComplete = level.topics.every((t) => t.completed);
        return (
          <View key={level.level} style={[styles.levelBanner, { top: bannerYByLevel[level.level] - 26 }]} pointerEvents="none">
            <View style={[styles.levelBannerPill, { backgroundColor: colors.paperRaised, borderColor: colors.borderStrong }]}>
              <IconChip name={LEVEL_ICON[level.level] ?? 'book-outline'} tone={allComplete ? 'positive' : 'petrol'} size={28} />
              <View>
                <Text variant="label" tone="muted">
                  LEVEL {level.level}
                </Text>
                <Text variant="bodyMedium">{level.title}</Text>
              </View>
            </View>
          </View>
        );
      })}

      {flat.map(({ topic }, i) => {
        const { x, y } = roadPoints[i];
        const isCurrent = i === firstIncompleteIndex || topic.topic_id === currentTopicId;
        const state = topic.completed ? 'complete' : isCurrent ? 'current' : 'upcoming';
        const tone = {
          complete: { bg: colors.positiveSoft, border: colors.positive, icon: colors.positive },
          current: { bg: colors.terracottaSoft, border: colors.terracotta, icon: colors.terracotta },
          upcoming: { bg: colors.paperRaised, border: colors.border, icon: colors.inkFaint },
        }[state];
        const iconName = topic.completed ? 'checkmark' : isCurrent ? 'flag' : 'ellipse-outline';

        return (
          <View key={topic.topic_id} style={[styles.roadmapNodeWrap, { left: x - 54, top: y - NODE_SIZE / 2 }]}>
            <Pressable
              onPress={() => onSelectTopic(topic.topic_id)}
              accessibilityRole="button"
              accessibilityLabel={topic.title}
              style={[styles.roadmapNode, { backgroundColor: tone.bg, borderColor: tone.border }]}
            >
              <Ionicons name={iconName} size={24} color={tone.icon} />
            </Pressable>
            <Text variant="caption" tone={isCurrent ? 'terracotta' : 'muted'} style={styles.roadmapNodeLabel} numberOfLines={2}>
              {topic.title}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

/** The lesson + quiz for a single tapped roadmap node, in a modal -- the
 * content every topic used to show inline (keeping the roadmap itself
 * compact) and the thing "Continue" now opens directly, so the button
 * always has something visible to jump to instead of relying on scroll
 * position. */
function TopicModal({
  active,
  onClose,
  completeItem,
  isPending,
  selectedAnswer,
  onSelectAnswer,
  feedback,
}: {
  active: { level: RoadmapLevelOut; topic: RoadmapTopicOut } | null;
  onClose: () => void;
  completeItem: CompleteFn;
  isPending: boolean;
  selectedAnswer?: number;
  onSelectAnswer: (index: number) => void;
  feedback?: { correct: boolean; explanation: string };
}) {
  const { colors } = useAppTheme();
  const topic = active?.topic;
  const level = active?.level;
  const passed = !!topic?.quiz_question?.passed;

  return (
    <Modal visible={!!active} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.modalBackdrop} onPress={onClose}>
        <Pressable onPress={(e) => e.stopPropagation()} style={styles.modalSheetWrap}>
          <ScrollView showsVerticalScrollIndicator={false}>
            {topic && level ? (
              <Card style={{ backgroundColor: colors.paperRaised }}>
                <View style={styles.modalHeaderRow}>
                  <Ionicons
                    name={topic.completed ? 'checkmark-circle' : 'ellipse-outline'}
                    size={20}
                    color={topic.completed ? colors.positive : colors.inkFaint}
                  />
                  <Text variant="label" tone="muted" style={styles.modalHeaderLabel}>
                    LEVEL {level.level} · {level.title}
                  </Text>
                  <Pressable onPress={onClose} hitSlop={10} accessibilityRole="button" accessibilityLabel="Close">
                    <Ionicons name="close" size={22} color={colors.inkFaint} />
                  </Pressable>
                </View>
                <Text variant="h2" style={styles.modalTitle}>
                  {topic.title}
                </Text>
                <Text variant="body" tone="muted" style={styles.modalDescription}>
                  {topic.description}
                </Text>
                <Button
                  label={topic.completed ? 'Done' : 'Learn'}
                  variant={topic.completed ? 'secondary' : 'primary'}
                  disabled={topic.completed || isPending}
                  onPress={() => completeItem(topic.topic_id, 'lesson')}
                  fullWidth
                />

                {topic.completed && topic.quiz_question ? (
                  <View style={[styles.quizCard, { backgroundColor: colors.paperSunken }]}>
                    <View style={styles.quizHeader}>
                      <IconChip name="help-circle-outline" tone="petrol" size={28} />
                      <Text variant="label" tone="petrol">
                        QUICK CHECK
                      </Text>
                    </View>
                    <Text variant="bodyMedium" style={styles.quizPrompt}>
                      {topic.quiz_question.prompt}
                    </Text>
                    <View style={styles.quizOptions}>
                      {topic.quiz_question.options.map((option, index) => {
                        const isSelected = selectedAnswer === index;
                        const state: 'default' | 'selected' | 'correct' | 'incorrect' = !isSelected
                          ? 'default'
                          : passed
                            ? 'correct'
                            : feedback
                              ? feedback.correct
                                ? 'correct'
                                : 'incorrect'
                              : 'selected';
                        return (
                          <QuizOption
                            key={option}
                            letter={String.fromCharCode(65 + index)}
                            label={option}
                            state={state}
                            disabled={passed || isPending}
                            onPress={() => onSelectAnswer(index)}
                          />
                        );
                      })}
                    </View>
                    {!passed ? (
                      <Button
                        label="Check answer"
                        disabled={selectedAnswer === undefined || isPending}
                        loading={isPending}
                        onPress={() => completeItem(topic.topic_id, 'quiz')}
                        fullWidth
                      />
                    ) : (
                      <View style={styles.quizPassedRow}>
                        <Ionicons name="trophy-outline" size={16} color={colors.positive} />
                        <Text variant="caption" tone="positive">
                          Passed — knowledge milestone recorded
                        </Text>
                      </View>
                    )}
                    {feedback && !passed ? (
                      <Reveal>
                        <View style={styles.quizFeedbackRow}>
                          <Ionicons
                            name={feedback.correct ? 'checkmark-circle-outline' : 'information-circle-outline'}
                            size={16}
                            color={feedback.correct ? colors.positive : colors.warning}
                          />
                          <Text variant="caption" tone={feedback.correct ? 'positive' : 'warning'} style={styles.quizFeedbackText}>
                            {feedback.explanation}
                          </Text>
                        </View>
                      </Reveal>
                    ) : null}
                  </View>
                ) : null}
              </Card>
            ) : null}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function ChecklistSectionCard({
  section,
  items,
  index,
  isOpen,
  onToggle,
  completeItem,
  isPending,
}: {
  section: string;
  items: ChecklistItemOut[];
  index: number;
  isOpen: boolean;
  onToggle: () => void;
  completeItem: CompleteFn;
  isPending: boolean;
}) {
  const { colors } = useAppTheme();
  const chevronRotation = useChevronRotation(isOpen);
  const completedCount = items.filter((i) => i.completed).length;
  const allComplete = completedCount === items.length;

  return (
    <Reveal index={index}>
      <Card>
        <Pressable
          onPress={onToggle}
          style={styles.levelHeader}
          accessibilityRole="button"
          accessibilityState={{ expanded: isOpen }}
          accessibilityLabel={section}
        >
          <IconChip name={CHECKLIST_SECTION_ICON[section] ?? 'list-outline'} tone={allComplete ? 'positive' : 'terracotta'} size={40} />
          <View style={styles.levelHeaderCopy}>
            <Text variant="h2">{section}</Text>
            <Text variant="caption" tone="muted">
              {completedCount} of {items.length} complete
            </Text>
          </View>
          <Animated.View style={{ transform: [{ rotate: chevronRotation }] }}>
            <Ionicons name="chevron-down" size={22} color={colors.inkFaint} />
          </Animated.View>
        </Pressable>
        {isOpen ? (
          <Reveal>
            <View style={styles.topicList}>
              {items.map((item) => (
                <View key={item.item_id} style={[styles.checkRow, { borderTopColor: colors.border }]}>
                  <Ionicons
                    name={item.completed ? 'checkmark-circle' : 'ellipse-outline'}
                    size={20}
                    color={item.completed ? colors.positive : colors.inkFaint}
                  />
                  <Text variant="body" style={styles.checkTitle}>
                    {item.title}
                  </Text>
                  {!item.completed ? (
                    <Button label="Complete" variant="ghost" disabled={isPending} onPress={() => completeItem(item.item_id, 'checklist')} />
                  ) : null}
                </View>
              ))}
            </View>
          </Reveal>
        ) : null}
      </Card>
    </Reveal>
  );
}

function MilestoneCard({ milestone, isNew }: { milestone: AwardedMilestoneOut; isNew?: boolean }) {
  const { colors } = useAppTheme();
  const hasDetails = Object.keys(milestone.details ?? {}).length > 0;

  return (
    <Card>
      <View style={styles.cardHeader}>
        <IconChip name={MILESTONE_CATEGORY_ICON[milestone.category] ?? 'trophy-outline'} tone="terracotta" size={36} />
        <View style={styles.cardHeaderText}>
          <View style={styles.pillRow}>
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
        </View>
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

function findNextTopic(roadmap: RoadmapLevelOut[]): { level: RoadmapLevelOut; topic: RoadmapTopicOut } | null {
  for (const level of roadmap) {
    const topic = level.topics.find((t) => !t.completed);
    if (topic) return { level, topic };
  }
  return null;
}

function EducationHub({ education }: { education: EducationProgressOut }) {
  const { colors } = useAppTheme();
  const complete = useCompleteEducation();
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [quizFeedback, setQuizFeedback] = useState<QuizFeedbackMap>({});
  // Which roadmap node's lesson + quiz is open in the modal -- null means
  // closed. Resolved by id (not a stored snapshot) so the modal always
  // reflects the latest `education` data after a completion mutation.
  const [activeTopicId, setActiveTopicId] = useState<string | null>(null);
  const [expandedChecklistSection, setExpandedChecklistSection] = useState<string | null>(() => {
    const firstIncomplete = CHECKLIST_SECTIONS.find((section) =>
      education.checklist.some((item) => item.section === section && !item.completed)
    );
    return firstIncomplete ?? null;
  });

  const completeItem: CompleteFn = (itemId, kind) =>
    complete.mutate(
      { itemId, kind, answerIndex: kind === 'quiz' ? selectedAnswers[itemId] : undefined },
      {
        onSuccess: (result) => {
          if (kind === 'quiz' && result) setQuizFeedback((current) => ({ ...current, [itemId]: result }));
        },
      }
    );

  const selectAnswer = (topicId: string, index: number) => {
    setSelectedAnswers((current) => ({ ...current, [topicId]: index }));
    // A fresh pick deserves a fresh read -- stale "not quite" feedback from
    // a previous guess on this same topic would otherwise linger and read
    // as if it applied to the new answer.
    setQuizFeedback((current) => {
      if (!(topicId in current)) return current;
      const next = { ...current };
      delete next[topicId];
      return next;
    });
  };

  const badgesEarned = education.badges.filter((b) => b.earned).length;
  const nextUp = findNextTopic(education.roadmap);

  return (
    <View style={styles.education}>
      <View>
        <Text variant="caption" tone="muted">
          Financial literacy roadmap
        </Text>
        <Text variant="h1">Learn with purpose</Text>
        <Text variant="body" tone="muted" style={styles.sectionIntro}>
          Short lessons move from financial hygiene to investing. Your progress reflects learning, never wealth or returns.
        </Text>
      </View>

      <Reveal index={0}>
        <Card raised>
          <View style={styles.statsRow}>
            <View style={styles.statItem}>
              <IconChip name="flame" tone="terracotta" size={36} />
              <AnimatedFigure target={education.learning_streak_days} formatter={(n) => `${Math.round(n)}`} variant="h1" />
              <Text variant="caption" tone="muted">
                day streak
              </Text>
            </View>
            <View style={[styles.statDivider, { backgroundColor: colors.border }]} />
            <View style={styles.statItem}>
              <IconChip name="book" tone="petrol" size={36} />
              <AnimatedFigure target={education.completed_topics} formatter={(n) => `${Math.round(n)}`} variant="h1" />
              <Text variant="caption" tone="muted">
                topics done
              </Text>
            </View>
            <View style={[styles.statDivider, { backgroundColor: colors.border }]} />
            <View style={styles.statItem}>
              <IconChip name="trophy" tone="warning" size={36} />
              <AnimatedFigure target={badgesEarned} formatter={(n) => `${Math.round(n)}`} variant="h1" />
              <Text variant="caption" tone="muted">
                badges
              </Text>
            </View>
          </View>
          <View style={styles.roadmapProgressRow}>
            <Text variant="bodyMedium">Roadmap progress</Text>
            <Text variant="figure" tone="petrol">
              {education.progress_pct}%
            </Text>
          </View>
          <ProgressBar fraction={education.progress_pct / 100} tone="petrol" duration={900} />
        </Card>
      </Reveal>

      <Reveal index={1}>
        {nextUp ? (
          <Card raised style={styles.continueCard}>
            <View style={styles.continueRow}>
              <IconChip name="play-circle" tone="terracotta" size={44} />
              <View style={styles.continueCopy}>
                <Text variant="label" tone="terracotta">
                  CONTINUE LEARNING
                </Text>
                <Text variant="bodyMedium">{nextUp.topic.title}</Text>
                <Text variant="caption" tone="muted">
                  Level {nextUp.level.level} · {nextUp.level.title}
                </Text>
              </View>
            </View>
            <Button label="Continue" fullWidth onPress={() => setActiveTopicId(nextUp.topic.topic_id)} />
          </Card>
        ) : (
          <Card raised style={styles.celebrateCard}>
            <IconChip name="trophy" tone="positive" size={48} />
            <Text variant="h2">Roadmap complete!</Text>
            <Text variant="caption" tone="muted" style={styles.celebrateText}>
              You've finished every topic on the beginner roadmap. Nice work.
            </Text>
          </Card>
        )}
      </Reveal>

      <View style={styles.subsection}>
        <SectionHeader title="Your learning path" subtitle="Follow the road — tap a stop to learn and quiz" />
        <Reveal index={2}>
          <Card>
            <RoadmapPath
              roadmap={education.roadmap}
              currentTopicId={nextUp?.topic.topic_id ?? null}
              onSelectTopic={(topicId) => setActiveTopicId(topicId)}
            />
          </Card>
        </Reveal>
      </View>

      <TopicModal
        active={activeTopicId ? findTopicById(education.roadmap, activeTopicId) : null}
        onClose={() => setActiveTopicId(null)}
        completeItem={completeItem}
        isPending={complete.isPending}
        selectedAnswer={activeTopicId ? selectedAnswers[activeTopicId] : undefined}
        onSelectAnswer={(i) => activeTopicId && selectAnswer(activeTopicId, i)}
        feedback={activeTopicId ? quizFeedback[activeTopicId] : undefined}
      />

      <View style={styles.subsection}>
        <SectionHeader title="Getting started checklist" subtitle="Everyday habits, ticked off at your own pace" />
        {CHECKLIST_SECTIONS.map((section, index) => {
          const items = education.checklist.filter((item) => item.section === section);
          if (items.length === 0) return null;
          return (
            <ChecklistSectionCard
              key={section}
              section={section}
              items={items}
              index={index}
              isOpen={expandedChecklistSection === section}
              onToggle={() => setExpandedChecklistSection(expandedChecklistSection === section ? null : section)}
              completeItem={completeItem}
              isPending={complete.isPending}
            />
          );
        })}
      </View>

      <View style={styles.subsection}>
        <SectionHeader title="Badges" subtitle="Earned by finishing modules and quizzes" />
        <View style={styles.badgeGrid}>
          {education.badges.map((badge, index) => (
            <Reveal key={badge.badge_id} index={index}>
              <Card style={[styles.badgeCard, !badge.earned && styles.badgeLocked]}>
                <View style={styles.badgeIconRow}>
                  <IconChip name={BADGE_ICON[badge.badge_id] ?? 'ribbon-outline'} tone={badge.earned ? 'positive' : 'neutral'} size={40} />
                  <Ionicons
                    name={badge.earned ? 'checkmark-circle' : 'lock-closed-outline'}
                    size={badge.earned ? 18 : 15}
                    color={badge.earned ? colors.positive : colors.inkFaint}
                  />
                </View>
                <Text variant="bodyMedium" style={styles.badgeTitle}>
                  {badge.title}
                </Text>
                <Text variant="caption" tone="muted">
                  {badge.description}
                </Text>
              </Card>
            </Reveal>
          ))}
        </View>
      </View>
    </View>
  );
}

export function ProgressScreen() {
  const { colors } = useAppTheme();
  const { data, isPending, isRefetching, error, refetch } = useMilestoneHistory();
  const educationQuery = useEducationProgress();
  const checkMutation = useCheckMilestones();
  const [newlyAwardedIds, setNewlyAwardedIds] = useState<Set<string>>(new Set());
  const [checked, setChecked] = useState(false);
  const [showAllMilestones, setShowAllMilestones] = useState(false);

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
  const visibleMilestones = showAllMilestones ? milestones : milestones.slice(0, 4);

  return (
    <ScreenContainer onRefresh={runCheck} refreshing={isRefetching || checkMutation.isPending}>
      <View>
        <Text variant="caption" tone="muted">
          Your journey
        </Text>
        <Text variant="display">Progress</Text>
        <Text variant="body" tone="muted" style={styles.subtitle}>
          A friendlier way to see what you've built -- one lesson, one habit, one milestone at a time.
        </Text>
      </View>

      {educationQuery.data ? <EducationHub education={educationQuery.data} /> : null}

      <View style={styles.subsection}>
        <SectionHeader title="Milestones" subtitle="Awarded automatically for what you've actually done" />
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
          <>
            {visibleMilestones.map((m, index) => (
              <Reveal key={m.milestone_id} index={index}>
                <MilestoneCard milestone={m} isNew={newlyAwardedIds.has(m.milestone_id)} />
              </Reveal>
            ))}
            {milestones.length > 4 ? (
              <Pressable
                onPress={() => setShowAllMilestones((v) => !v)}
                style={styles.showMoreRow}
                accessibilityRole="button"
                accessibilityLabel={showAllMilestones ? 'Show fewer milestones' : 'Show all milestones'}
              >
                <Text variant="bodyMedium" tone="petrol">
                  {showAllMilestones ? 'Show less' : `Show ${milestones.length - 4} more`}
                </Text>
                <Ionicons name={showAllMilestones ? 'chevron-up' : 'chevron-down'} size={18} color={colors.petrol} />
              </Pressable>
            ) : null}
          </>
        )}
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  subtitle: { marginTop: SPACE.xs },
  education: { gap: SPACE.lg, marginTop: SPACE.xxl },
  subsection: { gap: SPACE.md, marginTop: SPACE.lg },
  sectionIntro: { marginTop: SPACE.xs },

  statsRow: { flexDirection: 'row', alignItems: 'center' },
  statItem: { flex: 1, alignItems: 'center', gap: 2 },
  statDivider: { width: StyleSheet.hairlineWidth, alignSelf: 'stretch', marginVertical: SPACE.xs },
  roadmapProgressRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: SPACE.lg, marginBottom: SPACE.sm },

  continueCard: { gap: SPACE.md },
  continueRow: { flexDirection: 'row', gap: SPACE.sm, alignItems: 'center' },
  continueCopy: { flex: 1, gap: 2 },
  celebrateCard: { alignItems: 'center', gap: SPACE.xs },
  celebrateText: { textAlign: 'center' },

  levelHeader: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  levelHeaderCopy: { flex: 1, gap: 2 },

  topicList: { marginTop: SPACE.sm },

  roadmapSvgWrap: { position: 'absolute', left: 0, top: 0, right: 0, bottom: 0 },
  levelBanner: { position: 'absolute', left: 0, right: 0, alignItems: 'center' },
  levelBannerPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACE.sm,
    paddingHorizontal: SPACE.md,
    paddingVertical: SPACE.sm,
    borderRadius: RADIUS.pill,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
  },
  roadmapNodeWrap: { position: 'absolute', width: 108, alignItems: 'center' },
  roadmapNode: { width: NODE_SIZE, height: NODE_SIZE, borderRadius: NODE_SIZE / 2, borderWidth: 3, alignItems: 'center', justifyContent: 'center' },
  roadmapNodeLabel: { marginTop: SPACE.xs, textAlign: 'center', width: 100 },

  modalBackdrop: { flex: 1, backgroundColor: 'rgba(20, 15, 8, 0.55)', justifyContent: 'center', padding: SPACE.lg },
  modalSheetWrap: { maxHeight: '85%', borderRadius: RADIUS.lg },
  modalHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  modalHeaderLabel: { flex: 1 },
  modalTitle: { marginTop: SPACE.sm },
  modalDescription: { marginTop: SPACE.xs, marginBottom: SPACE.md },

  quizCard: { marginTop: SPACE.sm, padding: SPACE.md, borderRadius: RADIUS.md, gap: SPACE.sm },
  quizHeader: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  quizPrompt: {},
  quizOptions: { gap: SPACE.sm },
  quizOption: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACE.sm,
    padding: SPACE.sm,
    borderRadius: RADIUS.sm,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
  },
  quizLetter: { width: 26, height: 26, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  quizOptionLabel: { flex: 1 },
  quizPassedRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.xs },
  quizFeedbackRow: { flexDirection: 'row', alignItems: 'flex-start', gap: SPACE.xs },
  quizFeedbackText: { flex: 1 },

  checkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACE.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingTop: SPACE.sm,
    marginTop: SPACE.sm,
  },
  checkTitle: { flex: 1 },

  badgeGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACE.sm },
  badgeCard: { flexBasis: '47%', flexGrow: 1, gap: SPACE.xs },
  badgeLocked: { opacity: 0.55 },
  badgeIconRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  badgeTitle: { marginTop: SPACE.xs },

  showMoreRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: SPACE.xs, paddingVertical: SPACE.sm },

  cardHeader: { flexDirection: 'row', gap: SPACE.sm, alignItems: 'center' },
  cardHeaderText: { flex: 1 },
  pillRow: { flexDirection: 'row', gap: SPACE.sm, flexWrap: 'wrap' },
  pill: { paddingHorizontal: SPACE.sm, paddingVertical: 4, borderRadius: 6, alignSelf: 'flex-start' },
  headline: { marginTop: SPACE.sm },
  details: { marginTop: SPACE.md },
});
