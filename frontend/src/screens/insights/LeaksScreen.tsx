import { Ionicons } from '@expo/vector-icons';
import type { CompositeNavigationProp } from '@react-navigation/native';
import { useNavigation } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React, { useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
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
 * annual total. Expanding reveals each underlying record's own amount and
 * backend-written explanation -- real per-record detail, not a single
 * generic sentence repeated once per category (that sentence now lives
 * once, in the banner above the list). */
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
  // template (see leak_engine.py) -- shown once here, not once per
  // sub-item, for the same reason the category-level explanation moved
  // to a single banner instead of repeating per card.
  const concreteAction = item.items[0]?.concrete_action;

  return (
    <Reveal index={index}>
      <Card>
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
              {item.items.map((c) => (
                <View key={c.component_id} style={[styles.subItemRow, { borderTopColor: colors.border }]}>
                  <Text variant="bodyMedium">{formatPaise(c.annual_amount_paise)}/yr</Text>
                  <Text variant="caption" tone="faint" style={styles.subItemExplanation}>
                    {c.explanation}
                  </Text>
                </View>
              ))}
              <Button label="Review entry" variant="ghost" fullWidth onPress={onReviewEntry} />
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
        <>
          <Card style={{ backgroundColor: colors.terracottaSoft, borderColor: colors.terracottaSoft }}>
            <Text variant="caption" tone="muted">
              ANNUAL SPENDING IN THESE CATEGORIES
            </Text>
            <Text variant="figureLarge">{formatPaise(data!.total_recoverable_annual_paise)}/year</Text>
            <Text variant="caption" tone="faint" style={styles.totalNote}>
              Sum of every entry below — {data!.components.length} total, {grouped.length} unique categor
              {grouped.length === 1 ? 'y' : 'ies'}.
            </Text>
          </Card>

          {hasRepeatedEntries ? (
            <View style={[styles.banner, { backgroundColor: colors.petrolSoft }]}>
              <Ionicons name="bulb-outline" size={20} color={colors.petrol} />
              <Text variant="caption" tone="petrol" style={styles.bannerText}>
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
        </>
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

  banner: { flexDirection: 'row', alignItems: 'flex-start', gap: SPACE.sm, padding: SPACE.md, borderRadius: RADIUS.md },
  bannerText: { flex: 1 },

  cardHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: SPACE.sm },
  cardHeaderCopy: { flex: 1, gap: SPACE.xs },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm },
  titleText: { flex: 1 },
  countBadge: { paddingHorizontal: SPACE.sm, paddingVertical: 2, borderRadius: RADIUS.pill },
  proportionRow: { flexDirection: 'row', alignItems: 'center', gap: SPACE.sm, marginTop: 2 },
  proportionBar: { flex: 1 },

  expandedBody: { marginTop: SPACE.md, gap: SPACE.sm },
  subItemRow: { borderTopWidth: StyleSheet.hairlineWidth, paddingTop: SPACE.sm, gap: 2 },
  subItemExplanation: {},

  footerInfo: { flexDirection: 'row', justifyContent: 'center', marginTop: SPACE.lg },
});
