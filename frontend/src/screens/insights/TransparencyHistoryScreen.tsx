import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp, NativeStackScreenProps } from '@react-navigation/native-stack';
import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useAppTheme } from '../../theme/ThemeContext';
import { useTransparencyHistory } from '../../hooks/useTransparency';
import { SPACE } from '../../theme/tokens';
import { TRANSPARENCY_DISPLAY_NAME } from '../../utils/labels';
import type { InsightsStackParamList } from '../../navigation/types';

type Props = NativeStackScreenProps<InsightsStackParamList, 'TransparencyHistory'>;
type Nav = NativeStackNavigationProp<InsightsStackParamList, 'TransparencyHistory'>;

/**
 * Every version of one decision, newest first.
 *
 * Module 1 has always stored every decision; until this screen existed the
 * app could only ever show the latest one, so "my risk tier changed last
 * month -- what moved?" was unanswerable despite the answer sitting in the
 * database. Each row opens that specific decision's trace, and any row with
 * an older neighbour can be diffed against it.
 */
export function TransparencyHistoryScreen() {
  const { colors } = useAppTheme();
  const navigation = useNavigation<Nav>();
  const { params } = useRoute<Props['route']>();
  const { data, isPending, error, refetch } = useTransparencyHistory(params.moduleSource);

  return (
    <ScreenContainer>
      <View>
        <Text variant="caption" tone="muted">
          Transparency
        </Text>
        <Text variant="display">{TRANSPARENCY_DISPLAY_NAME[params.moduleSource]}</Text>
        <Text variant="body" tone="muted" style={styles.subtitle}>
          Every time this was decided. Nothing here is recomputed — each entry is the record written
          at the moment that decision was made.
        </Text>
      </View>

      {isPending ? (
        <>
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          title="No decisions recorded yet"
          message="Once this is computed for you, every version of it will be listed here."
        />
      ) : (
        data.map((row, i) => {
          const older = data[i + 1];
          return (
            <Card key={row.event_id}>
              <Pressable
                onPress={() =>
                  navigation.navigate('TransparencyDetail', {
                    moduleSource: params.moduleSource,
                    eventId: row.event_id,
                  })
                }
                style={({ pressed }) => [{ opacity: pressed ? 0.7 : 1 }]}
              >
                <View style={styles.rowHead}>
                  <Text variant="caption" tone="faint">
                    {new Date(row.timestamp).toLocaleString('en-IN')}
                  </Text>
                  {i === 0 ? (
                    <View style={[styles.pill, { backgroundColor: colors.petrolSoft }]}>
                      <Text variant="label" tone="petrol">
                        CURRENT
                      </Text>
                    </View>
                  ) : null}
                </View>
                <Text variant="bodyMedium">{row.headline}</Text>
                {row.gap_detected ? (
                  <Text variant="caption" tone="warning">
                    Partially recorded — some of this decision can’t be reconstructed
                  </Text>
                ) : null}
                {row.contested ? (
                  <Text variant="caption" tone="warning">
                    You flagged this one
                  </Text>
                ) : null}
              </Pressable>

              {older ? (
                <View style={styles.actions}>
                  <Button
                    label="What changed since the previous one"
                    variant="ghost"
                    onPress={() =>
                      navigation.navigate('TransparencyCompare', {
                        moduleSource: params.moduleSource,
                        beforeEventId: older.event_id,
                        afterEventId: row.event_id,
                      })
                    }
                  />
                </View>
              ) : null}
            </Card>
          );
        })
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  subtitle: { marginTop: SPACE.xs },
  rowHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  pill: { paddingHorizontal: SPACE.sm, paddingVertical: 2, borderRadius: 6 },
  actions: { marginTop: SPACE.sm },
});
