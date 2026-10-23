import { Ionicons } from '@expo/vector-icons';
import React, { useEffect, useRef, useState } from 'react';
import {
  AccessibilityInfo,
  Animated,
  Easing,
  LayoutChangeEvent,
  Modal,
  Pressable,
  ScrollView,
  StyleProp,
  StyleSheet,
  View,
  ViewStyle,
} from 'react-native';
import type {
  AwardedMilestoneOut,
  ChecklistItemOut,
  EducationProgressOut,
  RoadmapLevelOut,
  RoadmapTopicOut,
} from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { IconChip } from '../../components/IconChip';
import { ReasoningTree } from '../../components/ReasoningTree';
import { Reveal } from '../../components/Reveal';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useAppTheme } from '../../theme/ThemeContext';
import { useCheckMilestones, useCompleteEducation, useEducationProgress, useMilestoneHistory } from '../../hooks/useGamification';
import { MILESTONE_CATEGORY_LABEL } from '../../utils/labels';
import { RADIUS, SPACE } from '../../theme/tokens';

type QuizFeedbackMap = Record<string, { correct: boolean; explanation: string }>;
type CompleteFn = (itemId: string, kind: 'lesson' | 'quiz' | 'checklist') => void;
type IconName = keyof typeof Ionicons.glyphMap;
type TopicEntry = { level: RoadmapLevelOut; topic: RoadmapTopicOut };

/* -------------------------------------------------------------------------- */
/* Game palette + static maps                                                 */
/* -------------------------------------------------------------------------- */

const GAME = {
  bg: '#181715',
  panel: '#221F1B',
  panelRaised: '#2B2721',
  line: '#3A352E',
  text: '#F4EFE6',
  textMuted: '#A39B8E',
  gold: '#F2B93B',
  goldBg: '#2B2314',
  emerald: '#2FD39A',
  emeraldDeep: '#0E5C43',
  terracotta: '#E2784A',
  terracottaBg: '#2E1F18',
  dark: '#181715',
};

const PAGE_SIZE = 6; // 3 columns x 2 rows

// One icon per topic (matched by title), so the grid never repeats a glyph.
// Unrecognised titles fall back to a rotating pool keyed by position.
const TOPIC_ICON: Record<string, IconName> = {
  'income vs expenses': 'scale-outline',
  'needs vs wants': 'pie-chart-outline',
  'budgeting and cash flow': 'calculator-outline',
  'emergency funds': 'shield-outline',
  'inflation and interest': 'trending-up-outline',
  'buffers and insurance': 'umbrella-outline',
};
const FALLBACK_TOPIC_ICONS: IconName[] = [
  'receipt-outline',
  'bar-chart-outline',
  'git-branch-outline',
  'cash-outline',
  'bulb-outline',
  'school-outline',
  'pricetag-outline',
  'card-outline',
  'briefcase-outline',
  'leaf-outline',
];
function topicIcon(title: string, flatIndex: number): IconName {
  const key = title.trim().toLowerCase().replace(/\./g, '');
  return TOPIC_ICON[key] ?? FALLBACK_TOPIC_ICONS[flatIndex % FALLBACK_TOPIC_ICONS.length];
}

const CHECKLIST_SECTION_ICON: Record<string, IconName> = {
  'Financial foundation': 'home-outline',
  Savings: 'wallet-outline',
  Investing: 'trending-up-outline',
  'Financial literacy': 'book-outline',
};

const BADGE_ICON: Record<string, IconName> = {
  'budget-beginner': 'wallet-outline',
  'emergency-ready': 'shield-checkmark-outline',
  'debt-aware': 'trending-down-outline',
  'investing-101': 'trending-up-outline',
  'tax-smart': 'receipt-outline',
  'diversification-pro': 'pie-chart-outline',
  'foundations-complete': 'trophy-outline',
};

const MILESTONE_CATEGORY_ICON: Record<string, IconName> = {
  buffer: 'shield-checkmark-outline',
  capacity_unlock: 'lock-open-outline',
  debt: 'trending-down-outline',
  subscriptions: 'cut-outline',
  consistency: 'flame-outline',
};

const CHECKLIST_SECTIONS = ['Financial foundation', 'Savings', 'Investing', 'Financial literacy'];

type DeckTab = 'deck' | 'habits' | 'trophies';
const TABS: { key: DeckTab; label: string; icon: IconName }[] = [
  { key: 'deck', label: 'Learning', icon: 'albums-outline' },
  { key: 'habits', label: 'Habits', icon: 'checkbox-outline' },
  { key: 'trophies', label: 'Trophies', icon: 'trophy-outline' },
];

/* -------------------------------------------------------------------------- */
/* Small helpers                                                              */
/* -------------------------------------------------------------------------- */

/** Text with an explicit colour, so game UI stays legible on the dark shell
 * regardless of the app theme's `tone` colours. */
function GText({ color = GAME.text, style, ...rest }: React.ComponentProps<typeof Text> & { color?: string }) {
  return <Text {...rest} style={[{ color }, style]} />;
}

function useReduceMotion() {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    AccessibilityInfo.isReduceMotionEnabled()
      .then(setReduce)
      .catch(() => {});
    const sub = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduce);
    return () => sub.remove();
  }, []);
  return reduce;
}

/** Increments when `done` flips false -> true *after* mount, so a card plays
 * its unlock animation only when something is newly completed -- never on
 * first render or when the pager remounts it. */
function useUnlockTrigger(done: boolean) {
  const prev = useRef(done);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!prev.current && done) setTick((t) => t + 1);
    prev.current = done;
  }, [done]);
  return tick;
}

function findNextTopic(roadmap: RoadmapLevelOut[]): TopicEntry | null {
  for (const level of roadmap) {
    const topic = level.topics.find((t) => !t.completed);
    if (topic) return { level, topic };
  }
  return null;
}

function findTopicById(roadmap: RoadmapLevelOut[], topicId: string): TopicEntry | null {
  for (const level of roadmap) {
    const topic = level.topics.find((t) => t.topic_id === topicId);
    if (topic) return { level, topic };
  }
  return null;
}

/* -------------------------------------------------------------------------- */
/* CollectibleFrame: press-scale + pulse + flip + shine, shared by every card  */
/* -------------------------------------------------------------------------- */

function CollectibleFrame({
  children,
  slotStyle,
  background,
  borderColor,
  borderStyle = 'solid',
  glowColor,
  unlockTick = 0,
  pulse = false,
  disabled = false,
  selected = false,
  label,
  onPress,
}: {
  children: React.ReactNode;
  slotStyle?: StyleProp<ViewStyle>;
  background: string;
  borderColor: string;
  borderStyle?: 'solid' | 'dashed';
  glowColor?: string;
  unlockTick?: number;
  pulse?: boolean;
  disabled?: boolean;
  selected?: boolean;
  label: string;
  onPress?: () => void;
}) {
  const reduce = useReduceMotion();
  const pressScale = useRef(new Animated.Value(1)).current;
  const flip = useRef(new Animated.Value(0)).current;
  const shine = useRef(new Animated.Value(0)).current;
  const pulseVal = useRef(new Animated.Value(0)).current;
  const [width, setWidth] = useState(0);

  const springTo = (v: number) =>
    Animated.spring(pressScale, { toValue: v, useNativeDriver: true, speed: 40, bounciness: 6 }).start();

  // Gentle pulse on the card you should tap next.
  useEffect(() => {
    if (!pulse || reduce) {
      pulseVal.setValue(0);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseVal, { toValue: 1, duration: 900, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
        Animated.timing(pulseVal, { toValue: 0, duration: 900, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [pulse, reduce, pulseVal]);

  // Flip, then a diagonal shine sweep, when the card is newly completed.
  useEffect(() => {
    if (unlockTick === 0 || reduce) return;
    flip.setValue(0);
    shine.setValue(0);
    Animated.sequence([
      Animated.timing(flip, { toValue: 1, duration: 600, easing: Easing.out(Easing.cubic), useNativeDriver: true }),
      Animated.timing(shine, { toValue: 1, duration: 650, easing: Easing.linear, useNativeDriver: true }),
    ]).start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unlockTick]);

  const rotateY = flip.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });
  const pulseScale = pulseVal.interpolate({ inputRange: [0, 1], outputRange: [1, 1.035] });
  const scale = Animated.multiply(pressScale, pulseScale);
  const ringOpacity = pulseVal.interpolate({ inputRange: [0, 1], outputRange: [0.15, 0.95] });
  const shineX = shine.interpolate({ inputRange: [0, 1], outputRange: [-width * 0.6, width * 1.2] });
  const shineOpacity = shine.interpolate({ inputRange: [0, 0.1, 0.9, 1], outputRange: [0, 1, 1, 0] });

  return (
    <Pressable
      onPress={onPress}
      onPressIn={() => !disabled && springTo(0.95)}
      onPressOut={() => springTo(1)}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled, selected }}
      style={slotStyle}
    >
      <Animated.View
        style={[
          styles.frameOuter,
          glowColor
            ? { shadowColor: glowColor, shadowOpacity: 0.65, shadowRadius: 10, shadowOffset: { width: 0, height: 0 }, elevation: 6 }
            : null,
          { transform: [{ perspective: 900 }, { rotateY }, { scale }] },
        ]}
      >
        <View
          style={[styles.frameInner, { backgroundColor: background, borderColor, borderStyle }]}
          onLayout={(e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width)}
        >
          {children}
          <Animated.View
            pointerEvents="none"
            style={[styles.shine, { opacity: shineOpacity, transform: [{ translateX: shineX }, { rotate: '20deg' }] }]}
          />
        </View>
        {pulse ? (
          <Animated.View pointerEvents="none" style={[styles.pulseRing, { borderColor: GAME.terracotta, opacity: ringOpacity }]} />
        ) : null}
      </Animated.View>
    </Pressable>
  );
}

/* -------------------------------------------------------------------------- */
/* Top resource bar                                                           */
/* -------------------------------------------------------------------------- */

function GoldBar({ fraction }: { fraction: number }) {
  const anim = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(anim, {
      toValue: Math.max(0, Math.min(1, fraction)),
      duration: 900,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false,
    }).start();
  }, [fraction, anim]);
  const width = anim.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] });
  return (
    <View style={styles.barTrack}>
      <Animated.View style={[styles.barFill, { width }]} />
    </View>
  );
}

function StatTile({ icon, color, value, caption }: { icon: IconName; color: string; value: string; caption: string }) {
  return (
    <View style={styles.statTile}>
      <Ionicons name={icon} size={22} color={color} />
      <GText variant="bodyMedium" style={styles.statValue}>
        {value}
      </GText>
      <GText variant="caption" color={GAME.textMuted}>
        {caption}
      </GText>
    </View>
  );
}

function ResourceBar({
  streak,
  topics,
  badges,
  progressPct,
}: {
  streak: number;
  topics: number;
  badges: number;
  progressPct: number;
}) {
  return (
    <View style={styles.resourceBar}>
      <View style={styles.statsRow}>
        <StatTile icon="flame" color={GAME.terracotta} value={`${streak} ${streak === 1 ? 'Day' : 'Days'}`} caption="Streak" />
        <View style={styles.statDivider} />
        <StatTile icon="book" color={GAME.emerald} value={`${topics} Done`} caption="Topics" />
        <View style={styles.statDivider} />
        <StatTile icon="trophy" color={GAME.gold} value={`${badges} ${badges === 1 ? 'Badge' : 'Badges'}`} caption="Earned" />
      </View>
      <View style={styles.progressRow}>
        <GText variant="caption" color={GAME.textMuted}>
          Roadmap Progress
        </GText>
        <GText variant="bodyMedium" color={GAME.gold}>
          {progressPct}%
        </GText>
      </View>
      <GoldBar fraction={progressPct / 100} />
    </View>
  );
}

/* -------------------------------------------------------------------------- */
/* Segmented tabs                                                             */
/* -------------------------------------------------------------------------- */

function DeckTabs({ value, onChange }: { value: DeckTab; onChange: (tab: DeckTab) => void }) {
  return (
    <View style={styles.tabs}>
      {TABS.map((tab) => {
        const active = tab.key === value;
        return (
          <Pressable
            key={tab.key}
            onPress={() => onChange(tab.key)}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            style={({ pressed }) => [
              styles.tab,
              active && styles.tabActive,
              { transform: [{ scale: pressed ? 0.95 : 1 }] },
            ]}
          >
            <Ionicons name={tab.icon} size={16} color={active ? GAME.dark : GAME.textMuted} />
            <GText variant="bodyMedium" color={active ? GAME.dark : GAME.textMuted}>
              {tab.label}
            </GText>
          </Pressable>
        );
      })}
    </View>
  );
}

/* -------------------------------------------------------------------------- */
/* Tab 1: Learning deck                                                       */
/* -------------------------------------------------------------------------- */

type CardState = 'complete' | 'current' | 'available' | 'locked';

function TopicCard({
  entry,
  state,
  requiredLevel,
  iconName,
  onPress,
}: {
  entry: TopicEntry;
  state: CardState;
  requiredLevel: number;
  iconName: IconName;
  onPress: () => void;
}) {
  const { topic, level } = entry;
  const unlockTick = useUnlockTrigger(topic.completed);

  const look = {
    complete: { bg: '#22201D', border: 'rgba(242, 185, 59, 0.45)', glow: undefined, icon: GAME.gold },
    current: { bg: GAME.terracottaBg, border: GAME.terracotta, glow: GAME.terracotta, icon: GAME.terracotta },
    available: { bg: GAME.panelRaised, border: GAME.line, glow: undefined, icon: GAME.textMuted },
    locked: { bg: 'rgba(255,255,255,0.03)', border: GAME.line, glow: undefined, icon: GAME.textMuted },
  }[state];
  const locked = state === 'locked';

  return (
    <CollectibleFrame
      slotStyle={[styles.topicSlot, locked && styles.lockedSlot]}
      background={look.bg}
      borderColor={look.border}
      borderStyle={locked ? 'dashed' : 'solid'}
      glowColor={look.glow}
      unlockTick={unlockTick}
      pulse={state === 'current'}
      disabled={locked}
      label={locked ? `${topic.title}, locked. Finish level ${requiredLevel} first.` : topic.title}
      onPress={onPress}
    >
      <View style={styles.cardBody}>
        <View style={[styles.cardIcon, { borderColor: look.border }]}>
          <Ionicons name={locked ? 'lock-closed' : iconName} size={22} color={look.icon} />
        </View>
        <GText variant="caption" style={styles.cardTitle} numberOfLines={3} color={locked ? GAME.textMuted : GAME.text}>
          {topic.title}
        </GText>
      </View>

      {state === 'complete' ? (
        <View style={styles.checkBadge}>
          <Ionicons name="checkmark" size={14} color={GAME.dark} />
        </View>
      ) : null}

      <View
        style={[
          styles.levelPill,
          state === 'complete' && { backgroundColor: GAME.gold },
          state === 'current' && { backgroundColor: GAME.terracotta },
          state === 'available' && { backgroundColor: GAME.panel, borderTopWidth: 1, borderTopColor: GAME.line },
          locked && { backgroundColor: 'transparent', borderTopWidth: 1, borderTopColor: GAME.line },
        ]}
      >
        <GText
          variant="label"
          color={state === 'complete' || state === 'current' ? GAME.dark : GAME.textMuted}
          numberOfLines={1}
          style={styles.levelPillText}
        >
          {locked ? `Finish Level ${requiredLevel}` : `LEVEL ${level.level}`}
        </GText>
      </View>
    </CollectibleFrame>
  );
}

function LearningDeck({ roadmap, nextUp, onOpenTopic }: { roadmap: RoadmapLevelOut[]; nextUp: TopicEntry | null; onOpenTopic: (id: string) => void }) {
  const flat = roadmap.flatMap((level) => level.topics.map((topic) => ({ level, topic })));
  const nextIdx = flat.findIndex((f) => !f.topic.completed);
  const pageCount = Math.max(1, Math.ceil(flat.length / PAGE_SIZE));
  const [page, setPage] = useState(() => Math.max(0, Math.floor(nextIdx / PAGE_SIZE)));
  const currentLevel = nextUp?.level.level ?? 0;

  const pageItems = flat.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const placeholders = Math.max(0, PAGE_SIZE - pageItems.length);

  return (
    <View style={styles.tabBody}>
      {nextUp ? (
        <Pressable
          onPress={() => onOpenTopic(nextUp.topic.topic_id)}
          accessibilityRole="button"
          accessibilityLabel={`Continue lesson: ${nextUp.topic.title}`}
          style={({ pressed }) => [styles.upNext, { transform: [{ scale: pressed ? 0.97 : 1 }] }]}
        >
          <GText variant="caption" color={GAME.textMuted}>
            Up next
          </GText>
          <GText variant="bodyMedium" numberOfLines={1} style={styles.flex1}>
            {nextUp.topic.title}
          </GText>
          <Ionicons name="play-circle" size={22} color={GAME.terracotta} />
        </Pressable>
      ) : (
        <View style={[styles.celebrate, { borderColor: GAME.gold }]}>
          <Ionicons name="trophy" size={22} color={GAME.gold} />
          <GText variant="bodyMedium" color={GAME.gold}>
            Roadmap complete — nice work!
          </GText>
        </View>
      )}

      <View style={styles.grid}>
        {pageItems.map((entry, i) => {
          const isCurrent = nextUp?.topic.topic_id === entry.topic.topic_id;
          const state: CardState = entry.topic.completed
            ? 'complete'
            : isCurrent
              ? 'current'
              : entry.level.level > currentLevel
                ? 'locked'
                : 'available';
          return (
            <TopicCard
              key={entry.topic.topic_id}
              entry={entry}
              state={state}
              requiredLevel={currentLevel}
              iconName={topicIcon(entry.topic.title, page * PAGE_SIZE + i)}
              onPress={() => onOpenTopic(entry.topic.topic_id)}
            />
          );
        })}
        {Array.from({ length: placeholders }).map((_, i) => (
          <View key={`ph-${i}`} style={styles.topicSlot} />
        ))}
      </View>

      {pageCount > 1 ? (
        <View style={styles.pager}>
          <Pressable
            onPress={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            hitSlop={10}
            accessibilityRole="button"
            accessibilityLabel="Previous cards"
            style={[styles.pagerBtn, page === 0 && { opacity: 0.35 }]}
          >
            <Ionicons name="chevron-back" size={20} color={GAME.text} />
          </Pressable>
          <View style={styles.dots}>
            {Array.from({ length: pageCount }).map((_, i) => (
              <View key={i} style={[styles.dot, i === page && styles.dotActive]} />
            ))}
          </View>
          <Pressable
            onPress={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            disabled={page === pageCount - 1}
            hitSlop={10}
            accessibilityRole="button"
            accessibilityLabel="Next cards"
            style={[styles.pagerBtn, page === pageCount - 1 && { opacity: 0.35 }]}
          >
            <Ionicons name="chevron-forward" size={20} color={GAME.text} />
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

/* -------------------------------------------------------------------------- */
/* Tab 2: Habits & checklist                                                  */
/* -------------------------------------------------------------------------- */

function HabitsTab({
  checklist,
  selectedSection,
  onSelectSection,
  completeItem,
  isPending,
}: {
  checklist: ChecklistItemOut[];
  selectedSection: string;
  onSelectSection: (section: string) => void;
  completeItem: CompleteFn;
  isPending: boolean;
}) {
  const sections = CHECKLIST_SECTIONS.map((section) => ({ section, items: checklist.filter((i) => i.section === section) })).filter(
    (s) => s.items.length > 0
  );
  const selected = sections.find((s) => s.section === selectedSection) ?? sections[0];

  return (
    <View style={styles.tabBody}>
      <View style={styles.habitGrid}>
        {sections.map(({ section, items }) => {
          const done = items.filter((i) => i.completed).length;
          const all = done === items.length;
          const isSel = selected?.section === section;
          return (
            <HabitTile
              key={section}
              section={section}
              done={done}
              total={items.length}
              all={all}
              selected={isSel}
              onPress={() => onSelectSection(section)}
            />
          );
        })}
      </View>

      {selected ? (
        <View style={styles.habitPanel}>
          {selected.items.map((item, i) => (
            <View key={item.item_id} style={[styles.checkRow, i > 0 && styles.checkRowBorder]}>
              <Ionicons
                name={item.completed ? 'checkmark-circle' : 'ellipse-outline'}
                size={20}
                color={item.completed ? GAME.emerald : GAME.textMuted}
              />
              <GText variant="body" style={styles.flex1} color={item.completed ? GAME.textMuted : GAME.text}>
                {item.title}
              </GText>
              {!item.completed ? (
                <Pressable
                  onPress={() => completeItem(item.item_id, 'checklist')}
                  disabled={isPending}
                  accessibilityRole="button"
                  accessibilityLabel={`Complete ${item.title}`}
                  style={({ pressed }) => [styles.completeBtn, isPending && { opacity: 0.5 }, { transform: [{ scale: pressed ? 0.95 : 1 }] }]}
                >
                  <GText variant="label" color={GAME.dark}>
                    COMPLETE
                  </GText>
                </Pressable>
              ) : null}
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function HabitTile({
  section,
  done,
  total,
  all,
  selected,
  onPress,
}: {
  section: string;
  done: number;
  total: number;
  all: boolean;
  selected: boolean;
  onPress: () => void;
}) {
  const unlockTick = useUnlockTrigger(all);
  return (
    <CollectibleFrame
      slotStyle={styles.habitSlot}
      background={all ? '#22201D' : GAME.panelRaised}
      borderColor={all ? GAME.gold : selected ? GAME.terracotta : GAME.line}
            unlockTick={unlockTick}
      selected={selected}
      label={`${section}, ${done} of ${total} complete`}
      onPress={onPress}
    >
      <View style={styles.habitTile}>
        <Ionicons name={CHECKLIST_SECTION_ICON[section] ?? 'list-outline'} size={24} color={all ? GAME.gold : GAME.text} />
        <View style={styles.flex1}>
          <GText variant="bodyMedium" numberOfLines={2}>
            {section}
          </GText>
          <GText variant="caption" color={GAME.textMuted}>
            {done} of {total}
          </GText>
        </View>
        {all ? <Ionicons name="checkmark-circle" size={18} color={GAME.emerald} /> : null}
      </View>
    </CollectibleFrame>
  );
}

/* -------------------------------------------------------------------------- */
/* Tab 3: Trophy cabinet                                                      */
/* -------------------------------------------------------------------------- */

function BadgeTile({
  badge,
  selected,
  onPress,
}: {
  badge: EducationProgressOut['badges'][number];
  selected: boolean;
  onPress: () => void;
}) {
  const unlockTick = useUnlockTrigger(badge.earned);
  return (
    <CollectibleFrame
      slotStyle={styles.badgeSlot}
      background={badge.earned ? '#22201D' : 'rgba(255,255,255,0.03)'}
      borderColor={badge.earned ? GAME.gold : selected ? GAME.terracotta : GAME.line}
      borderStyle={badge.earned ? 'solid' : 'dashed'}
            unlockTick={unlockTick}
      selected={selected}
      label={`${badge.title}, ${badge.earned ? 'earned' : 'locked'}`}
      onPress={onPress}
    >
      <View style={[styles.cardBody, !badge.earned && { opacity: 0.5 }]}>
        <View style={[styles.cardIcon, { borderColor: badge.earned ? GAME.gold : GAME.line }]}>
          <Ionicons
            name={badge.earned ? BADGE_ICON[badge.badge_id] ?? 'ribbon-outline' : 'lock-closed'}
            size={22}
            color={badge.earned ? GAME.gold : GAME.textMuted}
          />
        </View>
        <GText variant="caption" style={styles.cardTitle} numberOfLines={2} color={badge.earned ? GAME.text : GAME.textMuted}>
          {badge.title}
        </GText>
      </View>
    </CollectibleFrame>
  );
}

type MilestoneState = {
  milestones: AwardedMilestoneOut[];
  isPending: boolean;
  error: { message: string } | null;
  onRetry: () => void;
  newlyAwardedIds: Set<string>;
};

function MilestoneCard({ milestone, isNew }: { milestone: AwardedMilestoneOut; isNew?: boolean }) {
  const { colors } = useAppTheme();
  const hasDetails = Object.keys(milestone.details ?? {}).length > 0;

  return (
    <Card>
      <View style={styles.cardHeader}>
        <IconChip name={MILESTONE_CATEGORY_ICON[milestone.category] ?? 'trophy-outline'} tone="terracotta" size={36} />
        <View style={styles.flex1}>
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

function TrophyTab({ badges, milestoneState }: { badges: EducationProgressOut['badges']; milestoneState: MilestoneState }) {
  const [selectedBadgeId, setSelectedBadgeId] = useState<string | null>(null);
  const selectedBadge = badges.find((b) => b.badge_id === selectedBadgeId);
  const { milestones, isPending, error, onRetry, newlyAwardedIds } = milestoneState;

  return (
    <View style={styles.tabBody}>
      <GText variant="label" color={GAME.textMuted}>
        BADGES
      </GText>
      <View style={styles.grid}>
        {badges.map((badge) => (
          <BadgeTile
            key={badge.badge_id}
            badge={badge}
            selected={selectedBadgeId === badge.badge_id}
            onPress={() => setSelectedBadgeId((cur) => (cur === badge.badge_id ? null : badge.badge_id))}
          />
        ))}
      </View>
      {selectedBadge ? (
        <View style={styles.badgeInfo}>
          <GText variant="bodyMedium" color={selectedBadge.earned ? GAME.gold : GAME.text}>
            {selectedBadge.title}
          </GText>
          <GText variant="caption" color={GAME.textMuted}>
            {selectedBadge.description}
          </GText>
        </View>
      ) : null}

      <GText variant="label" color={GAME.textMuted} style={styles.milestonesLabel}>
        MILESTONES
      </GText>
      {isPending ? (
        <SkeletonCard />
      ) : error ? (
        <ErrorState message={error.message} onRetry={onRetry} />
      ) : milestones.length === 0 ? (
        <Card>
          <EmptyState
            title="No milestones yet"
            message="These are awarded automatically as you build your buffer, unlock more capacity, clear debt, or cut a recurring cost — nothing to do here directly."
          />
        </Card>
      ) : (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.milestoneRail}>
          {milestones.map((m) => (
            <View key={m.milestone_id} style={styles.milestoneSlot}>
              <MilestoneCard milestone={m} isNew={newlyAwardedIds.has(m.milestone_id)} />
            </View>
          ))}
        </ScrollView>
      )}
    </View>
  );
}

/* -------------------------------------------------------------------------- */
/* Quiz + topic modal (unchanged behaviour)                                   */
/* -------------------------------------------------------------------------- */

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

function TopicModal({
  active,
  onClose,
  completeItem,
  isPending,
  selectedAnswer,
  onSelectAnswer,
  feedback,
}: {
  active: TopicEntry | null;
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
                    <Text variant="bodyMedium">{topic.quiz_question.prompt}</Text>
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

/* -------------------------------------------------------------------------- */
/* The deck: header bar + tabs + tab content (all tracking logic lives here)  */
/* -------------------------------------------------------------------------- */

function ProgressDeck({ education, milestoneState }: { education: EducationProgressOut; milestoneState: MilestoneState }) {
  const complete = useCompleteEducation();
  const [tab, setTab] = useState<DeckTab>('deck');
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [quizFeedback, setQuizFeedback] = useState<QuizFeedbackMap>({});
  // Resolved by id (not a stored snapshot) so the modal always reflects the
  // latest `education` data after a completion mutation.
  const [activeTopicId, setActiveTopicId] = useState<string | null>(null);
  const [selectedSection, setSelectedSection] = useState<string>(() => {
    const firstIncomplete = CHECKLIST_SECTIONS.find((section) =>
      education.checklist.some((item) => item.section === section && !item.completed)
    );
    return firstIncomplete ?? CHECKLIST_SECTIONS[0];
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
    // A fresh pick deserves a fresh read -- stale "not quite" feedback would
    // otherwise linger and read as if it applied to the new answer.
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
    <View style={styles.shell}>
      <ResourceBar
        streak={education.learning_streak_days}
        topics={education.completed_topics}
        badges={badgesEarned}
        progressPct={education.progress_pct}
      />
      <DeckTabs value={tab} onChange={setTab} />

      {tab === 'deck' ? (
        <LearningDeck roadmap={education.roadmap} nextUp={nextUp} onOpenTopic={setActiveTopicId} />
      ) : null}
      {tab === 'habits' ? (
        <HabitsTab
          checklist={education.checklist}
          selectedSection={selectedSection}
          onSelectSection={setSelectedSection}
          completeItem={completeItem}
          isPending={complete.isPending}
        />
      ) : null}
      {tab === 'trophies' ? <TrophyTab badges={education.badges} milestoneState={milestoneState} /> : null}

      <TopicModal
        active={activeTopicId ? findTopicById(education.roadmap, activeTopicId) : null}
        onClose={() => setActiveTopicId(null)}
        completeItem={completeItem}
        isPending={complete.isPending}
        selectedAnswer={activeTopicId ? selectedAnswers[activeTopicId] : undefined}
        onSelectAnswer={(i) => activeTopicId && selectAnswer(activeTopicId, i)}
        feedback={activeTopicId ? quizFeedback[activeTopicId] : undefined}
      />
    </View>
  );
}

/* -------------------------------------------------------------------------- */
/* Screen                                                                     */
/* -------------------------------------------------------------------------- */

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
      </View>

      {educationQuery.data ? (
        <ProgressDeck
          education={educationQuery.data}
          milestoneState={{
            milestones,
            isPending,
            error: error ?? null,
            onRetry: () => refetch(),
            newlyAwardedIds,
          }}
        />
      ) : educationQuery.error ? (
        <ErrorState message={educationQuery.error.message} onRetry={() => educationQuery.refetch()} />
      ) : (
        <SkeletonCard />
      )}
    </ScreenContainer>
  );
}

/* -------------------------------------------------------------------------- */
/* Styles                                                                     */
/* -------------------------------------------------------------------------- */

const styles = StyleSheet.create({
  flex1: { flex: 1 },

  shell: { backgroundColor: GAME.bg, borderRadius: RADIUS.lg, padding: SPACE.md, gap: SPACE.md, marginTop: SPACE.lg },
  tabBody: { gap: SPACE.md },

  // resource bar
  resourceBar: { backgroundColor: GAME.panel, borderRadius: RADIUS.md, padding: SPACE.md, borderWidth: 1, borderColor: GAME.line },
  statsRow: { flexDirection: 'row', alignItems: 'center' },
  statTile: { flex: 1, alignItems: 'center', gap: 2 },
  statValue: { color: GAME.text },
  statDivider: { width: StyleSheet.hairlineWidth, alignSelf: 'stretch', backgroundColor: GAME.line },
  progressRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: SPACE.md, marginBottom: SPACE.xs },
  barTrack: { height: 10, borderRadius: 5, backgroundColor: GAME.bg, overflow: 'hidden', borderWidth: 1, borderColor: GAME.line },
  barFill: { height: '100%', borderRadius: 5, backgroundColor: GAME.gold },

  // tabs
  tabs: { flexDirection: 'row', backgroundColor: GAME.panel, borderRadius: RADIUS.pill, padding: 4, gap: 4 },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: SPACE.xs, paddingVertical: SPACE.sm, borderRadius: RADIUS.pill },
  tabActive: { backgroundColor: GAME.gold },

  // collectible frame
  frameOuter: { flex: 1 },
  frameInner: { flex: 1, borderRadius: RADIUS.md, borderWidth: 2, overflow: 'hidden' },
  pulseRing: { position: 'absolute', top: -4, left: -4, right: -4, bottom: -4, borderRadius: RADIUS.md + 4, borderWidth: 2 },
  shine: { position: 'absolute', top: -40, bottom: -40, width: 34, backgroundColor: 'rgba(255,255,255,0.35)' },

  // learning grid
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', rowGap: SPACE.sm },
  topicSlot: { width: '31.5%', aspectRatio: 0.7 },
  cardBody: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: SPACE.xs, paddingHorizontal: 12, paddingTop: 8, paddingBottom: 36 },
  cardIcon: { width: 44, height: 44, borderRadius: 22, borderWidth: 2, alignItems: 'center', justifyContent: 'center', backgroundColor: GAME.bg },
  cardTitle: { textAlign: 'center' },
  checkBadge: { position: 'absolute', top: 6, right: 6, width: 22, height: 22, borderRadius: 11, backgroundColor: GAME.emerald, alignItems: 'center', justifyContent: 'center' },
  levelPill: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    height: 28,
    alignItems: 'center',
    justifyContent: 'center',
    borderBottomLeftRadius: RADIUS.md - 2,
    borderBottomRightRadius: RADIUS.md - 2,
  },
  levelPillText: { fontSize: 10, textAlign: 'center' },
  lockedSlot: { opacity: 0.6 },

  upNext: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm, paddingHorizontal: SPACE.md, height: 44, borderRadius: RADIUS.pill, backgroundColor: GAME.panel, borderWidth: 1, borderColor: GAME.line },
  celebrate: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: SPACE.sm, padding: SPACE.md, borderRadius: RADIUS.md, borderWidth: 2 },

  pager: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  pagerBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: GAME.panel, alignItems: 'center', justifyContent: 'center' },
  dots: { flexDirection: 'row', gap: 6 },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: GAME.line },
  dotActive: { backgroundColor: GAME.gold, width: 20 },

  // habits
  habitGrid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', rowGap: SPACE.sm },
  habitSlot: { width: '48.5%', height: 76 },
  habitTile: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: SPACE.sm, paddingHorizontal: SPACE.sm },
  habitPanel: { backgroundColor: GAME.panel, borderRadius: RADIUS.md, padding: SPACE.md, borderWidth: 1, borderColor: GAME.line },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  checkRowBorder: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: GAME.line, paddingTop: SPACE.sm, marginTop: SPACE.sm },
  completeBtn: { backgroundColor: GAME.gold, borderRadius: RADIUS.pill, paddingHorizontal: SPACE.sm, paddingVertical: 6 },

  // trophies
  badgeSlot: { width: '31.5%', aspectRatio: 0.9 },
  badgeInfo: { backgroundColor: GAME.panel, borderRadius: RADIUS.md, padding: SPACE.sm, gap: 2, borderWidth: 1, borderColor: GAME.line },
  milestonesLabel: { marginTop: SPACE.xs },
  milestoneRail: { gap: SPACE.sm },
  milestoneSlot: { width: 280 },
  cardHeader: { flexDirection: 'row', gap: SPACE.sm, alignItems: 'center' },
  pillRow: { flexDirection: 'row', gap: SPACE.sm, flexWrap: 'wrap' },
  pill: { paddingHorizontal: SPACE.sm, paddingVertical: 4, borderRadius: 6, alignSelf: 'flex-start' },
  headline: { marginTop: SPACE.sm },
  details: { marginTop: SPACE.md },

  // modal
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(20, 15, 8, 0.55)', justifyContent: 'center', padding: SPACE.lg },
  modalSheetWrap: { maxHeight: '85%', borderRadius: RADIUS.lg },
  modalHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  modalHeaderLabel: { flex: 1 },
  modalTitle: { marginTop: SPACE.sm },
  modalDescription: { marginTop: SPACE.xs, marginBottom: SPACE.md },

  quizCard: { marginTop: SPACE.sm, padding: SPACE.md, borderRadius: RADIUS.md, gap: SPACE.sm },
  quizHeader: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
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
});