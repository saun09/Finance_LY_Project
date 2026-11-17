import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { BackHeader } from '../../components/BackHeader';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { MenuList } from '../../components/MenuList';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useNudgeCalls } from '../../hooks/useNudgeCalls';
import type { ProfileStackParamList } from '../../navigation/types';
import { formatCallDuration, formatCallTime, surfaceLabel } from '../../utils/callFormat';

type Nav = NativeStackNavigationProp<ProfileStackParamList, 'YourCalls'>;

/** Every voice call with Nudge, most recent first. Calls are saved
 * line by line as they happen (see NudgeAssistantCore), so even a call that
 * dropped mid-way shows up here with what was said. */
export function YourCallsScreen() {
  const navigation = useNavigation<Nav>();
  const { data, isPending, isRefetching, error, refetch } = useNudgeCalls();

  return (
    <ScreenContainer onRefresh={() => refetch()} refreshing={isRefetching}>
      <View>
        <BackHeader label="Profile" />
        <Text variant="display" style={styles.title}>Your calls</Text>
        <Text variant="body" tone="muted">Transcripts of your voice conversations with Nudge.</Text>
      </View>

      {isPending ? (
        <SkeletonCard />
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : !data || data.length === 0 ? (
        <Card>
          <EmptyState
            title="No calls yet"
            message="Tap “Talk to Nudge” on the Home screen to start a voice call. Its transcript will be saved here."
          />
        </Card>
      ) : (
        <MenuList
          items={data.map((call) => {
            const duration = formatCallDuration(call.started_at, call.ended_at);
            return {
              key: call.id,
              title: call.preview ?? `Call from ${surfaceLabel(call.surface)}`,
              subtitle: [
                formatCallTime(call.started_at),
                duration,
                `${call.message_count} line${call.message_count === 1 ? '' : 's'}`,
              ]
                .filter(Boolean)
                .join(' · '),
              onPress: () => navigation.navigate('CallDetail', { conversationId: call.id }),
              icon: 'call-outline' as const,
              iconTone: 'terracotta' as const,
            };
          })}
        />
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  title: { marginTop: 4 },
});
