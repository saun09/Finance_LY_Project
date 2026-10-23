import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { LinearGradient } from 'expo-linear-gradient';
import React, { useEffect, useRef } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { TRANSPARENCY_DECISION_TYPES, TransparencyDecisionType } from '../../api/transparency';
import { AnimatedFigure } from '../../components/AnimatedFigure';
import { BackHeader } from '../../components/BackHeader';
import { Card } from '../../components/Card';
import { ErrorState } from '../../components/ErrorState';
import { IconChip } from '../../components/IconChip';
import { InfoTooltip } from '../../components/InfoTooltip';
import { Reveal } from '../../components/Reveal';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useReducedMotion } from '../../hooks/useReducedMotion';
import { useTransparencyIndex } from '../../hooks/useTransparency';
import { TRANSPARENCY_DISPLAY_NAME } from '../../utils/labels';
import { useAppTheme } from '../../theme/ThemeContext';
import { Palette, RADIUS, SPACE } from '../../theme/tokens';
import type { InsightsStackParamList } from '../../navigation/types';

type Nav = NativeStackNavigationProp<InsightsStackParamList, 'Transparency'>;

type IconName = keyof typeof Ionicons.glyphMap;
type PillTone = 'neutral' | 'petrol' | 'warning';

// How each decision type actually arrives at its answer -- shown as a
// badge instead of a paragraph. Never "AI": risk_profile_ml is the only
// trained model in the system, and even it gets "Trained Model", not "AI"
// -- same restraint Module 9's own framing_label assertion enforces on the
// backend (transparency.py), so the index page never overclaims what the
// detail trace underneath it actually says.
const METHOD_LABEL: Record<TransparencyDecisionType, string> = {
  risk_profile: 'Deterministic Rules',
  allocation: 'Deterministic Rules',
  debt_leak_engine: 'Deterministic Rules',
  personalization: 'Deterministic Rules',
  gamification: 'Deterministic Rules',
  risk_profile_ml: 'Trained Model',
  rumour_verification_local: 'Retrieval Engine',
  rumour_verification: 'External Workflow',
};

const METHOD_TONE: Record<TransparencyDecisionType, PillTone> = {
  risk_profile: 'neutral',
  allocation: 'neutral',
  debt_leak_engine: 'neutral',
  personalization: 'neutral',
  gamification: 'neutral',
  risk_profile_ml: 'petrol',
  rumour_verification_local: 'petrol',
  rumour_verification: 'warning',
};

const PILL_BG: Record<PillTone, keyof Palette> = {
  neutral: 'paperSunken',
  petrol: 'petrolSoft',
  warning: 'warningSoft',
};
const PILL_TEXT: Record<PillTone, React.ComponentProps<typeof Text>['tone']> = {
  neutral: 'muted',
  petrol: 'petrol',
  warning: 'warning',
};

interface Category {
  key: string;
  title: string;
  icon: IconName;
  tone: 'petrol' | 'positive' | 'terracotta';
  types: readonly TransparencyDecisionType[];
  about: { title: string; description: string };
}

const DETERMINISTIC_ABOUT = {
  title: 'How decision logging works',
  description:
    'These are rule-table lookups and weighted sums — no model is involved. Showing you the weights ' +
    'and the table is the whole of it, and we don’t claim more than that.',
};

const CATEGORIES: Category[] = [
  {
    key: 'portfolio',
    title: 'Portfolio Logic',
    icon: 'shield-checkmark-outline',
    tone: 'petrol',
    types: ['risk_profile', 'allocation', 'personalization'],
    about: DETERMINISTIC_ABOUT,
  },
  {
    key: 'financial',
    title: 'Financial Gains',
    icon: 'trending-up-outline',
    tone: 'positive',
    types: ['debt_leak_engine', 'gamification'],
    about: DETERMINISTIC_ABOUT,
  },
  {
    key: 'verification',
    title: 'Verification Engine',
    icon: 'search-outline',
    tone: 'terracotta',
    types: ['risk_profile_ml', 'rumour_verification_local', 'rumour_verification'],
    about: {
      title: 'How verification works',
      description:
        'Three different engines, making three different claims. One predicts your risk tier from a ' +
        'trained model and shows which of your answers mattered most. Another searches a fixed corpus ' +
        'of filings and can name the constraint that ruled out every candidate it rejected. The third ' +
        'calls an external workflow that returns its own written rationale, which we can show you but ' +
        'cannot verify.',
    },
  },
];

/** A small "recorded live, as it happens" status dot -- a narrow, deliberate
 * exception to this app's usual no-looping-motion rule, same as any native
 * OS "recording" indicator: it pulses to mean an ongoing state, not a one-
 * off event, so a single entrance animation can't say the same thing.
 * Freezes to a plain solid dot under reduced motion. */
function LiveDot() {
  const { colors } = useAppTheme();
  const pulse = useRef(new Animated.Value(0)).current;
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (reducedMotion) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 900, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 900, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse, reducedMotion]);

  const scale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.8] });
  const ringOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.5, 0] });

  return (
    <View style={styles.liveDotWrap}>
      {!reducedMotion ? (
        <Animated.View
          style={[styles.liveDotRing, { backgroundColor: colors.positive, opacity: ringOpacity, transform: [{ scale }] }]}
        />
      ) : null}
      <View style={[styles.liveDotCore, { backgroundColor: colors.positive }]} />
    </View>
  );
}

function Pill({ label, tone }: { label: string; tone: PillTone }) {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.pill, { backgroundColor: colors[PILL_BG[tone]] }]}>
      <Text variant="caption" tone={PILL_TEXT[tone]}>
        {label}
      </Text>
    </View>
  );
}

function AuditRow({
  moduleSource,
  count,
  onPress,
}: {
  moduleSource: TransparencyDecisionType;
  count: number;
  onPress: () => void;
}) {
  const { colors } = useAppTheme();
  const scale = useRef(new Animated.Value(1)).current;
  const disabled = count === 0;

  const pressIn = () => Animated.spring(scale, { toValue: 0.98, useNativeDriver: true, speed: 50, bounciness: 0 }).start();
  const pressOut = () => Animated.spring(scale, { toValue: 1, useNativeDriver: true, speed: 30, bounciness: 6 }).start();

  return (
    <Animated.View style={{ transform: [{ scale }] }}>
      <Pressable
        disabled={disabled}
        onPress={onPress}
        onPressIn={disabled ? undefined : pressIn}
        onPressOut={disabled ? undefined : pressOut}
        accessibilityRole="button"
        accessibilityLabel={`${TRANSPARENCY_DISPLAY_NAME[moduleSource]}. ${count === 0 ? 'No decisions recorded yet' : `${count} recorded decisions`}`}
        accessibilityState={{ disabled }}
        style={(state) => {
          const focused = (state as { focused?: boolean }).focused;
          return [
            styles.row,
            (state.pressed || focused) && !disabled ? { backgroundColor: colors.paperSunken } : null,
            { opacity: disabled ? 0.55 : 1 },
          ];
        }}
      >
        <View style={styles.rowText}>
          <Text variant="h2">{TRANSPARENCY_DISPLAY_NAME[moduleSource]}</Text>
          <Pill label={METHOD_LABEL[moduleSource]} tone={METHOD_TONE[moduleSource]} />
        </View>
        <View style={styles.rowTrailing}>
          <Pill label={disabled ? 'Not yet recorded' : `${count} decision${count === 1 ? '' : 's'}`} tone="neutral" />
          {!disabled ? (
            <Text variant="h2" tone="terracotta">
              →
            </Text>
          ) : null}
        </View>
      </Pressable>
    </Animated.View>
  );
}

function CategoryCard({ category, counts, index, onOpen }: {
  category: Category;
  counts: Record<string, number>;
  index: number;
  onOpen: (moduleSource: TransparencyDecisionType) => void;
}) {
  const { colors } = useAppTheme();
  return (
    <Reveal index={index}>
      <Card padded={false}>
        <View style={styles.categoryHeader}>
          <IconChip name={category.icon} tone={category.tone} size={32} />
          <Text variant="h2" style={styles.categoryTitle}>
            {category.title}
          </Text>
          <InfoTooltip title={category.about.title} description={category.about.description} />
        </View>
        {category.types.map((t, i) => (
          <View key={t}>
            <AuditRow moduleSource={t} count={counts[t] ?? 0} onPress={() => onOpen(t)} />
            {i < category.types.length - 1 ? <View style={[styles.divider, { backgroundColor: colors.border }]} /> : null}
          </View>
        ))}
      </Card>
    </Reveal>
  );
}

export function TransparencyScreen() {
  const navigation = useNavigation<Nav>();
  const { colors } = useAppTheme();
  const { data, isPending, error, refetch } = useTransparencyIndex();

  const openTrace = (moduleSource: TransparencyDecisionType) => navigation.navigate('TransparencyDetail', { moduleSource });

  const totalDecisions = data
    ? TRANSPARENCY_DECISION_TYPES.reduce((sum, t) => sum + (data.counts_by_module_source[t] ?? 0), 0)
    : 0;

  return (
    <ScreenContainer>
      <View>
        <Text variant="display" style={styles.title}>Transparency</Text>
      </View>

      {isPending ? (
        <>
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : (
        // ScreenContainer only puts its own gap between ITS direct children
        // -- this whole block is one of those (a bare fragment before), so
        // without an explicit gap here every card below rendered flush
        // against the next (same bug already fixed on the Leaks, Risk
        // Profile and Personalization screens).
        <View style={styles.resultsGroup}>
          <Reveal index={0}>
            <LinearGradient
              colors={[colors.petrolSoft, colors.paperRaised]}
              start={{ x: 0, y: 0 }}
              end={{ x: 0.7, y: 1 }}
              style={[styles.heroCard, { borderColor: colors.borderStrong }]}
            >
              <View style={styles.heroTopRow}>
                <Text variant="label" tone="muted">
                  DECISION AUDIT TRAIL
                </Text>
                <View style={styles.liveBadge}>
                  <LiveDot />
                  <Text variant="caption" tone="positive" style={styles.liveLabel}>
                    LIVE
                  </Text>
                </View>
              </View>
              <AnimatedFigure
                target={totalDecisions}
                formatter={(n) => `${Math.round(n)}`}
                variant="figureLarge"
              />
              <Text variant="caption" tone="faint" style={styles.heroHelper}>
                Total decisions verified across every module
              </Text>
              <Text variant="caption" tone="muted" style={styles.heroSubtitle}>
                Every decision the app makes about you is recorded when it’s made, and shown back to you
                exactly as recorded — never recomputed after the fact.
              </Text>
            </LinearGradient>
          </Reveal>

          {CATEGORIES.map((category, i) => (
            <CategoryCard
              key={category.key}
              category={category}
              counts={data!.counts_by_module_source}
              index={i + 1}
              onOpen={openTrace}
            />
          ))}
        </View>
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  title: { marginTop: SPACE.xs },
  resultsGroup: { gap: SPACE.lg },
  heroCard: {
    gap: SPACE.xs,
    borderRadius: RADIUS.lg,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    padding: SPACE.lg,
  },
  heroTopRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  heroHelper: { marginTop: 2 },
  heroSubtitle: { marginTop: SPACE.sm },
  liveBadge: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  liveLabel: { letterSpacing: 0.6 },
  liveDotWrap: { width: 8, height: 8, alignItems: 'center', justifyContent: 'center' },
  liveDotRing: { position: 'absolute', width: 8, height: 8, borderRadius: 4 },
  liveDotCore: { width: 8, height: 8, borderRadius: 4 },
  categoryHeader: { flexDirection: 'row', alignItems: 'center', gap: SPACE.md, padding: SPACE.lg, paddingBottom: SPACE.sm },
  categoryTitle: { flex: 1 },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: SPACE.lg, gap: SPACE.md },
  rowText: { flex: 1, gap: SPACE.xs },
  rowTrailing: { alignItems: 'flex-end', gap: SPACE.xs },
  divider: { height: StyleSheet.hairlineWidth, marginHorizontal: SPACE.lg },
  pill: { alignSelf: 'flex-start', paddingHorizontal: SPACE.sm, paddingVertical: 2, borderRadius: RADIUS.pill },
});
