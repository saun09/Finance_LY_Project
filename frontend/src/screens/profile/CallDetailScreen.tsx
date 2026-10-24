import type { RouteProp } from '@react-navigation/native';
import { useRoute } from '@react-navigation/native';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { BackHeader } from '../../components/BackHeader';
import { CallTranscript } from '../../components/CallTranscript';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { ScreenContainer } from '../../components/ScreenContainer';
import { SkeletonCard } from '../../components/Skeleton';
import { Text } from '../../components/Text';
import { useNudgeCall } from '../../hooks/useNudgeCalls';
import type { ProfileStackParamList } from '../../navigation/types';
import { formatCallDuration, formatCallTime, surfaceLabel } from '../../utils/callFormat';

/** One saved Nudge call's full transcript, in the same bubbles the live
 * call sheet shows. */
export function CallDetailScreen() {
  const { conversationId } = useRoute<RouteProp<ProfileStackParamList, 'CallDetail'>>().params;
  const { data, isPending, error, refetch } = useNudgeCall(conversationId);
  const duration = data ? formatCallDuration(data.started_at, data.ended_at) : null;

  return (
    <ScreenContainer>
      <View>
        <BackHeader label="Your calls" />
        <Text variant="display" style={styles.title}>Call transcript</Text>
        {data ? (
          <Text variant="caption" tone="muted">
            {[formatCallTime(data.started_at), duration, `from ${surfaceLabel(data.surface)}`].filter(Boolean).join(' · ')}
          </Text>
        ) : null}
      </View>

      {isPending ? (
        <SkeletonCard />
      ) : error ? (
        <ErrorState message={error.message} onRetry={() => refetch()} />
      ) : data.messages.length === 0 ? (
        <Card>
          <EmptyState title="Nothing was said" message="This call ended before anything was transcribed." />
        </Card>
      ) : (
        <Card>
          <CallTranscript lines={data.messages} />
        </Card>
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  title: { marginTop: 4 },
});
