import React from 'react';
import { StyleSheet, View } from 'react-native';
import { SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';
import { Button } from './Button';
import { Text } from './Text';

interface Props {
  message: string;
  onRetry?: () => void;
}

/** A single, consistent shape for every API failure (Section 20) --
 * human-readable message (already normalized by toApiError in
 * api/client.ts, so this never sees a raw stack trace), with a retry
 * action when one is available. */
export function ErrorState({ message, onRetry }: Props) {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.container, { borderColor: colors.dangerSoft, backgroundColor: colors.dangerSoft }]}>
      <Text variant="bodyMedium" tone="danger" style={styles.center}>
        {message}
      </Text>
      {onRetry ? <Button label="Try again" variant="secondary" onPress={onRetry} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: 'center', gap: SPACE.md, padding: SPACE.lg, borderRadius: 14, borderWidth: 1 },
  center: { textAlign: 'center' },
});
