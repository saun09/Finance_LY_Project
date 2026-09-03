import React from 'react';
import { StyleSheet, View } from 'react-native';
import { SPACE } from '../theme/tokens';
import { Text } from './Text';
import { Button } from './Button';

interface Props {
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}

/** For every "nothing here yet" screen (Section 18). Deliberately never
 * uses error-red or a warning icon -- an empty state is a normal,
 * expected part of a new user's journey, not a problem. */
export function EmptyState({ title, message, actionLabel, onAction }: Props) {
  return (
    <View style={styles.container}>
      <Text variant="h2" style={styles.center}>
        {title}
      </Text>
      <Text variant="body" tone="muted" style={styles.center}>
        {message}
      </Text>
      {actionLabel && onAction ? <Button label={actionLabel} onPress={onAction} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: 'center', gap: SPACE.md, paddingVertical: SPACE.xxl, paddingHorizontal: SPACE.lg },
  center: { textAlign: 'center' },
});
