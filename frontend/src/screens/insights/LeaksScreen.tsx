import { Ionicons } from '@expo/vector-icons';
import type { CompositeNavigationProp } from '@react-navigation/native';
import { useNavigation } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { LinearGradient } from 'expo-linear-gradient';
import React, { useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { BackHeader } from '../../components/BackHeader';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { IconChip } from '../../components/IconChip';
import { InfoTooltip } from '../../components/InfoTooltip';
import { ProgressBar } from '../../components/ProgressBar';
import { Reveal } from '../../components/Reveal';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useAppTheme } from '../../theme/ThemeContext';
import { useChevronRotation } from '../../hooks/useChevronRotation';
import { useDebtLeak } from '../../hooks/useDebtLeak';
import type { InsightsStackParamList, MainTabParamList } from '../../navigation/types';
import { RADIUS, SPACE } from '../../theme/tokens';
import { formatPaise } from '../../utils/currency';
import { groupByLabel, type GroupedInsight } from '../../utils/recoverableInsights';

type Nav = CompositeNavigationProp<
  NativeStackNavigationProp<InsightsStackParamList, 'Leaks'>,
  BottomTabNavigationProp<MainTabParamList>
>;

/** One category, collapsed to a header by default: icon, title, an entry-
 * count badge, the total, and a proportion bar showing its share of the
 * annual total. Expanding reveals a clean row per underlying record --
 * its own exact amount, a "possible duplicate" badge when that's actually
 * what's being flagged, and its own "Review" link -- instead of each
 * row repeating the same backend reasoning sentence (that pattern is now
 * stated once, in the banner above the list) or funnelling every record
 * into one shared button at the bottom. */
function LeakCategoryCard({
  item,
  index,
  totalAnnualPaise,
  isOpen,
  onToggle,
  onReviewEntry,
}: {
  item: GroupedInsight;
  index: number;
  totalAnnualPaise: number;
  isOpen: boolean;
  onToggle: () => void;
  onReviewEntry: () => void;
}) {
  const { colors } = useAppTheme();
  const chevronRotation = useChevronRotation(isOpen);
  const fraction = totalAnnualPaise > 0 ? item.amountPaise / totalAnnualPaise : 0;
  // Every record this card collapses shares the same concrete_action
  // template (see leak_engine.py) -- shown once here, not once per row.
  const concreteAction = item.items[0]?.concrete_action;
  const flagsDuplicates = item.kind === 'recurring' && item.count > 1;

  return (
    <Reveal index={index}>
      <Card raised>
        <Pressable
          onPress={onToggle}
          style={styles.cardHeader}
          accessibilityRole="button"
          accessibilityState={{ expanded: isOpen }}
          accessibilityLabel={`${item.title}, ${formatPaise(item.amountPaise)} per year`}
        >
          <IconChip name={item.icon} tone={item.tone} size={36} />
          <View style={styles.cardHeaderCopy}>
            <View style={styles.titleRow}>
              <Text variant="h2" style={styles.titleText} numberOfLines={1}>
                {item.title}
              </Text>
              <View style={[styles.countBadge, { backgroundColor: colors.paperSunken }]}>
                <Text variant="caption" tone="muted">
                  {item.count} {item.count === 1 ? 'entry' : 'entries'}
                </Text>
              </View>
            </View>
            <Text variant="figure" tone="terracotta">
              {formatPaise(item.amountPaise)}/yr
            </Text>
            <View style={styles.proportionRow}>
              <View style={styles.proportionBar}>
                <ProgressBar fraction={fraction} tone={item.tone} height={4} duration={700} />
              </View>
              <Text variant="caption" tone="faint">
                {Math.round(fraction * 100)}% of total
              </Text>
            </View>
          </View>
          <Animated.View style={{ transform: [{ rotate: chevronRotation }] }}>
            <Ionicons name="chevron-down" size={22} color={colors.inkFaint} />
          </Animated.View>
        </Pressable>
        {isOpen ? (
          <Reveal>
            <View style={styles.expandedBody}>
              {concreteAction ? (
                <Text variant="caption" tone="muted">
                  {concreteAction}
                </Text>
              ) : null}
              {item.items.map((c, idx) => (
                <View key={c.component_id} style={[styles.subItemRow, { borderTopColor: colors.border }]}>
                  <View style={styles.subItemLeft}>
                    <Text variant="bodyMedium">Entry {idx + 1}</Text>
                    {flagsDuplicates ? (
                      <View style={[styles.duplicateBadge, { backgroundColor: colors.warningSoft }]}>
                        <Text variant="caption" tone="warning">
                          Possible duplicate
                        </Text>
                      </View>
                    ) : null}
                  </View>
                  <View style={styles.subItemRight}>
                    <Text variant="bodyMedium">{formatPaise(c.annual_amount_paise)}/yr</Text>
                    <Pressable
                      onPress={onReviewEntry}
                      style={styles.reviewLink}
                      accessibilityRole="button"
                      accessibilityLabel={`Review entry ${idx + 1}`}
                    >
                      <Text variant="caption" tone="terracotta">
                        Review
                      </Text>
                      <Ionicons name="chevron-forward" size={14} color={colors.terracotta} />
                    </Pressable>
                  </View>
                </View>
              ))}
            </View>
          </Reveal>
        ) : null}
      </Card>
    </Reveal>
  );
}

export function LeaksScreen() {
  const navigation = useNavigation<Nav>();
  const { colors } = useAppTheme();
  const { data, isPending, error, refetch } = useDebtLeak();
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  // Grouped by category (same shared logic Home's preview uses, so the
  // two never disagree on how many unique things are flagged) -- the
  // total above is still the exact sum of every individual stored
  // record, not recomputed from the grouped view.
  const grouped = data ? groupByLabel(data.components) : [];
  const hasRepeatedEntries = grouped.some((g) => g.count > 1);

  const goToExpenses = () => navigation.navigate('ProfileTab', { screen: 'ExpensesManage' });

  return (
    <ScreenContainer>
      <View>
        <BackHeader label="Insights" />
        <Text variant="display" style={styles.title}>
          Spending to review
        </Text>
      </View>

      {isPending ? (
        <>
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : grouped.length === 0 ? (
        <Card>
          <EmptyState
            title="Nothing flagged right now"
            message="Based on what you've entered, there's no idle cash or recurring-spending pattern worth a second look."
          />
        </Card>
      ) : (
        // ScreenContainer only puts its own gap between ITS direct
        // children -- this whole block is one of those (previously a bare
        // fragment), so without an explicit gap here every card inside it
        // rendered flush against the next with nothing but two stacked
        // hairline borders between them.
        <View style={styles.resultsGroup}>
          <LinearGradient
            colors={[colors.terracottaSoft, colors.paperRaised]}
            start={{ x: 0, y: 0 }}
            end={{ x: 0.6, y: 1 }}
            style={[styles.heroCard, { borderColor: colors.borderStrong }]}
          >
            <Text variant="caption" tone="muted">
              ANNUAL SPENDING IN THESE CATEGORIES
            </Text>
            <Text variant="figureLarge">{formatPaise(data!.total_recoverable_annual_paise)}/year</Text>
            <Text variant="caption" tone="faint" style={styles.totalNote}>
              Sum of every entry below — {data!.components.length} total, {grouped.length} unique categor
              {grouped.length === 1 ? 'y' : 'ies'}.
            </Text>
          </LinearGradient>

          {hasRepeatedEntries ? (
            <View style={[styles.banner, { backgroundColor: colors.warningSoft, borderColor: colors.warning }]}>
              <Ionicons name="warning-outline" size={20} color={colors.warning} />
              <Text variant="caption" tone="warning" style={styles.bannerText}>
                Pattern detected — some categories below have more than one similar entry. That's worth a
                second look, not a confirmed duplicate payment.
              </Text>
            </View>
          ) : null}

          {grouped.map((item, index) => (
            <LeakCategoryCard
              key={item.key}
              item={item}
              index={index}
              totalAnnualPaise={data!.total_recoverable_annual_paise}
              isOpen={expandedKey === item.key}
              onToggle={() => setExpandedKey(expandedKey === item.key ? null : item.key)}
              onReviewEntry={goToExpenses}
            />
          ))}
        </View>
      )}

      <View style={styles.footerInfo}>
        <InfoTooltip
          label="How recurring charges are detected"
          title="How recurring charges are detected"
          description={
            data?.data_source_note ??
            'Based only on manually entered recurring expenses — this app has no bank or card statement parser.'
          }
        />
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  title: { marginTop: SPACE.xs },
  totalNote: { marginTop: SPACE.xs },

  resultsGroup: { gap: SPACE.lg },
  heroCard: { borderRadius: RADIUS.lg, borderWidth: StyleSheet.hairlineWidth * 1.5, padding: SPACE.lg, gap: 2 },

  banner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: SPACE.sm,
    padding: SPACE.md,
    borderRadius: RADIUS.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
  },
  bannerText: { flex: 1 },

  cardHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: SPACE.sm },
  cardHeaderCopy: { flex: 1, gap: SPACE.xs },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  titleText: { flex: 1 },
  countBadge: { paddingHorizontal: SPACE.sm, paddingVertical: 2, borderRadius: RADIUS.pill },
  proportionRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm, marginTop: 2 },
  proportionBar: { flex: 1 },

  expandedBody: { marginTop: SPACE.md, gap: SPACE.xs },
  subItemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: SPACE.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingVertical: SPACE.sm,
  },
  subItemLeft: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm, flexShrink: 1 },
  duplicateBadge: { paddingHorizontal: SPACE.sm, paddingVertical: 2, borderRadius: RADIUS.pill },
  subItemRight: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  reviewLink: { flexDirection: 'row', alignItems: 'center', gap: 2 },

  footerInfo: { flexDirection: 'row', justifyContent: 'center', marginTop: SPACE.lg },
});
