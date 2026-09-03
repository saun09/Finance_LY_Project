import React from 'react';
import { StyleSheet, View } from 'react-native';
import { RADIUS, SPACE } from '../theme/tokens';
import { useAppTheme } from '../theme/ThemeContext';
import { Text } from './Text';

interface Props {
  step: number;
  total: number;
  title: string;
  subtitle?: string;
}

/** A thin segmented progress bar + step title, shared by every onboarding
 * screen so the user always knows how much is left of the ~5 minute flow
 * the Welcome screen promises. */
export function OnboardingProgress({ step, total, title, subtitle }: Props) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.container}>
      <View style={styles.track}>
        {Array.from({ length: total }).map((_, i) => (
          <View
            key={i}
            style={[
              styles.segment,
              { backgroundColor: i < step ? colors.terracotta : colors.border },
            ]}
          />
        ))}
      </View>
      <Text variant="label" tone="terracotta">
        STEP {step} OF {total}
      </Text>
      <Text variant="h1">{title}</Text>
      {subtitle ? (
        <Text variant="body" tone="muted">
          {subtitle}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: SPACE.sm },
  track: { flexDirection: 'row', gap: SPACE.xs },
  segment: { flex: 1, height: 4, borderRadius: RADIUS.pill },
});
