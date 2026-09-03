import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { TRANSPARENCY_DECISION_TYPES } from '../../api/transparency';
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

export function TransparencyScreen() {
  const navigation = useNavigation<Nav>();
  const { data, isPending, error, refetch } = useTransparencyIndex();

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Insights
        </Text>
        <Text variant="display">Transparency</Text>
        <Text variant="body" tone="muted" style={styles.subtitle}>
          Every figure below is a rule-table lookup or a weighted sum — never a model call. This shows exactly
          which one produced each decision.
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
        <MenuList
          items={TRANSPARENCY_DECISION_TYPES.map((moduleSource) => {
            const count = data?.counts_by_module_source[moduleSource] ?? 0;
            return {
              key: moduleSource,
              title: TRANSPARENCY_DISPLAY_NAME[moduleSource],
              subtitle: count === 0 ? 'No decisions recorded yet' : `${count} recorded decision${count === 1 ? '' : 's'}`,
              disabled: count === 0,
              onPress: () => navigation.navigate('TransparencyDetail', { moduleSource }),
            };
          })}
        />
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  subtitle: { marginTop: SPACE.xs },
});
