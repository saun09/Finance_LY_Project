import { useRoute } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Card } from '../../components/Card';
import { ErrorState } from '../../components/ErrorState';
import { ReasoningTree } from '../../components/ReasoningTree';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SectionHeader } from '../../components/SectionHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useAppTheme } from '../../theme/ThemeContext';
import { useTransparencyTrace } from '../../hooks/useTransparency';
import { SPACE } from '../../theme/tokens';
import type { InsightsStackParamList } from '../../navigation/types';

type Props = NativeStackScreenProps<InsightsStackParamList, 'TransparencyDetail'>;

export function TransparencyDetailScreen() {
  const { colors } = useAppTheme();
  const { params } = useRoute<Props['route']>();
  const { data, isPending, error, refetch } = useTransparencyTrace(params.moduleSource);

  return (
    <ScreenContainer>
      {isPending ? (
        <>
          <Text variant="display">Transparency</Text>
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : error ? (
        <>
          <Text variant="display">Transparency</Text>
          <ErrorState message={error.message} onRetry={() => refetch()} />
        </>
      ) : (
        <>
          <View>
            <View style={[styles.badge, { backgroundColor: colors.petrolSoft }]}>
              <Text variant="label" tone="petrol">
                {data!.framing_label.toUpperCase()}
              </Text>
            </View>
            <Text variant="display" style={styles.title}>
              {data!.display_name}
            </Text>
            <Text variant="caption" tone="faint">
              {new Date(data!.timestamp).toLocaleString('en-IN')}
            </Text>
          </View>

          <Card>
            <Text variant="bodyMedium">{data!.headline}</Text>
          </Card>

          {data!.gap_detected ? (
            <Card style={{ backgroundColor: colors.warningSoft, borderColor: colors.warningSoft }}>
              <Text variant="bodyMedium" tone="warning">
                This trace is incomplete — the stored decision is missing:{' '}
                {data!.missing_fields.join(', ')}. Showing what was actually recorded rather than filling the
                gap with a freshly computed value.
              </Text>
            </Card>
          ) : null}

          <Card>
            <SectionHeader title="Reasoning" subtitle="Exactly what was stored when this decision was made" />
            <View style={styles.treeWrap}>
              <ReasoningTree data={data!.reasoning} />
            </View>
          </Card>
        </>
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  badge: { alignSelf: 'flex-start', paddingHorizontal: SPACE.sm, paddingVertical: 4, borderRadius: 6, marginBottom: SPACE.sm },
  title: { marginTop: 2 },
  treeWrap: { marginTop: SPACE.sm },
});
