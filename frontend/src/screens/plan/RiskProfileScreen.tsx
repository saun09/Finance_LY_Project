import { Ionicons } from '@expo/vector-icons';
import type { CompositeNavigationProp } from '@react-navigation/native';
import { useNavigation } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React, { useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { AnimatedFigure } from '../../components/AnimatedFigure';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { ProgressBar } from '../../components/ProgressBar';
import { Reveal } from '../../components/Reveal';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useReducedMotion } from '../../hooks/useReducedMotion';
import { useAppTheme } from '../../theme/ThemeContext';
import { useRiskProfileLatest } from '../../hooks/useRiskProfile';
import { RADIUS, SPACE } from '../../theme/tokens';
import type { MainTabParamList, PlanStackParamList } from '../../navigation/types';

type Nav = CompositeNavigationProp<
  NativeStackNavigationProp<PlanStackParamList, 'RiskProfile'>,
  BottomTabNavigationProp<MainTabParamList>
>;

function tierLabel(tier: number) {
  return `Tier ${tier} of 5`;
}

const TIER_LEGEND: { tier: number; name: string; description: string }[] = [
  { tier: 1, name: 'Capital preservation', description: 'Mostly cash & debt. Minimal equity exposure.' },
  { tier: 2, name: 'Cautious', description: 'Still cash/debt-heavy, with a small equity slice.' },
  { tier: 3, name: 'Balanced', description: 'A moderate mix across cash, debt, and equity.' },
  { tier: 4, name: 'Growth-oriented', description: 'Equity-tilted, with some real assets and alternatives.' },
  { tier: 5, name: 'Aggressive', description: 'Highest equity exposure, minimal cash held back.' },
];

/** Collapsed by default -- same disclosure pattern as Progress's roadmap
 * levels (Pressable header + chevron + accessibilityState), reused here
 * rather than invented fresh. Tiers are a *spectrum* of risk/return
 * trade-offs, not a ladder where higher is "better" -- the copy avoids
 * any "unlock more" framing. */
function TierLegendDisclosure() {
  const { colors } = useAppTheme();
  const [open, setOpen] = useState(false);
  const reducedMotion = useReducedMotion();
  const rotation = useRef(new Animated.Value(0)).current;

  const toggle = () => {
    const next = !open;
    setOpen(next);
    Animated.timing(rotation, {
      toValue: next ? 1 : 0,
      duration: reducedMotion ? 0 : 200,
      useNativeDriver: true,
    }).start();
  };

  const chevronRotation = rotation.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '180deg'] });

  return (
    <Card>
      <Pressable
        onPress={toggle}
        style={styles.legendHeader}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel="How risk tiers work"
      >
        <Text variant="bodyMedium">How risk tiers work</Text>
        <Animated.View style={{ transform: [{ rotate: chevronRotation }] }}>
          <Ionicons name="chevron-down" size={20} color={colors.inkFaint} />
        </Animated.View>
      </Pressable>
      {open ? (
        <Reveal>
          <View style={styles.legendList}>
            {TIER_LEGEND.map((t) => (
              <View key={t.tier} style={styles.legendRow}>
                <View style={[styles.legendBadge, { backgroundColor: colors.petrolSoft }]}>
                  <Text variant="bodyMedium" tone="petrol">
                    {t.tier}
                  </Text>
                </View>
                <View style={styles.legendCopy}>
                  <Text variant="bodyMedium">{t.name}</Text>
                  <Text variant="caption" tone="muted">
                    {t.description}
                  </Text>
                </View>
              </View>
            ))}
          </View>
        </Reveal>
      ) : null}
    </Card>
  );
}

export function RiskProfileScreen() {
  const navigation = useNavigation<Nav>();
  const { colors } = useAppTheme();
  const { data, isPending, error, refetch } = useRiskProfileLatest();

  return (
    <ScreenContainer>
      <View style={styles.header}>
        <Text variant="caption" tone="muted">
          Risk profile
        </Text>
        <Text variant="display">Your risk profile</Text>
        <Text variant="caption" tone="muted" style={styles.headerSubtitle}>
          What you're comfortable with, checked against what your finances currently support.
        </Text>
      </View>

      {isPending ? (
        <>
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : error && error.status !== 404 ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : !data ? (
        <Card>
          <EmptyState
            title="You haven't taken the risk questionnaire yet"
            message="A few short questions determine your stated risk preference, which is then checked against your financial capacity."
            actionLabel="Take the questionnaire"
            onAction={() => navigation.navigate('RiskQuestionnaire')}
          />
        </Card>
      ) : (
        <>
          <Reveal index={0}>
            <Card raised style={styles.resultCard}>
              <Text variant="label" tone="muted">
                YOUR RECOMMENDED STARTING TIER
              </Text>
              <AnimatedFigure
                target={data.final_tier}
                formatter={(n) => tierLabel(Math.round(n))}
                variant="hero"
                style={styles.resultFigure}
              />
              <View style={styles.tierBarWrap}>
                <ProgressBar fraction={data.final_tier / 5} tone="petrol" duration={700} />
              </View>

              {data.estimation_method !== 'deterministic' ? (
                <View style={[styles.estimatedBanner, { backgroundColor: colors.warningSoft, borderColor: colors.warning }]}>
                  <Ionicons name="flash-outline" size={16} color={colors.warning} />
                  <Text variant="caption" tone="warning" style={styles.estimatedBannerText}>
                    Estimated from your 4 main answers using a trained model — retake the questionnaire and answer
                    all 7 for a precise, formula-based tier.
                  </Text>
                </View>
              ) : null}

              <Text variant="caption" tone="muted" style={styles.resultNote}>
                {data.capped
                  ? 'This considers both your stated risk preference and your current financial capacity — right now, your financial capacity is the limiting factor, not your risk preference.'
                  : 'This considers both your stated risk preference and your current financial capacity — both currently point to the same tier.'}
              </Text>

              <View style={[styles.supportingRow, { borderTopColor: colors.border }]}>
                <View style={styles.supportingItem}>
                  <Text variant="caption" tone="faint">
                    Your stated risk preference
                  </Text>
                  <Text variant="bodyMedium">{tierLabel(data.stated_tier)}</Text>
                </View>
                <View style={[styles.supportingDivider, { backgroundColor: colors.border }]} />
                <View style={styles.supportingItem}>
                  <Text variant="caption" tone="faint">
                    Your current capacity limit
                  </Text>
                  <Text variant="bodyMedium">{tierLabel(data.capacity_ceiling)}</Text>
                </View>
              </View>
            </Card>
          </Reveal>

          <Reveal index={1}>
            <TierLegendDisclosure />
          </Reveal>

          {data.unlock_conditions.length > 0 ? (
            <Reveal index={2}>
              <View style={styles.unlockSection}>
                <Text variant="h2">Steps to strengthen your financial position</Text>
                <Card style={[styles.nextStepCard, { borderColor: colors.borderStrong }]}>
                  <Text variant="label" tone="petrol">
                    YOUR NEXT STEP
                  </Text>
                  <Text variant="bodyMedium" style={styles.nextStepMessage}>
                    {data.unlock_conditions[0].message}
                  </Text>
                  <View style={styles.unlockValues}>
                    <Text variant="caption" tone="muted">
                      Current: {data.unlock_conditions[0].current_value}
                    </Text>
                    <Text variant="caption" tone="terracotta">
                      Target: {data.unlock_conditions[0].target_value}
                    </Text>
                  </View>
                </Card>
                {data.unlock_conditions.slice(1).map((u) => (
                  <Card key={u.constraint}>
                    <Text variant="bodyMedium">{u.message}</Text>
                    <View style={styles.unlockValues}>
                      <Text variant="caption" tone="muted">
                        Current: {u.current_value}
                      </Text>
                      <Text variant="caption" tone="terracotta">
                        Target: {u.target_value}
                      </Text>
                    </View>
                  </Card>
                ))}
              </View>
            </Reveal>
          ) : null}

          <Pressable
            style={styles.mlLink}
            accessibilityRole="button"
            accessibilityLabel="How your risk profile is assessed"
            onPress={() =>
              navigation.navigate('InsightsTab', {
                screen: 'TransparencyDetail',
                params: { moduleSource: 'risk_profile_ml' },
              })
            }
          >
            <Ionicons name="information-circle-outline" size={18} color={colors.inkFaint} />
            <Text variant="caption" tone="muted">
              How your risk profile is assessed
            </Text>
          </Pressable>

          <View style={styles.footer}>
            <Button label="Explore your target allocation" fullWidth onPress={() => navigation.navigate('Allocation')} />
            <Button label="Retake questionnaire" variant="ghost" fullWidth onPress={() => navigation.navigate('RiskQuestionnaire')} />
          </View>
        </>
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  header: { gap: 2 },
  headerSubtitle: { marginTop: SPACE.xs },
  resultCard: { gap: SPACE.xs, alignItems: 'center' },
  resultFigure: { marginTop: SPACE.xs },
  tierBarWrap: { alignSelf: 'stretch', marginTop: SPACE.sm, paddingHorizontal: SPACE.lg },
  estimatedBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: SPACE.xs,
    alignSelf: 'stretch',
    marginTop: SPACE.md,
    padding: SPACE.sm,
    borderRadius: RADIUS.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
  },
  estimatedBannerText: { flex: 1 },
  resultNote: { textAlign: 'center', marginTop: SPACE.xs },
  supportingRow: {
    flexDirection: 'row',
    alignSelf: 'stretch',
    marginTop: SPACE.md,
    paddingTop: SPACE.md,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  supportingItem: { flex: 1, alignItems: 'center', gap: 2 },
  supportingDivider: { width: StyleSheet.hairlineWidth, marginHorizontal: SPACE.md },
  legendHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  legendList: { gap: SPACE.sm, marginTop: SPACE.md },
  legendRow: { flexDirection: 'row', gap: SPACE.sm, alignItems: 'flex-start' },
  legendBadge: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  legendCopy: { flex: 1 },
  mlLink: { flexDirection: 'row', alignItems: 'center', gap: SPACE.xs, alignSelf: 'flex-start' },
  unlockSection: { gap: SPACE.md },
  nextStepCard: { borderWidth: StyleSheet.hairlineWidth * 2 },
  nextStepMessage: { marginTop: SPACE.xs },
  unlockValues: { flexDirection: 'row', justifyContent: 'space-between', marginTop: SPACE.xs },
  footer: { gap: SPACE.sm, marginTop: SPACE.md },
});
