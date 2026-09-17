import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { TRANSPARENCY_DECISION_TYPES } from '../../api/transparency';
import { Card } from '../../components/Card';
import { ErrorState } from '../../components/ErrorState';
import { MenuList } from '../../components/MenuList';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useTransparencyIndex } from '../../hooks/useTransparency';
import { TRANSPARENCY_DISPLAY_NAME } from '../../utils/labels';
import { SPACE } from '../../theme/tokens';
import type { InsightsStackParamList } from '../../navigation/types';

type Nav = NativeStackNavigationProp<InsightsStackParamList, 'Transparency'>;

/** Decision types whose reasoning is a weighted sum or a rule-table lookup.
 * Printing the weights is the whole feature, and the label says exactly
 * that -- no more. */
const RULE_TABLE_TYPES = [
  'risk_profile',
  'allocation',
  'debt_leak_engine',
  'personalization',
  'gamification',
] as const;

export function TransparencyScreen() {
  const navigation = useNavigation<Nav>();
  const { data, isPending, error, refetch } = useTransparencyIndex();

  const item = (moduleSource: (typeof TRANSPARENCY_DECISION_TYPES)[number]) => {
    const count = data?.counts_by_module_source[moduleSource] ?? 0;
    return {
      key: moduleSource,
      title: TRANSPARENCY_DISPLAY_NAME[moduleSource],
      subtitle:
        count === 0 ? 'No decisions recorded yet' : `${count} recorded decision${count === 1 ? '' : 's'}`,
      disabled: count === 0,
      onPress: () => navigation.navigate('TransparencyDetail', { moduleSource }),
    };
  };

  const retrievalTypes = TRANSPARENCY_DECISION_TYPES.filter(
    (t) => !RULE_TABLE_TYPES.includes(t as (typeof RULE_TABLE_TYPES)[number]),
  );

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Insights
        </Text>
        <Text variant="display">Transparency</Text>
        <Text variant="body" tone="muted" style={styles.subtitle}>
          Every decision the app makes about you is recorded when it’s made, and shown back to you
          exactly as recorded — never recomputed after the fact.
        </Text>
      </View>

      {isPending ? (
        <>
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : (
        <>
          <Card>
            <Text variant="label" tone="petrol">
              TRANSPARENT REASONING
            </Text>
            <Text variant="caption" tone="muted" style={styles.groupNote}>
              These are rule-table lookups and weighted sums — no model is involved. Showing you the
              weights and the table is the whole of it, and we don’t claim more than that.
            </Text>
          </Card>
          <MenuList items={RULE_TABLE_TYPES.map(item)} />

          <Card>
            <Text variant="label" tone="petrol">
              RUMOUR VERIFICATION
            </Text>
            <Text variant="caption" tone="muted" style={styles.groupNote}>
              Two different engines, making two different claims. The explainable one searches a
              fixed corpus of filings and can name the constraint that ruled out every candidate it
              rejected. The other calls an external workflow that returns its own written rationale,
              which we can show you but cannot verify.
            </Text>
          </Card>
          <MenuList items={retrievalTypes.map(item)} />
        </>
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  subtitle: { marginTop: SPACE.xs },
  groupNote: { marginTop: SPACE.xs },
});
